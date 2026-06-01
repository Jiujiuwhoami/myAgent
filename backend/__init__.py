"""backend 模块 - 多用户后端引擎"""

__all__ = [
    "MultiUserEngine",
    "User",
    "UserRole",
    "TaskPriority",
    "TaskState",
    "QueuedTask",
    "Database",
    "UserRuntime",
    "TaskQueue",
    "_global_engine",
    "create_app",
    "get_engine",
    "get_current_user",
    "run_demo",
    "run_server",
]


def __getattr__(name):
    """延迟导入，避免循环依赖"""
    if name in (
        "MultiUserEngine",
        "User",
        "UserRole",
        "TaskPriority",
        "TaskState",
        "QueuedTask",
        "Database",
        "UserRuntime",
        "TaskQueue",
        "_global_engine",
    ):
        from backend.engine import (
            Database,
            MultiUserEngine,
            QueuedTask,
            TaskPriority,
            TaskQueue,
            TaskState,
            User,
            UserRole,
            UserRuntime,
            _global_engine,
        )

        return locals()[name]
    elif name == "create_app":
        from backend.server import create_app

        return create_app
    elif name == "get_engine":
        from backend.server import get_engine

        return get_engine
    elif name == "get_current_user":
        from backend.server import get_current_user

        return get_current_user
    elif name == "run_demo":
        from backend.cli import run_demo

        return run_demo
    elif name == "run_server":
        from backend.cli import run_server

        return run_server
    raise AttributeError(f"module 'backend' has no attribute '{name}'")
