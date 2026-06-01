"""runtime 模块 - Agent Runtime 运行时"""

# 直接导入，避免循环依赖问题
try:
    from runtime.agent_runtime import AgentRuntime, RuntimeConfig
except ImportError:
    # 如果导入失败，延迟加载
    def __getattr__(name):
        if name == "AgentRuntime":
            from runtime.agent_runtime import AgentRuntime

            return AgentRuntime
        elif name == "RuntimeConfig":
            from runtime.agent_runtime import RuntimeConfig

            return RuntimeConfig
        raise AttributeError(f"module 'runtime' has no attribute '{name}'")


__all__ = ["AgentRuntime", "RuntimeConfig"]
