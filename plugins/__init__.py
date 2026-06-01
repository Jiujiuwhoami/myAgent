"""插件系统 - 支持热插拔的工具管理

参考 Claude Code 和 Codex 的插件架构设计：
- 工具即插件，独立于核心
- 配置化管理，支持启用/禁用
- 热加载，运行时增减工具
"""

import importlib
import inspect
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional


class PluginStatus(Enum):
    """插件状态"""

    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    LOADING = "loading"


@dataclass
class ToolMeta:
    """工具元数据"""

    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    category: str = "utility"
    tags: List[str] = field(default_factory=list)
    requires_auth: bool = False
    rate_limit: Optional[int] = None  # 每分钟限制


@dataclass
class PluginConfig:
    """插件配置"""

    id: str
    name: str
    version: str
    description: str
    author: str = ""
    homepage: str = ""
    enabled: bool = True
    priority: int = 100  # 加载优先级
    dependencies: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginInfo:
    """插件信息"""

    config: PluginConfig
    status: PluginStatus = PluginStatus.DISABLED
    path: str = ""
    loaded_at: Optional[datetime] = None
    error_message: str = ""
    tools: Dict[str, Any] = field(default_factory=dict)


class ToolPlugin:
    """工具插件基类

    所有插件必须继承此类

    示例:
        class WeatherPlugin(ToolPlugin):
            @property
            def meta(self) -> ToolMeta:
                return ToolMeta(
                    name="weather",
                    description="获取天气信息"
                )

            async def execute(self, city: str) -> dict:
                return {"city": city, "weather": "晴天"}
    """

    @property
    def meta(self) -> ToolMeta:
        """返回工具元数据"""
        raise NotImplementedError

    async def execute(self, **kwargs) -> Any:
        """执行工具"""
        raise NotImplementedError

    def validate_params(self, **kwargs) -> List[str]:
        """验证参数，返回错误列表"""
        return []

    def to_mcp_format(self) -> dict:
        """转换为 MCP 格式"""
        return {
            "name": self.meta.name,
            "description": self.meta.description,
            "input_schema": {"type": "object", "properties": {}},
            "annotations": {
                "version": self.meta.version,
                "author": self.meta.author,
                "category": self.meta.category,
                "tags": self.meta.tags,
            },
        }


class PluginManager:
    """插件管理器

    功能：
    - 发现：自动扫描插件目录
    - 加载：动态导入插件模块
    - 管理：启用/禁用/卸载插件
    - 调用：统一工具调用接口
    """

    def __init__(self, plugin_dir: str = "plugins"):
        self.plugin_dir = Path(plugin_dir)
        self._plugins: Dict[str, PluginInfo] = {}
        self._tools: Dict[str, ToolPlugin] = {}
        self._tool_to_plugin: Dict[str, str] = {}

    def discover(self) -> List[str]:
        """发现所有插件

        扫描插件目录，查找 plugin.json 文件
        """
        discovered = []

        if not self.plugin_dir.exists():
            self.plugin_dir.mkdir(parents=True, exist_ok=True)
            return discovered

        for plugin_path in self.plugin_dir.iterdir():
            if not plugin_path.is_dir():
                continue

            config_file = plugin_path / "plugin.json"
            if not config_file.exists():
                continue

            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config_data = json.load(f)

                config = PluginConfig(
                    id=config_data.get("id", plugin_path.name),
                    name=config_data.get("name", plugin_path.name),
                    version=config_data.get("version", "1.0.0"),
                    description=config_data.get("description", ""),
                    author=config_data.get("author", ""),
                    homepage=config_data.get("homepage", ""),
                    enabled=config_data.get("enabled", True),
                    priority=config_data.get("priority", 100),
                    dependencies=config_data.get("dependencies", []),
                    tools=config_data.get("tools", []),
                    config=config_data.get("config", {}),
                )

                plugin_info = PluginInfo(
                    config=config, path=str(plugin_path), status=PluginStatus.DISABLED
                )

                self._plugins[config.id] = plugin_info
                discovered.append(config.id)

            except Exception as e:
                print(f"[WARN] 加载插件配置失败: {plugin_path.name} - {e}")

        return discovered

    def load(self, plugin_id: str) -> bool:
        """加载插件

        动态导入插件模块，注册工具
        """
        if plugin_id not in self._plugins:
            return False

        plugin_info = self._plugins[plugin_id]

        if plugin_info.status == PluginStatus.ENABLED:
            return True

        plugin_info.status = PluginStatus.LOADING

        try:
            plugin_path = Path(plugin_info.path)
            module_name = f"plugins.{plugin_id}"

            spec = importlib.util.spec_from_file_location(module_name, plugin_path / "__init__.py")

            if not spec or not spec.loader:
                raise ImportError(f"无法加载插件模块: {plugin_id}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                if (
                    inspect.isclass(attr)
                    and issubclass(attr, ToolPlugin)
                    and attr is not ToolPlugin
                ):
                    tool_instance = attr()
                    tool_name = tool_instance.meta.name

                    self._tools[tool_name] = tool_instance
                    self._tool_to_plugin[tool_name] = plugin_id
                    plugin_info.tools[tool_name] = tool_instance

            plugin_info.status = PluginStatus.ENABLED
            plugin_info.loaded_at = datetime.now()

            print(f"[OK] 插件已加载: {plugin_info.config.name} ({len(plugin_info.tools)} 个工具)")
            return True

        except Exception as e:
            plugin_info.status = PluginStatus.ERROR
            plugin_info.error_message = str(e)
            print(f"[ERROR] 插件加载失败: {plugin_id} - {e}")
            return False

    def unload(self, plugin_id: str) -> bool:
        """卸载插件"""
        if plugin_id not in self._plugins:
            return False

        plugin_info = self._plugins[plugin_id]

        for tool_name in plugin_info.tools:
            self._tools.pop(tool_name, None)
            self._tool_to_plugin.pop(tool_name, None)

        plugin_info.tools.clear()
        plugin_info.status = PluginStatus.DISABLED

        print(f"[OK] 插件已卸载: {plugin_info.config.name}")
        return True

    def reload(self, plugin_id: str) -> bool:
        """重载插件"""
        self.unload(plugin_id)
        return self.load(plugin_id)

    def enable(self, plugin_id: str) -> bool:
        """启用插件"""
        return self.load(plugin_id)

    def disable(self, plugin_id: str) -> bool:
        """禁用插件"""
        return self.unload(plugin_id)

    def get_tool(self, name: str) -> Optional[ToolPlugin]:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """列出所有工具"""
        return list(self._tools.keys())

    def list_plugins(self) -> List[PluginInfo]:
        """列出所有插件"""
        return list(self._plugins.values())

    def get_plugin_info(self, plugin_id: str) -> Optional[PluginInfo]:
        """获取插件信息"""
        return self._plugins.get(plugin_id)

    async def call_tool(self, name: str, **kwargs) -> Any:
        """调用工具"""
        tool = self.get_tool(name)

        if not tool:
            raise ValueError(f"工具不存在: {name}")

        errors = tool.validate_params(**kwargs)
        if errors:
            raise ValueError(f"参数验证失败: {errors}")

        return await tool.execute(**kwargs)

    def get_tools_schema(self) -> List[dict]:
        """获取所有工具的 MCP 格式 schema"""
        return [tool.to_mcp_format() for tool in self._tools.values()]

    def to_dict(self) -> dict:
        """导出插件状态"""
        return {
            "plugins": {
                pid: {
                    "name": p.config.name,
                    "status": p.status.value,
                    "tools": list(p.tools.keys()),
                    "loaded_at": p.loaded_at.isoformat() if p.loaded_at else None,
                }
                for pid, p in self._plugins.items()
            },
            "total_tools": len(self._tools),
            "total_plugins": len(self._plugins),
        }


def create_plugin_scaffold(plugin_name: str, output_dir: str = "plugins"):
    """创建插件脚手架

    快速生成插件模板
    """
    plugin_path = Path(output_dir) / plugin_name
    plugin_path.mkdir(parents=True, exist_ok=True)

    plugin_json = {
        "id": plugin_name,
        "name": plugin_name.replace("_", " ").title(),
        "version": "1.0.0",
        "description": f"{plugin_name} 工具插件",
        "author": "",
        "enabled": True,
        "tools": [plugin_name],
    }

    with open(plugin_path / "plugin.json", "w", encoding="utf-8") as f:
        json.dump(plugin_json, f, indent=2, ensure_ascii=False)

    init_py = f'''"""{plugin_name} 插件"""
from myAgent.plugins import ToolPlugin, ToolMeta


class {plugin_name.title().replace("_", "")}Plugin(ToolPlugin):
    """{plugin_name} 工具"""

    @property
    def meta(self) -> ToolMeta:
        return ToolMeta(
            name="{plugin_name}",
            description="{plugin_name} 工具描述",
            category="utility",
            tags=["{plugin_name}"]
        )

    async def execute(self, **kwargs) -> dict:
        """执行工具"""
        return {{"result": "success"}}
'''

    with open(plugin_path / "__init__.py", "w", encoding="utf-8") as f:
        f.write(init_py)

    print(f"[OK] 插件脚手架已创建: {plugin_path}")
    return str(plugin_path)
