"""test_custom_skill_final 技能执行代码"""

from typing import Any, Dict


async def run(**kwargs) -> Dict[str, Any]:
    """技能执行入口

    Args:
        **kwargs: 参数，从 skill.json 的 parameters 定义

    Returns:
        {
            "success": bool,
            "data": Any,
            "error": Optional[str]
        }
    """
    # 获取参数
    param1 = kwargs.get("param1", "默认值")
    param2 = kwargs.get("param2", 0)

    # 执行逻辑
    # TODO: 实现你的业务逻辑

    return {
        "success": True,
        "data": {"param1": param1, "param2": param2, "message": "技能执行成功"},
        "error": None,
    }


async def main(**kwargs) -> Dict[str, Any]:
    """兼容 Codex 格式的 main 函数"""
    return await run(**kwargs)
