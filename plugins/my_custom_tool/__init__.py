"""my_custom_tool 插件"""

from myAgent.plugins import ToolMeta, ToolPlugin


class MyCustomToolPlugin(ToolPlugin):
    """my_custom_tool 工具"""

    @property
    def meta(self) -> ToolMeta:
        return ToolMeta(
            name="my_custom_tool",
            description="my_custom_tool 工具描述",
            category="utility",
            tags=["my_custom_tool"],
        )

    async def execute(self, **kwargs) -> dict:
        """执行工具"""
        return {"result": "success"}
