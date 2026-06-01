"""LLM Client - 本地模型客户端

支持 OpenAI 兼容 API 的本地 LLM 部署。
配置来源优先级: 命令行参数 > 环境变量 > YAML 配置文件 > 默认值
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class Message:
    """消息"""

    role: str  # "user", "assistant", "system"
    content: str
    name: Optional[str] = None

    def to_dict(self) -> Dict:
        d = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        return d


@dataclass
class LLMResponse:
    """LLM 响应"""

    content: str
    model: str
    usage: Dict[str, Any] = field(default_factory=dict)
    finish_reason: str = ""
    raw_response: Optional[Dict] = None


@dataclass
class LLMConfig:
    """LLM 配置"""

    provider: str = "openai-compatible"
    base_url: str = "http://localhost:8080/v1"
    api_key: str = ""  # 本地模型通常不需要
    model: str = "Qwen/Qwen3-4B-GGUF:Q4_K_M"
    timeout: float = 120.0
    max_tokens: int = 1024
    temperature: float = 0.7
    top_p: float = 0.9
    stream: bool = False
    system_prompt: str = "你是一个有帮助的AI助手。"

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """从环境变量加载（向后兼容）"""
        return cls(
            provider=os.getenv("LLM_PROVIDER", "openai-compatible"),
            base_url=os.getenv("LLM_BASE_URL", "http://localhost:8080/v1"),
            model=os.getenv("LLM_MODEL", "Qwen/Qwen3-4B-GGUF:Q4_K_M"),
            api_key=os.getenv("LLM_API_KEY", ""),
            timeout=float(os.getenv("LLM_TIMEOUT", "120")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1024")),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            stream=os.getenv("LLM_STREAM", "false").lower() == "true",
        )

    @classmethod
    def from_config_manager(cls) -> "LLMConfig":
        """从统一配置管理器加载（推荐）"""
        try:
            from myAgent.config import get_llm_config as get_config

            config = get_config()
            return cls(
                provider=config.provider,
                base_url=config.base_url,
                api_key=config.api_key,
                model=config.model,
                timeout=config.timeout,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
                stream=config.stream,
                system_prompt=config.system_prompt,
            )
        except ImportError:
            # 如果配置管理器不可用，回退到环境变量
            return cls.from_env()


class LLMClient:
    """本地 LLM 客户端

    支持 OpenAI 兼容 API 的本地模型。

    示例:
        # 方式1: 使用统一配置管理器（推荐）
        client = LLMClient()  # 自动从配置文件/环境变量加载

        # 方式2: 手动指定配置
        config = LLMConfig(base_url="http://localhost:8080/v1", model="Qwen/Qwen3-4B")
        client = LLMClient(config)

        # 健康检查
        if client.health_check():
            print("✅ LLM 服务正常")

        # 简单对话
        response = client.chat("你好")
        print(response.content)

        # 多轮对话
        messages = [
            Message("system", "你是一个助手"),
            Message("user", "你好"),
        ]
        response = client.chat(messages=messages)
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        # 优先级: 传入的 config > 配置管理器 > 环境变量 > 默认值
        if config is not None:
            self.config = config
        else:
            self.config = LLMConfig.from_config_manager()
        self._messages: List[Message] = []
        print(f"   [OK] LLM Client initialized: {self.config.model} @ {self.config.base_url}")

    def add_message(self, role: str, content: str, name: Optional[str] = None):
        """添加消息"""
        self._messages.append(Message(role=role, content=content, name=name))

    def clear_messages(self):
        """清空消息历史"""
        self._messages = []

    def health_check(self) -> bool:
        """健康检查"""
        try:
            url = f"{self.config.base_url.rstrip('/')}/models"
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url)
                return response.status_code == 200
        except Exception:
            return False

    def chat(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Message]] = None,
        **kwargs,
    ) -> LLMResponse:
        """发送聊天请求

        Args:
            prompt: 简单提示（自动转换为 user 消息）
            messages: 消息列表（优先使用）
            **kwargs: 可覆盖配置参数（temperature, max_tokens, etc.）

        Returns:
            LLMResponse
        """
        if messages:
            msg_list = messages
        elif prompt:
            msg_list = [Message("user", prompt)]
        else:
            raise ValueError("需要 prompt 或 messages")

        url = f"{self.config.base_url.rstrip('/')}/chat/completions"

        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        # 使用配置值，允许 kwargs 覆盖
        payload = {
            "model": kwargs.get("model", self.config.model),
            "messages": [m.to_dict() for m in msg_list],
            "temperature": kwargs.get("temperature", self.config.temperature),
            "top_p": kwargs.get("top_p", self.config.top_p),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "stream": kwargs.get("stream", self.config.stream),
        }

        try:
            timeout = kwargs.get("timeout", self.config.timeout)
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()

                data = response.json()

                content = data["choices"][0]["message"]["content"]
                model = data.get("model", self.config.model)
                usage = data.get("usage", {})
                finish_reason = data.get("choices", [{}])[0].get("finish_reason", "")

                return LLMResponse(
                    content=content,
                    model=model,
                    usage=usage,
                    finish_reason=finish_reason,
                    raw_response=data,
                )

        except Exception as e:
            return LLMResponse(
                content=f"[错误: {e}]",
                model=self.config.model,
                usage={},
                finish_reason="error",
            )

    def chat_with_history(
        self,
        prompt: str,
    ) -> LLMResponse:
        """带历史记录的聊天"""
        self.add_message("user", prompt)
        response = self.chat(messages=self._messages)

        if response.finish_reason != "error":
            self.add_message("assistant", response.content)

        return response


def get_client(config: Optional[LLMConfig] = None) -> LLMClient:
    """获取客户端实例"""
    return LLMClient(config)


def chat(prompt: str, config: Optional[LLMConfig] = None) -> LLMResponse:
    """快捷聊天函数"""
    client = LLMClient(config)
    return client.chat(prompt)
