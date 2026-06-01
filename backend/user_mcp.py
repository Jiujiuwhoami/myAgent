"""用户级 MCP 工具管理器 - 支持多租户隔离

每个用户拥有独立的 MCP 工具注册表，实现完全隔离。
"""

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class UserMCPManager:
    """用户级 MCP 工具管理器

    每个用户拥有独立的 MCP 工具注册表：
        - 用户级工具：仅该用户可见
        - 全局工具：所有用户共享（只读）

    与全局 MCP 注册表分离，实现完全隔离。
    """

    def __init__(
        self,
        user_id: str,
        user_tools_dir: Optional[str] = None,
        global_tools_dir: Optional[str] = None,
    ):
        """初始化用户级 MCP 管理器

        Args:
            user_id: 用户 ID
            user_tools_dir: 用户工具目录（默认 ~/.hermes/mcp_tools/<user_id>）
            global_tools_dir: 全局工具目录（默认 mcp_tools/，作为共享库）
        """
        self.user_id = user_id

        # 用户级工具目录
        if user_tools_dir:
            self.user_tools_dir = Path(user_tools_dir)
        else:
            home = os.environ.get("HOME", Path.home())
            self.user_tools_dir = Path(home) / ".hermes" / "mcp_tools" / user_id

        # 全局工具目录（只读共享库）
        if global_tools_dir:
            self.global_tools_dir = Path(global_tools_dir)
        else:
            self.global_tools_dir = Path("mcp_tools")

        # 确保用户目录存在
        self.user_tools_dir.mkdir(parents=True, exist_ok=True)

        # 工具缓存
        self._user_tools: Dict[str, Any] = {}
        self._global_tools: Dict[str, Any] = {}

        # 工具处理器缓存
        self._user_handlers: Dict[str, Callable] = {}
        self._global_handlers: Dict[str, Callable] = {}

    def _load_tools_from_dir(self, tools_dir: Path) -> Dict[str, Any]:
        """从目录加载工具定义"""
        tools = {}
        if not tools_dir.exists():
            return tools

        for py_file in tools_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                import importlib.util

                spec = importlib.util.spec_from_file_location(f"mcp_tool_{py_file.stem}", py_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # 查找工具对象
                if hasattr(module, "tool"):
                    tool = module.tool
                    tools[tool.name] = {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.input_schema,
                        "source": str(py_file),
                        "scope": "user" if tools_dir == self.user_tools_dir else "global",
                    }
                    self._user_handlers[tool.name] = (
                        tool.handler if tools_dir == self.user_tools_dir else None
                    )
            except Exception as e:
                print(f"⚠️ 加载工具失败 {py_file.name}: {e}")

        return tools

    def discover(self) -> List[str]:
        """发现所有可用工具（用户级 + 全局共享）"""
        # 加载用户级工具（从目录）
        loaded_user_tools = self._load_tools_from_dir(self.user_tools_dir)

        # 保留手动注册的工具（不覆盖）
        for name, tool_info in self._user_tools.items():
            if tool_info.get("scope") == "user" and name not in loaded_user_tools:
                loaded_user_tools[name] = tool_info

        self._user_tools = loaded_user_tools

        # 加载全局工具
        self._global_tools = self._load_tools_from_dir(self.global_tools_dir)

        # 返回所有工具（用户级优先）
        all_tools = list(self._user_tools.keys())
        for name in self._global_tools:
            if name not in all_tools:
                all_tools.append(name)

        return all_tools

    def get_tool(self, name: str) -> Optional[Dict]:
        """获取工具信息（优先返回用户级工具）"""
        if name in self._user_tools:
            return self._user_tools[name]
        if name in self._global_tools:
            return self._global_tools[name]
        return None

    def get_tool_handler(self, name: str) -> Optional[Callable]:
        """获取工具处理器（优先返回用户级处理器）"""
        if name in self._user_handlers:
            return self._user_handlers[name]
        if name in self._global_handlers:
            return self._global_handlers[name]
        return None

    def is_user_tool(self, name: str) -> bool:
        """判断工具是否为用户级"""
        return name in self._user_tools

    def get_user_tools(self) -> List[str]:
        """获取用户级工具列表"""
        return list(self._user_tools.keys())

    def get_global_tools(self) -> List[str]:
        """获取全局共享工具列表"""
        return list(self._global_tools.keys())

    def register_tool(
        self, name: str, description: str, handler: Callable, input_schema: Optional[Dict] = None
    ) -> bool:
        """注册用户级工具"""
        from myAgent.mcp import MCPTool

        tool = MCPTool(
            name=name,
            description=description,
            handler=handler,
            input_schema=input_schema or {"type": "object", "properties": {}},
        )

        self._user_tools[name] = {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "scope": "user",
        }
        self._user_handlers[name] = tool.handler

        return True

    def unregister_tool(self, name: str) -> bool:
        """注销用户级工具（不影响全局共享）"""
        if name not in self._user_tools:
            return False

        self._user_tools.pop(name, None)
        self._user_handlers.pop(name, None)
        return True

    def list_tools(self, scope: Optional[str] = None) -> List[Dict]:
        """列出工具（可选按作用域过滤）"""
        if scope == "user":
            return list(self._user_tools.values())
        elif scope == "global":
            return list(self._global_tools.values())
        else:
            all_tools = list(self._user_tools.values())
            for name, info in self._global_tools.items():
                if name not in self._user_tools:
                    all_tools.append(info)
            return all_tools

    def call_tool(self, name: str, **kwargs) -> Any:
        """调用工具"""
        handler = self.get_tool_handler(name)
        if not handler:
            raise ValueError(f"工具不存在: {name}")

        import asyncio

        if asyncio.iscoroutinefunction(handler):
            return asyncio.run(handler(**kwargs))
        return handler(**kwargs)

    def get_status(self) -> Dict:
        """获取状态信息"""
        return {
            "user_id": self.user_id,
            "user_tools_dir": str(self.user_tools_dir),
            "global_tools_dir": str(self.global_tools_dir),
            "user_tools_count": len(self._user_tools),
            "global_tools_count": len(self._global_tools),
            "user_tools": list(self._user_tools.keys()),
            "global_tools": list(self._global_tools.keys()),
        }


# ========== 全局用户级 MCP 管理器注册 ==========

_user_mcp_managers: Dict[str, UserMCPManager] = {}


def get_user_mcp_manager(user_id: str) -> UserMCPManager:
    """获取或创建用户级 MCP 管理器"""
    if user_id not in _user_mcp_managers:
        _user_mcp_managers[user_id] = UserMCPManager(user_id)
    return _user_mcp_managers[user_id]


def remove_user_mcp_manager(user_id: str):
    """移除用户级 MCP 管理器"""
    _user_mcp_managers.pop(user_id, None)
