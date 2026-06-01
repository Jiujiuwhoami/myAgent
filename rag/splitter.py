"""文本分块器 - 将长文档分割成适合检索的块

支持多种分块策略：
- 固定字符数分块
- 按段落分块
- 按句子分块
- 语义分块（基于标题/结构）
- 递归分块（保持上下文）
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TextChunk:
    """文本块"""

    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    index: int = 0
    total_chunks: int = 0

    def __post_init__(self):
        if not self.metadata:
            self.metadata = {}
        self.metadata["chunk_index"] = self.index
        self.metadata["total_chunks"] = self.total_chunks


class TextSplitter:
    """
    通用文本分块器

    提供多种分块策略，适用于不同的文档类型和检索需求
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: Optional[List[str]] = None,
    ):
        """
        初始化分块器

        Args:
            chunk_size: 每个块的最大字符数
            chunk_overlap: 块之间的重叠字符数
            separators: 分隔符列表（按优先级尝试）
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # 默认分隔符（按优先级）
        self.separators = separators or [
            "\n\n",  # 段落
            "\n",  # 行
            "。",  # 中文句号
            "!",  # 英文感叹号
            "?",  # 问号
            ".",  # 英文句号
            "，",  # 中文逗号
            ",",  # 英文逗号
            " ",  # 空格
            "",  # 字符级（最后尝试）
        ]

    def split_text(self, text: str) -> List[TextChunk]:
        """
        分割文本

        Args:
            text: 要分割的文本

        Returns:
            文本块列表
        """
        if not text:
            return []

        # 如果文本本身小于 chunk_size，直接返回
        if len(text) <= self.chunk_size:
            return [TextChunk(content=text, index=0, total_chunks=1)]

        chunks = []
        self._split_recursive(text, self.separators, chunks)

        # 添加元数据
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            chunk.index = i
            chunk.total_chunks = total

        return chunks

    def _split_recursive(self, text: str, separators: List[str], chunks: List[TextChunk]):
        """递归分割"""
        # 如果文本足够小，直接添加
        if len(text) <= self.chunk_size:
            chunks.append(TextChunk(content=text))
            return

        # 尝试当前分隔符
        separator = separators[0]
        remaining_separators = separators[1:]

        # 找到所有分割点
        splits = self._split_text_by_separator(text, separator)

        # 如果只有一个块（无法分割），尝试下一个分隔符
        if len(splits) == 1 and remaining_separators:
            self._split_recursive(text, remaining_separators, chunks)
            return

        # 合并小块
        good_splits = []
        for split in splits:
            if len(split) < self.chunk_size:
                good_splits.append(split)
            else:
                # 大块递归分割
                if remaining_separators:
                    self._split_recursive(split, remaining_separators, chunks)
                else:
                    # 强制按字符分割
                    self._split_by_character(split, chunks)

        # 合并小块
        if good_splits:
            self._merge_splits(good_splits, chunks)

    def _split_text_by_separator(self, text: str, separator: str) -> List[str]:
        """按分隔符分割文本"""
        if not separator:
            # 字符级分割
            return [text[i : i + 1] for i in range(len(text))]

        splits = text.split(separator)
        # 保留分隔符
        result = []
        for i, split in enumerate(splits):
            if split:
                result.append(split)
            if i < len(splits) - 1 and split:
                result[-1] += separator

        return [s for s in result if s]

    def _merge_splits(self, splits: List[str], chunks: List[TextChunk]):
        """合并小块到合适大小"""
        current_chunk = []
        current_length = 0

        for split in splits:
            split_length = len(split)

            # 检查加上这个 split 是否超过 chunk_size
            if current_length + split_length + self.chunk_overlap > self.chunk_size:
                if current_chunk:
                    chunk_text = "".join(current_chunk)
                    chunks.append(TextChunk(content=chunk_text))
                    current_chunk = [split]
                    current_length = split_length
                else:
                    # split 本身太大，递归分割
                    self._split_by_character(split, chunks)
            else:
                current_chunk.append(split)
                current_length += split_length

        # 添加最后一个块
        if current_chunk:
            chunk_text = "".join(current_chunk)
            chunks.append(TextChunk(content=chunk_text))

    def _split_by_character(self, text: str, chunks: List[TextChunk]):
        """按字符强制分割"""
        for i in range(0, len(text), self.chunk_size):
            chunk_text = text[i : i + self.chunk_size]
            chunks.append(TextChunk(content=chunk_text))


class RecursiveCharacterTextSplitter(TextSplitter):
    """
    递归字符分块器

    保持文档结构（段落、句子）的完整性
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        length_function: callable = len,
    ):
        super().__init__(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n",  # 段落
                "\n",  # 行
                "。",  # 中文句子
                "!",
                "?",
                ".",  # 英文句子
                "，",  # 中文短语
                ",",
                " ",
                "",
            ],
        )
        self.length_function = length_function


class SemanticTextSplitter(TextSplitter):
    """
    语义分块器

    基于文档结构（标题、章节）进行分块
    """

    # Markdown 标题模式
    MARKDOWN_HEADER = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    # HTML 标题模式
    HTML_HEADER = re.compile(r"<h([1-6])>(.+?)</h[1-6]>", re.DOTALL)

    def split_by_headers(self, text: str) -> List[TextChunk]:
        """
        按标题分割

        保持每个章节的完整性
        """
        chunks = []

        # 查找所有标题
        headers = []
        for match in self.MARKDOWN_HEADER.finditer(text):
            level = len(match.group(1))
            title = match.group(2).strip()
            start = match.start()
            headers.append((start, level, title))

        if not headers:
            # 没有标题，使用普通分块
            return self.split_text(text)

        # 按标题分割
        for i, (start, level, title) in enumerate(headers):
            end = headers[i + 1][0] if i + 1 < len(headers) else len(text)
            section = text[start:end].strip()

            chunk = TextChunk(
                content=section,
                metadata={
                    "header_level": level,
                    "header_title": title,
                    "section_start": start,
                    "section_end": end,
                },
            )
            chunks.append(chunk)

        return chunks

    def split_text(self, text: str) -> List[TextChunk]:
        """
        智能分块：先按标题，再按大小
        """
        # 先按标题分割
        header_chunks = self.split_by_headers(text)

        # 如果每个 chunk 都小于 chunk_size，直接返回
        if all(len(c.content) <= self.chunk_size for c in header_chunks):
            total = len(header_chunks)
            for i, chunk in enumerate(header_chunks):
                chunk.index = i
                chunk.total_chunks = total
            return header_chunks

        # 否则对大 chunk 进一步分割
        final_chunks = []
        for chunk in header_chunks:
            if len(chunk.content) <= self.chunk_size:
                final_chunks.append(chunk)
            else:
                # 使用普通分块
                sub_chunks = super().split_text(chunk.content)
                # 合并元数据
                for sub in sub_chunks:
                    sub.metadata.update(chunk.metadata)
                final_chunks.extend(sub_chunks)

        # 更新索引
        total = len(final_chunks)
        for i, chunk in enumerate(final_chunks):
            chunk.index = i
            chunk.total_chunks = total

        return final_chunks


class TokenTextSplitter(TextSplitter):
    """
    Token 分块器

    基于 Token 数量分块（适用于 LLM 上下文限制）
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base",
    ):
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.encoding_name = encoding_name
        self._tokenizer = None

    def _get_tokenizer(self):
        """获取 tokenizer"""
        if self._tokenizer is None:
            try:
                import tiktoken

                self._tokenizer = tiktoken.get_encoding(self.encoding_name)
            except ImportError:
                # 降级：按字符估算（4 字符 ≈ 1 token）
                self._tokenizer = None
        return self._tokenizer

    def _count_tokens(self, text: str) -> int:
        """计算 token 数量"""
        tokenizer = self._get_tokenizer()
        if tokenizer:
            return len(tokenizer.encode(text))
        else:
            # 估算：4 字符 ≈ 1 token
            return len(text) // 4

    def split_text(self, text: str) -> List[TextChunk]:
        """按 Token 分块"""
        if not text:
            return []

        tokenizer = self._get_tokenizer()

        if tokenizer:
            tokens = tokenizer.encode(text)
            chunks = []

            for i in range(0, len(tokens), self.chunk_size - self.chunk_overlap):
                chunk_tokens = tokens[i : i + self.chunk_size]
                chunk_text = tokenizer.decode(chunk_tokens)
                chunks.append(TextChunk(content=chunk_text))

            # 更新索引
            total = len(chunks)
            for i, chunk in enumerate(chunks):
                chunk.index = i
                chunk.total_chunks = total

            return chunks
        else:
            # 降级：按字符分块
            return super().split_text(text)


class SentenceSplitter(TextSplitter):
    """
    句子分块器

    按句子分割，保持语义完整性
    """

    # 中文句子分隔符
    CN_SENTENCE_PATTERN = re.compile(r"[。！？\.!?\n]+\s*")

    def split_text(self, text: str) -> List[TextChunk]:
        """按句子分割"""
        sentences = self.CN_SENTENCE_PATTERN.split(text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return []

        # 合并句子到合适大小
        chunks = []
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            if current_length + sentence_length > self.chunk_size:
                if current_chunk:
                    chunks.append(TextChunk(content=" ".join(current_chunk)))
                    current_chunk = [sentence]
                    current_length = sentence_length
                else:
                    # 单句太长，按字符分割
                    for i in range(0, len(sentence), self.chunk_size):
                        chunks.append(TextChunk(content=sentence[i : i + self.chunk_size]))
            else:
                current_chunk.append(sentence)
                current_length += sentence_length

        if current_chunk:
            chunks.append(TextChunk(content=" ".join(current_chunk)))

        # 更新索引
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            chunk.index = i
            chunk.total_chunks = total

        return chunks
