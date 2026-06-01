# 文档撰写技能

## 概述

自动化技术文档撰写技能，支持 API 文档、README、设计文档等。

## 使用场景

- 生成 API 文档（OpenAPI/Swagger）
- 编写项目 README
- 创建架构设计文档
- 生成变更日志（CHANGELOG）
- 编写用户手册

## 工作流程

```
1. 分析代码/项目结构
2. 提取关键信息（API、组件、依赖）
3. 生成文档草稿
4. 格式化输出（Markdown/HTML）
5. 输出文档
```

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `doc_type` | string | 是 | 文档类型（readme/api/design/changelog） |
| `source_path` | string | 是 | 源代码/项目路径 |
| `output_format` | string | 否 | 输出格式（markdown/html，默认 markdown） |
| `output_path` | string | 否 | 输出路径（默认当前目录） |

## 支持的文档类型

- `readme` - 项目 README.md
- `api` - API 文档（从代码注释生成）
- `design` - 架构设计文档
- `changelog` - 变更日志
- `user_guide` - 用户手册

## References

- [Markdown 最佳实践](references/markdown_best_practices.md)
- [文档模板库](references/templates/)
