# Pandas 最佳实践

## 数据加载

```python
import pandas as pd

# CSV
df = pd.read_csv("data.csv", encoding="utf-8")

# Excel
df = pd.read_excel("data.xlsx", sheet_name=0)

# JSON
df = pd.read_json("data.json")
```

## 数据概览

```python
# 基本信息
df.info()

# 描述性统计
df.describe()

# 前 5 行
df.head()

# 数据类型
df.dtypes

# 缺失值统计
df.isnull().sum()
```

## 数据清洗

```python
# 删除缺失值
df.dropna()

# 填充缺失值
df.fillna(value)

# 删除重复值
df.drop_duplicates()

# 数据类型转换
df["column"] = df["column"].astype("int")
```

## 数据筛选

```python
# 条件筛选
df[df["column"] > 100]

# 多条件
df[(df["col1"] > 100) & (df["col2"] == "A")]

# 使用 query
df.query("column > 100 and category == 'A'")
```

## 数据聚合

```python
# 分组聚合
df.groupby("category").agg({"value": ["mean", "sum"]})

# 透视表
df.pivot_table(values="value", index="category", columns="month")
```

## 性能优化

1. **使用合适的数据类型**（category 用于分类变量）
2. **避免链式索引**（使用 .loc）
3. **使用向量化操作**（避免循环）
4. **大文件使用 chunksize**
