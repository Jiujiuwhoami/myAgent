"""
执行器 - 负责工具的注册和执行
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Optional

from myAgent.core.types import ExecutionResult, Tool


class Executor:
    """
    工具执行器

    功能：
    - 注册工具
    - 执行工具（同步或异步）
    - 记录执行历史
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._execution_history: list[dict] = []

    def register_tool(self, tool: Tool):
        """注册工具"""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """列出所有工具"""
        return list(self._tools.keys())

    async def execute(self, tool_name: str, **kwargs) -> ExecutionResult:
        """
        执行工具

        返回 ExecutionResult
        """
        start_time = time.time()

        if tool_name not in self._tools:
            return ExecutionResult(
                success=False,
                error=f"工具不存在: {tool_name}",
                execution_time=time.time() - start_time,
            )

        tool = self._tools[tool_name]

        try:
            # 判断函数是否是 async
            if asyncio.iscoroutinefunction(tool.func):
                result = await tool.func(**kwargs)
            else:
                result = tool.func(**kwargs)

            exec_time = time.time() - start_time

            # 记录历史
            self._execution_history.append(
                {
                    "tool_name": tool_name,
                    "timestamp": datetime.now(),
                    "success": True,
                    "execution_time": exec_time,
                }
            )

            return ExecutionResult(success=True, data=result, execution_time=exec_time)

        except Exception as e:
            exec_time = time.time() - start_time

            self._execution_history.append(
                {
                    "tool_name": tool_name,
                    "timestamp": datetime.now(),
                    "success": False,
                    "error": str(e),
                    "execution_time": exec_time,
                }
            )

            return ExecutionResult(success=False, error=str(e), execution_time=exec_time)

    def get_execution_history(self) -> list[dict]:
        """获取执行历史"""
        return self._execution_history.copy()

    def clear_history(self):
        """清空历史"""
        self._execution_history = []
