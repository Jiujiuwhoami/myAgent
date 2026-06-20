"""RAG 向量检索模块 - 使用 Zilliz Cloud + TF-IDF Embedding

工作流程：
1. 文档上传 → 切分段落 → 向量化 → 存入 Zilliz
2. 用户提问 → 向量化 → 语义搜索 → 召回 Top-K 相关段落
3. 将召回段落注入 LLM Prompt，增强回答质量

Embedding 策略（三级降级）：
- 优先：OpenAI 兼容 API（配置 LLM_BASE_URL + LLM_API_KEY）
- 其次：TF-IDF 向量化（零依赖，基于词汇重叠）
- 兜底：随机向量（仅开发测试）
"""
import math
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


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
    """Embedding 客户端 - 多级降级策略"""

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

        # TF-IDF 词汇表
        self._vocab: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._corpus_count = 0

    def embed(self, texts: List[str]) -> List[List[float]]:
        """批量生成 Embedding，自动选择最佳可用模型"""
        if not texts:
            return []

        # 策略 1：OpenAI 兼容 API
        if self.base_url and self.api_key:
            try:
                return self._embed_api(texts)
            except Exception as e:
                print(f"[WARN] Embedding API 失败 ({e})，降级到 TF-IDF")

        # 策略 2：TF-IDF 向量化（零依赖）
        try:
            return self._embed_tfidf(texts)
        except Exception as e:
            print(f"[WARN] TF-IDF 失败 ({e})，降级到随机向量")

        # 策略 3：随机向量（仅开发测试）
        import random
        print("[WARN] EmbeddingClient: 使用随机向量占位（开发模式）")
        return [[random.uniform(-1, 1) for _ in range(self.dimension)] for _ in texts]

    def _embed_api(self, texts: List[str]) -> List[List[float]]:
        """使用 OpenAI 兼容 API 生成 Embedding"""
        import httpx
        response = httpx.post(
            f"{self.base_url.rstrip('/')}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "input": texts,
                "encoding_format": "float",
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]

    def _build_vocab(self, texts: List[str]):
        """构建词汇表和 IDF"""
        if not texts:
            return
        doc_freq: Dict[str, int] = {}
        for text in texts:
            words = self._tokenize(text)
            for word in set(words):
                doc_freq[word] = doc_freq.get(word, 0) + 1
            self._corpus_count += 1
        # 更新全局词汇表
        for word in doc_freq:
            if word not in self._vocab:
                self._vocab[word] = len(self._vocab)
        # 计算 IDF
        for word, freq in doc_freq.items():
            self._idf[word] = math.log((self._corpus_count + 1) / (freq + 1)) + 1

    def _tokenize(self, text: str) -> List[str]:
        """简单分词（中英文通用）"""
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        english_words = re.findall(r'[a-zA-Z]+', text.lower())
        return chinese_chars + english_words

    def _embed_tfidf(self, texts: List[str]) -> List[List[float]]:
        """TF-IDF 向量化（零依赖实现，自动对齐维度）"""
        # 构建词汇表
        self._build_vocab(texts)

        if not self._vocab:
            raise ValueError("Empty vocabulary")

        vocab_size = len(self._vocab)
        target_dim = self.dimension  # 目标维度（1536）
        vectors = []
        for text in texts:
            words = self._tokenize(text)
            tf: Dict[str, int] = {}
            for w in words:
                tf[w] = tf.get(w, 0) + 1
            total = len(words) if words else 1

            # 创建目标维度的向量
            vec = [0.0] * target_dim
            for word, count in tf.items():
                if word in self._vocab:
                    idx = self._vocab[word]
                    if idx < target_dim:  # 防止词汇表超出维度
                        tf_val = count / total
                        idf_val = self._idf.get(word, 1.0)
                        vec[idx] = tf_val * idf_val
            # L2 归一化
            norm = sum(v * v for v in vec) ** 0.5
            if norm > 0:
                vec = [v / norm for v in vec]
            vectors.append(vec)

        return vectors


class RAGStore:
    """RAG 向量存储 - Zilliz Cloud（使用 MilvusClient 新 API）"""

    COLLECTION_NAME = "myagent_rag_chunks"

    def __init__(self, zilliz_uri: str, zilliz_token: str, embed_client: Optional[EmbeddingClient] = None):
        self.zilliz_uri = zilliz_uri
        self.zilliz_token = zilliz_token
        self.embed_client = embed_client or EmbeddingClient()

        # 使用 MilvusClient 新 API（设置超时避免阻塞）
        from pymilvus import MilvusClient
        try:
            self.client = MilvusClient(
                uri=zilliz_uri,
                token=zilliz_token,
                timeout=5,
            )
            # 测试连接
            self.client.heartbeat()
        except Exception as e:
            print(f"[WARN] Zilliz 连接失败: {e}，RAG 将不可用")
            self.client = None

        # 创建或加载 Collection
        self._ensure_collection()

    def _ensure_collection(self):
        """确保 Collection 存在"""
        if not self.client:
            return  # 连接失败，跳过
        dim = self.embed_client.dimension

        if self.client.has_collection(self.COLLECTION_NAME):
            # 加载集合
            self.client.load_collection(self.COLLECTION_NAME)
            return

        # 定义 Schema
        schema = self.client.create_schema(
            enable_dynamic_field=False,
            description="RAG 文档向量存储",
        )
        # 添加字段（pymilvus 3.0 需要 field_name + datatype）
        from pymilvus import DataType
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=64, is_primary=True)
        schema.add_field(field_name="user_id", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="doc_title", datatype=DataType.VARCHAR, max_length=256)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=4096)
        schema.add_field(field_name="metadata", datatype=DataType.VARCHAR, max_length=8192)
        schema.add_field(field_name="created_at", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dim)

        # 创建索引参数
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="HNSW",
            metric_type="IP",
            params={"M": 8, "efConstruction": 64},
        )

        # 创建 Collection
        self.client.create_collection(
            collection_name=self.COLLECTION_NAME,
            schema=schema,
            index_params=index_params,
        )

    def insert_documents(self, chunks: List[DocumentChunk]) -> int:
        """插入文档片段（自动生成 Embedding）"""
        if not self.client:
            raise RuntimeError("RAG 连接未就绪")
        if not chunks:
            return 0

        # 提取文本并生成 Embedding
        texts = [c.content for c in chunks]
        embeddings = self.embed_client.embed(texts)

        # 填充向量和时间戳
        for chunk, emb in zip(chunks, embeddings):
            chunk.vector = emb
            if not chunk.id:
                chunk.id = str(uuid.uuid4())[:32]
            if not chunk.created_at:
                chunk.created_at = datetime.now().isoformat()

        # 准备数据（MilvusClient 格式）
        data = [
            {
                "id": c.id,
                "user_id": c.user_id,
                "doc_title": c.doc_title,
                "content": c.content,
                "metadata": str(c.metadata),
                "created_at": c.created_at,
                "vector": c.vector,
            }
            for c in chunks
        ]

        # 写入 Zilliz
        self.client.insert(
            collection_name=self.COLLECTION_NAME,
            data=data,
            timeout=10,
        )
        return len(chunks)

    def search(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
        doc_title: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """语义搜索"""
        if not self.client:
            return []
        # 生成查询向量
        query_vec = self.embed_client.embed([query])[0]

        # 构造过滤条件
        expr = f'user_id == "{user_id}"'
        if doc_title:
            expr += f' and doc_title == "{doc_title}"'

        # 搜索
        results = self.client.search(
            collection_name=self.COLLECTION_NAME,
            data=[query_vec],
            limit=top_k,
            filter=expr,
            output_fields=["content", "doc_title", "metadata", "created_at"],
            search_params={"metric_type": "IP", "params": {"ef": 10}},
            timeout=10,
        )

        # 格式化结果
        items = []
        for hits in results:
            for hit in hits:
                items.append({
                    "score": float(hit["distance"]),
                    "content": hit["entity"].get("content", ""),
                    "doc_title": hit["entity"].get("doc_title", ""),
                    "metadata": hit["entity"].get("metadata", "{}"),
                    "created_at": hit["entity"].get("created_at", ""),
                })
        return items

    def delete_by_user(self, user_id: str) -> int:
        """删除用户所有数据"""
        expr = f'user_id == "{user_id}"'
        self.client.delete(collection_name=self.COLLECTION_NAME, filter=expr)
        return 0

    def get_stats(self) -> Dict[str, int]:
        """获取集合统计信息"""
        try:
            # MilvusClient 没有 estimate_num_entities 方法，使用 describe_collection
            desc = self.client.describe_collection(self.COLLECTION_NAME)
            return {"total_entities": desc.get("collections", [{}])[0].get("entities", 0)}
        except Exception:
            return {"total_entities": 0}

    def close(self):
        """断开连接"""
        # MilvusClient 自动管理连接，无需显式断开
        pass
