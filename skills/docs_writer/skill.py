"""文档撰写技能 - 自动化技术文档生成"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict


async def generate_readme(source_path: str, output_path: str = ".") -> Dict[str, Any]:
    """生成 README 文档"""
    source = Path(source_path)

    # 分析项目结构
    files = list(source.glob("**/*"))
    python_files = [f for f in files if f.suffix == ".py"]
    [f for f in files if f.suffix == ".md"]

    readme_content = f"""# 项目文档

## 概述

本项目包含 {len(python_files)} 个 Python 文件。

## 项目结构

```
{source.name}/
```

## 安装

```bash
pip install -r requirements.txt
```

## 使用

```python
from {source.name} import main

main()
```

## 开发

```bash
pytest tests/
```

## 许可证

MIT
"""

    output_file = Path(output_path) / "README.md"
    output_file.write_text(readme_content, encoding="utf-8")

    return {
        "success": True,
        "output_file": str(output_file),
        "message": f"README 已生成: {output_file}",
    }


async def generate_changelog(changes: list, output_path: str = ".") -> Dict[str, Any]:
    """生成变更日志"""
    today = datetime.now().strftime("%Y-%m-%d")

    changelog_content = f"""# Changelog

所有 notable 的变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

---

## [{today}] - {today}

### Added
- 新功能列表

### Changed
- 变更列表

### Fixed
- 修复列表

"""

    output_file = Path(output_path) / "CHANGELOG.md"
    output_file.write_text(changelog_content, encoding="utf-8")

    return {
        "success": True,
        "output_file": str(output_file),
        "message": f"CHANGELOG 已生成: {output_file}",
    }


async def run(
    doc_type: str,
    source_path: str,
    output_format: str = "markdown",
    output_path: str = ".",
    **kwargs,
) -> Dict[str, Any]:
    """
    文档撰写技能主函数

    Args:
        doc_type: 文档类型 (readme/api/design/changelog/user_guide)
        source_path: 源代码路径
        output_format: 输出格式
        output_path: 输出路径

    Returns:
        生成结果
    """
    if doc_type == "readme":
        return await generate_readme(source_path, output_path)
    elif doc_type == "changelog":
        changes = kwargs.get("changes", [])
        return await generate_changelog(changes, output_path)
    else:
        return {"success": False, "error": f"不支持的文档类型: {doc_type}"}
