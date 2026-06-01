"""天气插件"""

import random

from myAgent.plugins import ToolMeta, ToolPlugin


class WeatherPlugin(ToolPlugin):
    """天气查询工具"""

    @property
    def meta(self) -> ToolMeta:
        return ToolMeta(
            name="weather",
            description="获取指定城市的天气信息",
            version="1.0.0",
            author="Agent Team",
            category="utility",
            tags=["weather", "query"],
        )

    async def execute(self, city: str = "北京") -> dict:
        """执行天气查询"""
        weathers = ["晴天", "多云", "阴天", "小雨", "大雨", "雪"]
        return {
            "city": city,
            "weather": random.choice(weathers),
            "temperature": random.randint(-10, 40),
            "humidity": random.randint(30, 90),
            "update_time": "实时",
        }

    def validate_params(self, **kwargs) -> list:
        """验证参数"""
        errors = []
        city = kwargs.get("city", "")
        if city and len(city) > 50:
            errors.append("城市名称过长")
        return errors
