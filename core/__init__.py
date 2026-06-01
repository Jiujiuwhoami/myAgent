"""Agent OS 核心模块"""

# 延迟导入，避免循环依赖
__all__ = [
    "TaskStatus",
    "NodeStatus",
    "EventType",
    "Event",
    "Tool",
    "ExecutionResult",
    "Task",
    "AgentFSM",
    "StateChart",
    "StateChartConfig",
    "State",
    "Transition",
    "TransitionType",
    "StateMachineContext",
    "Executor",
    "DAG",
    "DAGNode",
    "DAGScheduler",
    "MemoryOS",
    "GraphMemory",
    "Entity",
    "Relation",
    "EntityType",
    "RelationType",
    "GraphQuery",
    "EventBus",
    "CheckpointManager",
    "GracefulShutdown",
    "InterruptibleTask",
    "ProgressCheckpoint",
    "TaskResumer",
    "DAGCheckpointManager",
    "DAGCheckpoint",
    "NodeCheckpoint",
    "InterruptibleDAGScheduler",
    "CheckpointType",
    "RecoveryStrategy",
    "RecoveryOrchestrator",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "RollbackManager",
    "RetryConfig",
    "Permission",
    "ResourceType",
    "Resource",
    "Policy",
    "Contract",
    "ContractRule",
    "AuditEntry",
    "ContractEngine",
    "PermissionManager",
    "BehavioralContract",
    "SecurityMonitor",
    "ContractEnforcer",
    "AccessDecision",
    "VectorStore",
    "VectorStoreConfig",
    "SemanticMemoryWithVector",
    "ToolRegistry",
    "ToolSource",
    "UnifiedTool",
    "create_tool",
]


def __getattr__(name):
    """延迟导入，避免循环依赖"""
    if name == "TaskStatus":
        from core.types import TaskStatus

        return TaskStatus
    elif name == "NodeStatus":
        from core.types import NodeStatus

        return NodeStatus
    elif name == "EventType":
        from core.types import EventType

        return EventType
    elif name == "Event":
        from core.types import Event

        return Event
    elif name == "Tool":
        from core.types import Tool

        return Tool
    elif name == "ExecutionResult":
        from core.types import ExecutionResult

        return ExecutionResult
    elif name == "Task":
        from core.task import Task

        return Task
    elif name == "AgentFSM":
        from core.state_machine import AgentFSM

        return AgentFSM
    elif name == "MemoryOS":
        from core.memory import MemoryOS

        return MemoryOS
    elif name == "Executor":
        from core.executor import Executor

        return Executor
    elif name == "DAG":
        from core.dag import DAG

        return DAG
    elif name == "DAGNode":
        from core.dag import DAGNode

        return DAGNode
    elif name == "DAGScheduler":
        from core.dag import DAGScheduler

        return DAGScheduler
    elif name == "EventBus":
        from core.event_bus import EventBus

        return EventBus
    elif name == "CheckpointManager":
        from core.checkpoint import CheckpointManager

        return CheckpointManager
    elif name == "StateChart":
        from core.statechart import StateChart

        return StateChart
    elif name == "StateChartConfig":
        from core.statechart import StateChartConfig

        return StateChartConfig
    elif name == "State":
        from core.statechart import State

        return State
    elif name == "Transition":
        from core.statechart import Transition

        return Transition
    elif name == "TransitionType":
        from core.statechart import TransitionType

        return TransitionType
    elif name == "StateMachineContext":
        from core.statechart import StateMachineContext

        return StateMachineContext
    elif name == "GraphMemory":
        from core.graph_memory import GraphMemory

        return GraphMemory
    elif name == "Entity":
        from core.graph_memory import Entity

        return Entity
    elif name == "Relation":
        from core.graph_memory import Relation

        return Relation
    elif name == "EntityType":
        from core.graph_memory import EntityType

        return EntityType
    elif name == "RelationType":
        from core.graph_memory import RelationType

        return RelationType
    elif name == "GraphQuery":
        from core.graph_memory import GraphQuery

        return GraphQuery
    elif name == "GracefulShutdown":
        from core.graceful_shutdown import GracefulShutdown

        return GracefulShutdown
    elif name == "InterruptibleTask":
        from core.graceful_shutdown import InterruptibleTask

        return InterruptibleTask
    elif name == "ProgressCheckpoint":
        from core.graceful_shutdown import ProgressCheckpoint

        return ProgressCheckpoint
    elif name == "TaskResumer":
        from core.graceful_shutdown import TaskResumer

        return TaskResumer
    elif name == "DAGCheckpointManager":
        from core.dag_checkpoint import DAGCheckpointManager

        return DAGCheckpointManager
    elif name == "DAGCheckpoint":
        from core.dag_checkpoint import DAGCheckpoint

        return DAGCheckpoint
    elif name == "NodeCheckpoint":
        from core.dag_checkpoint import NodeCheckpoint

        return NodeCheckpoint
    elif name == "InterruptibleDAGScheduler":
        from core.dag_checkpoint import InterruptibleDAGScheduler

        return InterruptibleDAGScheduler
    elif name == "CheckpointType":
        from core.dag_checkpoint import CheckpointType

        return CheckpointType
    elif name == "RecoveryStrategy":
        from core.recovery import RecoveryStrategy

        return RecoveryStrategy
    elif name == "RecoveryOrchestrator":
        from core.recovery import RecoveryOrchestrator

        return RecoveryOrchestrator
    elif name == "CircuitBreaker":
        from core.recovery import CircuitBreaker

        return CircuitBreaker
    elif name == "CircuitBreakerConfig":
        from core.recovery import CircuitBreakerConfig

        return CircuitBreakerConfig
    elif name == "CircuitState":
        from core.recovery import CircuitState

        return CircuitState
    elif name == "RollbackManager":
        from core.recovery import RollbackManager

        return RollbackManager
    elif name == "RetryConfig":
        from core.recovery import RetryConfig

        return RetryConfig
    elif name == "Permission":
        from core.contracts import Permission

        return Permission
    elif name == "ResourceType":
        from core.contracts import ResourceType

        return ResourceType
    elif name == "Resource":
        from core.contracts import Resource

        return Resource
    elif name == "Policy":
        from core.contracts import Policy

        return Policy
    elif name == "Contract":
        from core.contracts import Contract

        return Contract
    elif name == "ContractRule":
        from core.contracts import ContractRule

        return ContractRule
    elif name == "AuditEntry":
        from core.contracts import AuditEntry

        return AuditEntry
    elif name == "ContractEngine":
        from core.contracts import ContractEngine

        return ContractEngine
    elif name == "PermissionManager":
        from core.contracts import PermissionManager

        return PermissionManager
    elif name == "BehavioralContract":
        from core.contracts import BehavioralContract

        return BehavioralContract
    elif name == "SecurityMonitor":
        from core.contracts import SecurityMonitor

        return SecurityMonitor
    elif name == "ContractEnforcer":
        from core.contracts import ContractEnforcer

        return ContractEnforcer
    elif name == "AccessDecision":
        from core.contracts import AccessDecision

        return AccessDecision
    elif name == "VectorStore":
        from core.vector_store import VectorStore

        return VectorStore
    elif name == "VectorStoreConfig":
        from core.vector_store import VectorStoreConfig

        return VectorStoreConfig
    elif name == "SemanticMemoryWithVector":
        from core.vector_store import SemanticMemoryWithVector

        return SemanticMemoryWithVector
    elif name == "ToolRegistry":
        from core.tool_registry import ToolRegistry

        return ToolRegistry
    elif name == "ToolSource":
        from core.tool_registry import ToolSource

        return ToolSource
    elif name == "UnifiedTool":
        from core.tool_registry import UnifiedTool

        return UnifiedTool
    elif name == "create_tool":
        from core.tool_registry import create_tool

        return create_tool
    raise AttributeError(f"module 'core' has no attribute '{name}'")
