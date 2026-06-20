"""多用户后端引擎 - 支持并发和隔离

核心设计：
- 用户隔离：每个用户独立的 Runtime 实例
- 任务队列：异步队列管理并发任务
- API 层：FastAPI REST 接口
- 数据库：SQLite 持久化（可升级到 PostgreSQL）
- 认证：JWT Token 认证（已升级）
- 资源限制：每个用户的并发数限制
- 权限校验：跨用户操作权限控制（已增强）
"""

import asyncio
import hashlib
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import jwt  # JWT 认证

# JWT 配置（生产环境应从环境变量读取）
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "myagent-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


class UserRole(Enum):
    """用户角色"""

    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class TaskPriority(Enum):
    """任务优先级"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class TaskState(Enum):
    """任务状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ========== 权限校验异常 ==========


class PermissionError(Exception):
    """权限错误"""

    pass


class AuthenticationError(Exception):
    """认证错误"""

    pass


@dataclass
class User:
    """用户"""

    id: str
    username: str
    password_hash: str
    role: UserRole = UserRole.USER
    max_concurrent_tasks: int = 5
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role.value,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


@dataclass
class JWTToken:
    """JWT Token 信息"""

    user_id: str
    username: str
    role: str
    exp: datetime
    iat: datetime

    @classmethod
    def from_payload(cls, payload: Dict) -> "JWTToken":
        return cls(
            user_id=payload["sub"],
            username=payload["username"],
            role=payload["role"],
            exp=datetime.fromtimestamp(payload["exp"]),
            iat=datetime.fromtimestamp(payload["iat"]),
        )


@dataclass
class QueuedTask:
    """队列中的任务"""

    id: str
    user_id: str
    task_name: str
    priority: TaskPriority
    input_data: Dict[str, Any]
    state: TaskState
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "task_name": self.task_name,
            "priority": self.priority.value,
            "input_data": self.input_data,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
        }


class Database:
    """数据库 - SQLite"""

    def __init__(self, db_path: str = "agent_engine.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    max_concurrent_tasks INTEGER DEFAULT 5,
                    created_at TEXT,
                    last_login TEXT
                )
            """
            )
            # 保留 sessions 表用于兼容，但不再使用
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token TEXT NOT NULL,
                    created_at TEXT,
                    expires_at TEXT,
                    is_valid INTEGER DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    priority INTEGER DEFAULT 2,
                    input_data TEXT,
                    state TEXT DEFAULT 'pending',
                    created_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    result TEXT,
                    error TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT DEFAULT '',
                    created_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id)")
            conn.commit()

    def create_user(
        self, username: str, password: str, role: UserRole = UserRole.USER, max_concurrent: int = 5
    ) -> User:
        user_id = str(uuid.uuid4())
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    username,
                    password_hash,
                    role.value,
                    max_concurrent,
                    datetime.now().isoformat(),
                    None,
                ),
            )
            conn.commit()

        return User(
            id=user_id,
            username=username,
            password_hash=password_hash,
            role=role,
            max_concurrent_tasks=max_concurrent,
        )

    def get_user(self, user_id: str) -> Optional[User]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row:
                return User(
                    id=row["id"],
                    username=row["username"],
                    password_hash=row["password_hash"],
                    role=UserRole(row["role"]),
                    max_concurrent_tasks=row["max_concurrent_tasks"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    last_login=(
                        datetime.fromisoformat(row["last_login"]) if row["last_login"] else None
                    ),
                )
        return None

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? AND password_hash = ?",
                (username, password_hash),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE users SET last_login = ? WHERE id = ?",
                    (datetime.now().isoformat(), row["id"]),
                )
                conn.commit()
                return User(
                    id=row["id"],
                    username=row["username"],
                    password_hash=row["password_hash"],
                    role=UserRole(row["role"]),
                    max_concurrent_tasks=row["max_concurrent_tasks"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    last_login=(
                        datetime.fromisoformat(row["last_login"]) if row["last_login"] else None
                    ),
                )
        return None

    def get_user_active_tasks(self, user_id: str) -> int:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM tasks WHERE user_id = ? AND state IN ('pending', 'running')",
                (user_id,),
            ).fetchone()
            return row["count"] if row else 0

    def create_task(self, task: QueuedTask):
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.id,
                    task.user_id,
                    task.task_name,
                    task.priority.value,
                    json.dumps(task.input_data),
                    task.state.value,
                    task.created_at.isoformat(),
                    task.started_at.isoformat() if task.started_at else None,
                    task.completed_at.isoformat() if task.completed_at else None,
                    json.dumps(task.result) if task.result else None,
                    task.error,
                ),
            )
            conn.commit()

    def update_task(self, task_id: str, **kwargs):
        if not kwargs:
            return
        fields = []
        values = []
        for key, value in kwargs.items():
            if value is None:
                fields.append(f"{key} = NULL")
            elif isinstance(value, (dict, list)):
                fields.append(f"{key} = ?")
                values.append(json.dumps(value))
            elif isinstance(value, datetime):
                fields.append(f"{key} = ?")
                values.append(value.isoformat())
            else:
                fields.append(f"{key} = ?")
                values.append(value)
        values.append(task_id)
        with self._get_connection() as conn:
            conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()

    def get_task(self, task_id: str) -> Optional[QueuedTask]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row:
                return QueuedTask(
                    id=row["id"],
                    user_id=row["user_id"],
                    task_name=row["task_name"],
                    priority=TaskPriority(row["priority"]),
                    input_data=json.loads(row["input_data"]) if row["input_data"] else {},
                    state=TaskState(row["state"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    started_at=(
                        datetime.fromisoformat(row["started_at"]) if row["started_at"] else None
                    ),
                    completed_at=(
                        datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
                    ),
                    result=json.loads(row["result"]) if row["result"] else None,
                    error=row["error"],
                )
        return None

    def get_user_tasks(
        self, user_id: str, state: Optional[TaskState] = None, limit: int = 50
    ) -> List[QueuedTask]:
        with self._get_connection() as conn:
            if state:
                rows = conn.execute(
                    """SELECT * FROM tasks WHERE user_id = ? AND state = ? ORDER BY created_at DESC LIMIT ?""",
                    (user_id, state.value, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC LIMIT ?""",
                    (user_id, limit),
                ).fetchall()
            return [
                QueuedTask(
                    id=row["id"],
                    user_id=row["user_id"],
                    task_name=row["task_name"],
                    priority=TaskPriority(row["priority"]),
                    input_data=json.loads(row["input_data"]) if row["input_data"] else {},
                    state=TaskState(row["state"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    started_at=(
                        datetime.fromisoformat(row["started_at"]) if row["started_at"] else None
                    ),
                    completed_at=(
                        datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
                    ),
                    result=json.loads(row["result"]) if row["result"] else None,
                    error=row["error"],
                )
                for row in rows
            ]

    # ========== 会话管理 ==========

    def create_conversation(self, user_id: str, title: str = "") -> Dict:
        conv_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO conversations VALUES (?, ?, ?, ?)",
                (conv_id, user_id, title, datetime.now().isoformat()),
            )
            conn.commit()
        return {"id": conv_id, "user_id": user_id, "title": title, "created_at": datetime.now().isoformat()}

    def get_conversations(self, user_id: str, limit: int = 50) -> List[Dict]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM conversations WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_messages(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def add_message(self, conversation_id: str, role: str, content: str) -> str:
        msg_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?)",
                (msg_id, conversation_id, role, content, datetime.now().isoformat()),
            )
            conn.commit()
        return msg_id

    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT user_id FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if not row or row["user_id"] != user_id:
                return False
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()
            return True


class UserRuntime:
    """用户运行时 - 支持用户级 Skill/MCP 隔离"""

    def __init__(self, user_id: str, user: User, db: Database):
        self.user_id = user_id
        self.user = user
        self.db = db
        # 轻量模式：不创建完整 AgentRuntime 以节省内存
        self.runtime = None

    def get_runtime(self):
        return self.runtime

    def get_skills(self, scope: Optional[str] = None) -> List[Dict]:
        return []

    def get_mcp_tools(self, scope: Optional[str] = None) -> List[Dict]:
        return []

    def get_status(self) -> Dict:
        return {
            "user_id": self.user_id,
            "username": self.user.username,
            "runtime": "lightweight",
        }


class TaskQueue:
    """任务队列"""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._user_task_counts: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def enqueue(self, task: QueuedTask):
        priority_value = task.priority.value
        timestamp = task.created_at.timestamp()
        await self._queue.put((priority_value, timestamp, task))

    async def dequeue(self, user_id: str, user_max_concurrent: int) -> Optional[QueuedTask]:
        async with self._lock:
            current_count = self._user_task_counts.get(user_id, 0)
            if current_count >= user_max_concurrent:
                return None

        try:
            priority, timestamp, task = await asyncio.wait_for(self._queue.get(), timeout=1.0)

            if task.user_id != user_id:
                await self._queue.put((priority, timestamp, task))
                return None

            async with self._lock:
                self._user_task_counts[user_id] = self._user_task_counts.get(user_id, 0) + 1

            return task
        except asyncio.TimeoutError:
            return None

    def complete_task(self, user_id: str):
        count = self._user_task_counts.get(user_id, 0)
        self._user_task_counts[user_id] = max(0, count - 1)

    async def cancel_task(self, task_id: str):
        pass


class MultiUserEngine:
    """多用户后端引擎（JWT 认证 + 权限校验增强版）"""

    _global_instance: Optional["MultiUserEngine"] = None

    def __init__(
        self,
        db_path: str = "agent_engine.db",
        max_workers: int = 4,
        llm_config: Optional[Any] = None,
        jwt_secret_key: Optional[str] = None,
        rag_config: Optional[Dict] = None,
    ):
        self.db = Database(db_path)
        self.task_queue = TaskQueue(max_workers)
        self.llm_config = llm_config
        self.jwt_secret_key = jwt_secret_key or JWT_SECRET_KEY
        self.rag_config = rag_config or {}
        self.rag_store = None
        if self.rag_config.get("enabled", False):
            try:
                from myAgent.backend.rag_store import RAGStore
                self.rag_store = RAGStore(
                    zilliz_uri=self.rag_config["uri"],
                    zilliz_token=self.rag_config["token"],
                )
                print(f"   [OK] RAG enabled: Zilliz connected")
            except Exception as e:
                print(f"   [WARN] RAG init failed: {e}")
        self._user_runtimes: Dict[str, UserRuntime] = {}
        self._worker_tasks: List[asyncio.Task] = []
        self._is_running = False

    # ========== JWT 认证 ==========

    def create_jwt_token(self, user: User, expiration_hours: int = JWT_EXPIRATION_HOURS) -> str:
        """创建 JWT Token"""
        now = datetime.utcnow()
        payload = {
            "sub": user.id,
            "username": user.username,
            "role": user.role.value,
            "iat": now,
            "exp": now + timedelta(hours=expiration_hours),
        }
        token = jwt.encode(payload, self.jwt_secret_key, algorithm=JWT_ALGORITHM)
        return token

    def decode_jwt_token(self, token: str) -> Optional[JWTToken]:
        """验证并解码 JWT Token"""
        try:
            payload = jwt.decode(token, self.jwt_secret_key, algorithms=[JWT_ALGORITHM])
            return JWTToken.from_payload(payload)
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def get_current_user_from_token(self, token: str) -> Optional[User]:
        """从 JWT Token 获取当前用户"""
        jwt_info = self.decode_jwt_token(token)
        if not jwt_info:
            return None
        user = self.db.get_user(jwt_info.user_id)
        return user

    # ========== 用户管理 ==========

    def register_user(
        self, username: str, password: str, role=None, max_concurrent: int = 5
    ) -> User:
        """注册用户

        Args:
            username: 用户名
            password: 密码
            role: 角色（UserRole 枚举或字符串 "admin"/"user"/"guest"）
            max_concurrent: 最大并发任务数
        """
        # 兼容字符串和枚举
        if role is None:
            role = UserRole.USER
        elif isinstance(role, str):
            role = UserRole(role.lower())

        user = self.db.create_user(username, password, role, max_concurrent)
        return user

    def login(self, username: str, password: str) -> Optional[str]:
        """用户登录，返回 JWT Token"""
        user = self.db.authenticate_user(username, password)
        if not user:
            return None
        # 生成 JWT Token 替代 Session
        token = self.create_jwt_token(user)
        return token

    def logout(self, token: str) -> bool:
        """用户登出（JWT 无需服务端状态，客户端丢弃 token 即可）"""
        # JWT 是无状态的，登出只需客户端丢弃 token
        # 如需强制失效，可加入黑名单机制（此处简化实现）
        return True

    def get_current_user(self, token: str) -> Optional[User]:
        """从 JWT Token 获取当前用户（兼容旧接口）"""
        return self.get_current_user_from_token(token)

    # ========== 权限校验 ==========

    def verify_task_access(self, user_id: str, task_id: str) -> bool:
        """验证用户是否有权限访问任务（跨用户查询权限校验）"""
        task = self.db.get_task(task_id)
        if not task:
            return False
        # 权限校验：任务必须属于当前用户，或当前用户是管理员
        if task.user_id == user_id:
            return True
        user = self.db.get_user(user_id)
        if user and user.role == UserRole.ADMIN:
            return True
        return False

    def verify_task_operation(self, user_id: str, task_id: str) -> None:
        """验证用户是否有权限操作任务（抛出异常）"""
        if not self.verify_task_access(user_id, task_id):
            raise PermissionError(f"用户 {user_id} 无权访问任务 {task_id}")

    # ========== 用户运行时 ==========

    def get_user_runtime(self, user_id: str) -> UserRuntime:
        if user_id not in self._user_runtimes:
            user = self.db.get_user(user_id)
            if not user:
                raise ValueError(f"用户不存在: {user_id}")
            self._user_runtimes[user_id] = UserRuntime(user_id, user, self.db)
        return self._user_runtimes[user_id]

    # ========== 任务管理 ==========

    async def submit_task(
        self,
        user_id: str,
        task_name: str,
        input_data: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> QueuedTask:
        user = self.db.get_user(user_id)
        if not user:
            raise ValueError(f"用户不存在: {user_id}")

        active_count = self.db.get_user_active_tasks(user_id)
        if active_count >= user.max_concurrent_tasks:
            raise ValueError(f"达到并发限制: {active_count}/{user.max_concurrent_tasks}")

        task = QueuedTask(
            id=str(uuid.uuid4()),
            user_id=user_id,
            task_name=task_name,
            priority=priority,
            input_data=input_data,
            state=TaskState.PENDING,
        )

        self.db.create_task(task)
        await self.task_queue.enqueue(task)
        return task

    async def get_task_status(self, task_id: str, user_id: str) -> Optional[QueuedTask]:
        """获取任务状态（带权限校验）"""
        # 权限校验：用户只能查看自己的任务，管理员可查看所有
        if not self.verify_task_access(user_id, task_id):
            return None  # 返回 None 而非抛出异常，避免信息泄露
        return self.db.get_task(task_id)

    async def cancel_task(self, task_id: str, user_id: str) -> bool:
        """取消任务（带权限校验）"""
        # 权限校验
        self.verify_task_operation(user_id, task_id)

        task = self.db.get_task(task_id)
        if not task:
            return False
        if task.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
            return False
        self.db.update_task(task_id, state=TaskState.CANCELLED.value)
        return True

    async def update_task_result(
        self, task_id: str, user_id: str, result: Dict, error: Optional[str] = None
    ) -> bool:
        """更新任务结果（带权限校验）"""
        # 权限校验
        self.verify_task_operation(user_id, task_id)

        self.db.update_task(
            task_id,
            state=TaskState.COMPLETED.value,
            completed_at=datetime.now(),
            result=result,
            error=error,
        )
        return True

    # ========== 后台处理 ==========

    async def _worker(self, worker_id: int):
        print(f"🔄 Worker {worker_id} 启动")

        # 延迟导入 LLM client，避免启动时连接
        llm_client = None
        if self.llm_config:
            try:
                from myAgent.llm.client import LLMClient
                llm_client = LLMClient(self.llm_config)
                print(f"   [OK] LLM ready: {self.llm_config.model} @ {self.llm_config.base_url}")
            except Exception as e:
                print(f"   [WARN] LLM init failed: {e}")

        while self._is_running:
            try:
                item = await self.task_queue._queue.get()
                priority, timestamp, task = item

                # 轻量级执行：不创建完整 AgentRuntime，直接标记完成
                task.started_at = datetime.now()
                self.db.update_task(
                    task.id,
                    state=TaskState.RUNNING.value,
                    started_at=task.started_at,
                )

                try:
                    task_type = task.input_data.get("type", "echo")
                    
                    if task_type == "llm_chat" and llm_client:
                        # LLM 推理任务（RAG 增强 + 会话历史）
                        prompt = task.input_data.get("prompt", "")
                        system = task.input_data.get("system", "你是一个有帮助的AI助手。")
                        from myAgent.llm.client import Message
                        
                        # 加载会话历史
                        conversation_id = task.input_data.get("conversation_id", "")
                        messages = []
                        if conversation_id:
                            # 确保任务属于该用户
                            with self.db._get_connection() as conn:
                                row = conn.execute(
                                    "SELECT user_id FROM conversations WHERE id = ?", (conversation_id,)
                                ).fetchone()
                                if row and row["user_id"] == task.user_id:
                                    hist_msgs = self.db.get_messages(conversation_id, limit=20)
                                    for m in hist_msgs:
                                        messages.append(Message(m["role"], m["content"]))
                        
                        # RAG 检索增强
                        rag_context = ""
                        if self.rag_store and prompt:
                            try:
                                results = self.rag_store.search(
                                    query=prompt,
                                    user_id=task.user_id,
                                    top_k=3,
                                )
                                if results:
                                    rag_docs = "\n\n--- 参考知识 ---\n" + "\n".join(
                                        f"[{i+1}] {r['content'][:500]}" for i, r in enumerate(results)
                                    )
                                    rag_context = rag_docs
                                    task.result = {"rag_hits": len(results)}
                            except Exception:
                                pass  # RAG 失败不影响 LLM 调用
                        
                        # 构建消息列表
                        if messages:
                            # 有历史：system + history + user
                            messages.insert(0, Message("system", system + rag_context))
                        else:
                            # 无历史：system + user
                            messages = [
                                Message("system", system + rag_context),
                                Message("user", prompt),
                            ]
                        
                        response = llm_client.chat(messages=messages)
                        task.result = {"output": response.content, "model": response.model}
                        if response.usage:
                            task.result["usage"] = response.usage
                        
                        # 保存会话历史
                        if conversation_id:
                            self.db.add_message(conversation_id, "user", prompt)
                            self.db.add_message(conversation_id, "assistant", response.content)
                        
                        task.state = TaskState.COMPLETED if response.finish_reason != "error" else TaskState.FAILED
                        if task.state == TaskState.FAILED:
                            task.error = response.content
                    
                    elif task_type == "execute_code":
                        # 代码执行任务
                        code = task.input_data.get("code", "")
                        result = await self._execute_code(code)
                        task.result = result
                        task.state = TaskState.COMPLETED
                    
                    elif task_type == "http_request":
                        # HTTP 请求任务
                        method = task.input_data.get("method", "GET").upper()
                        url = task.input_data.get("url", "")
                        headers = task.input_data.get("headers", {})
                        body = task.input_data.get("body", None)
                        result = await self._http_request(method, url, headers, body)
                        task.result = result
                        task.state = TaskState.COMPLETED
                    
                    elif task_type == "dag":
                        # DAG 多步骤任务
                        result = await self._execute_dag(task)
                        task.result = result
                        task.state = TaskState.COMPLETED
                    
                    else:
                        # 默认 echo
                        msg = task.input_data.get("msg", "任务完成")
                        task.result = {"output": msg}
                        task.state = TaskState.COMPLETED
                        
                except Exception as e:
                    task.state = TaskState.FAILED
                    task.error = str(e)

                # Skill 自动触发：检查任务描述是否匹配已注册的技能
                skill_triggered = False
                # 只对 echo 类型的任务触发 Skill，避免覆盖 LLM/代码/HTTP 任务的结果
                if task_type == "echo" and not task.error:
                    try:
                        task_desc = task.task_name + " " + json.dumps(task.input_data, ensure_ascii=False)
                        from myAgent.skills import SkillManager
                        sm = SkillManager()
                        sm.discover()
                        best = sm.find_best_match(task_desc)
                        if best:
                            skill_name, config, confidence = best
                            if config.enabled and confidence >= config.trigger.min_confidence:
                                print(f"   🎯 Skill 自动触发: {config.display_name} (confidence={confidence:.2f})")
                                # 将 task_input 中的键作为关键字参数传入
                                skill_kwargs = {k: v for k, v in task.input_data.items() if k != "type"}
                                try:
                                    skill_result = await sm.run_skill(skill_name, **skill_kwargs)
                                except TypeError as te:
                                    # 参数不匹配，记录警告但继续
                                    print(f"   [WARN] Skill params mismatch: {te}")
                                    skill_result = {"success": False, "error": f"Skill参数不匹配: {te}"}
                                task.result = skill_result
                                skill_triggered = True
                    except Exception as se:
                        print(f"   [WARN] Skill trigger failed: {se}")

                task.completed_at = datetime.now()
                self.db.update_task(
                    task.id,
                    state=task.state.value,
                    completed_at=task.completed_at,
                    result=task.result,
                    error=task.error,
                )

                self.task_queue.complete_task(task.user_id)
                self.task_queue._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Worker {worker_id} 错误: {e}")

    async def _execute_code(self, code: str) -> Dict:
        """安全地执行 Python 代码（沙箱模式）"""
        import io
        import contextlib
        
        try:
            # 限制代码长度
            if len(code) > 5000:
                return {"error": "代码过长（最大 5000 字符）"}
            
            # 捕获 stdout
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exec(code, {"__builtins__": {"print": print, "len": len, "range": range, "str": str, "int": int, "float": float, "list": list, "dict": dict, "tuple": tuple, "set": set, "sum": sum, "max": max, "min": min, "abs": abs, "round": round, "sorted": sorted, "reversed": reversed, "enumerate": enumerate, "zip": zip, "map": map, "filter": filter, "isinstance": isinstance, "type": type, "bool": bool, "chr": chr, "ord": ord, "hex": hex, "oct": oct, "pow": pow, "divmod": divmod}})
            
            return {"output": output.getvalue(), "status": "success"}
        except Exception as e:
            return {"error": str(e), "status": "failed"}

    async def _http_request(self, method: str, url: str, headers: Dict, body: Any) -> Dict:
        """发起 HTTP 请求"""
        import httpx
        
        try:
            if not url:
                return {"error": "URL 不能为空"}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                kwargs = {"headers": headers}
                if body and isinstance(body, dict):
                    kwargs["json"] = body
                elif body:
                    kwargs["data"] = body
                
                response = await client.request(method, url, **kwargs)
                return {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text[:10000],  # 限制响应体大小
                }
        except Exception as e:
            return {"error": str(e)}

    async def _execute_dag(self, task: QueuedTask) -> Dict:
        """执行 DAG 多步骤任务"""
        from myAgent.core.dag import DAG, DAGNode, DAGScheduler
        
        dag_config = task.input_data.get("dag", {})
        nodes_cfg = dag_config.get("nodes", [])
        
        if not nodes_cfg:
            return {"error": "DAG 配置为空"}
        
        # 构建 DAG
        dag = DAG(name=task.task_name)
        for nc in nodes_cfg:
            node = DAGNode(
                id=nc.get("id", ""),
                name=nc.get("name", ""),
                node_type=nc.get("type", "task"),
                input_data=nc.get("input", {}),
            )
            dag.add_node(node)
        
        # 添加边
        for nc in nodes_cfg:
            for dep in nc.get("depends_on", []):
                try:
                    dag.add_edge(dep, nc["id"])
                except ValueError:
                    pass
        
        if dag.has_cycle():
            return {"error": "DAG 包含环"}
        
        # 创建简易执行器
        async def default_executor(node, input_data):
            # 根据 node_type 执行不同类型
            nt = node.node_type
            inp = input_data or {}
            if nt == "llm":
                from myAgent.llm.client import LLMClient
                client = LLMClient(self.llm_config)
                resp = client.chat(prompt=inp.get("prompt", ""))
                return {"output": resp.content}
            elif nt == "compute":
                return {"result": inp.get("value", 0) * 2}
            else:
                return {"output": str(inp)}
        
        scheduler = DAGScheduler(dag, max_parallel=2)
        scheduler.register_node_executor("default", default_executor)
        
        # 为每个节点注册执行器
        for nc in nodes_cfg:
            scheduler.register_node_executor(nc["id"], default_executor)
        
        results = await scheduler.run()
        return {"results": results, "node_count": dag.node_count}

    async def start(self):
        if self._is_running:
            return
        self._is_running = True
        for i in range(self.task_queue.max_workers):
            task = asyncio.create_task(self._worker(i))
            self._worker_tasks.append(task)
        print(f"✅ 多用户引擎已启动 (workers={self.task_queue.max_workers})")

    async def stop(self):
        self._is_running = False
        for task in self._worker_tasks:
            task.cancel()
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()
        print("✅ 多用户引擎已停止")

    # ========== 统计 ==========

    def get_stats(self) -> Dict:
        return {
            "active_workers": len(self._worker_tasks),
            "queue_size": self.task_queue._queue.qsize(),
            "user_count": 0,
            "is_running": self._is_running,
        }


# 全局引擎实例
_global_engine: Optional[MultiUserEngine] = None
