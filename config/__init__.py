"""Configuration Manager - 统一配置管理系统

支持从多种来源加载配置：
1. YAML 配置文件
2. 环境变量
3. 命令行参数

配置优先级（从高到低）：
1. 命令行参数
2. 环境变量
3. YAML 配置文件
4. 默认值
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class LLMConfig:
    """LLM 模型配置"""

    provider: str = "openai-compatible"
    base_url: str = "http://localhost:8080/v1"
    api_key: str = ""
    model: str = "Qwen/Qwen3-4B-GGUF:Q4_K_M"
    timeout: float = 120.0
    max_tokens: int = 1024
    temperature: float = 0.7
    top_p: float = 0.9
    stream: bool = False
    system_prompt: str = "你是一个有帮助的AI助手。"


@dataclass
class EmbeddingConfig:
    """嵌入模型配置"""

    provider: str = "openai-compatible"
    base_url: Optional[str] = None
    api_key: str = ""
    model: str = "text-embedding-3-small"
    dimensions: int = 1536
    batch_size: int = 32


@dataclass
class RerankerConfig:
    """Reranker 模型配置"""

    provider: str = "openai-compatible"
    model: str = "BAAI/bge-reranker-v2-m3"
    base_url: Optional[str] = None
    api_key: str = ""
    top_n: int = 3


@dataclass
class VectorStoreConfig:
    """向量数据库配置"""

    type: str = "chroma"
    host: str = "localhost"
    port: int = 8000
    collection_name: str = "knowledge_base"
    persist_directory: str = "./data/chroma"


@dataclass
class LocalModelConfig:
    """本地模型配置"""

    name: str = ""
    quantize: str = "Q4_K_M"
    port: int = 8080
    context_window: int = 8192


@dataclass
class ModelConfig:
    """统一模型配置"""

    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    reranker: RerankerConfig = field(default_factory=RerankerConfig)
    vector_store: VectorStoreConfig = field(default_factory=VectorStoreConfig)
    local_models: Dict[str, LocalModelConfig] = field(default_factory=dict)


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self._config: Optional[ModelConfig] = None

    def load_config(self) -> ModelConfig:
        """加载配置"""
        config = ModelConfig()

        # 1. 从 YAML 文件加载
        yaml_config = self._load_from_yaml()

        # 2. 从环境变量覆盖
        self._override_from_env(yaml_config)

        # 3. 合并到配置对象
        self._merge_to_config(yaml_config, config)

        self._config = config
        return config

    def _load_from_yaml(self) -> Dict[str, Any]:
        """从 YAML 文件加载配置"""
        config_file = self.config_dir / "models.yaml"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def _override_from_env(self, config: Dict[str, Any]):
        """从环境变量覆盖配置"""
        # LLM 配置
        if "LLM_PROVIDER" in os.environ:
            config["llm"] = config.get("llm", {})
            config["llm"]["provider"] = os.environ["LLM_PROVIDER"]
        if "LLM_BASE_URL" in os.environ:
            config["llm"] = config.get("llm", {})
            config["llm"]["base_url"] = os.environ["LLM_BASE_URL"]
        if "LLM_MODEL" in os.environ:
            config["llm"] = config.get("llm", {})
            config["llm"]["model"] = os.environ["LLM_MODEL"]
        if "LLM_API_KEY" in os.environ:
            config["llm"] = config.get("llm", {})
            config["llm"]["api_key"] = os.environ["LLM_API_KEY"]
        if "LLM_MAX_TOKENS" in os.environ:
            config["llm"] = config.get("llm", {})
            config["llm"]["max_tokens"] = int(os.environ["LLM_MAX_TOKENS"])
        if "LLM_TEMPERATURE" in os.environ:
            config["llm"] = config.get("llm", {})
            config["llm"]["temperature"] = float(os.environ["LLM_TEMPERATURE"])

        # 嵌入配置
        if "EMBEDDING_MODEL" in os.environ:
            config["embedding"] = config.get("embedding", {})
            config["embedding"]["model"] = os.environ["EMBEDDING_MODEL"]
        if "EMBEDDING_BASE_URL" in os.environ:
            config["embedding"] = config.get("embedding", {})
            config["embedding"]["base_url"] = os.environ["EMBEDDING_BASE_URL"]

        # 向量数据库配置
        if "VECTOR_STORE_TYPE" in os.environ:
            config["vector_store"] = config.get("vector_store", {})
            config["vector_store"]["type"] = os.environ["VECTOR_STORE_TYPE"]

    def _merge_to_config(self, yaml_config: Dict[str, Any], config: ModelConfig):
        """合并配置到对象"""
        # LLM 配置
        if "llm" in yaml_config:
            llm_cfg = yaml_config["llm"]
            config.llm.provider = llm_cfg.get("provider", config.llm.provider)
            config.llm.base_url = llm_cfg.get("base_url", config.llm.base_url)
            config.llm.api_key = llm_cfg.get("api_key", config.llm.api_key)
            config.llm.model = llm_cfg.get("model", config.llm.model)
            config.llm.timeout = llm_cfg.get("timeout", config.llm.timeout)
            config.llm.max_tokens = llm_cfg.get("max_tokens", config.llm.max_tokens)
            config.llm.temperature = llm_cfg.get("temperature", config.llm.temperature)
            config.llm.top_p = llm_cfg.get("top_p", config.llm.top_p)
            config.llm.stream = llm_cfg.get("stream", config.llm.stream)
            config.llm.system_prompt = llm_cfg.get("system_prompt", config.llm.system_prompt)

        # 嵌入配置
        if "embedding" in yaml_config:
            emb_cfg = yaml_config["embedding"]
            config.embedding.provider = emb_cfg.get("provider", config.embedding.provider)
            config.embedding.base_url = emb_cfg.get("base_url", config.embedding.base_url)
            config.embedding.api_key = emb_cfg.get("api_key", config.embedding.api_key)
            config.embedding.model = emb_cfg.get("model", config.embedding.model)
            config.embedding.dimensions = emb_cfg.get("dimensions", config.embedding.dimensions)
            config.embedding.batch_size = emb_cfg.get("batch_size", config.embedding.batch_size)

        # Reranker 配置
        if "reranker" in yaml_config:
            rerank_cfg = yaml_config["reranker"]
            config.reranker.provider = rerank_cfg.get("provider", config.reranker.provider)
            config.reranker.model = rerank_cfg.get("model", config.reranker.model)
            config.reranker.base_url = rerank_cfg.get("base_url", config.reranker.base_url)
            config.reranker.api_key = rerank_cfg.get("api_key", config.reranker.api_key)
            config.reranker.top_n = rerank_cfg.get("top_n", config.reranker.top_n)

        # 向量数据库配置
        if "vector_store" in yaml_config:
            vs_cfg = yaml_config["vector_store"]
            config.vector_store.type = vs_cfg.get("type", config.vector_store.type)
            config.vector_store.host = vs_cfg.get("host", config.vector_store.host)
            config.vector_store.port = vs_cfg.get("port", config.vector_store.port)
            config.vector_store.collection_name = vs_cfg.get(
                "collection_name", config.vector_store.collection_name
            )
            config.vector_store.persist_directory = vs_cfg.get(
                "persist_directory", config.vector_store.persist_directory
            )

        # 本地模型配置
        if "local_models" in yaml_config:
            for name, model_cfg in yaml_config["local_models"].items():
                config.local_models[name] = LocalModelConfig(
                    name=model_cfg.get("name", ""),
                    quantize=model_cfg.get("quantize", "Q4_K_M"),
                    port=model_cfg.get("port", 8080),
                    context_window=model_cfg.get("context_window", 8192),
                )

    def get_config(self) -> ModelConfig:
        """获取配置（懒加载）"""
        if self._config is None:
            self._config = self.load_config()
        return self._config

    def reload(self):
        """重新加载配置"""
        self._config = None
        return self.load_config()

    def get_llm_config(self) -> LLMConfig:
        """获取 LLM 配置"""
        return self.get_config().llm

    def get_embedding_config(self) -> EmbeddingConfig:
        """获取嵌入配置"""
        return self.get_config().embedding

    def get_reranker_config(self) -> RerankerConfig:
        """获取 Reranker 配置"""
        return self.get_config().reranker

    def get_vector_store_config(self) -> VectorStoreConfig:
        """获取向量数据库配置"""
        return self.get_config().vector_store


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_dir: str = "config") -> ConfigManager:
    """获取全局配置管理器"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_dir)
    return _config_manager


def load_model_config(config_dir: str = "config") -> ModelConfig:
    """加载模型配置（便捷函数）"""
    return get_config_manager(config_dir).get_config()


def get_llm_config(config_dir: str = "config") -> LLMConfig:
    """获取 LLM 配置（便捷函数）"""
    return get_config_manager(config_dir).get_llm_config()


def get_embedding_config(config_dir: str = "config") -> EmbeddingConfig:
    """获取嵌入配置（便捷函数）"""
    return get_config_manager(config_dir).get_embedding_config()


def get_vector_store_config(config_dir: str = "config") -> VectorStoreConfig:
    """获取向量数据库配置（便捷函数）"""
    return get_config_manager(config_dir).get_vector_store_config()
