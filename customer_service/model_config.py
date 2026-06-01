"""客服平台模型配置管理器

支持两种模式：
1. BYOK (Bring Your Own Key) - 用户使用自己的 API 密钥
2. Platform LLM - 平台提供大模型服务

用户可在管理后台自由切换。
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ModelProvider(Enum):
    """模型提供商"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    CUSTOM = "custom"  # 用户自定义
    PLATFORM = "platform"  # 平台提供


class ModelSource(Enum):
    """模型来源"""

    USER_PROVIDED = "user_provided"  # 用户自带 API
    PLATFORM_PROVIDED = "platform_provided"  # 平台提供


@dataclass
class ModelConfig:
    """模型配置"""

    source: ModelSource
    provider: ModelProvider
    model_name: str
    api_key: Optional[str] = None  # 用户自带时必填
    base_url: Optional[str] = None  # 自定义 endpoint
    timeout: int = 120
    max_tokens: int = 2048
    temperature: float = 0.7

    def to_llm_config(self) -> Dict[str, Any]:
        """转换为 LLM 客户端配置"""
        config = {
            "provider": self.provider.value,
            "model": self.model_name,
            "timeout": self.timeout,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        if self.source == ModelSource.USER_PROVIDED:
            config["api_key"] = self.api_key
            if self.base_url:
                config["base_url"] = self.base_url
        else:
            # 平台提供，使用平台配置
            config["api_key"] = os.environ.get("PLATFORM_LLM_API_KEY")
            config["base_url"] = os.environ.get("PLATFORM_LLM_BASE_URL")

        return config


@dataclass
class SellerModelSettings:
    """卖家模型设置"""

    seller_id: str
    default_source: ModelSource = ModelSource.USER_PROVIDED
    user_configs: Dict[str, ModelConfig] = field(default_factory=dict)
    platform_quota: int = 1000  # 平台免费额度（消息数/月）
    platform_quota_used: int = 0  # 已使用额度

    def get_default_config(self) -> ModelConfig:
        """获取默认模型配置"""
        if self.default_source == ModelSource.USER_PROVIDED:
            # 返回用户配置的默认模型
            if "default" in self.user_configs:
                return self.user_configs["default"]
            # 回退到平台配置
            return self.get_platform_config()
        else:
            return self.get_platform_config()

    def get_platform_config(self) -> ModelConfig:
        """获取平台提供的模型配置"""
        return ModelConfig(
            source=ModelSource.PLATFORM_PROVIDED,
            provider=ModelProvider.CUSTOM,
            model_name=os.environ.get("PLATFORM_DEFAULT_MODEL", "qwen-plus"),
        )

    def add_user_config(self, name: str, config: ModelConfig):
        """添加用户自定义模型配置"""
        config.source = ModelSource.USER_PROVIDED
        self.user_configs[name] = config

    def switch_source(self, source: ModelSource):
        """切换模型来源"""
        self.default_source = source

    def check_platform_quota(self, messages: int = 1) -> bool:
        """检查平台额度是否足够"""
        return self.platform_quota_used + messages <= self.platform_quota

    def use_platform_quota(self, messages: int = 1):
        """使用平台额度"""
        self.platform_quota_used += messages

    def get_status(self) -> Dict[str, Any]:
        """获取状态信息"""
        return {
            "seller_id": self.seller_id,
            "default_source": self.default_source.value,
            "user_configs_count": len(self.user_configs),
            "platform_quota": {
                "total": self.platform_quota,
                "used": self.platform_quota_used,
                "remaining": self.platform_quota - self.platform_quota_used,
            },
            "available_models": list(self.user_configs.keys()),
        }


class ModelConfigManager:
    """模型配置管理器"""

    def __init__(self, db_path: str = "model_configs.db"):
        self.db_path = db_path
        self._seller_settings: Dict[str, SellerModelSettings] = {}

    def get_seller_settings(self, seller_id: str) -> SellerModelSettings:
        """获取或创建卖家模型设置"""
        if seller_id not in self._seller_settings:
            self._seller_settings[seller_id] = SellerModelSettings(seller_id=seller_id)
        return self._seller_settings[seller_id]

    def update_seller_settings(self, seller_id: str, settings: SellerModelSettings):
        """更新卖家模型设置"""
        self._seller_settings[seller_id] = settings

    def create_llm_client(self, seller_id: str) -> "LLMClient":
        """为卖家创建 LLM 客户端"""
        from myAgent.llm.client import LLMClient

        settings = self.get_seller_settings(seller_id)
        config = settings.get_default_config()
        llm_config = config.to_llm_config()

        return LLMClient(llm_config)

    def get_available_providers(self) -> List[Dict[str, str]]:
        """获取可用的模型提供商列表"""
        return [{"value": p.value, "label": p.name} for p in ModelProvider]

    def get_pricing_info(self) -> Dict[str, Any]:
        """获取定价信息"""
        return {
            "free_tier": {
                "source": "platform",
                "quota": 1000,
                "price": 0,
            },
            "starter": {
                "source": "user_provided",
                "price": 9,
                "features": ["无限消息", "支持所有模型", "优先支持"],
            },
            "pro": {
                "source": "platform",
                "price": 29,
                "quota": 50000,
                "features": ["5 万消息/月", "高级模型", "优先支持"],
            },
        }


# ========== 数据库模型（SQLAlchemy） ==========

"""
from sqlalchemy import Column, String, Integer, Enum, JSON, ForeignKey
from sqlalchemy.orm import relationship

class SellerModelConfig(Base):
    __tablename__ = "seller_model_configs"

    id = Column(Integer, primary_key=True)
    seller_id = Column(String, ForeignKey("sellers.id"), nullable=False)
    config_name = Column(String, nullable=False)
    source = Column(Enum(ModelSource), nullable=False)
    provider = Column(Enum(ModelProvider), nullable=False)
    model_name = Column(String, nullable=False)
    api_key_encrypted = Column(String)  # 加密存储
    base_url = Column(String)
    is_default = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, onupdate=datetime.now)

    seller = relationship("Seller", back_populates="model_configs")


class SellerPlatformQuota(Base):
    __tablename__ = "seller_platform_quota"

    id = Column(Integer, primary_key=True)
    seller_id = Column(String, ForeignKey("sellers.id"), nullable=False, unique=True)
    quota_total = Column(Integer, default=1000)
    quota_used = Column(Integer, default=0)
    reset_date = Column(DateTime)  # 每月重置日期

    seller = relationship("Seller", back_populates="platform_quota")
"""
