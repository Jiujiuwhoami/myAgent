# 数据库配置指南

> **说明**: myAgent 框架支持通过配置文件灵活切换数据库类型。

---

## 📊 支持的数据库

| 数据库 | 类型标识 | 适用场景 |
|--------|----------|----------|
| **SQLite** | `sqlite` | 开发/测试、小生产 |
| **PostgreSQL** | `postgresql` | 中大型生产 |
| **MySQL** | `mysql` | 中大型生产 |

---

## 🚀 快速开始

### 方式 1: 使用配置文件（推荐）

```yaml
# myAgent/config/database.yaml

database:
  type: postgresql
  host: localhost
  port: 5432
  name: myagent
  user: myagent
  password: your_password
  pool_size: 5
  max_overflow: 10
  echo: false
```

```python
from myAgent.backend.database import create_database_from_config

db = create_database_from_config("myAgent/config/database.yaml")
db.connect()
```

### 方式 2: 使用环境变量

```bash
# .env
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myagent
DB_USER=myagent
DB_PASSWORD=your_password
```

```python
from myAgent.backend.database import create_database_from_env

db = create_database_from_env()
db.connect()
```

### 方式 3: 代码中直接配置

```python
from myAgent.backend.database import DatabaseConfig, DatabaseType, create_database

config = DatabaseConfig(
    type=DatabaseType.POSTGRESQL,
    host="db.example.com",
    port=5432,
    name="production",
    user="admin",
    password="secret",
)

db = create_database(config)
db.connect()
```

---

## 📋 配置文件示例

### SQLite（开发环境）

```yaml
database:
  type: sqlite
  path: agent_engine.db
  echo: false
```

### PostgreSQL（生产环境）

```yaml
database:
  type: postgresql
  host: db.example.com
  port: 5432
  name: myagent_production
  user: myagent_app
  password: ${DB_PASSWORD}  # 支持环境变量
  pool_size: 10
  max_overflow: 20
  echo: false
```

### MySQL（生产环境）

```yaml
database:
  type: mysql
  host: db.example.com
  port: 3306
  name: myagent_production
  user: myagent_app
  password: ${DB_PASSWORD}
  pool_size: 10
  max_overflow: 20
  echo: false
```

---

## 🔧 集成到 myAgent 引擎

### 修改 MultiUserEngine

```python
# myAgent/backend/engine.py

from .database import create_database, DatabaseConfig

class MultiUserEngine:
    def __init__(
        self,
        db_path: str = None,
        db_config: DatabaseConfig = None,
        db_config_path: str = None,
        ...
    ):
        # 支持多种初始化方式
        if db_config_path:
            self.db = create_database_from_config(db_config_path)
        elif db_config:
            self.db = create_database(db_config)
        elif db_path:
            # 兼容旧代码
            self.db = create_database(DatabaseConfig(path=db_path))
        else:
            self.db = create_database(DatabaseConfig())
        
        self.db.connect()
```

### 使用示例

```python
# 使用配置文件
engine = MultiUserEngine(db_config_path="config/database.yaml")

# 使用代码配置
from myAgent.backend.database import DatabaseConfig, DatabaseType

config = DatabaseConfig(type=DatabaseType.POSTGRESQL, ...)
engine = MultiUserEngine(db_config=config)

# 使用环境变量
engine = MultiUserEngine()  # 自动读取环境变量
```

---

## 📦 依赖安装

```bash
# SQLite（Python 内置，无需安装）

# PostgreSQL
pip install asyncpg

# MySQL
pip install pymysql
```

---

## 🔄 迁移指南

### 从 SQLite 迁移到 PostgreSQL

#### 步骤 1: 准备 PostgreSQL

```bash
# 安装 PostgreSQL
sudo apt install postgresql

# 创建数据库
sudo -u postgres createdb myagent

# 创建用户
sudo -u postgres createuser -P myagent  # 会提示输入密码
```

#### 步骤 2: 修改配置

```yaml
# myAgent/config/database.yaml
database:
  type: postgresql
  host: localhost
  port: 5432
  name: myagent
  user: myagent
  password: your_password
```

#### 步骤 3: 迁移数据

```python
# migrate_data.py
from myAgent.backend.database import create_database_from_config

# 读取 SQLite
sqlite_db = create_database_from_config("config/sqlite.yaml")
sqlite_db.connect()

# 写入 PostgreSQL
pg_db = create_database_from_config("config/postgresql.yaml")
pg_db.connect()

# 迁移数据
users = sqlite_db.fetch_all("SELECT * FROM users")
for user in users:
    pg_db.execute(
        "INSERT INTO users (id, username, ...) VALUES (%s, %s, ...)",
        (user["id"], user["username"], ...)
    )
```

---

## ⚠️ 注意事项

| 项目 | SQLite | PostgreSQL/MySQL |
|------|--------|------------------|
| **并发写入** | ❌ 不支持 | ✅ 支持 |
| **连接池** | ❌ 无 | ✅ 有 |
| **异步支持** | ❌ 无 | ✅ PostgreSQL 有 |
| **事务** | ✅ 支持 | ✅ 支持 |
| **数据量** | < 1GB 推荐 | 无限制 |
| **部署复杂度** | 简单 | 需要独立服务器 |

---

## 📊 性能对比

| 场景 | SQLite | PostgreSQL |
|------|--------|------------|
| **读取性能** | 快 | 快 |
| **写入性能** | 慢（锁表） | 快（行锁） |
| **并发连接** | 有限 | 高并发 |
| **100 卖家** | ✅ 足够 | ✅ 足够 |
| **1000 卖家** | ⚠️ 可能瓶颈 | ✅ 推荐 |
| **10000+ 卖家** | ❌ 不推荐 | ✅ 必需 |

---

## 🎯 推荐配置

| 阶段 | 数据库 | 配置 |
|------|--------|------|
| **开发** | SQLite | 单文件，零配置 |
| **测试** | SQLite | 内存数据库 `path=:memory:` |
| **小生产** | SQLite | 单文件，定期备份 |
| **中生产** | PostgreSQL | 连接池 10-20 |
| **大生产** | PostgreSQL + Redis | 主从复制，缓存加速 |

---

## 📎 相关文档

- [myAgent 框架文档](../README.md)
- [数据库架构设计](../../customer_service_backend/docs/database-design.md)

---

*文档版本: 1.0*
*最后更新: 2026-05-31*
