"""Celery 异步任务队列集成"""

import asyncio
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class TaskStatus(Enum):
    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"


@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "retry_count": self.retry_count,
            "duration": self.duration,
            "metadata": self.metadata,
        }


class TaskDefinition:
    def __init__(
        self,
        name: str,
        func: Callable,
        max_retries: int = 3,
        default_retry_delay: float = 60.0,
        timeout: Optional[float] = None,
    ):
        self.name = name
        self.func = func
        self.max_retries = max_retries
        self.default_retry_delay = default_retry_delay
        self.timeout = timeout


class CeleryTask:
    """
    Celery 任务封装

    提供类似 Celery 的任务接口，但使用 asyncio 实现
    支持：
    - 异步执行
    - 重试机制
    - 超时控制
    - 结果存储
    """

    def __init__(self, definition: TaskDefinition):
        self.definition = definition
        self._results: Dict[str, TaskResult] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._retry_delays: Dict[str, float] = {}
        self._callbacks: Dict[str, List[Callable]] = {}

    def delay(self, *args, **kwargs) -> str:
        """异步提交任务"""
        task_id = str(uuid.uuid4())
        self._results[task_id] = TaskResult(
            task_id=task_id,
            status=TaskStatus.PENDING,
        )
        self._locks[task_id] = threading.Lock()
        asyncio.create_task(self._execute(task_id, *args, **kwargs))
        return task_id

    def apply(self, *args, **kwargs) -> TaskResult:
        """同步执行任务"""
        task_id = str(uuid.uuid4())
        self._results[task_id] = TaskResult(
            task_id=task_id,
            status=TaskStatus.PENDING,
        )
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._execute(task_id, *args, **kwargs))
            return result
        finally:
            loop.close()

    async def _execute(self, task_id: str, *args, **kwargs):
        result = self._results[task_id]
        result.status = TaskStatus.STARTED
        result.started_at = datetime.now()

        try:
            if asyncio.iscoroutinefunction(self.definition.func):
                if self.definition.timeout:
                    result.result = await asyncio.wait_for(
                        self.definition.func(*args, **kwargs),
                        timeout=self.definition.timeout,
                    )
                else:
                    result.result = await self.definition.func(*args, **kwargs)
            else:
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor() as pool:
                    result.result = await loop.run_in_executor(
                        pool,
                        lambda: self.definition.func(*args, **kwargs),
                    )

            result.status = TaskStatus.SUCCESS
            result.completed_at = datetime.now()

        except asyncio.TimeoutError:
            result.status = TaskStatus.FAILURE
            result.error = f"Task timeout after {self.definition.timeout}s"
            result.completed_at = datetime.now()

        except Exception as e:
            if result.retry_count < self.definition.max_retries:
                result.status = TaskStatus.RETRY
                result.retry_count += 1
                delay = self.definition.default_retry_delay * (2 ** (result.retry_count - 1))
                self._retry_delays[task_id] = delay
                asyncio.create_task(self._retry(task_id, *args, **kwargs))
            else:
                result.status = TaskStatus.FAILURE
                result.error = str(e)
                result.completed_at = datetime.now()

        self._notify_callbacks(task_id)
        return result

    async def _retry(self, task_id: str, *args, **kwargs):
        delay = self._retry_delays.get(task_id, self.definition.default_retry_delay)
        await asyncio.sleep(delay)
        await self._execute(task_id, *args, **kwargs)

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        return self._results.get(task_id)

    def on_complete(self, callback: Callable[[TaskResult], None], task_id: str = None):
        if task_id:
            if task_id not in self._callbacks:
                self._callbacks[task_id] = []
            self._callbacks[task_id].append(callback)
        else:
            pass

    def _notify_callbacks(self, task_id: str):
        callbacks = self._callbacks.pop(task_id, [])
        result = self._results.get(task_id)
        for callback in callbacks:
            try:
                callback(result)
            except Exception:
                pass

    def revoke(self, task_id: str):
        if task_id in self._results:
            self._results[task_id].status = TaskStatus.REVOKED


class CeleryApp:
    """
    Celery 应用封装

    管理任务定义和任务执行

    示例:
        app = CeleryApp("agent_tasks")

        @app.task(max_retries=3)
        async def process_data(data):
            await asyncio.sleep(1)
            return {"processed": data}

        # 提交任务
        task_id = app.send_task("process_data", {"data": "hello"})

        # 获取结果
        result = app.get_result(task_id)
        print(result.result)
    """

    def __init__(self, name: str = "agent_tasks", redis_url: Optional[str] = None):
        self.name = name
        self.redis_url = redis_url
        self._tasks: Dict[str, TaskDefinition] = {}
        self._executors: Dict[str, CeleryTask] = {}
        self._task_queue: List[str] = []
        self._lock = threading.Lock()
        self._redis_available = False
        self._init_redis()

    def _init_redis(self):
        if self.redis_url:
            try:
                import redis

                self._redis_client = redis.from_url(self.redis_url)
                self._redis_client.ping()
                self._redis_available = True
                print(f"   ✅ Redis 连接成功: {self.redis_url}")
            except Exception as e:
                print(f"   ⚠️ Redis 连接失败: {e}")
                self._redis_available = False

    def task(
        self,
        name: str = None,
        max_retries: int = 3,
        retry_delay: float = 60.0,
        timeout: float = None,
    ):
        def decorator(func: Callable):
            task_name = name or func.__name__

            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)

            self.register_task(
                name=task_name,
                func=wrapper,
                max_retries=max_retries,
                default_retry_delay=retry_delay,
                timeout=timeout,
            )
            return wrapper

        return decorator

    def register_task(
        self,
        name: str,
        func: Callable,
        max_retries: int = 3,
        default_retry_delay: float = 60.0,
        timeout: Optional[float] = None,
    ):
        definition = TaskDefinition(
            name=name,
            func=func,
            max_retries=max_retries,
            default_retry_delay=default_retry_delay,
            timeout=timeout,
        )
        self._tasks[name] = definition
        self._executors[name] = CeleryTask(definition)
        print(f"   ✅ 任务注册: {name}")

    def send_task(self, name: str, *args, **kwargs) -> str:
        if name not in self._executors:
            raise ValueError(f"Task not registered: {name}")

        task_id = self._executors[name].delay(*args, **kwargs)

        with self._lock:
            self._task_queue.append(task_id)

        if self._redis_available:
            self._redis_client.rpush(
                f"celery:{self.name}:queue",
                json.dumps(
                    {
                        "task_id": task_id,
                        "task_name": name,
                        "args": args,
                        "kwargs": kwargs,
                    }
                ),
            )

        return task_id

    def apply_task(self, name: str, *args, **kwargs) -> TaskResult:
        if name not in self._executors:
            raise ValueError(f"Task not registered: {name}")
        return self._executors[name].apply(*args, **kwargs)

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        for executor in self._executors.values():
            result = executor.get_result(task_id)
            if result:
                return result
        return None

    def revoke(self, task_id: str):
        for executor in self._executors.values():
            executor.revoke(task_id)

    def list_tasks(self) -> List[str]:
        return list(self._tasks.keys())

    def get_queue_size(self) -> int:
        return len(self._task_queue)

    def get_stats(self) -> Dict[str, Any]:
        stats = {
            "app_name": self.name,
            "registered_tasks": len(self._tasks),
            "queue_size": self.get_queue_size(),
            "redis_available": self._redis_available,
            "tasks": {},
        }

        for name, executor in self._executors.items():
            task_stats = {"pending": 0, "running": 0, "success": 0, "failure": 0}
            for result in executor._results.values():
                if result.status == TaskStatus.PENDING:
                    task_stats["pending"] += 1
                elif result.status == TaskStatus.STARTED:
                    task_stats["running"] += 1
                elif result.status == TaskStatus.SUCCESS:
                    task_stats["success"] += 1
                elif result.status in (TaskStatus.FAILURE, TaskStatus.REVOKED):
                    task_stats["failure"] += 1
            stats["tasks"][name] = task_stats

        return stats


_global_celery_app: Optional[CeleryApp] = None


def get_celery_app(name: str = "agent_tasks", redis_url: Optional[str] = None) -> CeleryApp:
    global _global_celery_app
    if _global_celery_app is None:
        _global_celery_app = CeleryApp(name, redis_url)
    return _global_celery_app


class TaskWorker:
    """
    任务 worker - 从队列消费任务

    示例:
        worker = TaskWorker(celery_app)

        # 启动 worker (会阻塞)
        await worker.start()
    """

    def __init__(self, app: CeleryApp, concurrency: int = 4):
        self.app = app
        self.concurrency = concurrency
        self._running = False
        self._executor = ThreadPoolExecutor(max_workers=concurrency)

    async def start(self):
        self._running = True
        print(f"   🚀 Worker 启动 (并发数: {self.concurrency})")

        while self._running:
            if self.app._redis_available:
                task_data = self.app._redis_client.blpop(
                    f"celery:{self.app.name}:queue",
                    timeout=1,
                )
                if task_data:
                    _, data = task_data
                    task_info = json.loads(data)
                    self.app.send_task(
                        task_info["task_name"],
                        *task_info["args"],
                        **task_info["kwargs"],
                    )
            else:
                await asyncio.sleep(0.1)

    def stop(self):
        self._running = False
        self._executor.shutdown(wait=True)
        print("   🛑 Worker 已停止")
