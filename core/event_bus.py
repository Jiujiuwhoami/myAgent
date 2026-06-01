"""
事件总线 - 发布/订阅系统
"""

from typing import Awaitable, Callable, Dict, List, Optional

from core.types import Event, EventType


class EventBus:
    """
    事件总线

    支持异步事件发布和订阅
    """

    def __init__(self, history_limit: int = 1000):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._history: List[Event] = []
        self._history_limit = history_limit
        self._all_subscribers: List[Callable] = []

    def subscribe(self, event_type: EventType, callback: Callable[[Event], Awaitable[None]]):
        """订阅特定事件"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def subscribe_all(self, callback: Callable[[Event], Awaitable[None]]):
        """订阅所有事件"""
        self._all_subscribers.append(callback)

    async def publish(self, event: Event):
        """发布事件"""
        print(f"   📢 {event.type.value}: {event.source}")

        self._history.append(event)
        if len(self._history) > self._history_limit:
            self._history.pop(0)

        # 通知特定订阅者
        for callback in self._subscribers.get(event.type, []):
            try:
                await callback(event)
            except Exception as e:
                print(f"回调执行错误: {e}")

        # 通知所有事件订阅者
        for callback in self._all_subscribers:
            try:
                await callback(event)
            except Exception as e:
                print(f"回调执行错误: {e}")

    def get_history(self, event_type: Optional[EventType] = None, limit: int = 10) -> List[Event]:
        """获取历史事件"""
        history = []
        for event in reversed(self._history):
            if event_type is None or event.type == event_type:
                history.append(event)
                if len(history) >= limit:
                    break
        return list(reversed(history))

    def get_status(self) -> Dict:
        return {
            "events_stored": len(self._history),
            "subscribers_count": (
                sum(len(s) for s in self._subscribers.values()) + len(self._all_subscribers)
            ),
        }
