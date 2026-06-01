"""advanced 模块 - 高级功能"""

__all__ = [
    "StreamProcessor",
    "StreamChunk",
    "StreamResponse",
    "StreamingLLMAgent",
    "HumanInterventionHandler",
    "InterventionRequest",
    "InterventionResponse",
    "InterventionType",
    "InterventionAwareExecutor",
    "create_intervention_handler",
    "NestedDAG",
    "SubDAGNode",
    "NestedDAGExecutionResult",
    "create_nested_example",
]


def __getattr__(name):
    """延迟导入，避免循环依赖"""
    if name in ("StreamProcessor", "StreamChunk", "StreamResponse", "StreamingLLMAgent"):
        from advanced.streaming import (
            StreamChunk,
            StreamingLLMAgent,
            StreamProcessor,
            StreamResponse,
        )

        return locals()[name]
    elif name in (
        "HumanInterventionHandler",
        "InterventionRequest",
        "InterventionResponse",
        "InterventionType",
        "InterventionAwareExecutor",
        "create_intervention_handler",
    ):
        from advanced.intervention import (
            HumanInterventionHandler,
            InterventionAwareExecutor,
            InterventionRequest,
            InterventionResponse,
            InterventionType,
            create_intervention_handler,
        )

        return locals()[name]
    elif name in ("NestedDAG", "SubDAGNode", "NestedDAGExecutionResult", "create_nested_example"):
        from advanced.nested_dag import (
            NestedDAG,
            NestedDAGExecutionResult,
            SubDAGNode,
            create_nested_example,
        )

        return locals()[name]
    raise AttributeError(f"module 'advanced' has no attribute '{name}'")
