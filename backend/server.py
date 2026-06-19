"""FastAPI API 层 - REST 接口

认证方式：JWT Token（Header: X-Token）
权限校验：跨用户操作自动拦截
"""

from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.engine import (
    MultiUserEngine,
    PermissionError,
    TaskPriority,
    TaskState,
    User,
    UserRole,
)

# ========== Pydantic 模型 ==========


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    role: str = "user"
    max_concurrent_tasks: int = 5


class UserLogin(BaseModel):
    username: str
    password: str


class TaskSubmit(BaseModel):
    task_name: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    priority: str = "normal"


class TaskResponse(BaseModel):
    id: str
    user_id: str
    task_name: str
    priority: int
    state: str
    input_data: Dict[str, Any]
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None


class AuthResponse(BaseModel):
    token: str
    user: Dict[str, Any]
    expires_in: int = 86400  # 24 小时


class StatsResponse(BaseModel):
    active_workers: int
    queue_size: int
    user_count: int
    is_running: bool


# ========== 依赖项 ==========


def get_engine() -> MultiUserEngine:
    """获取引擎实例"""
    from .engine import _global_engine

    return _global_engine


def get_current_user(
    x_token: Optional[str] = Header(None),
    engine: MultiUserEngine = Depends(get_engine),
) -> User:
    """获取当前用户（JWT 认证）"""
    if not x_token:
        raise HTTPException(status_code=401, detail="缺少认证 token (X-Token)")

    # 使用 JWT 验证
    user = engine.get_current_user_from_token(x_token)
    if not user:
        raise HTTPException(status_code=401, detail="无效或过期的 JWT token")

    return user


# ========== 创建 FastAPI 应用 ==========


def create_app(engine: MultiUserEngine) -> FastAPI:
    """创建 FastAPI 应用"""

    app = FastAPI(
        title="Agent Runtime API",
        description="基于本地 LLM 的多用户 Agent 后端引擎（JWT 认证 + 权限校验）",
        version="2.1.0",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ========== 用户接口 ==========

    @app.post("/api/v1/users", response_model=AuthResponse)
    async def register(user: UserCreate):
        """注册用户（自动登录）"""
        try:
            role = UserRole(user.role)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的角色")

        engine = get_engine()
        try:
            user_obj = engine.register_user(
                username=user.username,
                password=user.password,
                role=role,
                max_concurrent=user.max_concurrent_tasks,
            )
        except Exception as e:
            if "UNIQUE" in str(e) or "duplicate" in str(e).lower():
                raise HTTPException(status_code=409, detail="用户名已存在")
            raise

        # 自动生成 JWT Token
        token = engine.login(user.username, user.password)

        return AuthResponse(
            token=token,
            user=user_obj.to_dict(),
        )

    @app.post("/api/v1/auth/login", response_model=AuthResponse)
    async def login(user: UserLogin):
        """用户登录（返回 JWT Token）"""
        engine = get_engine()
        token = engine.login(user.username, user.password)

        if not token:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        user_obj = engine.get_current_user(token)

        return AuthResponse(
            token=token,
            user=user_obj.to_dict(),
        )

    @app.post("/api/v1/auth/logout")
    async def logout(
        x_token: str = Header(...),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """用户登出（JWT 无状态，客户端丢弃 token 即可）"""
        # JWT 是无状态的，登出只需客户端丢弃 token
        # 如需强制失效，可加入黑名单机制（此处简化实现）
        return {"message": "已登出"}

    @app.get("/api/v1/users/me")
    async def get_me(user: User = Depends(get_current_user)):
        """获取当前用户信息"""
        return user.to_dict()

    # ========== 任务接口 ==========

    @app.post("/api/v1/tasks", response_model=TaskResponse)
    async def submit_task(
        task: TaskSubmit,
        user: User = Depends(get_current_user),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """提交任务"""
        try:
            priority = TaskPriority(task.priority)
        except ValueError:
            priority = TaskPriority.NORMAL

        queued_task = await engine.submit_task(
            user_id=user.id,
            task_name=task.task_name,
            input_data=task.input_data,
            priority=priority,
        )

        return TaskResponse(
            id=queued_task.id,
            user_id=queued_task.user_id,
            task_name=queued_task.task_name,
            priority=queued_task.priority.value,
            state=queued_task.state.value,
            input_data=queued_task.input_data,
            created_at=queued_task.created_at.isoformat(),
        )

    @app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
    async def get_task(
        task_id: str,
        user: User = Depends(get_current_user),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """获取任务状态（带权限校验）"""
        # 权限校验：用户只能查看自己的任务，管理员可查看所有
        task = await engine.get_task_status(task_id, user.id)
        if not task:
            # 任务不存在或无权限访问
            raise HTTPException(status_code=404, detail="任务不存在或无权访问")

        return TaskResponse(
            id=task.id,
            user_id=task.user_id,
            task_name=task.task_name,
            priority=task.priority.value,
            state=task.state.value,
            input_data=task.input_data,
            created_at=task.created_at.isoformat(),
            started_at=task.started_at.isoformat() if task.started_at else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            result=task.result,
            error=task.error,
        )

    @app.get("/api/v1/tasks", response_model=List[TaskResponse])
    async def list_tasks(
        state: Optional[str] = None,
        limit: int = 50,
        user: User = Depends(get_current_user),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """列出用户任务"""
        task_state = TaskState(state) if state else None
        tasks = engine.db.get_user_tasks(user.id, state=task_state, limit=limit)

        return [
            TaskResponse(
                id=t.id,
                user_id=t.user_id,
                task_name=t.task_name,
                priority=t.priority.value,
                state=t.state.value,
                input_data=t.input_data,
                created_at=t.created_at.isoformat(),
                started_at=t.started_at.isoformat() if t.started_at else None,
                completed_at=t.completed_at.isoformat() if t.completed_at else None,
                result=t.result,
                error=t.error,
            )
            for t in tasks
        ]

    @app.delete("/api/v1/tasks/{task_id}")
    async def cancel_task(
        task_id: str,
        user: User = Depends(get_current_user),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """取消任务（带权限校验）"""
        try:
            success = await engine.cancel_task(task_id, user.id)
        except PermissionError:
            raise HTTPException(status_code=403, detail="无权取消此任务")

        if not success:
            raise HTTPException(status_code=400, detail="无法取消此任务")
        return {"message": "任务已取消"}

    # ========== 系统接口 ==========

    @app.get("/api/v1/stats", response_model=StatsResponse)
    async def get_stats(engine: MultiUserEngine = Depends(get_engine)):
        """获取系统统计"""
        stats = engine.get_stats()
        return StatsResponse(**stats)

    @app.get("/api/v1/health")
    async def health_check():
        """健康检查"""
        return {"status": "ok", "version": "2.1.0"}

    return app
