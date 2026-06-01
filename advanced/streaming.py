"""流式输出支持 - 支持 LLM 响应的逐 token 流式传输"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator, Callable, List, Optional


@dataclass
class StreamChunk:
    """流式输出块"""

    content: str  # 当前 chunk 的内容
    is_final: bool = False  # 是否是最后一个 chunk
    model: str = ""
    usage: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=datetime.now().timestamp)


@dataclass
class StreamResponse:
    """完整的流式响应"""

    chunks: List[StreamChunk]
    full_content: str = ""
    model: str = ""
    usage: dict = field(default_factory=dict)
    finish_reason: str = ""

    def __post_init__(self):
        if not self.full_content:
            self.full_content = "".join(c.content for c in self.chunks)


class StreamProcessor:
    """流式处理器

    处理 LLM 的流式响应，支持：
    - 逐 token 输出
    - 回调函数
    - 异步迭代器
    - 响应聚合

    示例:
        processor = StreamProcessor()

        # 方式 1: 使用回调
        def on_chunk(chunk: StreamChunk):
            print(chunk.content, end="", flush=True)

        async for chunk in processor.stream(llm_client, "你好"):
            on_chunk(chunk)

        # 方式 2: 直接获取完整响应
        response = await processor.stream_collect(llm_client, "你好")
        print(response.full_content)
    """

    def __init__(
        self,
        chunk_size: int = 1,  # 每个 chunk 的字符数（1 = 逐字符）
        buffer_timeout: float = 0.05,  # 缓冲区超时（秒）
    ):
        """初始化流式处理器"""
        self.chunk_size = chunk_size
        self.buffer_timeout = buffer_timeout
        self._queue: asyncio.Queue = asyncio.Queue()
        self._is_finished = False

    async def stream(
        self,
        llm_client,
        prompt: str,
        on_chunk: Optional[Callable[[StreamChunk], None]] = None,
    ) -> AsyncIterator[StreamChunk]:
        """流式输出

        Args:
            llm_client: LLM 客户端
            prompt: 用户提示
            on_chunk: 每个 chunk 的回调函数

        Yields:
            StreamChunk 对象
        """
        try:
            # 调用 LLM
            response = llm_client.chat(prompt)
            full_content = response.content

            # 模拟逐字符输出
            for i in range(0, len(full_content), self.chunk_size):
                chunk_content = full_content[i : i + self.chunk_size]
                chunk = StreamChunk(
                    content=chunk_content,
                    is_final=False,  # 内容 chunk 不标记为 final
                    model=response.model,
                )

                # 放入队列
                await self._queue.put(chunk)

                # 触发回调
                if on_chunk:
                    on_chunk(chunk)

                # 小延迟模拟真实流式
                await asyncio.sleep(self.buffer_timeout)

                # 直接 yield（作为 async generator）
                yield chunk

            self._is_finished = True

            # 发送结束信号（空的 final chunk）
            final_chunk = StreamChunk(
                content="",
                is_final=True,
                model=response.model,
                usage=response.usage,
            )
            await self._queue.put(final_chunk)
            yield final_chunk

        except Exception as e:
            error_chunk = StreamChunk(
                content=f"\n[错误: {e}]",
                is_final=True,
            )
            await self._queue.put(error_chunk)
            yield error_chunk

    async def stream_async(
        self,
        llm_client,
        prompt: str,
    ) -> AsyncIterator[StreamChunk]:
        """异步流式输出（无回调）"""
        async for chunk in self.stream(llm_client, prompt):
            yield chunk

    async def stream_collect(
        self,
        llm_client,
        prompt: str,
    ) -> StreamResponse:
        """收集完整流式响应

        Args:
            llm_client: LLM 客户端
            prompt: 用户提示

        Returns:
            StreamResponse 完整响应
        """
        chunks = []
        async for chunk in self.stream(llm_client, prompt):
            chunks.append(chunk)
            if chunk.is_final:
                break

        return StreamResponse(
            chunks=chunks,
            model=chunks[0].model if chunks else "",
            usage=chunks[-1].usage if chunks else {},
        )

    async def get_next_chunk(self, timeout: float = 10.0) -> Optional[StreamChunk]:
        """获取下一个 chunk（手动控制）"""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def is_finished(self) -> bool:
        """检查是否已完成"""
        return self._is_finished

    def reset(self):
        """重置处理器"""
        self._queue = asyncio.Queue()
        self._is_finished = False


class StreamingLLMAgent:
    """支持流式输出的 LLM Agent

    在 LLMAgent 基础上添加流式支持。

    示例:
        agent = StreamingLLMAgent(llm_config=config)

        # 流式执行
        async for chunk in agent.stream_run("你好"):
            print(chunk.content, end="", flush=True)

        # 带回调
        def on_thought(text: str):
            print(f"🤔 {text}")

        def on_answer(text: str):
            print(f"✅ {text}")

        await agent.stream_run(
            "计算 10 + 20",
            on_thought=on_thought,
            on_answer=on_answer,
        )
    """

    def __init__(self, llm_agent, stream_processor: Optional[StreamProcessor] = None):
        """初始化流式 Agent"""
        self.agent = llm_agent
        self.stream_processor = stream_processor or StreamProcessor()

    async def stream_run(
        self,
        user_input: str,
        on_thought: Optional[Callable[[str], None]] = None,
        on_tool_call: Optional[Callable[[str, dict], None]] = None,
        on_tool_result: Optional[Callable[[str, dict], None]] = None,
        on_answer: Optional[Callable[[str], None]] = None,
    ) -> str:
        """流式执行任务

        Args:
            user_input: 用户输入
            on_thought: LLM 思考时的回调
            on_tool_call: 工具调用时的回调
            on_tool_result: 工具结果时的回调
            on_answer: 最终答案时的回调

        Returns:
            完整回答
        """
        print(f"\n📥 用户: {user_input}")

        full_answer = ""

        # 流式调用 LLM
        async for chunk in self.stream_processor.stream(
            self.agent.llm,
            user_input,
        ):
            if chunk.is_final:
                break

            full_answer += chunk.content

            # 触发回调
            if on_thought:
                on_thought(chunk.content)

        # 触发答案回调
        if on_answer:
            on_answer(full_answer)

        print(f"\n📤 代理回答: {full_answer}")
        return full_answer

    async def stream_execute_tool(
        self,
        tool_name: str,
        arguments: dict,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """流式执行工具"""
        if on_progress:
            on_progress(f"🔧 执行工具: {tool_name}")

        result = await self.agent._execute_tool(tool_name, arguments)

        if on_progress:
            status = "✅ 成功" if result.success else "❌ 失败"
            on_progress(f"   {status}: {result.data if result.success else result.error}")

        return result
