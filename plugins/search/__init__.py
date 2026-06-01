"""搜索插件"""

from myAgent.plugins import ToolMeta, ToolPlugin


class WebSearchPlugin(ToolPlugin):
    """网页搜索工具"""

    @property
    def meta(self) -> ToolMeta:
        return ToolMeta(
            name="web_search",
            description="搜索互联网信息",
            version="1.0.0",
            category="research",
            tags=["search", "web"],
        )

    async def execute(self, query: str, limit: int = 5) -> dict:
        """执行搜索"""
        return {
            "query": query,
            "results": [
                {"title": f"搜索结果 {i+1}", "url": f"https://example.com/{i+1}", "snippet": "..."}
                for i in range(limit)
            ],
            "total": limit,
        }


class NewsSearchPlugin(ToolPlugin):
    """新闻搜索工具"""

    @property
    def meta(self) -> ToolMeta:
        return ToolMeta(
            name="news_search",
            description="搜索新闻资讯",
            version="1.0.0",
            category="research",
            tags=["search", "news"],
        )

    async def execute(self, keyword: str, days: int = 7) -> dict:
        """搜索新闻"""
        return {
            "keyword": keyword,
            "news": [
                {"title": f"新闻标题 {i+1}", "source": "新闻源", "date": "2024-01-01"}
                for i in range(3)
            ],
            "date_range": f"最近 {days} 天",
        }
