"""上下文组装器 - 将检索结果组装成 LLM 可用的 prompt

负责：
- 格式化检索结果
- 构建 RAG prompt
- 处理上下文长度限制
- 添加引用信息
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class RAGContext:
    """RAG 上下文"""

    query: str
    documents: List[Dict[str, Any]]
    prompt: str
    total_tokens: int
    document_count: int


class ContextAssembler:
    """
    上下文组装器

    将检索到的文档组装成 LLM 可用的 prompt
    """

    # 默认 RAG Prompt 模板
    DEFAULT_PROMPT_TEMPLATE = """你是一个有帮助的助手。请根据以下提供的上下文信息回答问题。

如果上下文中没有相关信息，请如实告知，不要编造信息。

=== 上下文 ===
{context}

=== 问题 ===
{question}

=== 回答 ===
"""

    # 带引用的 Prompt 模板
    REFERENCE_PROMPT_TEMPLATE = """你是一个有帮助的助手。请根据以下提供的上下文信息回答问题。

请确保你的回答基于提供的上下文，并在适当的地方引用来源。

如果上下文中没有相关信息，请如实告知，不要编造信息。

=== 上下文 ===
{context}

=== 问题 ===
{question}

=== 回答 ===
"""

    # 客服专用 Prompt 模板
    CUSTOMER_SERVICE_TEMPLATE = """你是一个专业的客服助手。请根据以下知识库信息回答客户问题。

要求：
1. 回答要简洁、准确、友好
2. 如果问题涉及多个方面，请分点回答
3. 如果信息不足，请建议客户联系人工客服

=== 知识库 ===
{context}

=== 客户问题 ===
{question}

=== 客服回答 ===
"""

    def __init__(
        self,
        prompt_template: Optional[str] = None,
        max_context_tokens: int = 4000,
        document_separator: str = "\n\n---\n\n",
        include_metadata: bool = True,
        citation_style: str = "number",  # number, source, none
    ):
        """
        初始化上下文组装器

        Args:
            prompt_template: 自定义 prompt 模板
            max_context_tokens: 最大上下文 token 数
            document_separator: 文档分隔符
            include_metadata: 是否包含元数据
            citation_style: 引用风格（number/source/none）
        """
        self.prompt_template = prompt_template or self.DEFAULT_PROMPT_TEMPLATE
        self.max_context_tokens = max_context_tokens
        self.document_separator = document_separator
        self.include_metadata = include_metadata
        self.citation_style = citation_style

    def assemble(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        question: Optional[str] = None,
    ) -> RAGContext:
        """
        组装 RAG 上下文

        Args:
            query: 原始查询
            documents: 检索到的文档列表
            question: 问题（如果与 query 不同）

        Returns:
            RAGContext 对象
        """
        question = question or query

        # 格式化文档
        formatted_docs = self._format_documents(documents)

        # 构建上下文
        context = self.document_separator.join(formatted_docs)

        # 检查上下文长度
        estimated_tokens = self._estimate_tokens(context)

        if estimated_tokens > self.max_context_tokens:
            # 截断文档
            context = self._truncate_context(context, estimated_tokens, self.max_context_tokens)

        # 构建完整 prompt
        prompt = self.prompt_template.format(context=context, question=question)

        return RAGContext(
            query=query,
            documents=documents,
            prompt=prompt,
            total_tokens=self._estimate_tokens(prompt),
            document_count=len(documents),
        )

    def _format_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """格式化文档列表"""
        formatted = []

        for i, doc in enumerate(documents):
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})

            # 构建文档文本
            doc_text = content

            # 添加引用标记
            if self.citation_style == "number":
                citation = f"[{i + 1}]"
            elif self.citation_style == "source" and metadata.get("source"):
                citation = f"[{metadata['source']}]"
            else:
                citation = ""

            # 添加元数据
            if self.include_metadata:
                meta_text = ""
                if metadata.get("category"):
                    meta_text += f"类别: {metadata['category']}\n"
                if metadata.get("title"):
                    meta_text += f"标题: {metadata['title']}\n"
                if metadata.get("page"):
                    meta_text += f"页码: {metadata['page']}\n"

                if meta_text:
                    doc_text = f"{meta_text}\n\n{doc_text}"

            # 添加引用
            if citation:
                doc_text = f"{citation} {doc_text}"

            formatted.append(doc_text)

        return formatted

    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数量"""
        # 简单估算：4 字符 ≈ 1 token
        return len(text) // 4

    def _truncate_context(self, context: str, current_tokens: int, max_tokens: int) -> str:
        """截断上下文以适应长度限制"""
        # 目标：保留 80% 的 max_tokens 用于上下文
        target_tokens = int(max_tokens * 0.8)

        # 计算需要删除的字符数
        chars_to_remove = (current_tokens - target_tokens) * 4

        # 从中间开始截断（保留开头和结尾）
        if chars_to_remove <= 0:
            return context

        # 保留前 30% 和后 70%
        total_chars = len(context)
        keep_start = int(total_chars * 0.3)
        keep_end = int(total_chars * 0.7)

        start_part = context[:keep_start]
        end_part = context[-keep_end:] if keep_end > 0 else ""

        # 找到合适的截断点（段落边界）
        if "\n\n" in start_part:
            last_break = start_part.rfind("\n\n")
            start_part = start_part[: last_break + 2]

        return f"{start_part}\n\n... [内容被截断] ...\n\n{end_part}"

    def create_system_prompt(
        self, persona: str = "helpful_assistant", additional_instructions: Optional[str] = None
    ) -> str:
        """
        创建系统 prompt

        Args:
            persona: 助手角色（helpful_assistant, customer_service, expert）
            additional_instructions: 额外指令

        Returns:
            系统 prompt 字符串
        """
        personas = {
            "helpful_assistant": "你是一个有帮助、诚实、无害的助手。",
            "customer_service": "你是一个专业、友好、耐心的客服代表。",
            "expert": "你是一个在相关领域有专业知识的专家。",
        }

        system_prompt = personas.get(persona, personas["helpful_assistant"])

        if additional_instructions:
            system_prompt += f"\n\n{additional_instructions}"

        return system_prompt

    def create_few_shot_examples(self, examples: List[Dict[str, str]]) -> str:
        """
        创建少样本示例

        Args:
            examples: 示例列表，每个包含 question 和 answer

        Returns:
            少样本 prompt 字符串
        """
        if not examples:
            return ""

        examples_text = "=== 示例 ===\n\n"

        for i, ex in enumerate(examples):
            examples_text += f"Q{i + 1}: {ex.get('question', '')}\n"
            examples_text += f"A{i + 1}: {ex.get('answer', '')}\n\n"

        return examples_text


class AdvancedContextAssembler(ContextAssembler):
    """
    高级上下文组装器

    支持：
    - 多轮对话历史
    - 动态 prompt 调整
    - 上下文压缩
    """

    def __init__(
        self,
        *args,
        enable_history: bool = True,
        max_history_turns: int = 5,
        enable_compression: bool = False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.enable_history = enable_history
        self.max_history_turns = max_history_turns
        self.enable_compression = enable_compression

    def assemble_with_history(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        history: Optional[List[Dict[str, str]]] = None,
        question: Optional[str] = None,
    ) -> RAGContext:
        """
        带对话历史的上下文组装

        Args:
            query: 当前查询
            documents: 检索文档
            history: 对话历史 [{role: "user", content: "..."}, ...]
            question: 问题

        Returns:
            RAGContext
        """
        question = question or query

        # 组装基础上下文
        base_context = self.assemble(query, documents, question)

        # 添加对话历史
        if self.enable_history and history:
            # 只保留最近的 N 轮
            recent_history = history[-self.max_history_turns * 2 :]

            history_text = "=== 对话历史 ===\n\n"
            for turn in recent_history:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                role_label = "用户" if role == "user" else "助手"
                history_text += f"{role_label}: {content}\n\n"

            # 插入到 prompt 中
            base_context.prompt = history_text + "\n" + base_context.prompt

        # 上下文压缩（如果启用）
        if self.enable_compression:
            base_context.prompt = self._compress_prompt(base_context.prompt)

        return base_context

    def _compress_prompt(self, prompt: str) -> str:
        """压缩 prompt（移除冗余信息）"""
        # 移除多余空白
        prompt = re.sub(r"\n\s*\n", "\n\n", prompt)
        prompt = re.sub(r" +", " ", prompt)

        # 移除重复的标题
        prompt = re.sub(r"(=== .+ ===)\n+\1", r"\1", prompt)

        return prompt

    def assemble_with_refinement(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        llm_client,
        refinement_prompt: Optional[str] = None,
    ) -> RAGContext:
        """
        带精炼的上下文组装

        先用 LLM 精炼检索结果，再组装 prompt

        Args:
            query: 查询
            documents: 检索文档
            llm_client: LLM 客户端
            refinement_prompt: 精炼 prompt

        Returns:
            RAGContext
        """
        # 精炼文档
        refined_docs = self._refine_documents(query, documents, llm_client, refinement_prompt)

        # 组装
        return self.assemble(query, refined_docs, query)

    def _refine_documents(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        llm_client,
        refinement_prompt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """精炼文档（移除不相关信息）"""
        if not refinement_prompt:
            refinement_prompt = """请评估以下文档与查询的相关性，只保留相关文档。

查询: {query}

文档列表:
{documents}

请返回 JSON 格式的保留文档索引列表：
{{"keep_indices": [0, 2, 3]}}
"""

        doc_list = "\n".join(
            [f"[{i}] {doc.get('content', '')[:300]}" for i, doc in enumerate(documents)]
        )

        prompt = refinement_prompt.format(query=query, documents=doc_list)

        try:
            response = llm_client.chat(prompt)
            result = json.loads(response)
            keep_indices = result.get("keep_indices", [])

            return [documents[i] for i in keep_indices if i < len(documents)]

        except Exception:
            # 失败时返回所有文档
            return documents
