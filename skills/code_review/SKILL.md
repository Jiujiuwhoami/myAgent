# Code Review Skill

## Description
代码审查技能，检查安全、性能、架构问题

## Purpose
对代码进行全面的自动化审查，生成结构化的审查报告。适用于 PR 审查、代码提交前检查、技术债务识别等场景。

## Workflow

1. **预检查** — 运行 lint 和静态分析工具
2. **安全审查** — 检查常见安全漏洞（SQL 注入、XSS、硬编码密钥等）
3. **性能审查** — 检查性能问题（N+1 查询、内存泄漏、未关闭资源等）
4. **架构审查** — 检查代码结构、依赖关系、设计模式
5. **生成报告** — 输出结构化审查报告

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| file_path | string | Yes | 要审查的文件路径 |
| check_security | boolean | No | 是否检查安全问题，默认 true |
| check_performance | boolean | No | 是否检查性能问题，默认 true |
| check_architecture | boolean | No | 是否检查架构问题，默认 true |
| output_format | string | No | 输出格式：markdown/json，默认 markdown |

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Code Review Skill                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │ Pre-     │───▶│ Security │───▶│ Performance│         │
│  │ Check    │    │ Review   │    │ Review    │          │
│  └──────────┘    └──────────┘    └──────────┘          │
│       │               │               │                 │
│       ▼               ▼               ▼                 │
│  ┌──────────────────────────────────────────┐          │
│  │           Architecture Review            │          │
│  └──────────────────────────────────────────┘          │
│                       │                                 │
│                       ▼                                 │
│  ┌──────────────────────────────────────────┐          │
│  │           Report Generation              │          │
│  └──────────────────────────────────────────┘          │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## References

- [Security Checklist](references/security_checklist.md) — 安全审查清单
- [Performance Best Practices](references/performance_best_practices.md) — 性能最佳实践

## Scripts

| Script | Description |
|--------|-------------|
| `scripts/pre_check.sh` | 运行预检查（lint、格式检查） |
| `scripts/generate_report.py` | 生成结构化审查报告 |

## Tools Used

- `terminal` — 执行 lint 和静态分析工具
- `file` — 读取和分析代码文件
- `search` — 搜索相关代码模式

## Examples

### 基本使用

```bash
# 审查单个文件
skill run code_review --file src/main.py

# 审查整个目录
skill run code_review --path src/
```

### 自定义选项

```bash
# 只检查安全问题
skill run code_review --file src/main.py --check_security true --check_performance false

# JSON 格式输出
skill run code_review --file src/main.py --output_format json
```

### 在 PR 中使用

```bash
# 审查 PR 变更
skill run code_review --pr 123
```

## Output Format

### Markdown 报告

```markdown
# Code Review Report

**File:** src/main.py
**Date:** 2026-05-31
**Overall Score:** 85/100

## Summary

- 🔴 Critical Issues: 2
- 🟡 Warnings: 5
- 🟢 Suggestions: 3

## Critical Issues

### 1. SQL Injection Vulnerability [SEC-001]
**Location:** src/main.py:45
**Severity:** Critical
**Description:** User input directly concatenated into SQL query
**Recommendation:** Use parameterized queries

### 2. Hardcoded Secret [SEC-002]
**Location:** src/main.py:12
**Severity:** Critical
**Description:** API key hardcoded in source code
**Recommendation:** Use environment variables

## Warnings

...

## Suggestions

...
```

### JSON 报告

```json
{
  "file": "src/main.py",
  "date": "2026-05-31",
  "overall_score": 85,
  "issues": [
    {
      "id": "SEC-001",
      "type": "security",
      "severity": "critical",
      "location": {"file": "src/main.py", "line": 45},
      "description": "...",
      "recommendation": "..."
    }
  ]
}
```

## Credits

参考 OpenAI Codex Skill 规范和 Claude Code Skill 架构设计。
