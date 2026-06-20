# myAgent API 接口文档

## 认证方式
所有需要认证的接口，通过 Header `X-Token: <JWT_TOKEN>` 传递 token。
登录成功后返回的 token 有效期 24 小时。

---

## 1. 用户管理

### POST /api/v1/users
注册用户（自动登录）
- Body: `{"username": "string", "password": "string", "role": "user|admin", "max_concurrent_tasks": 5}`
- 返回: `{token, user: {...}, expires_in: 86400}`
- 重复用户名返回 409，无效角色返回 400

### POST /api/v1/auth/login
用户登录
- Body: `{"username": "string", "password": "string"}`
- 返回: `{token, user: {...}, expires_in: 86400}`

### POST /api/v1/auth/logout
用户登出（JWT 无状态，客户端丢弃 token 即可）

### GET /api/v1/users/me
获取当前用户信息（需认证）

---

## 2. 任务管理

### POST /api/v1/tasks
提交任务
- Body: `{"task_name": "echo|llm_chat|execute_code|http_request|agent_chat|dag", "input_data": {...}, "priority": "low|normal|high"}`
- 返回: `{id, user_id, task_name, priority, state, input_data, created_at}`

### GET /api/v1/tasks
列出当前用户的任务（可加 `?state=pending&limit=50` 过滤）

### GET /api/v1/tasks/{task_id}
获取单个任务详情（含 result、error、started_at 等）

### DELETE /api/v1/tasks/{task_id}
取消任务（pending/running 状态可取消）

### 支持的 task_name 及 input_data 格式：

| 类型 | input_data | 说明 |
|------|-----------|------|
| `echo` | `{"text": "hello"}` | 回显文本 |
| `llm_chat` | `{"prompt": "你好"}` | LLM 对话（RAG 增强） |
| `execute_code` | `{"code": "print('hi')"}` | 执行 Python 代码 |
| `http_request` | `{"url": "...", "method": "GET"}` | HTTP 请求 |
| `agent_chat` | `{"prompt": "..."}` | Agent 对话（Skill 自动触发） |
| `dag` | `{"steps": [...]}` | DAG 工作流 |

---

## 3. RAG 知识库

### POST /api/v1/rag/upload
上传文档到知识库
- Body: `{"title": "文档标题", "content": "段落1\n\n段落2\n\n段落3"}`
- 返回: `{status: "uploaded", chunks: 3, title: "文档标题"}`
- 文档按 `\n\n` 自动切分为段落，每段生成向量存入 Zilliz

### POST /api/v1/rag/search
搜索知识库
- Body: `{"query": "搜索词", "top_k": 3}`
- 返回: `{results: [{score, content, doc_title}], count: N}`

### GET /api/v1/rag/stats
获取知识库统计
- 返回: `{total_entities: N}`

### POST /api/v1/rag/rebuild
重建知识库（删除旧 Collection，准备用新模型重新索引）
- Body: `{"embed_config": {"model": "tf-idf", "dimension": 1536}}`（可选）
- 返回: `{status: "rebuilt", message: "知识库已重建，请重新上传文档"}`

---

## 4. 系统接口

### GET /api/v1/health
健康检查（无需认证）
- 返回: `{"status": "ok", "version": "2.1.0"}`

### GET /api/v1/stats
系统统计（无需认证）
- 返回: `{active_workers, queue_size, user_count, is_running}`

---

## 快速使用示例

```bash
# 1. 注册
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456","role":"admin"}'

# 2. 登录（获取 token）
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 3. 提交 LLM 任务
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Token: $TOKEN" \
  -d '{"task_name":"llm_chat","input_data":{"prompt":"你好"}}'

# 4. 上传知识库文档
curl -X POST http://localhost:8000/api/v1/rag/upload \
  -H "Content-Type: application/json" \
  -H "X-Token: $TOKEN" \
  -d '{"title":"Python教程","content":"Python 是一种高级编程语言。\n\nPython 语法简洁。"}'

# 5. 搜索知识库
curl -X POST http://localhost:8000/api/v1/rag/search \
  -H "Content-Type: application/json" \
  -H "X-Token: $TOKEN" \
  -d '{"query":"Python是什么","top_k":3}'
```
