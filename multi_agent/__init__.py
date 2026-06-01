"""
Multi-Agent 系统

支持多代理协作模式：
- 代理池管理
- 消息传递
- 任务分发
- 协作策略
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class MessageType(Enum):
    """消息类型"""

    REQUEST = "request"
    RESPONSE = "response"
    BROADCAST = "broadcast"
    NOTIFICATION = "notification"
    DELEGATION = "delegation"


@dataclass
class AgentMessage:
    """代理消息"""

    id: str
    type: MessageType
    sender: str
    receiver: str
    content: Any
    timestamp: datetime = field(default_factory=datetime.now)
    reply_to: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentCapability:
    """代理能力"""

    name: str
    description: str
    input_types: List[str]
    output_type: str


@dataclass
class AgentProfile:
    """代理配置"""

    id: str
    name: str
    role: str
    capabilities: List[AgentCapability]
    max_concurrent_tasks: int = 3


@dataclass
class TaskResult:
    """任务结果"""

    task_id: str
    agent_id: str
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float = 0.0


class AgentRegistry:
    """代理注册表"""

    def __init__(self):
        self._agents: Dict[str, "BaseAgent"] = {}
        self._profiles: Dict[str, AgentProfile] = {}

    def register(self, agent: "BaseAgent"):
        """注册代理"""
        self._agents[agent.id] = agent
        if agent.profile:
            self._profiles[agent.id] = agent.profile
        print(
            f"   📝 代理已注册: {agent.id} ({agent.profile.role if agent.profile else 'unknown'})"
        )

    def unregister(self, agent_id: str):
        """注销代理"""
        self._agents.pop(agent_id, None)
        self._profiles.pop(agent_id, None)

    def get(self, agent_id: str) -> Optional["BaseAgent"]:
        """获取代理"""
        return self._agents.get(agent_id)

    def find_by_role(self, role: str) -> List["BaseAgent"]:
        """根据角色查找代理"""
        return [
            agent for agent in self._agents.values() if agent.profile and agent.profile.role == role
        ]

    def find_by_capability(self, capability: str) -> List["BaseAgent"]:
        """根据能力查找代理"""
        return [agent for agent in self._agents.values() if agent.has_capability(capability)]

    def list_all(self) -> List["BaseAgent"]:
        """列出所有代理"""
        return list(self._agents.values())


class AgentMessageBus:
    """代理消息总线"""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self._messages: List[AgentMessage] = []
        self._subscriptions: Dict[str, Set[str]] = {}
        self._pending_messages: Dict[str, List[AgentMessage]] = {}

    def send(self, message: AgentMessage):
        """发送消息"""
        self._messages.append(message)

        if message.receiver not in self._pending_messages:
            self._pending_messages[message.receiver] = []
        self._pending_messages[message.receiver].append(message)

        print(f"   📨 消息: {message.sender} -> {message.receiver} [{message.type.value}]")

    def broadcast(self, sender: str, content: Any):
        """广播消息"""
        for agent_id in self.registry.list_all():
            if agent_id != sender:
                self.send(
                    AgentMessage(
                        id=str(uuid.uuid4())[:8],
                        type=MessageType.BROADCAST,
                        sender=sender,
                        receiver=agent_id,
                        content=content,
                    )
                )

    def receive(self, agent_id: str) -> List[AgentMessage]:
        """接收消息"""
        messages = self._pending_messages.get(agent_id, [])
        self._pending_messages[agent_id] = []
        return messages

    def subscribe(self, agent_id: str, event_type: str):
        """订阅事件"""
        if event_type not in self._subscriptions:
            self._subscriptions[event_type] = set()
        self._subscriptions[event_type].add(agent_id)


class BaseAgent:
    """基础代理"""

    def __init__(
        self,
        agent_id: str,
        name: str,
        role: str,
        capabilities: Optional[List[AgentCapability]] = None,
    ):
        self.id = agent_id
        self.name = name
        self.profile = AgentProfile(
            id=agent_id, name=name, role=role, capabilities=capabilities or []
        )

        self._inbox: List[AgentMessage] = []
        self._context: Dict[str, Any] = {}
        self._is_running = False

    def has_capability(self, capability: str) -> bool:
        """检查是否有某能力"""
        return any(c.name == capability for c in self.profile.capabilities)

    async def send_message(
        self,
        message_bus: AgentMessageBus,
        receiver: str,
        content: Any,
        msg_type: MessageType = MessageType.REQUEST,
    ) -> AgentMessage:
        """发送消息"""
        message = AgentMessage(
            id=str(uuid.uuid4())[:8],
            type=msg_type,
            sender=self.id,
            receiver=receiver,
            content=content,
        )
        message_bus.send(message)
        return message

    async def receive_messages(self, message_bus: AgentMessageBus):
        """接收消息"""
        self._inbox.extend(message_bus.receive(self.id))

    def process_message(self, message: AgentMessage) -> Any:
        """处理消息（子类实现）"""
        raise NotImplementedError

    async def run(self):
        """运行代理"""
        self._is_running = True
        while self._is_running:
            await asyncio.sleep(0.1)


class OrchestratorAgent(BaseAgent):
    """编排代理 - 负责任务分发和协调"""

    def __init__(
        self, agent_id: str, name: str, registry: AgentRegistry, message_bus: AgentMessageBus
    ):
        super().__init__(agent_id, name, "orchestrator")
        self.registry = registry
        self.message_bus = message_bus
        self._task_queue: List[str] = []

    async def dispatch_task(
        self,
        task: str,
        required_capability: Optional[str] = None,
        preferred_role: Optional[str] = None,
    ) -> TaskResult:
        """分发任务"""
        if required_capability:
            agents = self.registry.find_by_capability(required_capability)
        elif preferred_role:
            agents = self.registry.find_by_role(preferred_role)
        else:
            agents = self.registry.list_all()

        if not agents:
            return TaskResult(
                task_id=task, agent_id="", success=False, result=None, error="没有可用的代理"
            )

        target = agents[0]

        await self.send_message(self.message_bus, target.id, task, MessageType.DELEGATION)

        return TaskResult(
            task_id=task,
            agent_id=target.id,
            success=True,
            result={"status": "dispatched", "target": target.id},
        )

    def process_message(self, message: AgentMessage) -> Any:
        """处理消息"""
        if message.type == MessageType.REQUEST:
            return {"status": "task_received", "task": message.content}


class WorkerAgent(BaseAgent):
    """工作代理 - 执行具体任务"""

    def __init__(self, agent_id: str, name: str, role: str, capabilities: List[AgentCapability]):
        super().__init__(agent_id, name, role, capabilities)
        self._task_handlers: Dict[str, Callable] = {}

    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self._task_handlers[task_type] = handler

    async def execute_task(self, task: Any) -> TaskResult:
        """执行任务"""
        start_time = datetime.now()

        try:
            if isinstance(task, str):
                result = await self.process_task_string(task)
            else:
                result = await self.process_task_dict(task)

            execution_time = (datetime.now() - start_time).total_seconds()

            return TaskResult(
                task_id=str(uuid.uuid4())[:8],
                agent_id=self.id,
                success=True,
                result=result,
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return TaskResult(
                task_id=str(uuid.uuid4())[:8],
                agent_id=self.id,
                success=False,
                result=None,
                error=str(e),
                execution_time=execution_time,
            )

    async def process_task_string(self, task: str) -> Any:
        """处理字符串任务"""
        await asyncio.sleep(0.1)
        return f"Processed by {self.name}: {task}"

    async def process_task_dict(self, task: Dict) -> Any:
        """处理字典任务"""
        task_type = task.get("type", "default")
        handler = self._task_handlers.get(task_type)

        if handler:
            return await handler(task)
        else:
            return {"status": "no_handler", "type": task_type}

    def process_message(self, message: AgentMessage) -> Any:
        """处理消息"""
        return asyncio.run(self.execute_task(message.content))


class SupervisorAgent(BaseAgent):
    """监督代理 - 监控和协调其他代理"""

    def __init__(
        self, agent_id: str, name: str, registry: AgentRegistry, message_bus: AgentMessageBus
    ):
        super().__init__(agent_id, name, "supervisor")
        self.registry = registry
        self.message_bus = message_bus
        self._monitored_agents: Set[str] = set()
        self._health_status: Dict[str, bool] = {}

    def monitor(self, agent_id: str):
        """监控指定代理"""
        self._monitored_agents.add(agent_id)

    async def check_health(self) -> Dict[str, bool]:
        """检查所有被监控代理的健康状态"""
        for agent_id in self._monitored_agents:
            agent = self.registry.get(agent_id)
            if agent:
                self._health_status[agent_id] = agent._is_running
            else:
                self._health_status[agent_id] = False
        return self._health_status

    async def get_status_report(self) -> Dict[str, Any]:
        """获取状态报告"""
        health = await self.check_health()

        return {
            "timestamp": datetime.now().isoformat(),
            "total_agents": len(self.registry.list_all()),
            "monitored_agents": len(self._monitored_agents),
            "healthy_agents": sum(1 for v in health.values() if v),
            "unhealthy_agents": sum(1 for v in health.values() if not v),
            "agent_details": [
                {
                    "id": agent.id,
                    "name": agent.name,
                    "role": agent.profile.role,
                    "healthy": health.get(agent.id, False),
                }
                for agent in self.registry.list_all()
            ],
        }


class MultiAgentSystem:
    """
    Multi-Agent 系统

    整合多个代理，实现协作：
    - 任务分发
    - 消息传递
    - 状态同步
    - 监督协调
    """

    def __init__(self):
        self.registry = AgentRegistry()
        self.message_bus = AgentMessageBus(self.registry)

        self.orchestrator: Optional[OrchestratorAgent] = None
        self.supervisor: Optional[SupervisorAgent] = None

        self._active_tasks: Dict[str, TaskResult] = {}

    def setup(self, orchestrator_name: str = "orchestrator", supervisor_name: str = "supervisor"):
        """设置系统"""
        self.orchestrator = OrchestratorAgent(
            agent_id="orchestrator",
            name=orchestrator_name,
            registry=self.registry,
            message_bus=self.message_bus,
        )

        self.supervisor = SupervisorAgent(
            agent_id="supervisor",
            name=supervisor_name,
            registry=self.registry,
            message_bus=self.message_bus,
        )

        self.registry.register(self.orchestrator)
        self.registry.register(self.supervisor)

        print("   ✅ Multi-Agent 系统已设置")

    def register_worker(
        self, name: str, role: str, capabilities: List[AgentCapability]
    ) -> WorkerAgent:
        """注册工作代理"""
        agent_id = f"worker_{len(self.registry.list_all())}"
        agent = WorkerAgent(agent_id, name, role, capabilities)
        self.registry.register(agent)

        if self.supervisor:
            self.supervisor.monitor(agent_id)

        return agent

    async def submit_task(
        self,
        task: str,
        required_capability: Optional[str] = None,
        preferred_role: Optional[str] = None,
    ) -> TaskResult:
        """提交任务"""
        if not self.orchestrator:
            return TaskResult(
                task_id=task, agent_id="", success=False, result=None, error="系统未初始化"
            )

        result = await self.orchestrator.dispatch_task(task, required_capability, preferred_role)

        self._active_tasks[task] = result
        return result

    async def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "orchestrator": {
                "id": self.orchestrator.id if self.orchestrator else None,
                "name": self.orchestrator.name if self.orchestrator else None,
            },
            "supervisor": {
                "id": self.supervisor.id if self.supervisor else None,
                "name": self.supervisor.name if self.supervisor else None,
            },
            "workers": [
                {
                    "id": agent.id,
                    "name": agent.name,
                    "role": agent.profile.role,
                    "capabilities": [c.name for c in agent.profile.capabilities],
                }
                for agent in self.registry.list_all()
                if agent.profile.role not in ("orchestrator", "supervisor")
            ],
            "active_tasks": len(self._active_tasks),
            "total_messages": len(self.message_bus._messages),
        }
