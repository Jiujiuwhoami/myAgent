"""RAG Pipeline - 完整的检索增强生成流水线

完整的 RAG 流程：
1. 文档加载（Document Loading）
2. 文本分块（Text Splitting）
3. 嵌入生成（Embedding）
4. 向量存储（Vector Storage）
5. 检索（Retrieval）
6. 重排序（Reranking）
7. 上下文组装（Context Assembly）
8. 生成（Generation）

支持：
- 离线索引构建
- 在线检索生成
- 流式输出
- 多源检索
- 混合检索（向量 + 关键词）
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional


@dataclass
class RAGConfig:
    """RAG 配置"""

    chunk_size: int = 500
    chunk_overlap: int = 50
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: Optional[int] = None
    retrieval_top_k: int = 10
    rerank_top_k: int = 5
    max_context_tokens: int = 4000
    enable_reranking: bool = True
    enable_history: bool = True
    max_history_turns: int = 5


@dataclass
class RAGResult:
    """RAG 结果"""

    query: str
    answer: str
    documents: List[Dict[str, Any]]
    reranked_documents: List[Dict[str, Any]]
    context_tokens: int
    total_tokens: int
    latency_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class RAGPipeline:
    """
    完整的 RAG 流水线

    整合所有 RAG 组件，提供统一的接口
    """

    def __init__(
        self,
        config: Optional[RAGConfig] = None,
        vector_store=None,
        embedding_client=None,
        reranker=None,
        assembler=None,
        llm_client=None,
    ):
        """
        初始化 RAG 流水线

        Args:
            config: RAG 配置
            vector_store: 向量存储（VectorStore）
            embedding_client: 嵌入客户端
            reranker: 重排序器
            assembler: 上下文组装器
            llm_client: LLM 客户端
        """
        self.config = config or RAGConfig()

        self.vector_store = vector_store
        self.embedding_client = embedding_client
        self.reranker = reranker
        self.assembler = assembler
        self.llm = llm_client

        self._index_built = False
        self._stats = {
            "documents_indexed": 0,
            "queries_processed": 0,
            "total_tokens_used": 0,
        }

    def build_index(
        self,
        documents: List[Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        构建索引

        Args:
            documents: 文档列表（Document 或 str）
            metadata: 批量元数据

        Returns:
            索引统计信息
        """
        if not self.vector_store or not self.embedding_client:
            raise ValueError("需要配置 vector_store 和 embedding_client")

        chunks = []
        chunk_metadata = []

        for i, doc in enumerate(documents):
            # 获取文档内容
            if hasattr(doc, "content"):
                content = doc.content
                doc_metadata = doc.metadata or {}
            else:
                content = str(doc)
                doc_metadata = {}

            # 添加批量元数据
            if metadata:
                doc_metadata.update(metadata)

            doc_metadata["source_index"] = i
            doc_metadata["source_type"] = type(doc).__name__

            # 分块
            from myAgent.rag.splitter import RecursiveCharacterTextSplitter

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
            )

            doc_chunks = splitter.split_text(content)

            for chunk in doc_chunks:
                chunk.metadata.update(doc_metadata)
                chunks.append(chunk.content)
                chunk_metadata.append(chunk.metadata)

        # 生成嵌入
        print(f"   📝 生成 {len(chunks)} 个块的嵌入...")
        embeddings = self.embedding_client.embed_documents(chunks)

        # 添加到向量存储
        print(f"   💾 索引 {len(chunks)} 个块到向量存储...")
        for i, (chunk, emb, meta) in enumerate(zip(chunks, embeddings, chunk_metadata)):
            self.vector_store.add(
                text=chunk,
                document_id=f"chunk_{i}",
                metadata=meta,
                embedding=emb.embedding,
            )

        self._index_built = True
        self._stats["documents_indexed"] = len(documents)

        return {
            "total_chunks": len(chunks),
            "total_documents": len(documents),
            "chunk_size": self.config.chunk_size,
            "chunk_overlap": self.config.chunk_overlap,
        }

    def build_index_from_files(
        self,
        file_paths: List[str],
        recursive: bool = False,
    ) -> Dict[str, Any]:
        """
        从文件构建索引

        Args:
            file_paths: 文件路径列表
            recursive: 是否递归目录

        Returns:
            索引统计
        """
        from myAgent.rag.loader import DocumentLoader

        loader = DocumentLoader()
        all_documents = []

        for path in file_paths:
            if recursive and path.endswith("/"):
                docs = loader.load_directory(path, recursive=True)
            else:
                docs = loader.load(path)
            all_documents.extend(docs)

        return self.build_index(all_documents)

    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
        enable_reranking: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        检索文档

        Args:
            query: 查询文本
            top_k: 检索数量
            filter_metadata: 元数据过滤
            enable_reranking: 是否启用重排序

        Returns:
            检索结果
        """
        if not self.vector_store:
            raise ValueError("需要配置 vector_store")

        top_k = top_k or self.config.retrieval_top_k
        enable_reranking = enable_reranking or self.config.enable_reranking

        start_time = datetime.now()

        # 1. 生成查询嵌入
        query_embedding = self.embedding_client.embed_query(query)

        # 2. 向量检索
        results = self.vector_store.search(
            query=query,
            n_results=top_k * 2,  # 检索更多用于重排序
            query_embedding=query_embedding,
            filter_metadata=filter_metadata,
        )

        # 3. 重排序（如果启用）
        reranked = []
        if enable_reranking and self.reranker and results:
            rerank_result = self.reranker.rerank(
                query=query,
                documents=results,
                top_k=top_k,
            )
            reranked = rerank_result.documents
        else:
            reranked = [
                {
                    "content": r["text"],
                    "score": 1.0 - r.get("distance", 0),
                    "metadata": r.get("metadata", {}),
                }
                for r in results[:top_k]
            ]

        latency = (datetime.now() - start_time).total_seconds() * 1000

        return {
            "query": query,
            "retrieved_documents": results,
            "reranked_documents": reranked,
            "retrieval_latency_ms": latency,
            "count": len(reranked),
        }

    async def generate(
        self,
        query: str,
        top_k: Optional[int] = None,
        enable_reranking: Optional[bool] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> RAGResult:
        """
        完整的 RAG 生成

        Args:
            query: 查询/问题
            top_k: 检索数量
            enable_reranking: 是否启用重排序
            history: 对话历史

        Returns:
            RAGResult
        """
        if not self.llm:
            raise ValueError("需要配置 llm_client")

        start_time = datetime.now()

        # 1. 检索
        retrieval_result = await self.retrieve(
            query=query,
            top_k=top_k,
            enable_reranking=enable_reranking,
        )

        documents = retrieval_result["retrieved_documents"]
        reranked = retrieval_result["reranked_documents"]

        # 2. 组装上下文
        if not self.assembler:
            from myAgent.rag.assembler import ContextAssembler

            self.assembler = ContextAssembler(
                max_context_tokens=self.config.max_context_tokens,
            )

        context = self.assembler.assemble_with_history(
            query=query,
            documents=reranked,
            history=history,
        )

        # 3. 生成回答
        response = await self.llm.chat(context.prompt)

        latency = (datetime.now() - start_time).total_seconds() * 1000

        # 更新统计
        self._stats["queries_processed"] += 1
        self._stats["total_tokens_used"] += context.total_tokens

        return RAGResult(
            query=query,
            answer=response,
            documents=documents,
            reranked_documents=reranked,
            context_tokens=context.total_tokens,
            total_tokens=context.total_tokens,
            latency_ms=latency,
            metadata={
                "document_count": len(reranked),
                "retrieval_latency_ms": retrieval_result["retrieval_latency_ms"],
            },
        )

    async def stream_generate(
        self,
        query: str,
        top_k: Optional[int] = None,
        enable_reranking: Optional[bool] = None,
        history: Optional[List[Dict[str, str]]] = None,
        on_chunk: Optional[callable] = None,
    ) -> AsyncIterator[str]:
        """
        流式 RAG 生成

        Args:
            query: 查询
            top_k: 检索数量
            enable_reranking: 是否启用重排序
            history: 对话历史
            on_chunk: 每个 chunk 的回调

        Yields:
            生成的文本块
        """
        if not self.llm:
            raise ValueError("需要配置 llm_client")

        # 1. 检索
        retrieval_result = await self.retrieve(
            query=query,
            top_k=top_k,
            enable_reranking=enable_reranking,
        )

        reranked = retrieval_result["reranked_documents"]

        # 2. 组装上下文
        if not self.assembler:
            from myAgent.rag.assembler import ContextAssembler

            self.assembler = ContextAssembler(
                max_context_tokens=self.config.max_context_tokens,
            )

        context = self.assembler.assemble_with_history(
            query=query,
            documents=reranked,
            history=history,
        )

        # 3. 流式生成
        if hasattr(self.llm, "stream_chat"):
            async for chunk in self.llm.stream_chat(context.prompt):
                yield chunk
                if on_chunk:
                    on_chunk(chunk)
        else:
            # 降级：非流式
            response = await self.llm.chat(context.prompt)
            yield response

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        store_stats = self.vector_store.get_status() if self.vector_store else {}
        embedding_stats = self.embedding_client.get_model_info() if self.embedding_client else {}

        return {
            "index": {
                "built": self._index_built,
                "documents": self._stats["documents_indexed"],
                **store_stats,
            },
            "query": {
                "processed": self._stats["queries_processed"],
                "total_tokens": self._stats["total_tokens_used"],
            },
            "embedding": embedding_stats,
            "config": {
                "chunk_size": self.config.chunk_size,
                "retrieval_top_k": self.config.retrieval_top_k,
                "enable_reranking": self.config.enable_reranking,
            },
        }

    def clear_index(self):
        """清空索引"""
        if self.vector_store:
            self.vector_store.reset()
        self._index_built = False
        self._stats["documents_indexed"] = 0


class HybridRAGPipeline(RAGPipeline):
    """
    混合 RAG 流水线

    结合向量检索和关键词检索
    """

    def __init__(self, *args, keyword_weight: float = 0.3, **kwargs):
        super().__init__(*args, **kwargs)
        self.keyword_weight = keyword_weight

    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
        enable_reranking: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """混合检索"""
        if not self.vector_store:
            raise ValueError("需要配置 vector_store")

        top_k = top_k or self.config.retrieval_top_k

        # 1. 向量检索
        query_embedding = self.embedding_client.embed_query(query)
        vector_results = self.vector_store.search(
            query=query,
            n_results=top_k * 2,
            query_embedding=query_embedding,
            filter_metadata=filter_metadata,
        )

        # 2. 关键词检索（使用向量存储的 fallback）
        keyword_results = self.vector_store.search(
            query=query,
            n_results=top_k * 2,
            filter_metadata=filter_metadata,
        )

        # 3. 融合结果
        fused = self._fuse_results(
            vector_results,
            keyword_results,
            self.keyword_weight,
        )

        # 4. 重排序
        reranked = []
        if self.config.enable_reranking and self.reranker and fused:
            rerank_result = self.reranker.rerank(
                query=query,
                documents=fused,
                top_k=top_k,
            )
            reranked = rerank_result.documents
        else:
            reranked = fused[:top_k]

        return {
            "query": query,
            "retrieved_documents": fused,
            "reranked_documents": reranked,
            "retrieval_latency_ms": 0,  # 简化
            "count": len(reranked),
        }

    def _fuse_results(
        self,
        vector_results: List[Dict],
        keyword_results: List[Dict],
        keyword_weight: float,
    ) -> List[Dict]:
        """融合向量检索和关键词检索结果"""
        # 使用 Reciprocal Rank Fusion (RRF)
        rrf_scores = {}

        # 向量检索分数
        for i, doc in enumerate(vector_results):
            doc_id = doc.get("id", str(i))
            vector_score = 1.0 - doc.get("distance", 0)
            rrf_scores[doc_id] = {
                "score": vector_score * (1 - keyword_weight),
                "doc": doc,
            }

        # 关键词检索分数
        for i, doc in enumerate(keyword_results):
            doc_id = doc.get("id", str(i))
            keyword_score = 1.0 / (i + 1)  # RRF 公式

            if doc_id in rrf_scores:
                rrf_scores[doc_id]["score"] += keyword_score * keyword_weight
            else:
                rrf_scores[doc_id] = {
                    "score": keyword_score * keyword_weight,
                    "doc": doc,
                }

        # 排序
        fused = sorted(
            rrf_scores.values(),
            key=lambda x: x["score"],
            reverse=True,
        )

        return [item["doc"] for item in fused]


def create_rag_pipeline(
    config: Optional[RAGConfig] = None, provider: str = "local", **kwargs
) -> RAGPipeline:
    """
    工厂函数：创建 RAG 流水线

    Args:
        config: RAG 配置
        provider: 提供商（local, openai）
        **kwargs: 其他参数

    Returns:
        RAGPipeline 实例
    """
    from myAgent.core.vector_store import VectorStore, VectorStoreConfig
    from myAgent.rag.assembler import ContextAssembler
    from myAgent.rag.embedding import create_embedding_client
    from myAgent.rag.reranker import create_reranker

    # 创建组件
    vector_store = VectorStore(
        VectorStoreConfig(
            persist_directory=kwargs.get("persist_directory", "./data/rag_index"),
            collection_name=kwargs.get("collection_name", "rag_kb"),
        )
    )

    embedding_client = create_embedding_client(
        provider=provider,
        model=config.embedding_model if config else "text-embedding-3-small",
        base_url=kwargs.get("base_url"),
        api_key=kwargs.get("api_key"),
    )

    reranker = create_reranker(
        provider=kwargs.get("rerank_provider", "mock"),
    )

    assembler = ContextAssembler(
        max_context_tokens=config.max_context_tokens if config else 4000,
    )

    llm_client = kwargs.get("llm_client")

    # 创建流水线
    pipeline = RAGPipeline(
        config=config,
        vector_store=vector_store,
        embedding_client=embedding_client,
        reranker=reranker,
        assembler=assembler,
        llm_client=llm_client,
    )

    return pipeline
