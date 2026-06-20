"""RAG 向量检索模块 - 使用 Zilliz Cloud

工作流程：
1. 文档上传 → 切分段落 → 向量化 → 存入 Zilliz
2. 用户提问 → 向量化 → 语义搜索 → 召回 Top-K 相关段落
3. 将召回段落注入 LLM Prompt，增强回答质量
"""
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)


@dataclass
class DocumentChunk:
    """文档片段"""
    id: str = ""
    user_id: str = ""
    doc_title: str = ""
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    vector: Optional[List[float]] = None
    created_at: str = ""


class EmbeddingClient:
    """Embedding 客户端 - 支持多种模型"""

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        base_url: str = "",
        api_key: str = "",
        dimension: int = 1536,
    ):
        self.model = model
        self.dimension = dimension
        self.base_url = base_url
        self.api_key = api_key

    def embed(self, texts: List[str]) -> List[List[float]]:
        """批量生成 Embedding"""
        if not texts:
            return []

        # 尝试使用 OpenAI 兼容 API
        if self.base_url and self.api_key:
            import httpx
            response = httpx.post(
                f"{self.base_url.rstrip('/')}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "input": texts,
                    "encoding_format": "float",
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]

        # 回退：使用随机向量（开发阶段）
        # 生产环境必须配置 base_url + api_key
        import random
        print("[WARN] EmbeddingClient: 未配置 API，使用随机向量占位")
        return [[random.uniform(-1, 1) for _ in range(self.dimension)] for _ in texts]


class RAGStore:
    """RAG 向量存储 - Zilliz Cloud"""

    COLLECTION_NAME = "myagent_rag_chunks"
    INDEX_NAME = "vector_idx"

    def __init__(self, zilliz_uri: str, zilliz_token: str, embed_client: Optional[EmbeddingClient] = None):
        self.zilliz_uri = zilliz_uri
        self.zilliz_token = zilliz_token
        self.embed_client = embed_client or EmbeddingClient()

        # 建立连接
        connections.connect(
            alias="default",
            uri=zilliz_uri,
            token=zilliz_token,
        )

        # 创建或加载 Collection
        self._ensure_collection()

    def _ensure_collection(self):
        """确保 Collection 存在"""
        dim = self.embed_client.dimension

        if utility.has_collection(self.COLLECTION_NAME):
            self.collection = Collection(self.COLLECTION_NAME)
            self.collection.load()
            return

        # 定义 Schema
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
            FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="doc_title", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=4096),
            FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="created_at", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
        ]
        schema = CollectionSchema(fields, description="RAG 文档向量存储")
        self.collection = Collection(self.COLLECTION_NAME, schema)

        # 创建索引
        index_params = {
            "index_type": "HNSW",
            "metric_type": "IP",  # 内积相似度
            "params": {"M": 8, "efConstruction": 64},
        }
        self.collection.create_index("vector", index_params)
        self.collection.load()

    def insert_documents(self, chunks: List[DocumentChunk]) -> int:
        """插入文档片段（自动生成 Embedding）"""
        if not chunks:
            return 0

        # 提取文本并生成 Embedding
        texts = [c.content for c in chunks]
        embeddings = self.embed_client.embed(texts)

        # 填充向量
        for chunk, emb in zip(chunks, embeddings):
            chunk.vector = emb
            if not chunk.id:
                chunk.id = str(uuid.uuid4())[:32]
            if not chunk.created_at:
                chunk.created_at = datetime.now().isoformat()

        # 准备数据
        data = [
            [c.id for c in chunks],
            [c.user_id for c in chunks],
            [c.doc_title for c in chunks],
            [c.content for c in chunks],
            [str(c.metadata) for c in chunks],
            [c.created_at for c in chunks],
            [c.vector for c in chunks],
        ]

        # 写入 Zilliz
        self.collection.insert(data)
        self.collection.flush()
        return len(chunks)

    def search(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
        doc_title: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """语义搜索"""
        # 生成查询向量
        query_vec = self.embed_client.embed([query])[0]

        # 构造过滤条件
        expr = f'user_id == "{user_id}"'
        if doc_title:
            expr += f' and doc_title == "{doc_title}"'

        # 搜索
        results = self.collection.search(
            data=[query_vec],
            anns_field="vector",
            param={"metric_type": "IP", "params": {"ef": 10}},
            limit=top_k,
            expr=expr,
            output_fields=["content", "doc_title", "metadata", "created_at"],
        )

        # 格式化结果
        items = []
        for hits in results:
            for hit in hits:
                items.append({
                    "score": float(hit.distance),
                    "content": hit.entity.get("content", ""),
                    "doc_title": hit.entity.get("doc_title", ""),
                    "metadata": hit.entity.get("metadata", "{}"),
                    "created_at": hit.entity.get("created_at", ""),
                })
        return items

    def delete_by_user(self, user_id: str) -> int:
        """删除用户所有数据"""
        expr = f'user_id == "{user_id}"'
        self.collection.delete(expr)
        return 0

    def get_stats(self) -> Dict[str, int]:
        """获取集合统计信息"""
        return {
            "total_entities": self.collection.num_entities,
        }

    def close(self):
        """断开连接"""
        connections.disconnect("default")
