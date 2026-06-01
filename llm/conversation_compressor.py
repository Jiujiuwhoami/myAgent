"""对话历史压缩管理器

实现 Claude Code/Codex 式的对话压缩机制：
- 滑动窗口：保留最近 N 轮对话
- 智能摘要：用 LLM 对旧对话生成摘要
- 关键信息提取：提取重要决策、用户偏好
- Token 预算：根据 context_window 动态调整

使用方式:
    from myAgent.llm import ConversationCompressor

    compressor = ConversationCompressor(llm_client, max_history_tokens=4096)
    compressed = compressor.compress(messages)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class CompressionStrategy(Enum):
    """压缩策略"""

    SLIDING_WINDOW = "sliding_window"  # 滑动窗口（保留最近 N 轮）
    SUMMARIZATION = "summarization"  # LLM 摘要
    KEY_EXTRACTION = "key_extraction"  # 关键信息提取
    HYBRID = "hybrid"  # 混合策略


@dataclass
class ConversationSummary:
    """对话摘要"""

    summary: str
    key_points: List[str]
    user_preferences: Dict[str, Any]
    task_status: Dict[str, Any]
    token_count: int


@dataclass
class CompressedConversation:
    """压缩后的对话"""

    summary: Optional[ConversationSummary]
    recent_messages: List[Dict[str, str]]
    total_tokens: int
    compression_ratio: float


class ConversationCompressor:
    """
    对话历史压缩管理器

    实现 Claude Code/Codex 式的对话压缩机制。
    """

    def __init__(
        self,
        llm_client=None,
        max_history_tokens: int = 4096,
        max_recent_messages: int = 10,
        strategy: CompressionStrategy = CompressionStrategy.HYBRID,
        summary_prompt: Optional[str] = None,
    ):
        """初始化压缩器

        Args:
            llm_client: LLM 客户端（用于智能摘要）
            max_history_tokens: 最大历史 token 数
            max_recent_messages: 保留最近多少轮对话（详细）
            strategy: 压缩策略
            summary_prompt: 自定义摘要 prompt
        """
        self.llm = llm_client
        self.max_history_tokens = max_history_tokens
        self.max_recent_messages = max_recent_messages
        self.strategy = strategy
        self.summary_prompt = summary_prompt or self._default_summary_prompt()

        # 累积摘要（长期记忆）
        self._accumulated_summary: Optional[ConversationSummary] = None
        self._summary_token_count = 0

    def _default_summary_prompt(self) -> str:
        """默认摘要 prompt"""
        return """你是一个对话分析专家。请分析以下对话历史，提取关键信息。

请输出 JSON 格式：
{{
    "summary": "对话总体摘要（100 字以内）",
    "key_points": ["关键点 1", "关键点 2", ...],
    "user_preferences": {{
        "preference_key": "preference_value"
    }},
    "task_status": {{
        "task_name": "status"
    }}
}}

对话历史：
{history}
"""

    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数量（4 字符 ≈ 1 token）"""
        return len(text) // 4

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """格式化消息为文本"""
        lines = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            role_label = "用户" if role == "user" else "助手" if role == "assistant" else "系统"
            lines.append(f"{role_label}: {content}")
        return "\n\n".join(lines)

    def _create_summary(self, messages: List[Dict[str, str]]) -> ConversationSummary:
        """创建对话摘要"""
        if not self.llm:
            # 无 LLM 时返回简单摘要
            return ConversationSummary(
                summary=f"共 {len(messages)} 轮对话",
                key_points=[],
                user_preferences={},
                task_status={},
                token_count=0,
            )

        history_text = self._format_messages(messages)
        prompt = self.summary_prompt.format(history=history_text)

        # 调用 LLM 生成摘要
        try:
            response = self.llm.chat(prompt=prompt)
            import json

            data = json.loads(response.content)

            return ConversationSummary(
                summary=data.get("summary", ""),
                key_points=data.get("key_points", []),
                user_preferences=data.get("user_preferences", {}),
                task_status=data.get("task_status", {}),
                token_count=self._estimate_tokens(response.content),
            )
        except Exception as e:
            print(f"⚠️ 摘要生成失败: {e}")
            return ConversationSummary(
                summary=f"共 {len(messages)} 轮对话（摘要生成失败）",
                key_points=[],
                user_preferences={},
                task_status={},
                token_count=0,
            )

    def compress(
        self,
        messages: List[Dict[str, str]],
    ) -> CompressedConversation:
        """压缩对话历史

        Args:
            messages: 完整对话历史

        Returns:
            压缩后的对话
        """
        if not messages:
            return CompressedConversation(
                summary=None,
                recent_messages=[],
                total_tokens=0,
                compression_ratio=0.0,
            )

        original_tokens = self._estimate_tokens(self._format_messages(messages))

        # 根据策略选择压缩方式
        if self.strategy == CompressionStrategy.SLIDING_WINDOW:
            return self._compress_sliding_window(messages, original_tokens)
        elif self.strategy == CompressionStrategy.SUMMARIZATION:
            return self._compress_summarization(messages, original_tokens)
        elif self.strategy == CompressionStrategy.KEY_EXTRACTION:
            return self._compress_key_extraction(messages, original_tokens)
        else:  # HYBRID
            return self._compress_hybrid(messages, original_tokens)

    def _compress_sliding_window(
        self,
        messages: List[Dict[str, str]],
        original_tokens: int,
    ) -> CompressedConversation:
        """滑动窗口压缩：保留最近 N 轮"""
        recent = messages[-self.max_recent_messages * 2 :]  # 每轮 2 条消息

        recent_tokens = self._estimate_tokens(self._format_messages(recent))

        return CompressedConversation(
            summary=None,
            recent_messages=recent,
            total_tokens=recent_tokens,
            compression_ratio=recent_tokens / original_tokens if original_tokens > 0 else 1.0,
        )

    def _compress_summarization(
        self,
        messages: List[Dict[str, str]],
        original_tokens: int,
    ) -> CompressedConversation:
        """摘要压缩：用 LLM 生成摘要"""
        # 保留最近 2 轮作为上下文
        recent = messages[-4:] if len(messages) > 4 else messages

        # 生成摘要
        summary = self._create_summary(messages[:-4] if len(messages) > 4 else [])

        # 将摘要作为系统消息插入
        if summary:
            system_msg = {
                "role": "system",
                "content": f"【对话摘要】\n{summary.summary}\n\n【关键点】\n"
                + "\n".join(f"- {p}" for p in summary.key_points),
            }
            recent = [system_msg] + recent

        recent_tokens = self._estimate_tokens(self._format_messages(recent))

        return CompressedConversation(
            summary=summary,
            recent_messages=recent,
            total_tokens=recent_tokens,
            compression_ratio=recent_tokens / original_tokens if original_tokens > 0 else 1.0,
        )

    def _compress_key_extraction(
        self,
        messages: List[Dict[str, str]],
        original_tokens: int,
    ) -> CompressedConversation:
        """关键信息提取压缩"""
        summary = self._create_summary(messages)

        # 构建关键信息消息
        key_msg = {
            "role": "system",
            "content": f"""【关键信息】
用户偏好: {summary.user_preferences}
任务状态: {summary.task_status}
关键点: {summary.key_points}
""",
        }

        # 保留最近 N 轮
        recent = [key_msg] + messages[-self.max_recent_messages * 2 :]

        recent_tokens = self._estimate_tokens(self._format_messages(recent))

        return CompressedConversation(
            summary=summary,
            recent_messages=recent,
            total_tokens=recent_tokens,
            compression_ratio=recent_tokens / original_tokens if original_tokens > 0 else 1.0,
        )

    def _compress_hybrid(
        self,
        messages: List[Dict[str, str]],
        original_tokens: int,
    ) -> CompressedConversation:
        """混合压缩：摘要 + 滑动窗口"""
        if len(messages) <= self.max_recent_messages * 2:
            # 对话较短，直接返回
            return CompressedConversation(
                summary=None,
                recent_messages=messages,
                total_tokens=original_tokens,
                compression_ratio=1.0,
            )

        # 对旧对话生成摘要
        old_messages = messages[: -self.max_recent_messages * 2]
        summary = self._create_summary(old_messages)

        # 保留最近 N 轮
        recent = messages[-self.max_recent_messages * 2 :]

        # 将摘要作为系统消息插入
        if summary:
            system_msg = {
                "role": "system",
                "content": f"【历史摘要】{summary.summary}",
            }
            recent = [system_msg] + recent

        recent_tokens = self._estimate_tokens(self._format_messages(recent))

        return CompressedConversation(
            summary=summary,
            recent_messages=recent,
            total_tokens=recent_tokens,
            compression_ratio=recent_tokens / original_tokens if original_tokens > 0 else 1.0,
        )

    def update_summary(self, new_messages: List[Dict[str, str]]):
        """更新累积摘要（用于长期对话）"""
        all_messages = []

        # 添加之前的摘要作为上下文
        if self._accumulated_summary:
            all_messages.append(
                {
                    "role": "system",
                    "content": f"【之前的摘要】{self._accumulated_summary.summary}",
                }
            )

        # 添加新消息
        all_messages.extend(new_messages)

        # 重新生成摘要
        self._accumulated_summary = self._create_summary(all_messages)

    def get_status(self) -> Dict[str, Any]:
        """获取压缩器状态"""
        return {
            "strategy": self.strategy.value,
            "max_history_tokens": self.max_history_tokens,
            "max_recent_messages": self.max_recent_messages,
            "has_summary": self._accumulated_summary is not None,
            "summary_token_count": self._summary_token_count,
        }


# ========== 集成到 LLM Client ==========


def create_compressed_client(
    llm_config=None,
    max_history_tokens: int = 4096,
    strategy: CompressionStrategy = CompressionStrategy.HYBRID,
):
    """创建带对话压缩的 LLM 客户端"""
    from myAgent.llm.client import LLMClient, LLMConfig

    config = llm_config or LLMConfig.from_config_manager()
    client = LLMClient(config)

    compressor = ConversationCompressor(
        llm_client=client,
        max_history_tokens=max_history_tokens,
        strategy=strategy,
    )

    return client, compressor
