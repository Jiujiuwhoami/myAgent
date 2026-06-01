"""RAG（检索增强生成）模块

完整的 RAG 流水线，支持：
- 多格式文档加载（PDF/Word/Markdown/HTML）
- 多种分块策略（字符/段落/语义/Token）
- 多种嵌入模型（本地/OpenAI/HuggingFace/Cohere）
- 多种重排序策略（Cross-Encoder/LLM/Cohere）
- 灵活的上下文组装
- 完整的 RAG Pipeline

使用示例：

```python
from myAgent.rag import RAGPipeline, RAGConfig

# 创建流水线
config = RAGConfig(
    chunk_size=500,
    retrieval_top_k=5,
    enable_reranking=True,
)
pipeline = RAGPipeline(config=config)

# 构建索引
pipeline.build_index_from_files(["./knowledge/base.pdf"])

# 检索生成
result = await pipeline.generate("如何重置密码？")
print(result.answer)
```
"""

from rag.assembler import (
    AdvancedContextAssembler,
    ContextAssembler,
    RAGContext,
)
from rag.embedding import (
    CohereEmbeddingClient,
    EmbeddingClient,
    EmbeddingResult,
    HuggingFaceEmbeddingClient,
    create_embedding_client,
)
from rag.loader import (
    Document,
    DocumentLoader,
    FAQLoader,
)
from rag.pipeline import (
    HybridRAGPipeline,
    RAGConfig,
    RAGPipeline,
    RAGResult,
    create_rag_pipeline,
)
from rag.reranker import (
    BGEReranker,
    LLMReranker,
    RankedDocument,
    Reranker,
    RerankResult,
    create_reranker,
)
from rag.splitter import (
    RecursiveCharacterTextSplitter,
    SemanticTextSplitter,
    SentenceSplitter,
    TextChunk,
    TextSplitter,
    TokenTextSplitter,
)

__all__ = [
    # Loader
    "DocumentLoader",
    "Document",
    "FAQLoader",
    # Splitter
    "TextSplitter",
    "TextChunk",
    "RecursiveCharacterTextSplitter",
    "SemanticTextSplitter",
    "TokenTextSplitter",
    "SentenceSplitter",
    # Embedding
    "EmbeddingClient",
    "EmbeddingResult",
    "HuggingFaceEmbeddingClient",
    "CohereEmbeddingClient",
    "create_embedding_client",
    # Reranker
    "Reranker",
    "RankedDocument",
    "RerankResult",
    "LLMReranker",
    "BGEReranker",
    "create_reranker",
    # Assembler
    "ContextAssembler",
    "RAGContext",
    "AdvancedContextAssembler",
    # Pipeline
    "RAGConfig",
    "RAGResult",
    "RAGPipeline",
    "HybridRAGPipeline",
    "create_rag_pipeline",
]
