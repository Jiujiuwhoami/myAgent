"""人类介入（Human-in-the-loop）支持

允许在 Agent 执行过程中暂停，等待人工确认或修改。
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class InterventionType(Enum):
    """介入类型"""

    CONFIRM = "confirm"  # 确认继续
    MODIFY = "modify"  # 修改参数
    SKIP = "skip"  # 跳过当前步骤
    ABORT = "abort"  # 中止执行
    OVERRIDE = "override"  # 覆盖决策


@dataclass
class InterventionRequest:
    """介入请求"""

    request_id: str
    timestamp: datetime
    step_name: str
    step_type: str  # "llm_call", "tool_call", "decision"
    context: Dict[str, Any]  # 当前上下文
    proposed_action: str  # 建议的行动
    options: List[str]  # 可选操作
    priority: str = "normal"  # "low", "normal", "high", "critical"

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "step_name": self.step_name,
            "step_type": self.step_type,
            "context": self.context,
            "proposed_action": self.proposed_action,
            "options": self.options,
            "priority": self.priority,
        }


@dataclass
class InterventionResponse:
    """介入响应"""

    request_id: str
    action: InterventionType
    modified_data: Optional[Dict[str, Any]] = None
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def confirm(cls, request_id: str, reason: str = "") -> "InterventionResponse":
        return cls(request_id=request_id, action=InterventionType.CONFIRM, reason=reason)

    @classmethod
    def modify(cls, request_id: str, data: Dict, reason: str = "") -> "InterventionResponse":
        return cls(
            request_id=request_id, action=InterventionType.MODIFY, modified_data=data, reason=reason
        )

    @classmethod
    def skip(cls, request_id: str, reason: str = "") -> "InterventionResponse":
        return cls(request_id=request_id, action=InterventionType.SKIP, reason=reason)

    @classmethod
    def abort(cls, request_id: str, reason: str = "") -> "InterventionResponse":
        return cls(request_id=request_id, action=InterventionType.ABORT, reason=reason)


class HumanInterventionHandler:
    """人类介入处理器

    管理 Agent 执行过程中的暂停和人工介入。

    示例:
        handler = HumanInterventionHandler()

        # 注册介入点
        handler.register_intervention_point(
            step_name="tool_call",
            condition=lambda ctx: ctx["tool_name"] == "delete_file",
            priority="high",
        )

        # 在 Agent 执行中调用
        response = await handler.request_intervention(request)
        if response.action == InterventionType.CONFIRM:
            # 继续执行
        elif response.action == InterventionType.MODIFY:
            # 使用修改后的数据
    """

    def __init__(
        self,
        timeout: float = 300.0,  # 默认超时 5 分钟
        auto_approve_conditions: Optional[List[Callable]] = None,
    ):
        """初始化介入处理器"""
        self.timeout = timeout
        self.auto_approve_conditions = auto_approve_conditions or []

        self._intervention_points: Dict[str, Dict] = {}
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._intervention_history: List[Dict] = []

    def register_intervention_point(
        self,
        step_name: str,
        condition: Callable[[Dict], bool],
        priority: str = "normal",
        message_template: str = "",
    ):
        """注册介入点

        Args:
            step_name: 步骤名称
            condition: 触发条件函数
            priority: 优先级
            message_template: 显示消息模板
        """
        self._intervention_points[step_name] = {
            "condition": condition,
            "priority": priority,
            "message_template": message_template,
        }

    def should_intervene(self, step_name: str, context: Dict) -> bool:
        """检查是否需要介入"""
        point = self._intervention_points.get(step_name)
        if not point:
            return False

        try:
            return point["condition"](context)
        except Exception:
            return False

    async def request_intervention(
        self,
        request: InterventionRequest,
    ) -> InterventionResponse:
        """请求人类介入

        Args:
            request: 介入请求

        Returns:
            介入响应
        """
        # 检查自动批准条件
        for condition in self.auto_approve_conditions:
            try:
                if condition(request):
                    return InterventionResponse.confirm(request.request_id, reason="自动批准")
            except Exception:
                pass

        # 创建 Future 等待响应
        future = asyncio.Future()
        self._pending_requests[request.request_id] = future

        # 打印介入请求
        print("\n⚠️ 需要人类介入!")
        print(f"   请求 ID: {request.request_id}")
        print(f"   步骤: {request.step_name}")
        print(f"   类型: {request.step_type}")
        print(f"   建议: {request.proposed_action}")
        print(f"   选项: {', '.join(request.options)}")
        print(f"   优先级: {request.priority}")
        print(f"   上下文: {json.dumps(request.context, ensure_ascii=False, indent=2)}")

        # 等待响应（带超时）
        try:
            response = await asyncio.wait_for(future, timeout=self.timeout)

            # 记录历史
            self._intervention_history.append(
                {
                    "request": request.to_dict(),
                    "response": {
                        "action": response.action.value,
                        "modified_data": response.modified_data,
                        "reason": response.reason,
                        "timestamp": response.timestamp.isoformat(),
                    },
                }
            )

            return response

        except asyncio.TimeoutError:
            print("   ⏰ 介入请求超时")
            return InterventionResponse.abort(request.request_id, reason="超时未响应")

    def respond(
        self,
        request_id: str,
        response: InterventionResponse,
    ):
        """提交介入响应"""
        future = self._pending_requests.get(request_id)
        if future and not future.done():
            future.set_result(response)
            del self._pending_requests[request_id]

    def respond_sync(
        self,
        request_id: str,
        action: str,
        modified_data: Optional[Dict] = None,
        reason: str = "",
    ):
        """同步提交响应（用于 CLI/交互界面）"""
        action_map = {
            "confirm": InterventionType.CONFIRM,
            "modify": InterventionType.MODIFY,
            "skip": InterventionType.SKIP,
            "abort": InterventionType.ABORT,
        }

        response = InterventionResponse(
            request_id=request_id,
            action=action_map.get(action, InterventionType.CONFIRM),
            modified_data=modified_data,
            reason=reason,
        )

        self.respond(request_id, response)

    def get_history(self) -> List[Dict]:
        """获取介入历史"""
        return self._intervention_history.copy()

    def clear_history(self):
        """清空历史"""
        self._intervention_history = []


class InterventionAwareExecutor:
    """支持人类介入的执行器

    在 Executor 基础上添加介入支持。

    示例:
        executor = InterventionAwareExecutor()
        executor.set_intervention_handler(handler)

        # 执行工具（可能触发介入）
        result = await executor.execute_with_intervention(
            tool_name="delete_file",
            arguments={"path": "/tmp/test"},
        )
    """

    def __init__(
        self, base_executor, intervention_handler: Optional[HumanInterventionHandler] = None
    ):
        """初始化"""
        self.executor = base_executor
        self.intervention_handler = intervention_handler

    def set_intervention_handler(self, handler: HumanInterventionHandler):
        """设置介入处理器"""
        self.intervention_handler = handler

    async def execute_with_intervention(
        self,
        tool_name: str,
        arguments: Dict,
        context: Optional[Dict] = None,
    ):
        """执行工具（带介入支持）"""
        from ..core import ExecutionResult

        # 检查是否需要介入
        if self.intervention_handler:
            exec_context = {
                "tool_name": tool_name,
                "arguments": arguments,
                "context": context or {},
            }

            if self.intervention_handler.should_intervene("tool_call", exec_context):
                # 创建介入请求
                request = InterventionRequest(
                    request_id=f"INT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    timestamp=datetime.now(),
                    step_name="tool_call",
                    step_type="tool_call",
                    context=exec_context,
                    proposed_action=f"执行工具 {tool_name} 参数: {arguments}",
                    options=["confirm", "modify", "skip", "abort"],
                    priority="high",
                )

                # 请求介入
                response = await self.intervention_handler.request_intervention(request)

                if response.action == InterventionType.ABORT:
                    return ExecutionResult(
                        success=False,
                        error="执行被中止",
                    )

                if response.action == InterventionType.SKIP:
                    return ExecutionResult(
                        success=True,
                        data={"skipped": True, "reason": response.reason},
                    )

                if response.action == InterventionType.MODIFY:
                    arguments = response.modified_data or arguments

        # 执行工具
        return await self.executor.execute(tool_name, **arguments)


# 便捷函数
def create_intervention_handler(
    timeout: float = 300.0,
    auto_approve: Optional[List[Callable]] = None,
) -> HumanInterventionHandler:
    """创建介入处理器"""
    return HumanInterventionHandler(
        timeout=timeout,
        auto_approve_conditions=auto_approve or [],
    )
