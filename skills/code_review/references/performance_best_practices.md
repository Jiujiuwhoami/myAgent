# Performance Best Practices

## 性能优化检查清单

### ⚡ 数据库性能

- [ ] **N+1 查询** — 检查循环中的数据库查询
  - 使用 `SELECT_related` / `JOIN` 预加载
  - 使用 `IN` 查询批量获取
  
- [ ] **索引缺失** — 检查查询是否使用索引
  - 为 WHERE/ORDER BY 列添加索引
  - 避免 `SELECT *`
  
- [ ] **慢查询** — 检查慢查询日志
  - 分析执行计划
  - 优化复杂查询

### 🖥️ 内存管理

- [ ] **内存泄漏** — 检查未释放的资源
  - 关闭文件句柄、数据库连接
  - 清理全局缓存
  
- [ ] **大对象处理** — 检查大文件/数据流处理
  - 使用流式处理而非一次性加载
  - 分页处理大数据集

### 🌐 网络性能

- [ ] **API 调用优化** — 检查外部 API 调用
  - 批量请求而非逐个请求
  - 添加缓存层
  
- [ ] **连接池** — 检查数据库/HTTP 连接池
  - 复用连接而非每次创建
  - 设置合理的超时

### 📦 缓存策略

- [ ] **缓存命中率** — 检查缓存使用
  - 热点数据预加载
  - 设置合理的 TTL
  
- [ ] **缓存失效** — 检查缓存更新策略
  - 写穿/写回策略
  - 缓存版本管理

### 🔄 异步处理

- [ ] **阻塞操作** — 检查同步阻塞调用
  - 使用异步 I/O
  - 后台任务队列
  
- [ ] **并发控制** — 检查并发限制
  - 限制并发数避免资源耗尽
  - 使用信号量控制

## 性能分析工具

```bash
# Python 性能分析
python -m cProfile -o profile.stats script.py
snakeviz profile.stats

# 内存分析
memory_profiler script.py

# 数据库查询分析
EXPLAIN ANALYZE SELECT ...

# 网络请求分析
# 使用浏览器 DevTools Network 面板
```

## 性能基准

| 操作 | 目标延迟 | 警告阈值 |
|------|----------|----------|
| API 响应 | < 200ms | > 500ms |
| 数据库查询 | < 50ms | > 100ms |
| 页面加载 | < 2s | > 5s |
| 文件读取 | < 100ms | > 500ms |

## 参考资源

- [Google Web Vitals](https://web.dev/vitals/)
- [Database Performance Tuning](https://www.oracle.com/database/technologies/appdev/tuning.html)
- [Python Performance Tips](https://wiki.python.org/moin/PythonSpeed/PerformanceTips)
