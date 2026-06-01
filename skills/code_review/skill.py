"""代码审查技能 - 分析代码质量、安全漏洞和最佳实践"""

import re
from typing import Any, Dict

# 常见安全模式
SECURITY_PATTERNS = {
    "sql_injection": [
        r"execute\s*\(\s*['\"]?\s*SELECT",
        r"cursor\.execute\s*\(\s*f['\"]",
        r"execute\s*\(.*\+\s*.*",
    ],
    "xss": [
        r"innerHTML\s*=",
        r"document\.write\s*\(",
        r"eval\s*\(",
    ],
    "command_injection": [
        r"os\.system\s*\(",
        r"subprocess\.call\s*\(.*shell\s*=\s*True",
        r"subprocess\.Popen\s*\(.*shell\s*=\s*True",
    ],
    "hardcoded_secret": [
        r"password\s*=\s*['\"]\w+['\"]",
        r"api_key\s*=\s*['\"]\w+['\"]",
        r"secret\s*=\s*['\"]\w+['\"]",
        r"token\s*=\s*['\"]\w+['\"]",
    ],
    "unsafe_deserialization": [
        r"pickle\.loads?\s*\(",
        r"yaml\.load\s*\([^)]*Loader\s*=\s*None",
    ],
}

# 代码风格模式
STYLE_PATTERNS = {
    "long_line": (r".{120,}", "行过长（>120 字符）"),
    "magic_number": (r"(?<!\w)\b(?!0|x)[1-9]\d{2,}\b(?!\w)", "魔术数字，建议定义为常量"),
    "missing_docstring": (r"^(def|class)\s+\w+", "缺少文档字符串"),
}


async def run(
    file_path: str,
    check_style: bool = True,
    check_security: bool = True,
    max_issues: int = 10,
    **kwargs,
) -> Dict[str, Any]:
    """
    代码审查技能主函数

    Args:
        file_path: 要审查的文件路径
        check_style: 是否检查代码风格
        check_security: 是否检查安全问题
        max_issues: 最大问题数

    Returns:
        审查结果
    """
    from pathlib import Path

    file_path = Path(file_path)
    if not file_path.exists():
        return {"success": False, "error": f"文件不存在: {file_path}"}

    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    issues = []
    lines_scanned = len(lines)

    # 安全检查
    if check_security:
        for category, patterns in SECURITY_PATTERNS.items():
            for pattern in patterns:
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line):
                        issues.append(
                            {
                                "type": "security",
                                "category": category,
                                "line": i,
                                "message": f"潜在安全问题: {category}",
                                "code": line.strip()[:80],
                            }
                        )

    # 风格检查
    if check_style:
        for category, (pattern, message) in STYLE_PATTERNS.items():
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    issues.append(
                        {
                            "type": "style",
                            "category": category,
                            "line": i,
                            "message": message,
                            "code": line.strip()[:80],
                        }
                    )

    # 限制问题数
    issues = issues[:max_issues]

    # 分类统计
    errors = len([i for i in issues if i["type"] == "security"])
    warnings = len([i for i in issues if i["type"] == "style"])

    return {
        "success": True,
        "file": str(file_path),
        "summary": {
            "lines_scanned": lines_scanned,
            "total_issues": len(issues),
            "errors": errors,
            "warnings": warnings,
        },
        "issues": issues,
        "recommendations": (
            [
                "使用参数化查询防止 SQL 注入",
                "避免使用 eval() 和 exec()",
                "将魔术数字定义为常量",
                "为函数和类添加文档字符串",
            ]
            if issues
            else ["代码质量良好，无重大问题"]
        ),
    }
