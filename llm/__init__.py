"""llm 模块 - 本地 LLM 集成"""

__all__ = [
    "LLMClient",
    "LLMConfig",
    "Message",
    "LLMResponse",
    "get_client",
    "chat",
    "LLMAgent",
    "create_agent",
    "AgentState",
]


def __getattr__(name):
    """延迟导入，避免循环依赖"""
    if name == "LLMClient":
        from llm.client import LLMClient

        return LLMClient
    elif name == "LLMConfig":
        from llm.client import LLMConfig

        return LLMConfig
    elif name == "Message":
        from llm.client import Message

        return Message
    elif name == "LLMResponse":
        from llm.client import LLMResponse

        return LLMResponse
    elif name == "get_client":
        from llm.client import get_client

        return get_client
    elif name == "chat":
        from llm.client import chat

        return chat
    elif name == "LLMAgent":
        from llm.agent import LLMAgent

        return LLMAgent
    elif name == "create_agent":
        from llm.agent import create_agent

        return create_agent
    elif name == "AgentState":
        from llm.agent import AgentState

        return AgentState
    raise AttributeError(f"module 'llm' has no attribute '{name}'")
