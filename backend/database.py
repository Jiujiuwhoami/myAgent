"""数据库抽象层 - 支持多种数据库

通过配置文件灵活切换数据库类型：
- SQLite (开发/测试)
- PostgreSQL (生产)
- MySQL (生产)

使用方式:
    # 配置文件 config.yaml
    database:
      type: postgresql
      host: localhost
      port: 5432
      name: myagent
      user: myagent
      password: xxx

    # 代码中使用
    from myAgent.backend.database import create_database
    db = create_database(config)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class DatabaseType(Enum):
    """数据库类型"""

    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


@dataclass
class DatabaseConfig:
    """数据库配置"""

    type: DatabaseType = DatabaseType.SQLITE
    host: Optional[str] = None
    port: Optional[int] = None
    name: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    path: Optional[str] = None  # SQLite 文件路径
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "DatabaseConfig":
        """从字典创建配置"""
        db_type = config.get("type", "sqlite")
        return cls(
            type=DatabaseType(db_type),
            host=config.get("host"),
            port=config.get("port", 5432 if db_type != "sqlite" else None),
            name=config.get("name"),
            user=config.get("user"),
            password=config.get("password"),
            path=config.get("path", "agent_engine.db"),
            pool_size=config.get("pool_size", 5),
            max_overflow=config.get("max_overflow", 10),
            echo=config.get("echo", False),
        )

    @classmethod
    def from_yaml(cls, path: str) -> "DatabaseConfig":
        """从 YAML 文件加载配置"""
        import yaml

        with open(path, "r") as f:
            config = yaml.safe_load(f)
        return cls.from_dict(config.get("database", {}))

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """从环境变量加载配置"""
        import os

        db_type = os.environ.get("DB_TYPE", "sqlite")

        if db_type == "sqlite":
            return cls(
                type=DatabaseType.SQLITE,
                path=os.environ.get("DB_PATH", "agent_engine.db"),
            )
        else:
            return cls(
                type=DatabaseType(db_type),
                host=os.environ.get("DB_HOST", "localhost"),
                port=int(os.environ.get("DB_PORT", 5432)),
                name=os.environ.get("DB_NAME"),
                user=os.environ.get("DB_USER"),
                password=os.environ.get("DB_PASSWORD"),
            )

    def to_url(self) -> str:
        """生成数据库连接 URL"""
        if self.type == DatabaseType.SQLITE:
            return f"sqlite:///{self.path}"
        elif self.type == DatabaseType.POSTGRESQL:
            return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        elif self.type == DatabaseType.MYSQL:
            return (
                f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
            )
        else:
            raise ValueError(f"不支持的数据库类型：{self.type}")


class BaseDatabase(ABC):
    """数据库抽象基类"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._connection = None

    @abstractmethod
    def connect(self):
        """连接数据库"""
        pass

    @abstractmethod
    def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    def execute(self, sql: str, params: tuple = None) -> Any:
        """执行 SQL"""
        pass

    @abstractmethod
    def fetch_all(self, sql: str, params: tuple = None) -> List[Dict]:
        """查询所有"""
        pass

    @abstractmethod
    def fetch_one(self, sql: str, params: tuple = None) -> Optional[Dict]:
        """查询一条"""
        pass

    @abstractmethod
    def begin_transaction(self):
        """开始事务"""
        pass

    @abstractmethod
    def commit(self):
        """提交事务"""
        pass

    @abstractmethod
    def rollback(self):
        """回滚事务"""
        pass


class SQLiteDatabase(BaseDatabase):
    """SQLite 数据库适配器"""

    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self._connection = None

    def connect(self):
        """连接 SQLite"""
        import sqlite3

        self._connection = sqlite3.connect(
            self.config.path or "agent_engine.db",
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        return self

    def disconnect(self):
        """断开连接"""
        if self._connection:
            self._connection.close()
            self._connection = None

    def execute(self, sql: str, params: tuple = None) -> Any:
        """执行 SQL"""
        if not self._connection:
            self.connect()
        cursor = self._connection.cursor()
        cursor.execute(sql, params or ())
        self._connection.commit()
        return cursor

    def fetch_all(self, sql: str, params: tuple = None) -> List[Dict]:
        """查询所有"""
        if not self._connection:
            self.connect()
        cursor = self._connection.cursor()
        cursor.execute(sql, params or ())
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def fetch_one(self, sql: str, params: tuple = None) -> Optional[Dict]:
        """查询一条"""
        if not self._connection:
            self.connect()
        cursor = self._connection.cursor()
        cursor.execute(sql, params or ())
        row = cursor.fetchone()
        return dict(row) if row else None

    def begin_transaction(self):
        """开始事务"""
        pass  # SQLite 自动管理

    def commit(self):
        """提交事务"""
        if self._connection:
            self._connection.commit()

    def rollback(self):
        """回滚事务"""
        if self._connection:
            self._connection.rollback()


class PostgreSQLDatabase(BaseDatabase):
    """PostgreSQL 数据库适配器"""

    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self._connection = None
        self._pool = None

    def connect(self):
        """连接 PostgreSQL"""
        try:
            import asyncpg
        except ImportError:
            raise ImportError("请安装 asyncpg: pip install asyncpg")

        self._pool = asyncpg.create_pool(
            host=self.config.host,
            port=self.config.port,
            database=self.config.name,
            user=self.config.user,
            password=self.config.password,
            min_size=self.config.pool_size,
            max_size=self.config.pool_size + self.config.max_overflow,
        )
        return self

    async def connect_async(self):
        """异步连接"""
        if self._pool:
            await self._pool.close()
        self._pool = await asyncpg.create_pool(
            host=self.config.host,
            port=self.config.port,
            database=self.config.name,
            user=self.config.user,
            password=self.config.password,
            min_size=self.config.pool_size,
            max_size=self.config.pool_size + self.config.max_overflow,
        )
        return self

    def disconnect(self):
        """断开连接"""
        if self._pool:
            self._pool.close()
            self._pool = None

    def execute(self, sql: str, params: tuple = None) -> Any:
        """执行 SQL"""
        raise NotImplementedError("PostgreSQL 请使用异步接口")

    async def execute_async(self, sql: str, params: tuple = None) -> Any:
        """异步执行 SQL"""
        if not self._pool:
            raise RuntimeError("数据库未连接")
        async with self._pool.acquire() as conn:
            return await conn.execute(sql, *params or ())

    async def fetch_all_async(self, sql: str, params: tuple = None) -> List[Dict]:
        """异步查询所有"""
        if not self._pool:
            raise RuntimeError("数据库未连接")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params or ())
            return [dict(row) for row in rows]

    async def fetch_one_async(self, sql: str, params: tuple = None) -> Optional[Dict]:
        """异步查询一条"""
        if not self._pool:
            raise RuntimeError("数据库未连接")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, *params or ())
            return dict(row) if row else None

    def begin_transaction(self):
        """开始事务"""
        raise NotImplementedError("PostgreSQL 请使用异步接口")

    def commit(self):
        """提交事务"""
        raise NotImplementedError("PostgreSQL 使用事务块")

    def rollback(self):
        """回滚事务"""
        raise NotImplementedError("PostgreSQL 使用事务块")


class MySQLDatabase(BaseDatabase):
    """MySQL 数据库适配器"""

    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self._connection = None
        self._pool = None

    def connect(self):
        """连接 MySQL"""
        try:
            import pymysql
        except ImportError:
            raise ImportError("请安装 pymysql: pip install pymysql")

        self._connection = pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            database=self.config.name,
            user=self.config.user,
            password=self.config.password,
            cursorclass=pymysql.cursors.DictCursor,
        )
        return self

    def disconnect(self):
        """断开连接"""
        if self._connection:
            self._connection.close()
            self._connection = None

    def execute(self, sql: str, params: tuple = None) -> Any:
        """执行 SQL"""
        if not self._connection:
            self.connect()
        cursor = self._connection.cursor()
        cursor.execute(sql, params or ())
        self._connection.commit()
        return cursor

    def fetch_all(self, sql: str, params: tuple = None) -> List[Dict]:
        """查询所有"""
        if not self._connection:
            self.connect()
        cursor = self._connection.cursor()
        cursor.execute(sql, params or ())
        return cursor.fetchall()

    def fetch_one(self, sql: str, params: tuple = None) -> Optional[Dict]:
        """查询一条"""
        if not self._connection:
            self.connect()
        cursor = self._connection.cursor()
        cursor.execute(sql, params or ())
        return cursor.fetchone()

    def begin_transaction(self):
        """开始事务"""
        if self._connection:
            self._connection.begin()

    def commit(self):
        """提交事务"""
        if self._connection:
            self._connection.commit()

    def rollback(self):
        """回滚事务"""
        if self._connection:
            self._connection.rollback()


# ========== 工厂函数 ==========


def create_database(config: DatabaseConfig) -> BaseDatabase:
    """创建数据库实例（工厂函数）"""
    if config.type == DatabaseType.SQLITE:
        return SQLiteDatabase(config)
    elif config.type == DatabaseType.POSTGRESQL:
        return PostgreSQLDatabase(config)
    elif config.type == DatabaseType.MYSQL:
        return MySQLDatabase(config)
    else:
        raise ValueError(f"不支持的数据库类型：{config.type}")


def create_database_from_config(config_path: str) -> BaseDatabase:
    """从配置文件创建数据库"""
    config = DatabaseConfig.from_yaml(config_path)
    return create_database(config)


def create_database_from_env() -> BaseDatabase:
    """从环境变量创建数据库"""
    config = DatabaseConfig.from_env()
    return create_database(config)
