"""LLM Agent - 基于本地 LLM 的智能代理

将 Agent Runtime 与本地 LLM 集成，实现真正的智能代理。
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from core import ExecutionResult, Tool
from llm.client import LLMClient, LLMConfig, Message


@dataclass
class AgentState:
    """Agent 状态"""

    name: str
    is_running: bool = False
    current_step: str = ""
    step_count: int = 0
    max_steps: int = 5
    tools: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


class LLMAgent:
    """LLM 智能代理

    集成 LLM 与工具调用，实现多步推理能力。

    示例:
        config = LLMConfig.from_env()
        agent = LLMAgent(config)

        # 注册工具
        agent.register_tool(my_tool)

        # 运行任务
        result = await agent.run("计算 10 + 20")
        print(result)
    """

    def __init__(
        self,
        llm_client: LLMClient,
        name: str = "LLMAgent",
        max_steps: int = 5,
    ):
        self.llm = llm_client
        self.name = name
        self.max_steps = max_steps

        self.state = AgentState(
            name=name,
            max_steps=max_steps,
        )

        self._tools: Dict[str, Tool] = {}
        self._history: List[Dict] = []

    def register_tool(self, tool: Tool):
        """注册工具"""
        self._tools[tool.name] = tool
        self.state.tools = list(self._tools.keys())

    def list_tools(self) -> List[str]:
        """列出工具"""
        return list(self._tools.keys())

    async def _execute_tool(self, tool_name: str, arguments: Dict) -> ExecutionResult:
        """执行工具"""
        tool = self._tools.get(tool_name)
        if not tool:
            return ExecutionResult(
                success=False,
                error=f"工具不存在: {tool_name}",
            )

        try:
            if asyncio.iscoroutinefunction(tool.func):
                result = await tool.func(**arguments)
            else:
                result = tool.func(**arguments)

            if isinstance(result, dict):
                return ExecutionResult(success=True, data=result)
            else:
                return ExecutionResult(success=True, data={"result": result})

        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    async def run(self, user_input: str) -> str:
        """运行任务

        Args:
            user_input: 用户输入

        Returns:
            最终结果
        """
        self.state.is_running = True
        self.state.step_count = 0

        # 构建提示
        tool_descriptions = "\n".join(f"- {t.name}: {t.description}" for t in self._tools.values())

        system_prompt = f"""你是一个智能代理，可以调用以下工具：

{tool_descriptions}

请根据用户需求，选择合适的工具完成任务。
如果不需要工具，直接回答。
"""

        messages = [
            Message("system", system_prompt),
            Message("user", user_input),
        ]

        # 多步推理
        while self.state.step_count < self.max_steps:
            self.state.step_count += 1
            self.state.current_step = f"step_{self.state.step_count}"

            # 调用 LLM
            response = self.llm.chat(messages=messages)

            if response.finish_reason == "error":
                return f"LLM 错误: {response.content}"

            # 解析响应
            content = response.content

            # 检查是否需要调用工具
            # 简化：假设 LLM 返回 JSON 格式的工具调用
            try:
                # 尝试解析工具调用
                if content.strip().startswith("{"):
                    tool_call = json.loads(content)
                    if "tool" in tool_call:
                        # 执行工具
                        result = await self._execute_tool(
                            tool_call["tool"],
                            tool_call.get("arguments", {}),
                        )

                        if result.success:
                            messages.append(Message("assistant", content))
                            messages.append(Message("tool", json.dumps(result.data)))
                            continue
                        else:
                            messages.append(Message("assistant", content))
                            messages.append(Message("tool", f"Error: {result.error}"))
                            continue

            except json.JSONDecodeError:
                pass

            # 直接回答
            self.state.is_running = False
            return content

        self.state.is_running = False
        return f"达到最大步数限制 ({self.max_steps})"

    def get_history(self) -> List[Dict]:
        """获取历史"""
        return self._history.copy()

    async def close(self):
        """关闭代理"""
        self.state.is_running = False
        self.llm.clear_messages()


async def create_agent(
    name: str = "智能代理",
    llm_config: Optional[LLMConfig] = None,
    max_steps: int = 5,
) -> LLMAgent:
    """创建 LLM Agent

    Args:
        name: Agent 名称
        llm_config: LLM 配置
        max_steps: 最大步数

    Returns:
        LLMAgent 实例
    """
    config = llm_config or LLMConfig.from_env()
    llm = LLMClient(config)

    if not llm.health_check():
        print("⚠️ LLM 服务可能不可用，但仍可创建 Agent")

    agent = LLMAgent(llm, name=name, max_steps=max_steps)
    return agent
