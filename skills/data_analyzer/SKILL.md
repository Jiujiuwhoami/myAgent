# 数据分析技能

## 概述

自动化数据分析技能，支持数据探索、统计分析和可视化报告生成。

## 使用场景

- 探索性数据分析（EDA）
- 统计分析和假设检验
- 数据清洗和预处理
- 生成数据可视化报告
- 时间序列分析

## 工作流程

```
1. 加载数据（CSV/Excel/JSON/数据库）
2. 数据概览（形状、类型、缺失值）
3. 描述性统计
4. 数据可视化
5. 生成分析报告
```

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `data_path` | string | 是 | 数据文件路径 |
| `analysis_type` | string | 否 | 分析类型（eda/statistics/visualization） |
| `output_format` | string | 否 | 输出格式（report/html/notebook） |

## 支持的格式

- CSV
- Excel (.xlsx)
- JSON
- Parquet
- 数据库（PostgreSQL, MySQL）

## References

- [Pandas 最佳实践](references/pandas_best_practices.md)
- [可视化指南](references/visualization_guide.md)
