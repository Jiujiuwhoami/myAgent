"""Skill 创建模板生成器

生成 Codex 兼容格式的技能模板：
    skills/<skill_name>/
    ├── SKILL.md         # 主说明书（LLM 直接阅读）
    ├── skill.json       # 配置（触发关键词、元数据）
    ├── skill.py         # 执行代码（run 函数）
    ├── references/      # 参考资料（可选）
    └── scripts/         # 辅助脚本（可选）
"""

from pathlib import Path


def create_skill_scaffold(
    skill_name: str,
    output_dir: str = "skills",
    category: str = "custom",
    description: str = "自定义技能",
    author: str = "user",
    version: str = "1.0.0",
) -> Path:
    """创建技能模板骨架

    Args:
        skill_name: 技能名称（如 "code_review"）
        output_dir: 输出目录（如 "skills"）
        category: 技能分类（devops, development, data, research, automation, security, custom）
        description: 技能描述
        author: 作者
        version: 版本号

    Returns:
        技能目录路径
    """
    output_path = Path(output_dir) / skill_name
    output_path.mkdir(parents=True, exist_ok=True)

    # 创建 references 和 scripts 子目录
    (output_path / "references").mkdir(exist_ok=True)
    (output_path / "scripts").mkdir(exist_ok=True)

    # 生成 SKILL.md
    skill_md = f"""# {skill_name.replace('_', ' ').title()}

## 描述

{description}

## 使用场景

当需要执行以下操作时，此技能将被自动触发：

- 示例任务 1
- 示例任务 2
- 示例任务 3

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| param1 | str | 否 | 参数 1 说明 |
| param2 | int | 否 | 参数 2 说明 |

## 示例

```python
# 在 skill.py 中实现
async def run(**kwargs):
    param1 = kwargs.get("param1", "默认值")
    param2 = kwargs.get("param2", 0)

    # 执行逻辑
    result = await execute_task(param1, param2)

    return {{"success": True, "data": result}}
```

## 参考资料

- [参考链接 1](./references/ref1.md)
- [参考链接 2](./references/ref2.md)

## 脚本

- `scripts/helper.sh` - 辅助脚本示例

## 注意事项

- 注意事项 1
- 注意事项 2
"""
    (output_path / "SKILL.md").write_text(skill_md)

    # 生成 skill.json
    skill_json = f"""{{
    "name": "{skill_name}",
    "display_name": "{skill_name.replace('_', ' ').title()}",
    "version": "{version}",
    "description": "{description}",
    "author": "{author}",
    "category": "{category}",
    "enabled": true,
    "trigger": {{
        "trigger_keywords": ["{skill_name}", "{description.split()[0] if description else skill_name}"],
        "negative_keywords": [],
        "confidence_threshold": 0.5
    }},
    "parameters": {{
        "param1": {{"type": "string", "description": "参数 1 说明", "required": false}},
        "param2": {{"type": "integer", "description": "参数 2 说明", "required": false}}
    }},
    "metadata": {{
        "created_at": "auto-generated",
        "tags": ["{category}", "custom"]
    }}
}}
"""
    (output_path / "skill.json").write_text(skill_json)

    # 生成 skill.py
    skill_py = f'''"""{skill_name} 技能执行代码"""
from typing import Dict, Any, Optional


async def run(**kwargs) -> Dict[str, Any]:
    """技能执行入口

    Args:
        **kwargs: 参数，从 skill.json 的 parameters 定义

    Returns:
        {{
            "success": bool,
            "data": Any,
            "error": Optional[str]
        }}
    """
    # 获取参数
    param1 = kwargs.get("param1", "默认值")
    param2 = kwargs.get("param2", 0)

    # 执行逻辑
    # TODO: 实现你的业务逻辑

    return {{
        "success": True,
        "data": {{
            "param1": param1,
            "param2": param2,
            "message": "技能执行成功"
        }},
        "error": None
    }}


async def main(**kwargs) -> Dict[str, Any]:
    """兼容 Codex 格式的 main 函数"""
    return await run(**kwargs)
'''
    (output_path / "skill.py").write_text(skill_py)

    # 生成 .gitignore
    gitignore = """# 忽略临时文件
*.pyc
__pycache__/

# 忽略敏感信息
.env
*.key
"""
    (output_path / ".gitignore").write_text(gitignore)

    return output_path


def create_mcp_tool_template(
    tool_name: str,
    output_dir: str = "mcp_tools",
    description: str = "自定义 MCP 工具",
) -> Path:
    """创建 MCP 工具模板

    Args:
        tool_name: 工具名称
        output_dir: 输出目录
        description: 工具描述

    Returns:
        工具文件路径
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    tool_py = f'''"""MCP 工具模板

使用方法：
    from myAgent.mcp import MCPTool, create_mcp_tool

    # 方式 1: 使用装饰器
    @create_mcp_tool(
        name="{tool_name}",
        description="{description}",
        parameters={{
            "param1": {{"type": "string", "description": "参数 1"}},
            "param2": {{"type": "integer", "description": "参数 2"}}
        }}
    )
    async def my_tool(param1: str, param2: int) -> dict:
        return {{"result": "success"}}

    # 方式 2: 手动创建
    tool = MCPTool(
        name="{tool_name}",
        description="{description}",
        handler=my_handler,
        input_schema={{
            "type": "object",
            "properties": {{
                "param1": {{"type": "string"}},
                "param2": {{"type": "integer"}}
            }},
            "required": ["param1"]
        }}
    )
'''
    (output_path / f"{tool_name}.py").write_text(tool_py)

    return output_path / f"{tool_name}.py"
