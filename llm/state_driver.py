"""
LLM 驱动的状态迁移

使用 LLM 来决定状态机的状态转换，实现智能决策。
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from core.statechart import StateChart
from core.task import Task
from llm.client import LLMClient, LLMConfig, get_client

SYSTEM_PROMPT = """你是一个状态机决策引擎。你的任务是根据当前状态和上下文，决定下一个状态转换。

可用状态：
{available_states}

当前状态：{current_state}

历史状态：{state_history}

上下文信息：
{context}

请分析当前情况，选择最合适的状态转换。

输出格式（JSON）：
{{
    "reasoning": "你的分析过程",
    "next_state": "目标状态",
    "confidence": 0.0-1.0之间的置信度,
    "action": "建议执行的动作（可选）"
}}
"""


@dataclass
class StateDecision:
    """状态迁移决策"""

    reasoning: str
    next_state: str
    confidence: float
    action: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TransitionContext:
    """状态迁移上下文"""

    current_state: str
    available_states: List[str]
    state_history: List[str]
    task: Optional[Task] = None
    memory_context: Optional[Dict] = None
    user_input: Optional[str] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)


class LLMStateDriver:
    """
    LLM 驱动的状态迁移

    使用 LLM 来决定状态机的状态转换，实现：
    - 智能状态决策
    - 自适应转换路径
    - 上下文感知决策
    """

    def __init__(
        self,
        statechart: StateChart,
        llm_client: Optional[LLMClient] = None,
        llm_config: Optional[LLMConfig] = None,
        min_confidence: float = 0.6,
        fallback_state: Optional[str] = None,
    ):
        self.statechart = statechart
        self.llm = llm_client or get_client(llm_config)
        self.min_confidence = min_confidence
        self.fallback_state = fallback_state

        self._decision_history: List[StateDecision] = []
        self._state_transitions: Dict[str, str] = {}
        self._callbacks: Dict[str, List[Callable]] = {}

    def learn_transition(self, from_state: str, to_state: str):
        """学习一个状态转换（用于后续决策参考）"""
        if from_state not in self._state_transitions:
            self._state_transitions[from_state] = to_state

    async def decide(self, context: TransitionContext) -> StateDecision:
        """使用 LLM 决定下一个状态"""
        prompt = self._build_prompt(context)

        try:
            response = self.llm.chat(prompt=prompt)
            content = response.content

            decision = self._parse_decision(content)
            decision = self._validate_decision(decision, context)

            self._decision_history.append(decision)

            print(f"   🤖 LLM 决策: {context.current_state} -> {decision.next_state}")
            print(f"   💭 推理: {decision.reasoning[:100]}...")
            print(f"   📊 置信度: {decision.confidence:.2f}")

            return decision

        except Exception as e:
            print(f"   ⚠️ LLM 决策失败: {e}，使用回退策略")
            return self._fallback_decision(context)

    def _build_prompt(self, context: TransitionContext) -> str:
        """构建提示"""
        state_history_str = " -> ".join(context.state_history[-5:]) or "无"

        context_str = ""
        if context.task:
            context_str += f"任务: {context.task.name}\n"
            context_str += f"状态: {context.task.status.value}\n"
            if context.task.input_data:
                context_str += f"输入: {json.dumps(context.task.input_data, ensure_ascii=False)}\n"
            if context.task.output_data:
                context_str += f"输出: {json.dumps(context.task.output_data, ensure_ascii=False)}\n"
            if context.task.error:
                context_str += f"错误: {context.task.error}\n"

        if context.memory_context:
            context_str += f"记忆: {json.dumps(context.memory_context, ensure_ascii=False)}\n"

        if context.user_input:
            context_str += f"用户输入: {context.user_input}\n"

        for key, value in context.extra_data.items():
            context_str += f"{key}: {value}\n"

        return SYSTEM_PROMPT.format(
            available_states=", ".join(context.available_states),
            current_state=context.current_state,
            state_history=state_history_str,
            context=context_str or "无",
        )

    def _parse_decision(self, content: str) -> StateDecision:
        """解析 LLM 响应"""
        try:
            data = json.loads(content.strip())

            return StateDecision(
                reasoning=data.get("reasoning", ""),
                next_state=data.get("next_state", ""),
                confidence=float(data.get("confidence", 0.5)),
                action=data.get("action"),
            )
        except json.JSONDecodeError:
            lines = content.strip().split("\n")
            if len(lines) > 0:
                return StateDecision(
                    reasoning="无法解析结构化输出", next_state=lines[0].strip(), confidence=0.3
                )
            return StateDecision(reasoning="解析失败", next_state="", confidence=0.0)

    def _validate_decision(
        self, decision: StateDecision, context: TransitionContext
    ) -> StateDecision:
        """验证决策有效性"""
        if decision.next_state not in context.available_states:
            print(f"   ⚠️ 目标状态不可用: {decision.next_state}")
            decision.next_state = self._find_nearest_valid_state(
                decision.next_state, context.available_states
            )
            decision.confidence *= 0.5

        if decision.confidence < self.min_confidence:
            print("   ⚠️ 置信度低于阈值，使用回退")
            if self.fallback_state and self.fallback_state in context.available_states:
                decision.next_state = self.fallback_state
                decision.confidence = 0.5

        return decision

    def _find_nearest_valid_state(self, target: str, available: List[str]) -> str:
        """找到最近似的有效状态"""
        if target in available:
            return target

        target_lower = target.lower()
        for state in available:
            if state.lower() == target_lower:
                return state

        for state in available:
            if target_lower in state.lower() or state.lower() in target_lower:
                return state

        return available[0] if available else ""

    def _fallback_decision(self, context: TransitionContext) -> StateDecision:
        """回退决策策略"""
        if context.current_state in self._state_transitions:
            next_state = self._state_transitions[context.current_state]
            if next_state in context.available_states:
                return StateDecision(
                    reasoning="基于历史学习的回退决策", next_state=next_state, confidence=0.4
                )

        if self.fallback_state and self.fallback_state in context.available_states:
            return StateDecision(
                reasoning="默认回退状态", next_state=self.fallback_state, confidence=0.3
            )

        return StateDecision(
            reasoning="无可用回退，使用第一个可用状态",
            next_state=context.available_states[0] if context.available_states else "",
            confidence=0.1,
        )

    async def execute_transition(self, context: TransitionContext) -> bool:
        """执行状态转换"""
        decision = await self.decide(context)

        if not decision.next_state:
            return False

        current = context.current_state

        if current != decision.next_state:
            success = self.statechart.trigger(decision.next_state)

            if success:
                self._trigger_callbacks(decision.next_state, decision)

            return success

        return True

    def _trigger_callbacks(self, state: str, decision: StateDecision):
        """触发回调"""
        for callback in self._callbacks.get(state, []):
            try:
                callback(state, decision)
            except Exception as e:
                print(f"回调执行错误: {e}")

    def on_transition(self, state: str, callback: Callable):
        """注册转换回调"""
        if state not in self._callbacks:
            self._callbacks[state] = []
        self._callbacks[state].append(callback)

    def get_decision_history(self) -> List[StateDecision]:
        """获取决策历史"""
        return self._decision_history.copy()

    def get_last_decision(self) -> Optional[StateDecision]:
        """获取最后一次决策"""
        return self._decision_history[-1] if self._decision_history else None

    def clear_history(self):
        """清空决策历史"""
        self._decision_history = []

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "current_state": self.statechart.get_current_state(),
            "decision_count": len(self._decision_history),
            "learned_transitions": len(self._state_transitions),
            "min_confidence": self.min_confidence,
            "last_decision": (
                self.get_last_decision().__dict__ if self.get_last_decision() else None
            ),
        }


class HierarchicalStateDriver:
    """
    层次化状态驱动

    在多个层次的状态机之间协调决策。
    """

    def __init__(self):
        self.drivers: Dict[str, LLMStateDriver] = {}
        self.hierarchy: Dict[str, List[str]] = {}

    def add_driver(self, name: str, driver: LLMStateDriver):
        """添加子驱动"""
        self.drivers[name] = driver

    def set_hierarchy(self, parent: str, children: List[str]):
        """设置层次关系"""
        self.hierarchy[parent] = children

    async def decide(self, context: TransitionContext) -> Dict[str, StateDecision]:
        """层次化决策"""
        decisions = {}

        for name, driver in self.drivers.items():
            decision = await driver.decide(context)
            decisions[name] = decision

        return decisions

    def sync_states(self):
        """同步所有子状态机的状态"""
        pass
