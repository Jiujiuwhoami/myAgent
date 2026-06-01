# 🤖 我的 Agent OS

这是一个**完全从零构建**的完整 Agent 运行时系统，支持本地 LLM 集成！

**🆕 v2.1 新增**: 多用户后端引擎、API 服务器

---

## 📁 项目结构

```
myAgent/
├── __init__.py              # 包初始化
├── README.md                 # 本文件
├── main.py                  # 🚀 主入口
├── server.py                # 🆕 API 服务器入口
│
├── core/                    # 核心组件
│   ├── types.py             # 核心类型
│   ├── task.py              # 任务模型和状态机
│   ├── executor.py          # 工具执行器
│   ├── dag.py               # DAG 和调度器
│   ├── memory.py            # 三层记忆系统
│   ├── event_bus.py         # 事件总线
│   └── checkpoint.py        # 检查点系统
│
├── backend_engine.py        # 🆕 多用户后端引擎
│   ├── MultiUserEngine      # 核心引擎
│   ├── Database             # SQLite 数据库
│   ├── UserRuntime          # 用户隔离运行时
│   └── TaskQueue            # 优先级任务队列
│
├── api_server.py            # 🆕 FastAPI API 层
│
├── llm_client.py            # 本地 LLM 客户端
├── llm_agent.py             # LLM 智能代理
├── streaming.py             # 流式输出支持
├── intervention.py          # 人类介入支持
├── nested_dag.py            # 子图嵌套支持
├── skills/                  # 🆕 技能系统
│   ├── code_review/         # 代码审查技能
│   ├── cli.py               # 技能管理 CLI
│   └── __init__.py          # 技能核心模块
├── plugins/                 # 🆕 插件化工具系统
│   ├── weather/            # 天气插件示例
│   ├── calculator/         # 计算器插件示例
│   └── search/             # 搜索插件示例
└── docs/                    # 使用文档
```

---

## 🎯 功能特性

| 功能 | 模块 | 说明 |
|------|------|------|
| 任务管理 | `core/task.py` | Task 模型 + FSM 状态机 |
| 工具执行 | `core/executor.py` | 支持同步/异步工具 |
| DAG 调度 | `core/dag.py` | 有向无环图 + 调度器 |
| 记忆系统 | `core/memory.py` | Working/Episodic/Semantic |
| 事件总线 | `core/event_bus.py` | 发布/订阅系统 |
| 检查点 | `core/checkpoint.py` | 状态持久化 |
| **本地 LLM** | `llm_client.py` | **Qwen3-4B @ 192.168.3.191:8080** |
| **智能代理** | `llm_agent.py` | **LLM + 工具调用 + 多步推理** |
| **流式输出** | `streaming.py` | **逐 token 流式传输** |
| **人类介入** | `intervention.py` | **Human-in-the-loop** |
| **子图嵌套** | `nested_dag.py` | **层次化 DAG** |
| **🆕 多用户后端** | `backend_engine.py` | **用户隔离 + 并发控制** |
| **🆕 API 服务器** | `api_server.py` | **FastAPI REST 接口** |
| **🆕 Skill 系统** | `skills/` | **可复用工作流管理** |

---

## 🚀 快速开始

### 本地演示模式

```bash
cd /mnt/c/Users/六度的电脑/Desktop/agent_runtime_training
python -m myAgent.server --mode demo
```

### 启动 API 服务器

```bash
# 启动服务器
python -m myAgent.server --mode server --host 0.0.0.0 --port 8000

# 或使用环境变量
export AGENT_DB_PATH=/path/to/database.db
export AGENT_MAX_WORKERS=10
python -m myAgent.server --mode server
```

### API 文档

启动服务器后访问：
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **健康检查**: http://localhost:8000/api/v1/health

---

## 📊 多用户后端引擎架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI API Server                          │
│  /api/v1/users      /api/v1/auth      /api/v1/tasks             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MultiUserEngine                               │
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐    │
│  │   Database     │  │   TaskQueue    │  │   Session      │    │
│  │   (SQLite)     │  │   (Priority)   │  │   Cache        │    │
│  └────────────────┘  └────────────────┘  └────────────────┘    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │              User Runtimes (隔离)                        │     │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐             │     │
│  │  │ User A   │  │ User B   │  │ User C   │             │     │
│  │  │ Runtime  │  │ Runtime  │  │ Runtime  │             │     │
│  │  └──────────┘  └──────────┘  └──────────┘             │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Worker Pool (并发处理)                         │
│  Worker 0  Worker 1  Worker 2  ...  Worker N                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    本地 LLM (Qwen3-4B)                            │
│                    http://192.168.3.191:8080                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔑 核心特性

### 1. 用户隔离

每个用户拥有独立的 AgentRuntime 实例，互不干扰：

```python
from myAgent.backend_engine import MultiUserEngine

engine = MultiUserEngine()

# 用户 A 的运行时
runtime_a = engine.get_user_runtime(user_a_id)

# 用户 B 的运行时
runtime_b = engine.get_user_runtime(user_b_id)

# 两者完全隔离
```

### 2. 并发控制

每个用户可以配置最大并发任务数：

```python
# 创建用户，限制并发数为 3
user = engine.register_user("alice", "password", max_concurrent=3)

# 提交第 4 个任务会失败
task = await engine.submit_task(user.id, "task", {})
# ValueError: 达到并发限制: 3/3
```

### 3. 优先级队列

任务支持优先级（LOW < NORMAL < HIGH < CRITICAL）：

```python
from myAgent.backend_engine import TaskPriority

# 高优先级任务先执行
task = await engine.submit_task(
    user_id, "紧急任务", {"data": "..."},
    priority=TaskPriority.CRITICAL
)
```

### 4. 数据库持久化

所有数据持久化到 SQLite（可升级到 PostgreSQL）：

```sql
-- 用户表
CREATE TABLE users (id, username, password_hash, role, ...);

-- 会话表
CREATE TABLE sessions (session_id, user_id, token, ...);

-- 任务表
CREATE TABLE tasks (id, user_id, task_name, state, ...);
```

### 5. API 接口

完整的 REST API：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/users` | 注册用户 |
| POST | `/api/v1/auth/login` | 用户登录 |
| POST | `/api/v1/auth/logout` | 用户登出 |
| POST | `/api/v1/tasks` | 提交任务 |
| GET | `/api/v1/tasks/{id}` | 获取任务状态 |
| GET | `/api/v1/tasks` | 列出用户任务 |
| DELETE | `/api/v1/tasks/{id}` | 取消任务 |
| GET | `/api/v1/stats` | 系统统计 |
| GET | `/api/v1/health` | 健康检查 |

---

## 📝 API 使用示例

### 注册和登录

```bash
# 注册
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "password123"}'

# 登录
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "password123"}'

# 返回: {"token": "uuid...", "user": {...}}
```

### 提交任务

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Token: <your_token>" \
  -d '{"task_name": "测试任务", "input_data": {"message": "Hello"}}'
```

### 查询任务状态

```bash
curl http://localhost:8000/api/v1/tasks/task_id \
  -H "X-Token: <your_token>"
```

---

##  与 LangGraph 对比

| 功能 | LangGraph | 我们的项目 v2.1 |
|------|-----------|-----------------|
| 流式输出 | ✅ 原生 | ✅ 已实现 |
| 人类介入 | ✅ 原生 | ✅ 已实现 |
| 子图嵌套 | ✅ 原生 | ✅ 已实现 |
| **多用户** | ❌ 需自研 | ✅ **已实现** |
| **API 服务器** | ❌ 需自研 | ✅ **已实现** |
| 依赖大小 | ~50MB+ | ~5MB |
| 学习曲线 | 陡峭 | 平缓 |
| 本地 LLM | 需配置 | ✅ 原生 |

---

## 🏗️ 从零构建！

- ✅ 所有核心组件都在 `core/` 目录
- ✅ 完整的类型定义和数据结构
- ✅ 本地 LLM 集成（Qwen3-4B）
- ✅ 流式输出、人类介入、子图嵌套
- ✅ **多用户后端引擎**
- ✅ **FastAPI API 服务器**
- ✅ 可以直接运行！

---

祝你玩得开心！🎊
