"""重排序器 - 对检索结果进行精排序

重排序（Reranking）是 RAG 系统的关键组件：
1. 第一阶段：向量检索（召回，速度快但精度一般）
2. 第二阶段：重排序（精排，速度慢但精度高）

支持：
- Cross-Encoder 模型（BGE-Reranker, Cohere Rerank）
- LLM 重排序
- 自定义重排序函数
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RankedDocument:
    """重排序后的文档"""

    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    original_index: int = 0


@dataclass
class RerankResult:
    """重排序结果"""

    documents: List[RankedDocument]
    model: str
    query: str
    original_count: int
    returned_count: int


class Reranker:
    """
    通用重排序器

    提供多种重排序策略
    """

    def __init__(
        self,
        model: Optional[str] = None,
        top_k: int = 5,
        score_threshold: float = 0.5,
    ):
        """
        初始化重排序器

        Args:
            model: 重排序模型名称
            top_k: 返回前 K 个结果
            score_threshold: 分数阈值（低于此分数的结果被过滤）
        """
        self.model = model
        self.top_k = top_k
        self.score_threshold = score_threshold
        self._backend = "mock"

        self._check_availability()

    def _check_availability(self):
        """检查重排序服务"""
        if os.environ.get("COHERE_API_KEY"):
            self._backend = "cohere"
        elif os.environ.get("RERANK_API_KEY"):
            self._backend = "custom"
        else:
            self._backend = "mock"

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None,
    ) -> RerankResult:
        """
        对文档列表进行重排序

        Args:
            query: 查询文本
            documents: 文档列表（每个文档包含 content 和 metadata）
            top_k: 返回数量（覆盖默认值）

        Returns:
            RerankResult 对象
        """
        top_k = top_k or self.top_k

        if not documents:
            return RerankResult(
                documents=[],
                model=self.model or "none",
                query=query,
                original_count=0,
                returned_count=0,
            )

        # 根据后端重排序
        if self._backend == "cohere":
            scored_docs = self._rerank_cohere(query, documents)
        elif self._backend == "custom":
            scored_docs = self._rerank_custom(query, documents)
        else:
            scored_docs = self._rerank_mock(query, documents)

        # 过滤低分结果
        scored_docs = [doc for doc in scored_docs if doc.score >= self.score_threshold]

        # 取 top_k
        scored_docs = scored_docs[:top_k]

        return RerankResult(
            documents=scored_docs,
            model=self.model or "mock",
            query=query,
            original_count=len(documents),
            returned_count=len(scored_docs),
        )

    def _rerank_cohere(
        self,
        query: str,
        documents: List[Dict[str, Any]],
    ) -> List[RankedDocument]:
        """调用 Cohere Rerank API"""
        import urllib.request

        api_key = os.environ["COHERE_API_KEY"]
        url = "https://api.cohere.ai/v1/rerank"

        # 准备文档文本
        texts = [doc.get("content", "") for doc in documents]

        payload = {
            "query": query,
            "documents": texts,
            "model": self.model or "rerank-english-v3.0",
            "top_n": len(documents),
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))

        # 解析结果
        ranked_docs = []
        for item in result.get("results", []):
            idx = item["index"]
            ranked_docs.append(
                RankedDocument(
                    content=documents[idx].get("content", ""),
                    score=item["relevance_score"],
                    metadata=documents[idx].get("metadata", {}),
                    original_index=idx,
                )
            )

        return ranked_docs

    def _rerank_custom(
        self,
        query: str,
        documents: List[Dict[str, Any]],
    ) -> List[RankedDocument]:
        """调用自定义重排序 API"""
        import urllib.request

        api_key = os.environ["RERANK_API_KEY"]
        base_url = os.environ.get("RERANK_BASE_URL", "http://localhost:8000")
        url = f"{base_url}/rerank"

        texts = [doc.get("content", "") for doc in documents]

        payload = {
            "query": query,
            "documents": texts,
            "model": self.model,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))

        ranked_docs = []
        for item in result.get("results", []):
            idx = item["index"]
            ranked_docs.append(
                RankedDocument(
                    content=documents[idx].get("content", ""),
                    score=item["score"],
                    metadata=documents[idx].get("metadata", {}),
                    original_index=idx,
                )
            )

        return ranked_docs

    def _rerank_mock(
        self,
        query: str,
        documents: List[Dict[str, Any]],
    ) -> List[RankedDocument]:
        """模拟重排序（基于关键词匹配）"""
        import hashlib

        query_terms = set(query.lower().split())
        scored_docs = []

        for i, doc in enumerate(documents):
            content = doc.get("content", "").lower()
            metadata = doc.get("metadata", {})

            # 计算匹配分数
            score = 0.0

            # 关键词匹配
            for term in query_terms:
                if term in content:
                    score += 0.3

            # 标题匹配（如果 metadata 中有标题）
            title = metadata.get("title", "").lower()
            for term in query_terms:
                if term in title:
                    score += 0.5

            # 类别匹配
            category = metadata.get("category", "")
            if category in query.lower():
                score += 0.2

            # 添加一些随机性（模拟模型行为）
            hash_val = int(
                hashlib.md5(f"{query}:{doc.get('content', '')}".encode()).hexdigest()[:8], 16
            )
            score += (hash_val % 100) / 1000.0

            scored_docs.append(
                RankedDocument(
                    content=doc.get("content", ""),
                    score=min(score, 1.0),
                    metadata=metadata,
                    original_index=i,
                )
            )

        # 按分数降序排序
        scored_docs.sort(key=lambda x: x.score, reverse=True)

        return scored_docs


class LLMReranker(Reranker):
    """
    使用 LLM 进行重排序

    通过 LLM 评估查询与文档的相关性
    """

    def __init__(
        self,
        llm_client,
        model: Optional[str] = None,
        top_k: int = 5,
        score_threshold: float = 0.5,
        max_tokens: int = 100,
    ):
        super().__init__(
            model=model,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        self.llm = llm_client
        self.max_tokens = max_tokens
        self._backend = "llm"

    def _rerank_llm(
        self,
        query: str,
        documents: List[Dict[str, Any]],
    ) -> List[RankedDocument]:
        """使用 LLM 重排序"""
        # 构建 prompt
        doc_texts = "\n\n".join(
            [f"[{i}] {doc.get('content', '')[:500]}" for i, doc in enumerate(documents)]
        )

        prompt = f"""请评估以下文档与查询的相关性，返回 JSON 格式：

查询: {query}

文档:
{doc_texts}

请返回 JSON：
{{
    "rankings": [
        {{"index": 0, "score": 0.9, "reason": "..."}}
    ]
}}

只返回 JSON，不要其他内容。"""

        try:
            response = self.llm.chat(prompt)
            # 解析 JSON
            result = json.loads(response)

            rankings = result.get("rankings", [])
            ranked_docs = []

            for item in rankings:
                idx = item["index"]
                ranked_docs.append(
                    RankedDocument(
                        content=documents[idx].get("content", ""),
                        score=item["score"],
                        metadata=documents[idx].get("metadata", {}),
                        original_index=idx,
                    )
                )

            return ranked_docs

        except Exception as e:
            print(f"   ⚠️ LLM 重排序失败: {e}")
            # 回退到 mock
            return self._rerank_mock(query, documents)

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None,
    ) -> RerankResult:
        """使用 LLM 重排序"""
        top_k = top_k or self.top_k

        if not documents:
            return RerankResult(
                documents=[],
                model="llm",
                query=query,
                original_count=0,
                returned_count=0,
            )

        # LLM 重排序可能较慢，分批处理
        batch_size = 10
        all_ranked = []

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            ranked = self._rerank_llm(query, batch)
            all_ranked.extend(ranked)

        # 按分数排序
        all_ranked.sort(key=lambda x: x.score, reverse=True)

        # 过滤和截断
        all_ranked = [doc for doc in all_ranked if doc.score >= self.score_threshold][:top_k]

        return RerankResult(
            documents=all_ranked,
            model="llm",
            query=query,
            original_count=len(documents),
            returned_count=len(all_ranked),
        )


class BGEReranker(Reranker):
    """
    BGE Reranker（智源）

    使用 BAAI/bge-reranker 模型
    """

    def __init__(
        self,
        model: str = "BAAI/bge-reranker-v2-m3",
        top_k: int = 5,
        score_threshold: float = 0.5,
        device: str = "cpu",
    ):
        super().__init__(
            model=model,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        self.device = device
        self._model = None
        self._tokenizer = None
        self._load_model()

    def _load_model(self):
        """加载模型"""
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model)
            self._model = AutoModelForSequenceClassification.from_pretrained(self.model)
            self._model.to(self.device)
            self._model.eval()

            self._backend = "bge"
            print(f"   ✅ BGE Reranker 加载成功: {self.model}")

        except Exception as e:
            print(f"   ⚠️ BGE Reranker 加载失败: {e}")
            print("   💡 使用模拟模式")
            self._backend = "mock"

    def _rerank_bge(
        self,
        query: str,
        documents: List[Dict[str, Any]],
    ) -> List[RankedDocument]:
        """使用 BGE Reranker"""
        import torch
        from torch.nn import functional as F

        # 准备输入
        pairs = [[query, doc.get("content", "")] for doc in documents]

        inputs = self._tokenizer(
            pairs,
            padding=True,
            truncation=True,
            return_tensors="pt",
            max_length=512,
        )

        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # 推理
        with torch.no_grad():
            scores = self._model(**inputs).logits.squeeze()

            # 应用 sigmoid
            if scores.dim() == 0:
                scores = scores.unsqueeze(0)
            scores = F.sigmoid(scores).cpu().numpy()

        # 构建结果
        ranked_docs = []
        for i, doc in enumerate(documents):
            ranked_docs.append(
                RankedDocument(
                    content=doc.get("content", ""),
                    score=float(scores[i]),
                    metadata=doc.get("metadata", {}),
                    original_index=i,
                )
            )

        return ranked_docs

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None,
    ) -> RerankResult:
        """BGE 重排序"""
        if self._backend == "mock":
            return super().rerank(query, documents, top_k)

        top_k = top_k or self.top_k

        if not documents:
            return RerankResult(
                documents=[],
                model=self.model,
                query=query,
                original_count=0,
                returned_count=0,
            )

        ranked = self._rerank_bge(query, documents)

        # 过滤和截断
        ranked = [doc for doc in ranked if doc.score >= self.score_threshold][:top_k]

        return RerankResult(
            documents=ranked,
            model=self.model,
            query=query,
            original_count=len(documents),
            returned_count=len(ranked),
        )


def create_reranker(provider: str = "mock", **kwargs) -> Reranker:
    """
    工厂函数：创建重排序器

    Args:
        provider: 提供商（mock, cohere, bge, llm）
        **kwargs: 其他参数

    Returns:
        Reranker 实例
    """
    if provider == "mock":
        return Reranker(**kwargs)
    elif provider == "cohere":
        return Reranker(model="rerank-english-v3.0", **kwargs)
    elif provider == "bge":
        return BGEReranker(**kwargs)
    elif provider == "llm":
        return LLMReranker(**kwargs)
    else:
        raise ValueError(f"不支持的提供商: {provider}")
