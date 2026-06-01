"""向量数据库集成 - ChromaDB 支持"""

import hashlib
from typing import Any, Callable, Dict, List, Optional


class VectorStoreConfig:
    def __init__(
        self,
        persist_directory: str = "./data/vector_store",
        collection_name: str = "semantic_memory",
        embedding_function: Optional[Callable] = None,
        distance_function: str = "cosine",
    ):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding_function = embedding_function
        self.distance_function = distance_function


class VectorStore:
    """
    向量存储接口 - 支持 ChromaDB

    提供语义搜索功能：
    - 存储文档和向量
    - 相似度搜索
    - 按类别/元数据过滤
    """

    def __init__(self, config: Optional[VectorStoreConfig] = None):
        self.config = config or VectorStoreConfig()
        self._client = None
        self._collection = None
        self._chroma_available = False
        self._fallback_memory: Dict[str, Dict] = {}
        self._init_chroma()

    def _init_chroma(self):
        """初始化 ChromaDB"""
        try:
            import chromadb
            from chromadb.config import Settings

            self._client = chromadb.PersistentClient(
                path=self.config.persist_directory, settings=Settings(anonymized_telemetry=False)
            )
            self._collection = self._client.get_or_create_collection(
                name=self.config.collection_name,
                metadata={"hnsw:space": self.config.distance_function},
            )
            self._chroma_available = True
            print(f"   ✅ ChromaDB 初始化成功: {self.config.collection_name}")
        except ImportError:
            print("   ⚠️ ChromaDB 未安装，使用内存回退模式")
            print("   💡 安装命令: pip install chromadb")
            self._chroma_available = False

    def add(
        self,
        text: str,
        document_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
    ) -> str:
        """
        添加文档到向量库

        Args:
            text: 文档文本
            document_id: 文档ID (可选，自动生成)
            metadata: 元数据
            embedding: 预计算的向量 (可选)

        Returns:
            文档ID
        """
        doc_id = document_id or self._generate_id(text)
        metadata = metadata or {}

        if self._chroma_available:
            self._collection.add(
                documents=[text],
                ids=[doc_id],
                metadatas=[metadata],
                embeddings=[embedding] if embedding else None,
            )
        else:
            self._fallback_memory[doc_id] = {
                "text": text,
                "metadata": metadata,
                "embedding": embedding,
            }

        return doc_id

    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        语义搜索

        Args:
            query: 查询文本
            n_results: 返回数量
            filter_metadata: 元数据过滤条件
            query_embedding: 预计算的查询向量

        Returns:
            搜索结果列表
        """
        if self._chroma_available:
            where_clause = filter_metadata if filter_metadata else None
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_clause,
                query_embeddings=[query_embedding] if query_embedding else None,
            )

            formatted_results = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    formatted_results.append(
                        {
                            "id": doc_id,
                            "text": results["documents"][0][i],
                            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                            "distance": (
                                results["distances"][0][i] if results["distances"] else None
                            ),
                        }
                    )
            return formatted_results
        else:
            return self._fallback_search(query, n_results)

    def _fallback_search(self, query: str, n_results: int) -> List[Dict[str, Any]]:
        """内存回退搜索 (简单关键词匹配)"""
        results = []
        query_lower = query.lower()
        for doc_id, data in self._fallback_memory.items():
            text_lower = data["text"].lower()
            score = query_lower in text_lower
            if score:
                results.append(
                    {
                        "id": doc_id,
                        "text": data["text"],
                        "metadata": data["metadata"],
                        "distance": 0.0 if score else 1.0,
                    }
                )
        return results[:n_results]

    def delete(self, document_id: str):
        """删除文档"""
        if self._chroma_available:
            self._collection.delete(ids=[document_id])
        else:
            self._fallback_memory.pop(document_id, None)

    def get(self, document_id: str) -> Optional[Dict[str, Any]]:
        """获取单个文档"""
        if self._chroma_available:
            results = self._collection.get(ids=[document_id])
            if results["ids"]:
                return {
                    "id": results["ids"][0],
                    "text": results["documents"][0],
                    "metadata": results["metadatas"][0] if results["metadatas"] else {},
                }
            return None
        else:
            data = self._fallback_memory.get(document_id)
            if data:
                return {
                    "id": document_id,
                    "text": data["text"],
                    "metadata": data["metadata"],
                }
            return None

    def count(self) -> int:
        """获取文档数量"""
        if self._chroma_available:
            return self._collection.count()
        return len(self._fallback_memory)

    def reset(self):
        """清空集合"""
        if self._chroma_available:
            self._client.delete_collection(self.config.collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self.config.collection_name
            )
        self._fallback_memory = {}

    @staticmethod
    def _generate_id(text: str) -> str:
        """生成文档ID"""
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def get_status(self) -> Dict[str, Any]:
        return {
            "backend": "chroma" if self._chroma_available else "memory",
            "collection": self.config.collection_name,
            "count": self.count(),
            "persist_directory": self.config.persist_directory,
        }


class SemanticMemoryWithVector:
    """
    增强版语义记忆 - 集成向量搜索

    在原有 SemanticMemory 基础上增加：
    - 向量存储
    - 语义搜索
    - 相似度匹配
    """

    def __init__(
        self,
        vector_config: Optional[VectorStoreConfig] = None,
    ):
        self.vector_store = VectorStore(vector_config)

    def add_knowledge(
        self,
        key: str,
        value: str,
        category: str = "general",
        embedding: Optional[List[float]] = None,
    ):
        """添加知识到向量库"""
        self.vector_store.add(
            text=value,
            document_id=key,
            metadata={"category": category, "key": key},
            embedding=embedding,
        )

    def search(self, query: str, n_results: int = 5) -> List[Dict]:
        """语义搜索"""
        results = self.vector_store.search(query, n_results=n_results)
        return [
            {
                "key": r["metadata"].get("key", r["id"]),
                "text": r["text"],
                "category": r["metadata"].get("category", "unknown"),
                "distance": r.get("distance"),
            }
            for r in results
        ]

    def search_by_category(self, query: str, category: str, n_results: int = 5) -> List[Dict]:
        """按类别搜索"""
        results = self.vector_store.search(
            query,
            n_results=n_results,
            filter_metadata={"category": category},
        )
        return [
            {
                "key": r["metadata"].get("key", r["id"]),
                "text": r["text"],
                "category": r["metadata"].get("category", "unknown"),
                "distance": r.get("distance"),
            }
            for r in results
        ]

    def get_status(self) -> Dict:
        return self.vector_store.get_status()
