"""FastAPI API 层 - REST 接口

认证方式：JWT Token（Header: X-Token）
权限校验：跨用户操作自动拦截
"""

from typing import Any, Dict, List, Optional
import asyncio
import json

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

    # ========== RAG API ==========

    class DocumentUpload(BaseModel):
        title: str = Field(..., min_length=1, max_length=256)
        content: str = Field(..., min_length=1)

    @app.post("/api/v1/rag/upload")
    async def upload_document(
        payload: DocumentUpload,
        token: str = Header(..., alias="X-Token"),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """上传文档到 RAG 知识库"""
        user = engine.get_current_user_from_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="无效的认证 token")
        
        if not engine.rag_store:
            raise HTTPException(status_code=503, detail="RAG 服务未启用")
        
        # 切分文档（按段落）
        from backend.rag_store import DocumentChunk
        paragraphs = [p.strip() for p in payload.content.split("\n\n") if p.strip()]
        chunks = [
            DocumentChunk(
                user_id=user.id,
                doc_title=payload.title,
                content=p,
                metadata={"source": "upload"},
            ) for p in paragraphs
        ]
        
        count = engine.rag_store.insert_documents(chunks)
        return {"status": "uploaded", "chunks": count, "title": payload.title}

    @app.post("/api/v1/rag/search")
    async def search_rag(
        payload: Dict[str, Any],
        token: str = Header(..., alias="X-Token"),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """搜索 RAG 知识库"""
        user = engine.get_current_user_from_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="无效的认证 token")
        
        if not engine.rag_store:
            raise HTTPException(status_code=503, detail="RAG 服务未启用")
        
        query = payload.get("query", "")
        top_k = payload.get("top_k", 3)
        
        results = engine.rag_store.search(query=query, user_id=user.id, top_k=top_k)
        return {"results": results, "count": len(results)}

    @app.get("/api/v1/rag/stats")
    async def rag_stats(
        token: str = Header(..., alias="X-Token"),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """获取 RAG 统计信息"""
        user = engine.get_current_user_from_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="无效的认证 token")
        
        if not engine.rag_store:
            raise HTTPException(status_code=503, detail="RAG 服务未启用")
        
        stats = engine.rag_store.get_stats()
        return stats

    @app.post("/api/v1/rag/rebuild")
    async def rebuild_rag(
        payload: Optional[Dict[str, Any]] = None,
        token: str = Header(..., alias="X-Token"),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """重建知识库（删除旧 Collection 并用新模型重新索引）"""
        user = engine.get_current_user_from_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="无效的认证 token")
        
        if not engine.rag_store:
            raise HTTPException(status_code=503, detail="RAG 服务未启用")
        
        rag_store = engine.rag_store
        
        # 更新 Embedding 配置
        embed_config = (payload or {}).get("embed_config", {})
        if embed_config:
            from backend.rag_store import EmbeddingClient
            rag_store.embed_client = EmbeddingClient(
                model=embed_config.get("model", "tf-idf"),
                base_url=embed_config.get("base_url", ""),
                api_key=embed_config.get("api_key", ""),
                dimension=embed_config.get("dimension", 1536),
            )
        
        # 标记 Collection 需要重建（下次操作时自动重建）
        rag_store._need_rebuild = True
        
        return {
            "status": "rebuilt",
            "message": "知识库已重建，请重新上传文档",
        }

    # ========== 聊天接口（Manus 风格）==========

    class ChatRequest(BaseModel):
        message: str = Field(..., min_length=1, description="用户消息")
        system: str = Field("你是一个有帮助的AI助手。", description="系统提示词")
        rag: bool = Field(True, description="是否启用知识库检索增强")
        model: Optional[str] = Field(None, description="指定模型（可选）")
        conversation_id: Optional[str] = Field(None, description="会话ID（用于多轮对话）")

    class ChatResponse(BaseModel):
        reply: str
        model: str
        rag_used: bool = False
        rag_hits: int = 0

    @app.post("/api/v1/chat", response_model=ChatResponse)
    async def chat(
        req_body: ChatRequest,
        token: str = Header(..., alias="X-Token"),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """同步聊天（基于任务队列，支持 RAG）
        
        提交 llm_chat 任务后立即轮询结果，对外表现为同步接口。
        """
        user = engine.get_current_user_from_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="无效的认证 token")
        
        # 提交任务到队列
        task_input: Dict[str, Any] = {
            "type": "llm_chat",
            "prompt": req_body.message,
            "system": req_body.system,
        }
        if req_body.rag:
            task_input["rag"] = True
        task = await engine.submit_task(
            user_id=user.id,
            task_name="llm_chat",
            input_data=task_input,
        )
        
        # 轮询等待结果（最多 60 秒）
        import asyncio
        for _ in range(60):
            await asyncio.sleep(1)
            task_info = await engine.get_task_status(task.id, user.id)
            if task_info and task_info.state.value == "completed":
                result = task_info.result or {}
                output = result.get("output", "")
                model = result.get("model", "unknown")
                rag_hits = result.get("rag_hits", 0)
                return ChatResponse(
                    reply=output,
                    model=model,
                    rag_used=bool(rag_hits),
                    rag_hits=rag_hits,
                )
            elif task_info and task_info.state.value == "failed":
                raise HTTPException(status_code=500, detail=task_info.error or "任务失败")
        
        raise HTTPException(status_code=504, detail="LLM 响应超时")

    @app.post("/api/v1/chat/stream")
    async def chat_stream(
        req_body: ChatRequest,
        token: str = Header(..., alias="X-Token"),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """流式聊天（基于任务队列 + SSE）
        
        提交任务后轮询结果，通过 SSE 逐 chunk 推送。
        """
        from fastapi.responses import StreamingResponse
        
        user = engine.get_current_user_from_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="无效的认证 token")
        
        # 提交任务到队列
        task_input: Dict[str, Any] = {
            "type": "llm_chat",
            "prompt": req_body.message,
            "system": req_body.system,
        }
        task = await engine.submit_task(
            user_id=user.id,
            task_name="llm_chat",
            input_data=task_input,
        )
        
        async def event_generator():
            # 等待任务完成，逐 chunk 推送
            import asyncio
            try:
                for _ in range(60):
                    await asyncio.sleep(1)
                    task_info = await engine.get_task_status(task.id, user.id)
                    if not task_info:
                        continue
                    
                    if task_info.state.value == "completed":
                        result = task_info.result or {}
                        output = result.get("output", "")
                        model = result.get("model", "unknown")
                        rag_hits = result.get("rag_hits", 0)
                        
                        yield f"data: {{\"type\": \"start\", \"model\": {json.dumps(model)}, \"rag_used\": {json.dumps(bool(rag_hits))}, \"rag_hits\": {rag_hits}}}\n\n"
                        
                        # 逐 chunk 发送
                        for i in range(0, len(output), 10):
                            chunk = output[i:i+10]
                            yield f"data: {{\"type\": \"chunk\", \"text\": {json.dumps(chunk, ensure_ascii=False)}}}\n\n"
                            await asyncio.sleep(0.01)
                        
                        yield f"data: {{\"type\": \"done\"}}\n\n"
                        return
                    
                    elif task_info.state.value == "failed":
                        err_msg = task_info.error or "任务失败"
                        yield f"data: {{\"type\": \"error\", \"message\": {json.dumps(err_msg)}}}\n\n"
                        return
                
                yield f"data: {{\"type\": \"error\", \"message\": \"响应超时\"}}\n\n"
            except GeneratorExit:
                pass  # 客户端断开连接
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # ========== 会话管理接口 ==========

    class ConversationCreate(BaseModel):
        title: Optional[str] = ""

    @app.post("/api/v1/conversations")
    async def create_conversation(
        payload: ConversationCreate,
        token: str = Header(..., alias="X-Token"),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """创建新会话"""
        user = engine.get_current_user_from_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="无效的认证 token")
        conv = engine.db.create_conversation(user.id, payload.title or "新对话")
        return conv

    @app.get("/api/v1/conversations")
    async def list_conversations(
        token: str = Header(..., alias="X-Token"),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """列出用户的所有会话"""
        user = engine.get_current_user_from_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="无效的认证 token")
        return engine.db.get_conversations(user.id)

    @app.get("/api/v1/conversations/{conv_id}/messages")
    async def get_messages(
        conv_id: str,
        token: str = Header(..., alias="X-Token"),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """获取会话消息历史"""
        user = engine.get_current_user_from_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="无效的认证 token")
        msgs = engine.db.get_messages(conv_id)
        # 权限校验
        conv_row = engine.db._get_connection().execute(
            "SELECT user_id FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        if conv_row and conv_row["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="无权访问此会话")
        return msgs

    @app.delete("/api/v1/conversations/{conv_id}")
    async def delete_conversation(
        conv_id: str,
        token: str = Header(..., alias="X-Token"),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """删除会话"""
        user = engine.get_current_user_from_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="无效的认证 token")
        ok = engine.db.delete_conversation(conv_id, user.id)
        if not ok:
            raise HTTPException(status_code=404, detail="会话不存在或无权删除")
        return {"message": "已删除"}

    # ========== 带历史的聊天接口 ==========

    @app.post("/api/v1/chat/session", response_model=ChatResponse)
    async def chat_session(
        req_body: ChatRequest,
        token: str = Header(..., alias="X-Token"),
        engine: MultiUserEngine = Depends(get_engine),
    ):
        """带会话历史的聊天（基于任务队列）
        
        支持 conversation_id 参数延续历史对话。
        不传则自动创建新会话。
        """
        user = engine.get_current_user_from_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="无效的认证 token")
        
        # 获取或创建会话
        conv_id = req_body.conversation_id
        if not conv_id:
            conv = engine.db.create_conversation(user.id, req_body.message[:50])
            conv_id = conv["id"]
        else:
            with engine.db._get_connection() as conn:
                row = conn.execute(
                    "SELECT user_id FROM conversations WHERE id = ?", (conv_id,)
                ).fetchone()
                if not row or row["user_id"] != user.id:
                    raise HTTPException(status_code=403, detail="无权访问此会话")
        
        # 提交任务到队列（带 conversation_id）
        task_input: Dict[str, Any] = {
            "type": "llm_chat",
            "prompt": req_body.message,
            "system": req_body.system,
            "conversation_id": conv_id,
        }
        task = await engine.submit_task(
            user_id=user.id,
            task_name="llm_chat",
            input_data=task_input,
        )
        
        # 轮询等待结果
        import asyncio
        for _ in range(60):
            await asyncio.sleep(1)
            task_info = await engine.get_task_status(task.id, user.id)
            if task_info and task_info.state.value == "completed":
                result = task_info.result or {}
                output = result.get("output", "")
                model = result.get("model", "unknown")
                rag_hits = result.get("rag_hits", 0)
                return ChatResponse(
                    reply=output,
                    model=model,
                    rag_used=bool(rag_hits),
                    rag_hits=rag_hits,
                )
            elif task_info and task_info.state.value == "failed":
                raise HTTPException(status_code=500, detail=task_info.error or "任务失败")
        
        raise HTTPException(status_code=504, detail="LLM 响应超时")

    return app
