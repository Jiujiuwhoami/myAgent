"""
状态机 - Agent 状态管理
"""

from datetime import datetime
from typing import Callable, Dict, Set

from core.task import Task
from core.types import TaskStatus


class AgentFSM:
    """
    Agent 状态机

    管理任务状态的合法转换
    """

    ALLOWED_TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
        TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
        TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
        TaskStatus.FAILED: {TaskStatus.RETRYING, TaskStatus.CANCELLED},
        TaskStatus.RETRYING: {TaskStatus.RUNNING, TaskStatus.FAILED},
        TaskStatus.COMPLETED: set(),
        TaskStatus.CANCELLED: set(),
    }

    def __init__(self):
        self.transition_history: list[tuple[TaskStatus, TaskStatus, datetime]] = []
        self.callbacks: Dict[TaskStatus, list[Callable]] = {}

    def can_transition_to(self, from_status: TaskStatus, to_status: TaskStatus) -> bool:
        """检查是否可以进行状态转换"""
        return to_status in self.ALLOWED_TRANSITIONS.get(from_status, set())

    def transition(self, task: Task, to_status: TaskStatus) -> bool:
        """执行状态转换"""
        if not self.can_transition_to(task.status, to_status):
            return False

        old_status = task.status
        task.status = to_status

        if to_status == TaskStatus.RUNNING and not task.started_at:
            task.started_at = datetime.now()
        if to_status in {TaskStatus.COMPLETED, TaskStatus.FAILED}:
            task.completed_at = datetime.now()

        self.transition_history.append((old_status, to_status, datetime.now()))

        self._trigger_callbacks(to_status, task)

        return True

    def _trigger_callbacks(self, status: TaskStatus, task: Task):
        """触发状态变化的回调"""
        for callback in self.callbacks.get(status, []):
            try:
                callback(task)
            except Exception as e:
                print(f"回调执行错误: {e}")

    def on_status(self, status: TaskStatus, callback: Callable):
        """注册状态变化回调"""
        if status not in self.callbacks:
            self.callbacks[status] = []
        self.callbacks[status].append(callback)
