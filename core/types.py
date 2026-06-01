"""核心类型定义"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional


class TaskStatus(Enum):
    """任务状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"  # 添加 RETRYING 状态


class NodeStatus(Enum):
    """DAG 节点状态"""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EventType(Enum):
    """事件类型"""

    START = "start"
    COMPLETE = "complete"
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
    TASK_RETRYING = "task_retrying"
    TOOL_EXECUTED = "tool_executed"
    CHECKPOINT_CREATED = "checkpoint_created"
    MEMORY_UPDATED = "memory_updated"
    ERROR = "error"


@dataclass
class Event:
    """事件"""

    type: EventType
    source: str
    payload: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "source": self.source,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Tool:
    """工具定义"""

    name: str
    func: Callable
    description: str = ""
    parameters: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class ExecutionResult:
    """执行结果"""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
