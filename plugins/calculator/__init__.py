"""计算器插件"""

import math

from myAgent.plugins import ToolMeta, ToolPlugin


class CalculatorPlugin(ToolPlugin):
    """计算器工具"""

    @property
    def meta(self) -> ToolMeta:
        return ToolMeta(
            name="calculate",
            description="执行数学计算",
            version="1.0.0",
            category="utility",
            tags=["math", "calculate"],
        )

    async def execute(self, expression: str) -> dict:
        """执行计算

        Args:
            expression: 数学表达式，如 "1+2*3"
        """
        try:
            safe_dict = {
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "pow": pow,
                "sqrt": math.sqrt,
                "sin": math.sin,
                "cos": math.cos,
                "tan": math.tan,
                "pi": math.pi,
                "e": math.e,
            }

            result = eval(expression, {"__builtins__": {}}, safe_dict)

            return {"expression": expression, "result": result, "status": "success"}
        except Exception as e:
            return {"expression": expression, "error": str(e), "status": "error"}

    def validate_params(self, **kwargs) -> list:
        """验证参数"""
        errors = []
        expression = kwargs.get("expression", "")

        if not expression:
            errors.append("表达式不能为空")

        dangerous = ["import", "exec", "eval", "open", "file", "__"]
        for word in dangerous:
            if word in expression:
                errors.append(f"表达式包含危险关键字: {word}")

        return errors
