"""
层次状态机 (StateChart)

支持：
- 嵌套状态（正交区域）
- 状态历史（浅历史、深历史）
- 默认状态入口
- 监护条件（guard conditions）
- 完成转换
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class TransitionType(Enum):
    """转换类型"""

    EXTERNAL = "external"
    INTERNAL = "internal"
    LOCAL = "local"


@dataclass
class StateChartConfig:
    """StateChart 配置"""

    initial_state: str = "idle"
    parallel_enter: bool = True
    parallel_exit: bool = True


@dataclass
class State:
    """状态定义"""

    id: str
    name: str
    parent: Optional["State"] = None
    children: Dict[str, "State"] = field(default_factory=dict)
    entry_actions: List[Callable] = field(default_factory=list)
    exit_actions: List[Callable] = field(default_factory=list)
    do_actions: List[Callable] = field(default_factory=list)
    is_initial: bool = False
    is_final: bool = False
    history_type: str = "none"
    transitions: Dict[str, "Transition"] = field(default_factory=dict)
    parallel_regions: List["State"] = field(default_factory=list)

    def is_composite(self) -> bool:
        return len(self.children) > 0

    def is_parallel(self) -> bool:
        return len(self.parallel_regions) > 0

    def is_leaf(self) -> bool:
        return not self.is_composite() and not self.is_parallel()


@dataclass
class Transition:
    """转换定义"""

    target: str
    event: Optional[str] = None
    guard: Optional[Callable[[], bool]] = None
    action: Optional[Callable] = None
    transition_type: TransitionType = TransitionType.EXTERNAL

    def can_fire(self) -> bool:
        if self.guard is None:
            return True
        return self.guard()


@dataclass
class StateMachineContext:
    """状态机执行上下文"""

    current_states: Dict[str, str] = field(default_factory=dict)
    history_states: Dict[str, str] = field(default_factory=dict)
    deep_history_states: Dict[str, str] = field(default_factory=dict)
    event_queue: List[Any] = field(default_factory=list)
    is_running: bool = False
    transition_history: List[tuple] = field(default_factory=list)


class StateChart:
    """
    层次状态机实现

    支持 UML StateChart 的核心特性：
    - 嵌套状态（层次）
    - 平行区域（Parallel）
    - 历史状态（History）
    - 监护条件（Guard）
    - 完成转换（Completion Transition）
    """

    def __init__(self, config: Optional[StateChartConfig] = None):
        self.config = config or StateChartConfig()
        self.states: Dict[str, State] = {}
        self._state_counter = 0
        self.context = StateMachineContext()
        self._callbacks: Dict[str, List[Callable]] = {}

        self._create_initial_structure()

    def _create_initial_structure(self):
        """创建初始结构"""
        self.add_state("idle", is_initial=True)
        self.add_state("active")
        self.add_state("completed", is_final=True)
        self.add_state("error")
        self.set_initial_state("idle")

    def add_state(
        self,
        state_id: str,
        parent: Optional[str] = None,
        is_initial: bool = False,
        is_final: bool = False,
        history_type: str = "none",
        **kwargs,
    ) -> State:
        """添加状态"""
        if state_id in self.states:
            raise ValueError(f"状态已存在: {state_id}")

        state = State(
            id=state_id,
            name=state_id,
            is_initial=is_initial,
            is_final=is_final,
            history_type=history_type,
        )

        if parent:
            if parent not in self.states:
                raise ValueError(f"父状态不存在: {parent}")
            state.parent = self.states[parent]
            self.states[parent].children[state_id] = state

        self.states[state_id] = state
        return state

    def add_parallel_region(self, parent_id: str, region_id: str) -> State:
        """添加并行区域"""
        if parent_id not in self.states:
            raise ValueError(f"父状态不存在: {parent_id}")

        region = self.add_state(region_id, parent=parent_id)
        self.states[parent_id].parallel_regions.append(region)
        return region

    def add_transition(
        self,
        source: str,
        target: str,
        event: Optional[str] = None,
        guard: Optional[Callable] = None,
        action: Optional[Callable] = None,
        transition_type: TransitionType = TransitionType.EXTERNAL,
    ) -> Transition:
        """添加转换"""
        if source not in self.states:
            raise ValueError(f"源状态不存在: {source}")
        if target not in self.states:
            raise ValueError(f"目标状态不存在: {target}")

        transition = Transition(
            target=target, event=event, guard=guard, action=action, transition_type=transition_type
        )

        self.states[source].transitions[event or ""] = transition
        return transition

    def set_initial_state(self, state_id: str):
        """设置初始状态"""
        if state_id not in self.states:
            raise ValueError(f"状态不存在: {state_id}")

        for state in self.states.values():
            state.is_initial = False
        self.states[state_id].is_initial = True
        self.config.initial_state = state_id

    def add_entry_action(self, state_id: str, action: Callable):
        """添加进入动作"""
        if state_id in self.states:
            self.states[state_id].entry_actions.append(action)

    def add_exit_action(self, state_id: str, action: Callable):
        """添加退出动作"""
        if state_id in self.states:
            self.states[state_id].exit_actions.append(action)

    def add_do_action(self, state_id: str, action: Callable):
        """添加do动作（状态内活动）"""
        if state_id in self.states:
            self.states[state_id].do_actions.append(action)

    def _get_initial_states(self, state: State) -> List[str]:
        """获取状态的初始子状态"""
        if state.is_parallel():
            return [s.id for s in state.parallel_regions]

        if not state.is_composite():
            return [state.id]

        for child in state.children.values():
            if child.is_initial:
                return [child.id]

        return [list(state.children.values())[0].id]

    def _exit_state(self, state_id: str, depth: int = 0):
        """退出状态及其所有子状态"""
        if state_id not in self.states:
            return

        state = self.states[state_id]

        for child in state.children.values():
            self._exit_state(child.id, depth + 1)

        for action in reversed(state.exit_actions):
            try:
                action()
            except Exception as e:
                print(f"退出动作执行错误 [{state_id}]: {e}")

        if state.history_type != "none":
            self.context.history_states[state_id] = state_id

    def _enter_state(self, state_id: str, depth: int = 0):
        """进入状态及其所有子状态"""
        if state_id not in self.states:
            return

        state = self.states[state_id]

        for action in state.entry_actions:
            try:
                action()
            except Exception as e:
                print(f"进入动作执行错误 [{state_id}]: {e}")

        if state.is_parallel():
            for region in state.parallel_regions:
                initial_states = self._get_initial_states(region)
                for init_state in initial_states:
                    self._enter_state(init_state, depth + 1)
        elif state.is_composite():
            initial_states = self._get_initial_states(state)
            for init_state in initial_states:
                self._enter_state(init_state, depth + 1)

    def _get_lca(self, state1: str, state2: str) -> Optional[str]:
        """获取两个状态的最低公共祖先"""
        if state1 == state2:
            return state1

        ancestors1 = set()
        current = state1
        while current:
            ancestors1.add(current)
            if current in self.states and self.states[current].parent:
                current = self.states[current].parent.id
            else:
                break

        current = state2
        while current:
            if current in ancestors1:
                return current
            if current in self.states and self.states[current].parent:
                current = self.states[current].parent.id
            else:
                break

        return None

    def _execute_transition(self, source: str, target: str):
        """执行转换"""
        source_state = self.states.get(source)
        target_state = self.states.get(target)

        if not source_state or not target_state:
            return

        lca = self._get_lca(source, target)

        exit_list = []
        current = source
        while current and current != lca:
            exit_list.append(current)
            if current in self.states and self.states[current].parent:
                current = self.states[current].parent.id
            else:
                break

        for state_id in reversed(exit_list):
            self._exit_state(state_id)

        enter_list = []
        path = []
        current = target
        while current and current != lca:
            path.append(current)
            if current in self.states and self.states[current].parent:
                current = self.states[current].parent.id
            else:
                break

        for state_id in reversed(path):
            enter_list.append(state_id)

        for state_id in enter_list:
            self._enter_state(state_id)

        if target_state.history_type == "shallow":
            self.context.history_states[source] = source
        elif target_state.history_type == "deep":
            self.context.deep_history_states[source] = source

        self.context.transition_history.append((source, target, datetime.now()))

    def trigger(self, event: str, payload: Optional[Any] = None) -> bool:
        """触发事件"""
        if not self.context.current_states:
            initial = self._get_initial_states(self.states[self.config.initial_state])
            for state_id in initial:
                self.context.current_states[state_id] = state_id
                self._enter_state(state_id)

        fired = False

        for current_state_id in list(self.context.current_states.keys()):
            if current_state_id not in self.states:
                continue

            state = self.states[current_state_id]

            transition = state.transitions.get(event)
            if not transition:
                transition = state.transitions.get("")

            if transition and transition.can_fire():
                if transition.guard and not transition.guard():
                    continue

                if transition.action:
                    try:
                        transition.action()
                    except Exception as e:
                        print(f"转换动作执行错误: {e}")

                self._execute_transition(current_state_id, transition.target)
                fired = True

                self._trigger_callbacks(event, current_state_id, transition.target)

                break

        if not fired:
            self.context.event_queue.append((event, payload))

        return fired

    def _trigger_callbacks(self, event: str, from_state: str, to_state: str):
        """触发回调"""
        for callback in self._callbacks.get(to_state, []):
            try:
                callback(event, from_state, to_state)
            except Exception as e:
                print(f"回调执行错误: {e}")

    def on_state_change(self, state_id: str, callback: Callable):
        """注册状态变化回调"""
        if state_id not in self._callbacks:
            self._callbacks[state_id] = []
        self._callbacks[state_id].append(callback)

    def get_current_state(self) -> str:
        """获取当前状态"""
        if not self.context.current_states:
            return self.config.initial_state
        return list(self.context.current_states.values())[0]

    def get_all_current_states(self) -> List[str]:
        """获取所有当前状态（并行区域）"""
        return list(self.context.current_states.values())

    def is_in_state(self, state_id: str) -> bool:
        """检查是否处于指定状态"""
        return state_id in self.context.current_states

    def is_completed(self) -> bool:
        """检查是否到达最终状态"""
        return self.states.get(self.get_current_state(), State("", "")).is_final

    def reset(self):
        """重置状态机"""
        self.context = StateMachineContext()
        initial = self._get_initial_states(self.states[self.config.initial_state])
        for state_id in initial:
            self.context.current_states[state_id] = state_id
            self._enter_state(state_id)

    def get_status(self) -> Dict[str, Any]:
        """获取状态机状态"""
        return {
            "current_state": self.get_current_state(),
            "all_current_states": self.get_all_current_states(),
            "is_completed": self.is_completed(),
            "transition_count": len(self.context.transition_history),
            "queued_events": len(self.context.event_queue),
            "states": list(self.states.keys()),
        }
