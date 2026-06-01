# 数据可视化指南

## Matplotlib 基础

```python
import matplotlib.pyplot as plt

# 折线图
plt.plot(x, y)
plt.xlabel("X 轴")
plt.ylabel("Y 轴")
plt.title("标题")
plt.show()

# 保存
plt.savefig("output.png", dpi=300, bbox_inches="tight")
```

## Seaborn 统计图

```python
import seaborn as sns

# 分布图
sns.histplot(data, x="column")

# 箱线图
sns.boxplot(data, x="category", y="value")

# 热力图
sns.heatmap(correlation_matrix, annot=True)

# 成对关系图
sns.pairplot(data)
```

## 图表类型选择

| 目的 | 推荐图表 |
|------|----------|
| 趋势 | 折线图 |
| 分布 | 直方图、箱线图 |
| 比较 | 柱状图 |
| 关系 | 散点图 |
| 占比 | 饼图、环形图 |
| 相关性 | 热力图 |

## 最佳实践

1. **选择合适的图表类型**
2. **添加清晰的标签和标题**
3. **使用有意义的颜色**
4. **避免过度装饰**
5. **确保图表可读性**

## 中文支持

```python
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False
```
