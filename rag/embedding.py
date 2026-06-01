"""嵌入模型客户端 - 生成文本向量表示

支持：
- 本地嵌入模型（通过 OpenAI 兼容 API）
- OpenAI Embeddings API
- HuggingFace 嵌入模型
- 自定义嵌入模型

配置来源优先级: 命令行参数 > 环境变量 > YAML 配置文件 > 默认值
"""

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class EmbeddingResult:
    """嵌入结果"""

    embedding: List[float]
    model: str
    input_tokens: int
    index: int = 0


def _get_default_config():
    """从统一配置管理器获取默认配置"""
    try:
        from myAgent.config import get_embedding_config

        return get_embedding_config()
    except ImportError:
        return None


class EmbeddingClient:
    """
    通用嵌入客户端

    提供统一的嵌入接口，支持多种后端

    示例:
        # 使用配置管理器（推荐）
        client = EmbeddingClient()  # 自动从配置文件加载

        # 手动指定配置
        client = EmbeddingClient(model="text-embedding-3-small", base_url="http://localhost:8080/v1")
    """

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        dimensions: Optional[int] = None,
    ):
        """
        初始化嵌入客户端

        Args:
            model: 嵌入模型名称（默认从配置文件读取）
            base_url: API 基础 URL（本地模型或代理，默认从配置文件读取）
            api_key: API Key（默认从配置文件读取）
            dimensions: 输出维度（可选）
        """
        # 从配置管理器获取默认值
        config = _get_default_config()

        self.model = model or (config.model if config else "text-embedding-3-small")
        self.base_url = base_url or (config.base_url if config else None)
        self.api_key = (
            api_key or (config.api_key if config else "") or os.environ.get("EMBEDDING_API_KEY", "")
        )
        self.dimensions = dimensions or (config.dimensions if config else None)

        self._cache: Dict[str, List[float]] = {}
        self._check_availability()

    def _check_availability(self):
        """检查嵌入服务可用性"""
        self._backend = "unknown"

        # 检查本地模型
        if self.base_url:
            try:
                import urllib.request

                url = f"{self.base_url.rstrip('/')}/models"
                req = urllib.request.Request(url)
                if self.api_key:
                    req.add_header("Authorization", f"Bearer {self.api_key}")

                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        self._backend = "local"
                        print(f"   [OK] Local embedding model available: {self.base_url}")
                        return
            except Exception as e:
                print(f"   [WARN] Local embedding model unavailable: {e}")

        # 检查环境变量
        if os.environ.get("OPENAI_API_KEY"):
            self._backend = "openai"
            print("   [OK] OpenAI Embeddings available")
            return

        # 默认回退
        self._backend = "mock"
        print("   [WARN] No embedding model configured, using mock mode")
        print("   [HINT] Set EMBEDDING_API_KEY or base_url in config")

    def embed(self, text: str) -> EmbeddingResult:
        """
        生成文本嵌入

        Args:
            text: 要嵌入的文本

        Returns:
            EmbeddingResult 对象
        """
        # 检查缓存
        cache_key = self._get_cache_key(text)
        if cache_key in self._cache:
            return EmbeddingResult(
                embedding=self._cache[cache_key],
                model=self.model,
                input_tokens=len(text) // 4,
            )

        # 根据后端生成嵌入
        if self._backend == "local":
            embedding = self._embed_local(text)
        elif self._backend == "openai":
            embedding = self._embed_openai(text)
        else:
            embedding = self._embed_mock(text)

        # 缓存结果
        self._cache[cache_key] = embedding

        return EmbeddingResult(
            embedding=embedding,
            model=self.model,
            input_tokens=len(text) // 4,
        )

    def embed_documents(self, texts: List[str]) -> List[EmbeddingResult]:
        """
        批量生成文档嵌入

        Args:
            texts: 文本列表

        Returns:
            嵌入结果列表
        """
        results = []
        for i, text in enumerate(texts):
            result = self.embed(text)
            result.index = i
            results.append(result)
        return results

    def embed_query(self, query: str) -> List[float]:
        """
        生成查询嵌入（用于检索）

        Args:
            query: 查询文本

        Returns:
            嵌入向量
        """
        return self.embed(query).embedding

    def _get_cache_key(self, text: str) -> str:
        """生成缓存键"""
        return hashlib.md5(f"{self.model}:{text}".encode()).hexdigest()

    def _embed_local(self, text: str) -> List[float]:
        """调用本地嵌入模型"""
        import urllib.request

        url = f"{self.base_url.rstrip('/')}/embeddings"

        payload = {
            "input": text,
            "model": self.model,
        }

        if self.dimensions:
            payload["dimensions"] = self.dimensions

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))

        # 提取嵌入向量
        if "data" in result and len(result["data"]) > 0:
            return result["data"][0]["embedding"]

        raise ValueError("Local model returned invalid format")

    def _embed_openai(self, text: str) -> List[float]:
        """调用 OpenAI Embeddings"""
        import urllib.request

        api_key = self.api_key or os.environ["OPENAI_API_KEY"]

        url = "https://api.openai.com/v1/embeddings"

        payload = {
            "input": text,
            "model": self.model,
        }

        if self.dimensions:
            payload["dimensions"] = self.dimensions

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

        if "data" in result and len(result["data"]) > 0:
            return result["data"][0]["embedding"]

        raise ValueError("OpenAI returned invalid format")

    def _embed_mock(self, text: str) -> List[float]:
        """模拟嵌入（用于测试）"""
        # 生成确定性但随机的向量
        hash_bytes = hashlib.sha256(f"{self.model}:{text}".encode()).digest()

        # 转换为 float 向量（1536 维，类似 text-embedding-3-small）
        embedding = []
        for i in range(0, len(hash_bytes) * 4, 4):
            # 使用 hash 生成 -1 到 1 之间的值
            int_val = (
                int.from_bytes(
                    hash_bytes[(i // 4) % len(hash_bytes) : ((i // 4) % len(hash_bytes)) + 1], "big"
                )
                if (i // 4) % len(hash_bytes) < len(hash_bytes)
                else 0
            )
            embedding.append((int_val % 256) / 128.0 - 1.0)

        # 填充到 1536 维
        while len(embedding) < 1536:
            embedding.append(0.0)

        return embedding[:1536]

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "model": self.model,
            "backend": self._backend,
            "base_url": self.base_url,
            "dimensions": self.dimensions,
            "cache_size": len(self._cache),
        }

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()


class HuggingFaceEmbeddingClient(EmbeddingClient):
    """
    HuggingFace 嵌入客户端

    使用 HuggingFace Inference API
    """

    def __init__(
        self,
        model: str = "sentence-transformers/all-MiniLM-L6-v2",
        api_token: Optional[str] = None,
    ):
        super().__init__(
            model=model,
            base_url="https://api-inference.huggingface.co/pipeline/feature-extraction",
            api_key=api_token,
        )
        self._backend = "huggingface"

    def _embed_local(self, text: str) -> List[float]:
        """调用 HuggingFace API"""
        import urllib.request

        api_token = self.api_key or os.environ.get("HUGGINGFACE_TOKEN")
        if not api_token:
            raise ValueError("Need to set HUGGINGFACE_TOKEN")

        url = f"https://api-inference.huggingface.co/models/{self.model}"

        payload = {"inputs": text}
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_token}",
            },
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))

        # HuggingFace 返回嵌套列表
        if isinstance(result, list) and len(result) > 0:
            if isinstance(result[0], list):
                return result[0]
            return result

        raise ValueError("HuggingFace returned invalid format")


class CohereEmbeddingClient(EmbeddingClient):
    """
    Cohere Embeddings API 客户端
    """

    def __init__(
        self,
        model: str = "embed-english-v3.0",
        api_key: Optional[str] = None,
        input_type: str = "search_document",
    ):
        super().__init__(model=model, api_key=api_key)
        self.input_type = input_type
        self._backend = "cohere"

    def _embed_openai(self, text: str) -> List[float]:
        """调用 Cohere API（使用 OpenAI 兼容格式）"""
        import urllib.request

        url = "https://api.cohere.ai/v1/embed"

        payload = {
            "texts": [text],
            "model": self.model,
            "input_type": self.input_type,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))

        if "embeddings" in result and len(result["embeddings"]) > 0:
            return result["embeddings"][0]

        raise ValueError("Cohere returned invalid format")


def create_embedding_client(provider: Optional[str] = None, **kwargs) -> EmbeddingClient:
    """
    工厂函数：创建嵌入客户端

    Args:
        provider: 提供商（local, openai, huggingface, cohere），默认从配置文件读取
        **kwargs: 其他参数

    Returns:
        EmbeddingClient 实例
    """
    # 如果没有指定 provider，从配置文件读取
    if provider is None:
        config = _get_default_config()
        provider = config.provider if config else "local"

    if provider == "local":
        return EmbeddingClient(**kwargs)
    elif provider == "openai":
        return EmbeddingClient(**kwargs)
    elif provider == "huggingface":
        return HuggingFaceEmbeddingClient(**kwargs)
    elif provider == "cohere":
        return CohereEmbeddingClient(**kwargs)
    else:
        raise ValueError(f"Unsupported provider: {provider}")
