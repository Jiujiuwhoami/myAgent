"""
MCP (Model Context Protocol) 实现

MCP 是一种标准化的工具调用协议，用于：
- 工具发现和注册
- 统一的工具调用接口
- 类型安全的参数传递
- 工具执行结果标准化
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional


class MCPErrorCode(Enum):
    """MCP 错误码"""

    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    TOOL_NOT_FOUND = -32001
    TOOL_EXECUTION_FAILED = -32002
    PERMISSION_DENIED = -32003
    RATE_LIMITED = -32004


@dataclass
class MCPRequest:
    """MCP 请求"""

    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: str = ""
    params: Optional[Dict[str, Any]] = None


@dataclass
class MCPResponse:
    """MCP 响应"""

    jsonrpc: str = "2.0"
    id: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


@dataclass
class ToolDefinition:
    """工具定义"""

    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None
    annotations: Optional[Dict[str, Any]] = None


@dataclass
class ToolExecution:
    """工具执行记录"""

    execution_id: str
    tool_name: str
    parameters: Dict[str, Any]
    start_time: datetime
    end_time: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None


class MCPError(Exception):
    """MCP 错误"""

    def __init__(self, code: MCPErrorCode, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"[{code.name}] {message}")


class MCPTool:
    """MCP 工具"""

    def __init__(
        self,
        name: str,
        description: str,
        handler: Callable[..., Awaitable[Any]],
        input_schema: Optional[Dict[str, Any]] = None,
        annotations: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.description = description
        self.handler = handler
        self.input_schema = input_schema or {"type": "object", "properties": {}}
        self.annotations = annotations or {}

    def to_definition(self) -> ToolDefinition:
        """转换为工具定义"""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
            annotations=self.annotations,
        )


class MCPProtocol:
    """
    MCP 协议处理器

    实现标准的 JSON-RPC 2.0 风格接口：
    - tools/list - 列出可用工具
    - tools/call - 调用工具
    - tools/schema - 获取工具模式
    """

    def __init__(self):
        self._tools: Dict[str, MCPTool] = {}
        self._execution_history: List[ToolExecution] = []

    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable[..., Awaitable[Any]],
        input_schema: Optional[Dict[str, Any]] = None,
        annotations: Optional[Dict[str, Any]] = None,
    ):
        """注册工具"""
        tool = MCPTool(
            name=name,
            description=description,
            handler=handler,
            input_schema=input_schema,
            annotations=annotations,
        )
        self._tools[name] = tool
        print(f"   ✅ MCP 工具已注册: {name}")

    def unregister_tool(self, name: str):
        """注销工具"""
        self._tools.pop(name, None)

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        """列出所有工具定义"""
        return [tool.to_definition() for tool in self._tools.values()]

    async def call_tool(self, name: str, parameters: Dict[str, Any]) -> Any:
        """调用工具"""
        tool = self._tools.get(name)
        if not tool:
            raise MCPError(MCPErrorCode.TOOL_NOT_FOUND, f"工具不存在: {name}")

        execution = ToolExecution(
            execution_id=str(uuid.uuid4())[:8],
            tool_name=name,
            parameters=parameters,
            start_time=datetime.now(),
        )

        try:
            self._validate_parameters(tool, parameters)

            result = await tool.handler(**parameters)

            execution.result = result
            execution.end_time = datetime.now()

            print(f"   ✅ MCP 工具执行成功: {name}")
            return result

        except Exception as e:
            execution.error = str(e)
            execution.end_time = datetime.now()
            print(f"   ❌ MCP 工具执行失败: {name} - {e}")
            raise MCPError(
                MCPErrorCode.TOOL_EXECUTION_FAILED,
                f"工具执行失败: {e}",
                {"tool": name, "parameters": parameters},
            )

        finally:
            self._execution_history.append(execution)

    def _validate_parameters(self, tool: MCPTool, parameters: Dict[str, Any]):
        """验证参数"""
        required = tool.input_schema.get("required", [])
        for param in required:
            if param not in parameters:
                raise MCPError(MCPErrorCode.INVALID_PARAMS, f"缺少必需参数: {param}")

    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """处理 MCP 请求"""
        try:
            if request.method == "tools/list":
                result = {"tools": [self._tool_to_dict(t) for t in self.list_tools()]}
                return MCPResponse(id=request.id, result=result)

            elif request.method == "tools/call":
                if not request.params:
                    raise MCPError(MCPErrorCode.INVALID_PARAMS, "缺少参数")

                name = request.params.get("name")
                arguments = request.params.get("arguments", {})

                result = await self.call_tool(name, arguments)
                return MCPResponse(
                    id=request.id,
                    result={
                        "name": name,
                        "result": result,
                        "execution_id": (
                            self._execution_history[-1].execution_id
                            if self._execution_history
                            else None
                        ),
                    },
                )

            elif request.method == "tools/schema":
                if not request.params or "name" not in request.params:
                    raise MCPError(MCPErrorCode.INVALID_PARAMS, "缺少工具名称")

                tool = self.get_tool(request.params["name"])
                if not tool:
                    raise MCPError(
                        MCPErrorCode.TOOL_NOT_FOUND, f"工具不存在: {request.params['name']}"
                    )

                return MCPResponse(
                    id=request.id,
                    result={
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.input_schema,
                        "annotations": tool.annotations,
                    },
                )

            else:
                raise MCPError(MCPErrorCode.METHOD_NOT_FOUND, f"方法不存在: {request.method}")

        except MCPError as e:
            return MCPResponse(
                id=request.id, error={"code": e.code.value, "message": e.message, "data": e.data}
            )

    def _tool_to_dict(self, tool: ToolDefinition) -> Dict[str, Any]:
        """工具定义转字典"""
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "annotations": tool.annotations,
        }

    def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取执行历史"""
        history = self._execution_history[-limit:]
        return [
            {
                "execution_id": e.execution_id,
                "tool_name": e.tool_name,
                "parameters": e.parameters,
                "start_time": e.start_time.isoformat(),
                "end_time": e.end_time.isoformat() if e.end_time else None,
                "duration": (e.end_time - e.start_time).total_seconds() if e.end_time else None,
                "success": e.error is None,
                "error": e.error,
            }
            for e in history
        ]

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "registered_tools": len(self._tools),
            "execution_count": len(self._execution_history),
            "recent_executions": self.get_execution_history(10),
        }


class MCPServer:
    """
    MCP 服务器

    基于 MCP 协议提供工具服务。
    """

    def __init__(self, name: str = "MyAgent MCP Server"):
        self.name = name
        self.protocol = MCPProtocol()
        self._is_running = False

    def register(self, tool: MCPTool):
        """注册工具"""
        self.protocol.register_tool(
            name=tool.name,
            description=tool.description,
            handler=tool.handler,
            input_schema=tool.input_schema,
            annotations=tool.annotations,
        )

    async def handle(self, request: Dict) -> Dict:
        """处理请求"""
        mcp_request = MCPRequest(
            jsonrpc=request.get("jsonrpc", "2.0"),
            id=request.get("id"),
            method=request.get("method", ""),
            params=request.get("params"),
        )

        response = await self.protocol.handle_request(mcp_request)

        return {
            "jsonrpc": response.jsonrpc,
            "id": response.id,
            "result": response.result,
            "error": response.error,
        }

    def start(self):
        """启动服务器"""
        self._is_running = True
        print(f"   ✅ MCP 服务器已启动: {self.name}")

    def stop(self):
        """停止服务器"""
        self._is_running = False
        print(f"   🛑 MCP 服务器已停止: {self.name}")

    def get_tools(self) -> List[Dict[str, Any]]:
        """获取工具列表"""
        return self.protocol.list_tools()

    async def call(self, tool_name: str, **kwargs) -> Any:
        """直接调用工具"""
        return await self.protocol.call_tool(tool_name, kwargs)


class MCPClient:
    """
    MCP 客户端

    连接 MCP 服务器并调用工具。
    """

    def __init__(self, server_url: str):
        self.server_url = server_url
        self._tools: Dict[str, ToolDefinition] = {}
        self._is_connected = False

    async def connect(self):
        """连接 MCP 服务器"""
        # TODO: 实现实际连接逻辑
        self._is_connected = True
        await self.discover_tools()

    async def disconnect(self):
        """断开连接"""
        self._is_connected = False

    async def discover_tools(self):
        """发现可用工具"""
        # TODO: 实现实际工具发现逻辑
        # 对于本地工具，可以从注册表获取
        from . import get_registered_tools

        self._tools = {t.name: t.to_definition() for t in get_registered_tools()}

    async def list_tools(self) -> List[ToolDefinition]:
        """列出工具"""
        if not self._is_connected:
            await self.connect()
        return [ToolDefinition(**t) for t in self._tools.values()]

    async def call_tool(self, name: str, **kwargs) -> Any:
        """调用工具"""
        if not self._is_connected:
            await self.connect()

        if name not in self._tools:
            raise MCPError(MCPErrorCode.TOOL_NOT_FOUND, f"工具不存在: {name}")

        # TODO: 实现实际调用逻辑
        # 对于本地工具，直接调用 handler
        from . import get_tool_handler

        handler = get_tool_handler(name)
        if handler:
            return await handler(**kwargs)
        raise MCPError(MCPErrorCode.TOOL_NOT_FOUND, f"工具处理器未找到: {name}")


# ========== 工具注册管理 ==========

_registered_tools: Dict[str, MCPTool] = {}


def register_tool(tool: MCPTool):
    """注册全局 MCP 工具"""
    _registered_tools[tool.name] = tool


def unregister_tool(name: str) -> bool:
    """注销全局 MCP 工具"""
    if name in _registered_tools:
        del _registered_tools[name]
        return True
    return False


def get_registered_tools() -> List[MCPTool]:
    """获取所有已注册的全局工具"""
    return list(_registered_tools.values())


def get_tool_handler(name: str) -> Optional[Callable]:
    """获取工具处理器"""
    tool = _registered_tools.get(name)
    return tool.handler if tool else None


def list_tools() -> List[Dict]:
    """列出所有已注册的工具定义"""
    return [t.to_definition().__dict__ for t in _registered_tools.values()]


class MCPManager:
    """MCP 工具管理器（CLI 使用）"""

    def list_tools(self) -> List[Dict]:
        """列出所有工具"""
        return list_tools()

    def get_tool(self, name: str) -> Optional[Dict]:
        """获取单个工具"""
        tools = list_tools()
        for t in tools:
            if t.get("name") == name:
                return t
        return None


def create_mcp_tool(
    name: str,
    description: str,
    parameters: Dict[str, Any],
    annotations: Optional[Dict[str, Any]] = None,
):
    """装饰器：创建并注册 MCP 工具"""

    def decorator(func: Callable) -> MCPTool:
        input_schema = {
            "type": "object",
            "properties": parameters,
            "required": [k for k, v in parameters.items() if v.get("required", False)],
        }

        tool = MCPTool(
            name=name,
            description=description,
            handler=func,
            input_schema=input_schema,
            annotations=annotations,
        )

        # 自动注册到全局
        register_tool(tool)

        return tool

    return decorator
