"""Agent Runtime - All Components Integration"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

from core import (
    DAG,
    AgentFSM,
    CheckpointManager,
    DAGCheckpointManager,
    DAGNode,
    DAGScheduler,
    Event,
    EventBus,
    EventType,
    ExecutionResult,
    Executor,
    GracefulShutdown,
    MemoryOS,
    Task,
    TaskStatus,
    Tool,
)
from core.tool_registry import ToolRegistry, ToolSource, UnifiedTool
from skills import SkillConfigV2, SkillManager, SkillTriggerEngine


@dataclass
class RuntimeConfig:
    """Runtime 配置"""

    name: str = "My Agent OS"
    max_retries: int = 3
    checkpoint_interval: int = 5
    max_checkpoints: int = 10
    enable_checkpoint: bool = False
    enable_event_bus: bool = True

    # 工具系统配置
    enable_tools: bool = True
    enable_plugins: bool = True
    enable_skills: bool = True

    # Skill 自动触发配置（Codex 兼容）
    enable_auto_skill_trigger: bool = True  # 是否启用自动触发
    auto_trigger_min_confidence: float = 0.5  # 最小置信度阈值
    auto_trigger_max_candidates: int = 3  # 最多返回候选技能数

    # 优雅退出配置
    enable_graceful_shutdown: bool = True  # 是否启用优雅退出
    graceful_shutdown_checkpoint_dir: str = "checkpoints"  # 检查点目录

    # DAG 检查点配置
    enable_dag_checkpoint: bool = True  # 是否启用 DAG 检查点
    dag_checkpoint_dir: str = "checkpoints/dag"  # DAG 检查点目录
    dag_checkpoint_save_interval: int = 3  # DAG 检查点保存间隔（节点数）

    plugin_dir: str = "plugins"
    skill_dir: str = "skills"
    home_dir: Optional[str] = None


class AgentRuntime:
    """
    完整的 Agent Runtime

    功能：
    - 任务管理
    - 工具执行（统一 ToolRegistry：Core + Plugin + Skill）
    - DAG 调度（支持节点级断点恢复）
    - 记忆管理
    - 事件总线
    - 检查点 + 优雅退出
    - **Skill 自动触发**（Codex 兼容）
    """

    def __init__(self, config: Optional[RuntimeConfig] = None):
        self.config = config or RuntimeConfig()
        self.name = self.config.name

        # 核心组件
        self.fsm = AgentFSM()
        self.executor = Executor()
        self.memory = MemoryOS()
        self.event_bus = EventBus() if self.config.enable_event_bus else None

        # 检查点
        self.checkpoint_manager = (
            CheckpointManager(max_checkpoints=self.config.max_checkpoints)
            if self.config.enable_checkpoint
            else None
        )

        # 优雅退出
        self.graceful_shutdown: Optional[GracefulShutdown] = None
        if self.config.enable_graceful_shutdown:
            self.graceful_shutdown = GracefulShutdown(
                checkpoint_callback=self._create_checkpoint_state,
                cleanup_callback=self._cleanup,
                checkpoint_dir=self.config.graceful_shutdown_checkpoint_dir,
            )
            self.graceful_shutdown.setup()
            print("   [OK] Graceful shutdown enabled")

        # DAG 检查点管理器
        self.dag_checkpoint_manager: Optional[DAGCheckpointManager] = None
        if self.config.enable_dag_checkpoint:
            self.dag_checkpoint_manager = DAGCheckpointManager(
                checkpoint_dir=self.config.dag_checkpoint_dir,
                max_checkpoints=self.config.max_checkpoints,
                save_interval=self.config.dag_checkpoint_save_interval,
            )
            print("   [OK] DAG breakpoint recovery enabled")

        # 统一工具系统（整合 Tool + Plugin + Skill）
        self.tool_registry: Optional[ToolRegistry] = None
        if self.config.enable_tools:
            self.tool_registry = ToolRegistry(
                plugin_dir=self.config.plugin_dir,
                skill_dir=self.config.skill_dir,
                home_dir=self.config.home_dir,
            )
            self.tool_registry.discover_all()
            self.tool_registry.sync_from_subsystems()

        # Skill system (Codex compatible)
        self.skill_manager: Optional[SkillManager] = None
        self.skill_trigger_engine: Optional[SkillTriggerEngine] = None
        if self.config.enable_skills:
            self.skill_manager = SkillManager(skill_dir=self.config.skill_dir)
            self.skill_manager.discover()
            if self.config.enable_auto_skill_trigger:
                self.skill_trigger_engine = SkillTriggerEngine()
                print(
                    f"   [OK] Skill auto-trigger enabled (min confidence: {self.config.auto_trigger_min_confidence})"
                )

        # 状态
        self._tasks: Dict[str, Task] = {}
        self._current_dag: Optional[DAG] = None
        self._task_counter = 0

    # =========================================================================
    # 工具管理（统一 ToolRegistry）
    # =========================================================================

    def register_tool(self, tool: Union[Tool, UnifiedTool]) -> Optional[UnifiedTool]:
        """注册工具"""
        if not self.tool_registry:
            return None

        if isinstance(tool, Tool):
            unified = self.tool_registry.register_core_tool(tool)
        else:
            unified = self.tool_registry.register_tool(tool)

        if unified:
            print(f"   [OK] Registered tool: {unified.name} (source: {unified.source.value})")
        return unified

    def list_tools(self, source: Optional[ToolSource] = None) -> List[str]:
        """列出工具名称"""
        if not self.tool_registry:
            return []
        return self.tool_registry.list_tools(source)

    def get_tool(self, name: str) -> Optional[UnifiedTool]:
        """获取工具定义"""
        if not self.tool_registry:
            return None
        return self.tool_registry.get_tool(name)

    def get_tools_schema(self) -> List[dict]:
        """获取所有工具的 MCP 格式 schema（用于 LLM 工具调用）"""
        if not self.tool_registry:
            return []
        return self.tool_registry.get_tools_schema()

    async def execute_tool(self, tool_name: str, **kwargs) -> ExecutionResult:
        """执行工具（统一入口）"""
        if not self.tool_registry:
            return ExecutionResult(success=False, error="工具系统未启用")
        return await self.tool_registry.execute(tool_name, **kwargs)

    # =========================================================================
    # Skill 自动触发（Codex 兼容）
    # =========================================================================

    def match_skill(self, task_description: str) -> Optional[Tuple[str, float]]:
        """根据任务描述自动匹配 Skill

        Args:
            task_description: 任务描述（如 "review this PR for security issues"）

        Returns:
            (skill_name, confidence) 或 None
        """
        if not self.skill_trigger_engine or not self.skill_manager:
            return None

        # 构建技能配置字典
        skill_configs = {}
        for name, info in self.skill_manager._skills.items():
            try:
                config = SkillConfigV2.from_file(self.skill_manager.skill_dir / name / "skill.json")
                skill_configs[name] = config
            except Exception as e:
                print(f"   [WARNING] Failed to load skill config: {name} - {e}")
                continue

        if not skill_configs:
            return None

        # 找到最佳匹配
        best_match = self.skill_trigger_engine.find_best_match(task_description, skill_configs)

        if best_match:
            name, config, confidence = best_match
            if confidence >= self.config.auto_trigger_min_confidence:
                print(f"   [AUTO] Matched skill: {name} (confidence: {confidence:.2f})")
                return name, confidence

        return None

    async def execute_with_auto_trigger(self, task_description: str, **kwargs) -> dict:
        """执行任务，自动触发匹配的 Skill

        Args:
            task_description: 任务描述
            **kwargs: 传递给 Skill 的参数

        Returns:
            执行结果
        """
        if not self.skill_manager:
            return {"success": False, "error": "Skill system not enabled"}

        # 尝试自动匹配 Skill
        match = self.match_skill(task_description)

        if match:
            skill_name, confidence = match

            # 加载技能
            if not self.skill_manager.load(skill_name):
                return {"success": False, "error": f"加载技能失败: {skill_name}"}

            # 执行技能
            result = await self.skill_manager.run_skill(skill_name, **kwargs)
            result["auto_triggered"] = True
            result["trigger_confidence"] = confidence
            result["matched_skill"] = skill_name
            return result

        # No matched skill, return suggestion
        return {
            "success": False,
            "error": f'No matching skill found: "{task_description}"',
            "suggestion": f"Available skills: {self.skill_manager.list_skills()}",
        }

    # =========================================================================
    # 任务管理
    # =========================================================================

    def create_task(self, name: str, input_data: Optional[Dict] = None, **kwargs) -> Task:
        """创建任务"""
        self._task_counter += 1
        task = Task(
            name=name, input_data=input_data or {}, max_retries=self.config.max_retries, **kwargs
        )
        self._tasks[task.id] = task

        if self.event_bus:
            import asyncio

            asyncio.create_task(
                self.event_bus.publish(
                    Event(type=EventType.TASK_CREATED, source=task.id, payload={"name": name})
                )
            )

        print(f"   [OK] Task created: {task.name} (ID: {task.id})")
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)

    # =========================================================================
    # 执行任务
    # =========================================================================

    async def execute(self, task_id: str, tool_name: str, **kwargs) -> Task:
        """执行单个任务"""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        if not self.fsm.transition(task, TaskStatus.RUNNING):
            return task

        if self.event_bus:
            await self.event_bus.publish(
                Event(type=EventType.TASK_STARTED, source=task_id, payload={"name": task.name})
            )

        self.memory.start_task(task_id)

        try:
            result = await self.executor.execute(tool_name, **kwargs)

            if result.success:
                task.output_data = result.data
                self.fsm.transition(task, TaskStatus.COMPLETED)
                print(f"   [OK] Task completed: {task.name}")
            else:
                task.error = result.error
                self.fsm.transition(task, TaskStatus.FAILED)
                print(f"   [ERROR] Task failed: {result.error}")

        except Exception as e:
            task.error = str(e)
            self.fsm.transition(task, TaskStatus.FAILED)
            print(f"   [ERROR] Task exception: {e}")

        self.memory.end_task(task_id, task)

        if self.event_bus:
            if task.status == TaskStatus.COMPLETED:
                await self.event_bus.publish(Event(type=EventType.TASK_COMPLETED, source=task_id))
            else:
                await self.event_bus.publish(
                    Event(type=EventType.TASK_FAILED, source=task_id, payload={"error": task.error})
                )

        return task

    # =========================================================================
    # DAG 支持
    # =========================================================================

    def set_dag(self, dag: DAG):
        """设置 DAG"""
        self._current_dag = dag

    async def execute_dag(self, task_id: str) -> Task:
        """执行 DAG 任务"""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        if not self._current_dag:
            raise ValueError("未设置 DAG")

        self.fsm.transition(task, TaskStatus.RUNNING)
        self.memory.start_task(task_id)

        if self.event_bus:
            await self.event_bus.publish(
                Event(type=EventType.TASK_STARTED, source=task_id, payload={"name": task.name})
            )

        scheduler = DAGScheduler(self._current_dag, max_parallel=4)

        for node_id, node in self._current_dag.nodes.items():

            async def create_executor(tool_name: str, params: Dict):
                async def executor(n: DAGNode) -> Dict:
                    result = await self.executor.execute(tool_name, **params)
                    return result.data if result.success else {"error": result.error}

                return executor

            tool_name = node.metadata.get("tool", "echo")
            executor = await create_executor(tool_name, node.input_data)
            scheduler.register_node_executor(node_id, executor)

        all_success = await scheduler.run()

        if all_success:
            task.output_data = {
                node_id: node.output_data for node_id, node in self._current_dag.nodes.items()
            }
            self.fsm.transition(task, TaskStatus.COMPLETED)
        else:
            task.error = "部分节点执行失败"
            self.fsm.transition(task, TaskStatus.FAILED)

        self.memory.end_task(task_id, task)

        if self.checkpoint_manager and self._task_counter % self.config.checkpoint_interval == 0:
            self._create_checkpoint()

        if self.event_bus:
            if task.status == TaskStatus.COMPLETED:
                await self.event_bus.publish(Event(type=EventType.TASK_COMPLETED, source=task_id))
            else:
                await self.event_bus.publish(Event(type=EventType.TASK_FAILED, source=task_id))

        return task

    # =========================================================================
    # 内部方法
    # =========================================================================

    def _create_checkpoint(self):
        """创建检查点"""
        if not self.checkpoint_manager:
            return
        state = {
            "tasks": {t_id: t.to_dict() for t_id, t in self._tasks.items()},
            "timestamp": datetime.now(),
        }
        self.checkpoint_manager.create_checkpoint(state)

    def _create_checkpoint_state(self) -> dict:
        """创建检查点状态（用于优雅退出）"""
        return {
            "tasks": {t_id: t.to_dict() for t_id, t in self._tasks.items()},
            "memory": self.memory.get_status(),
            "timestamp": datetime.now().isoformat(),
        }

    def _cleanup(self):
        """Cleanup callback (for graceful shutdown)"""
        print("   [CLEANUP] Executing cleanup...")
        if self.event_bus:
            print("   - Closing event bus")

    def check_interrupt(self) -> bool:
        """检查是否被中断"""
        return self.graceful_shutdown.interrupted if self.graceful_shutdown else False

    # =========================================================================
    # 状态
    # =========================================================================

    def print_status(self):
        """Print status report"""
        print("\n" + "=" * 60)
        print(f"[AGENT] {self.name} Status Report")
        print("=" * 60)

        print(f"\n[TASKS] {len(self._tasks)} tasks")
        status_counts = {}
        for task in self._tasks.values():
            status = task.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        for status, count in status_counts.items():
            if count > 0:
                print(f"   {status}: {count}")

        # Tool system status
        if self.tool_registry:
            all_tools = self.tool_registry.list_tools()
            print(f"\n[TOOLS] {len(all_tools)} tools (unified registry)")

            for source in ToolSource:
                tools = self.tool_registry.get_tools_by_source(source)
                enabled = [t for t in tools if t.enabled]
                if enabled:
                    icon = {
                        "core": "[CORE]",
                        "plugin": "[PLUGIN]",
                        "skill": "[SKILL]",
                        "mcp": "[MCP]",
                        "custom": "[CUSTOM]",
                    }
                    print(
                        f"   {icon.get(source.value, '[?]')} {source.value}: {len(enabled)} tools"
                    )
                    for t in enabled[:5]:
                        print(f"      - {t.name}")
                    if len(enabled) > 5:
                        print(f"      ... and {len(enabled)-5} more")
        else:
            print("\n[TOOLS] Tool system not enabled")
            print(f"   Legacy tools: {len(self.executor.list_tools())} tools")
            for tool_name in self.executor.list_tools():
                print(f"   - {tool_name}")

        # Skill system status (Codex compatible)
        if self.skill_manager:
            print(f"\n[SKILLS] {len(self.skill_manager.list_skills())} skills")
            if self.config.enable_auto_skill_trigger:
                print(
                    f"   Auto-trigger: [OK] enabled (min confidence: {self.config.auto_trigger_min_confidence})"
                )
            else:
                print("   Auto-trigger: [DISABLED]")

            for name in self.skill_manager.list_skills():
                info = self.skill_manager.get_skill_info(name)
                status_icon = "[OK]" if info and info.status.value == "enabled" else "[PAUSED]"
                print(f"   {status_icon} {name} v{info.config.meta.version if info else 'unknown'}")
                if info and info.usage_count > 0:
                    print(f"      Usage count: {info.usage_count}")
        else:
            print("\n[SKILLS] Skill system not enabled")

        mem_status = self.memory.get_status()
        print("\n[MEMORY]")
        print(
            f"   Working: {mem_status['working_memory']['size']}/{mem_status['working_memory']['max']}"
        )
        print(f"   Episodic: {mem_status['episodic_memory']['count']}")
        print(f"   Semantic: {mem_status['semantic_memory']['count']}")

        if self.checkpoint_manager:
            cp_status = self.checkpoint_manager.get_status()
            print(f"\n[CHECKPOINT] {cp_status['count']} checkpoints")

        if self.graceful_shutdown:
            print("\n[GRACEFUL SHUTDOWN]")
            print(
                f"   Status: {'[INTERRUPTED]' if self.graceful_shutdown.interrupted else '[RUNNING]'}"
            )
            print(f"   Interrupt count: {self.graceful_shutdown.interrupt_count}")

        if self.dag_checkpoint_manager:
            checkpoints = self.dag_checkpoint_manager.list_checkpoints()
            print("\n[DAG CHECKPOINT]")
            print(f"   Checkpoints: {len(checkpoints)}")
            for cp in checkpoints[:3]:
                print(f"   - {cp['checkpoint_id']} ({cp['completed_nodes']} nodes completed)")

        if self.event_bus:
            event_status = self.event_bus.get_status()
            print(f"\n[EVENTS] {event_status['events_stored']} events stored")

        print("=" * 60)
