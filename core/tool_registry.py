"""统一工具注册表 - 整合 Tool/Plugin/Skill/MCP

设计目标：
1. 单一来源：所有工具通过统一接口发现和调用
2. 分层架构：Tool(基础) → Plugin(工具集) → Skill(工作流) → MCP(协议)
3. 自动发现：扫描各模块目录自动注册
4. MCP 兼容：所有工具自动生成 MCP 格式 schema

架构：
┌─────────────────────────────────────────────────────────────┐
│                    ToolRegistry (统一入口)                    │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐  │
│  │ CoreTool │  │  Plugin   │  │  Skill   │  │   MCP    │  │
│  │ (手动注册)│  │ (自动扫描)│  │(自动扫描)│  │(外部连接)│  │
│  └──────────┘  └───────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Executor (执行器)    │
              │  - 同步/异步执行       │
              │  - 参数验证            │
              │  - 错误处理            │
              └───────────────────────┘
"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.types import ExecutionResult

# 导入各子系统
from core.types import Tool as CoreTool
from plugins import PluginManager
from skills import SkillManager


class ToolSource(Enum):
    """工具来源"""

    CORE = "core"  # 手动注册的核心工具
    PLUGIN = "plugin"  # 插件系统
    SKILL = "skill"  # 技能系统
    MCP = "mcp"  # MCP 外部工具
    CUSTOM = "custom"  # 自定义工具


@dataclass
class UnifiedTool:
    """统一工具定义（MCP 格式）"""

    name: str
    description: str
    input_schema: Dict[str, Any]
    source: ToolSource
    version: str = "1.0.0"
    author: str = ""
    category: str = "utility"
    tags: List[str] = field(default_factory=list)
    enabled: bool = True
    handler: Optional[Callable] = None  # 执行处理器
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_mcp_format(self) -> dict:
        """转换为 MCP 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "annotations": {
                "version": self.version,
                "author": self.author,
                "category": self.category,
                "tags": self.tags,
                "source": self.source.value,
            },
        }

    def to_dict(self) -> dict:
        """转换为普通字典"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "source": self.source.value,
            "version": self.version,
            "enabled": self.enabled,
            "category": self.category,
        }


class ToolRegistry:
    """统一工具注册表

    功能：
    1. 注册：手动注册核心工具
    2. 发现：自动扫描 Plugin/Skill 目录
    3. 管理：启用/禁用/列出工具
    4. 执行：统一调用接口
    5. Schema：生成 MCP 格式工具列表
    """

    def __init__(
        self, plugin_dir: str = "plugins", skill_dir: str = "skills", home_dir: Optional[str] = None
    ):
        self.plugin_dir = Path(plugin_dir)
        self.skill_dir = Path(skill_dir)
        self.home_dir = Path(home_dir or os.path.expanduser("~/.hermes"))

        # 工具存储
        self._tools: Dict[str, UnifiedTool] = {}

        # 子系统管理器
        self.plugin_manager: Optional[PluginManager] = None
        self.skill_manager: Optional[SkillManager] = None

        # 执行历史
        self._execution_history: List[Dict] = []

        # 初始化子系统
        self._init_subsystems()

    def _init_subsystems(self):
        """初始化 Plugin 和 Skill 子系统"""
        # 初始化 PluginManager
        if self.plugin_dir.exists():
            self.plugin_manager = PluginManager(str(self.plugin_dir))
            self.plugin_manager.discover()

        # Initialize SkillManager
        if self.skill_dir.exists():
            self.skill_manager = SkillManager(skill_dir=str(self.skill_dir))
            self.skill_manager.discover()

    # =========================================================================
    # 注册
    # =========================================================================

    def register_core_tool(self, tool: CoreTool) -> UnifiedTool:
        """注册核心工具（手动）"""
        unified = UnifiedTool(
            name=tool.name,
            description=tool.description or "",
            input_schema=tool.parameters or {"type": "object", "properties": {}},
            source=ToolSource.CORE,
            handler=tool.func,
        )
        self._tools[tool.name] = unified
        return unified

    def register_tool(self, tool: UnifiedTool) -> UnifiedTool:
        """注册统一工具"""
        self._tools[tool.name] = tool
        return tool

    def unregister_tool(self, name: str) -> bool:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    # =========================================================================
    # 发现
    # =========================================================================

    def discover_all(self) -> Dict[str, int]:
        """发现所有工具（Plugin + Skill）"""
        counts = {"plugin": 0, "skill": 0}

        # 发现 Plugin
        if self.plugin_manager:
            self.plugin_manager.discover()
            for plugin_id in self.plugin_manager.list_tools():
                # Plugin 工具已经在 PluginManager 中，稍后统一加载
                counts["plugin"] += 1

            # 加载已启用的插件
            for plugin_id in self.plugin_manager.list_tools():
                plugin_info = self.plugin_manager.get_plugin_info(plugin_id)
                if plugin_info and plugin_info.config.enabled:
                    self.plugin_manager.load(plugin_id)

        # 发现 Skill
        if self.skill_manager:
            self.skill_manager.discover()
            for skill_name in self.skill_manager.list_skills():
                info = self.skill_manager.get_skill_info(skill_name)
                if info and info.config.enabled:
                    self.skill_manager.load(skill_name)
                    counts["skill"] += 1

        return counts

    def sync_from_subsystems(self) -> int:
        """从 Plugin 和 Skill 子系统同步工具到统一注册表"""
        synced = 0

        # 从 PluginManager 同步
        if self.plugin_manager:
            for tool_name in self.plugin_manager.list_tools():
                if tool_name not in self._tools:
                    plugin = self.plugin_manager.get_tool(tool_name)
                    if plugin:
                        unified = UnifiedTool(
                            name=tool_name,
                            description=plugin.meta.description,
                            input_schema={
                                "type": "object",
                                "properties": {},
                                "required": [],
                            },  # Plugin 需要自己实现 schema
                            source=ToolSource.PLUGIN,
                            version=plugin.meta.version,
                            category=plugin.meta.category,
                            tags=plugin.meta.tags,
                            handler=self._create_plugin_handler(tool_name),
                            metadata={"plugin_id": tool_name},
                        )
                        self._tools[tool_name] = unified
                        synced += 1

        # 从 SkillManager 同步
        if self.skill_manager:
            for skill_name in self.skill_manager.list_skills():
                if skill_name not in self._tools:
                    skill = self.skill_manager.get_skill(skill_name)
                    if skill:
                        unified = UnifiedTool(
                            name=skill_name,
                            description=skill.description,
                            input_schema=skill.get_param_schema(),
                            source=ToolSource.SKILL,
                            version=skill.config.meta.version,
                            author=skill.config.meta.author,
                            category=skill.config.meta.category.value,
                            tags=skill.config.meta.tags,
                            handler=self._create_skill_handler(skill_name),
                            metadata={
                                "version": skill.config.meta.version,
                                "category": skill.config.meta.category.value,
                            },
                        )
                        self._tools[skill_name] = unified
                        synced += 1

        return synced

    def _create_plugin_handler(self, plugin_name: str) -> Callable:
        """创建 Plugin 调用处理器"""

        async def handler(**kwargs) -> Any:
            if not self.plugin_manager:
                raise ValueError("Plugin 系统未初始化")
            return await self.plugin_manager.call_tool(plugin_name, **kwargs)

        return handler

    def _create_skill_handler(self, skill_name: str) -> Callable:
        """创建 Skill 调用处理器"""

        async def handler(**kwargs) -> Any:
            if not self.skill_manager:
                raise ValueError("Skill 系统未初始化")
            result = await self.skill_manager.run_skill(skill_name, **kwargs)
            if result.get("success"):
                return result.get("data")
            else:
                raise Exception(result.get("error", "技能执行失败"))

        return handler

    # =========================================================================
    # 管理
    # =========================================================================

    def list_tools(self, source: Optional[ToolSource] = None) -> List[str]:
        """列出所有工具名称"""
        if source:
            return [n for n, t in self._tools.items() if t.source == source and t.enabled]
        return [n for n, t in self._tools.items() if t.enabled]

    def get_tool(self, name: str) -> Optional[UnifiedTool]:
        """获取工具"""
        return self._tools.get(name)

    def enable_tool(self, name: str) -> bool:
        """启用工具"""
        if name in self._tools:
            self._tools[name].enabled = True
            return True
        return False

    def disable_tool(self, name: str) -> bool:
        """禁用工具"""
        if name in self._tools:
            self._tools[name].enabled = False
            return True
        return False

    def get_tools_by_source(self, source: ToolSource) -> List[UnifiedTool]:
        """按来源获取工具"""
        return [t for t in self._tools.values() if t.source == source]

    # =========================================================================
    # 执行
    # =========================================================================

    async def execute(self, tool_name: str, **kwargs) -> ExecutionResult:
        """统一工具执行入口"""
        tool = self._tools.get(tool_name)
        if not tool:
            return ExecutionResult(success=False, error=f"工具不存在: {tool_name}")

        if not tool.enabled:
            return ExecutionResult(success=False, error=f"工具已禁用: {tool_name}")

        if not tool.handler:
            return ExecutionResult(success=False, error=f"工具无执行处理器: {tool_name}")

        # 记录执行开始
        exec_id = f"{tool_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        try:
            result = await tool.handler(**kwargs)

            # 记录执行历史
            self._execution_history.append(
                {
                    "id": exec_id,
                    "tool": tool_name,
                    "source": tool.source.value,
                    "parameters": kwargs,
                    "success": True,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            return ExecutionResult(success=True, data=result)

        except Exception as e:
            self._execution_history.append(
                {
                    "id": exec_id,
                    "tool": tool_name,
                    "source": tool.source.value,
                    "parameters": kwargs,
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            )

            return ExecutionResult(success=False, error=str(e))

    async def execute_by_mcp_request(self, name: str, arguments: Dict) -> Any:
        """通过 MCP 格式请求执行工具"""
        result = await self.execute(name, **arguments)
        if result.success:
            return result.data
        else:
            raise Exception(result.error)

    # =========================================================================
    # Schema
    # =========================================================================

    def get_tools_schema(self) -> List[dict]:
        """获取所有工具的 MCP 格式 schema（用于 LLM 工具调用）"""
        return [t.to_mcp_format() for t in self._tools.values() if t.enabled]

    def get_execution_history(self, limit: int = 100) -> List[Dict]:
        """获取执行历史"""
        return self._execution_history[-limit:]

    # =========================================================================
    # 状态
    # =========================================================================

    def to_dict(self) -> dict:
        """导出完整状态"""
        return {
            "tools": {name: tool.to_dict() for name, tool in self._tools.items()},
            "summary": {
                "total": len(self._tools),
                "enabled": len(self.list_tools()),
                "by_source": {
                    source.value: len(self.get_tools_by_source(source)) for source in ToolSource
                },
            },
            "subsystems": {
                "plugin": {
                    "enabled": self.plugin_manager is not None,
                    "tools": self.plugin_manager.list_tools() if self.plugin_manager else [],
                },
                "skill": {
                    "enabled": self.skill_manager is not None,
                    "tools": self.skill_manager.list_skills() if self.skill_manager else [],
                },
            },
        }

    def print_status(self):
        """打印状态报告"""
        print("\n" + "=" * 60)
        print("🔧 统一工具注册表状态")
        print("=" * 60)

        if not self._tools:
            print("  未注册任何工具")
            print(f"  Plugin 目录: {self.plugin_dir}")
            print(f"  Skill 目录: {self.skill_dir}")
            return

        # 按来源分组
        by_source: Dict[ToolSource, List[UnifiedTool]] = {}
        for tool in self._tools.values():
            if tool.source not in by_source:
                by_source[tool.source] = []
            by_source[tool.source].append(tool)

        for source, tools in sorted(by_source.items()):
            icon = {"core": "🎯", "plugin": "🧩", "skill": "📚", "mcp": "🔌", "custom": "🔧"}
            print(f"\n{icon.get(source.value, '⚙️')} {source.value.upper()} ({len(tools)} 个)")
            for tool in sorted(tools, key=lambda t: t.name):
                status = "✅" if tool.enabled else "⏸️"
                print(f"   {status} {tool.name}")
                print(f"      {tool.description[:50]}...")

        print(f"\n📊 总计: {len(self._tools)} 个工具")
        print("=" * 60)


# =========================================================================
# 便捷函数
# =========================================================================


def create_tool(
    name: str,
    func: Callable,
    description: str = "",
    parameters: Optional[Dict] = None,
    source: ToolSource = ToolSource.CUSTOM,
) -> UnifiedTool:
    """便捷创建工具"""
    return UnifiedTool(
        name=name,
        description=description,
        input_schema=parameters or {"type": "object", "properties": {}},
        source=source,
        handler=func,
    )
