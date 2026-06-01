"""
故障恢复系统 - 完整的恢复策略
"""

import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Optional


class RecoveryStrategy(Enum):
    """恢复策略类型"""

    RETRY = "retry"
    ROLLBACK = "rollback"
    CIRCUIT_BREAKER = "circuit_breaker"
    FALLBACK = "fallback"
    ESCALATE = "escalate"


class CircuitState(Enum):
    """断路器状态"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class RetryConfig:
    """重试配置"""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0

    def get_delay(self, attempt: int) -> float:
        """计算重试延迟（指数退避）"""
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        return min(delay, self.max_delay)


@dataclass
class CircuitBreakerConfig:
    """断路器配置"""

    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: float = 60.0


class CircuitBreaker:
    """
    断路器模式

    防止持续失败调用，当失败次数超过阈值时"熔断"，
    后续调用直接失败，直到超时后进入半开状态尝试恢复。
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self._callbacks: list[Callable] = []

    def record_success(self):
        """记录成功调用"""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                print("   🔄 断路器关闭（恢复）")
                self._trigger_callbacks(RecoveryStrategy.CIRCUIT_BREAKER, "closed")

    def record_failure(self):
        """记录失败调用"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            print("   ⚡ 断路器打开（半开状态失败）")
        elif self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            print("   ⚡ 断路器打开（失败次数超限）")
            self._trigger_callbacks(RecoveryStrategy.CIRCUIT_BREAKER, "opened")

    def can_execute(self) -> bool:
        """检查是否可以执行"""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed >= self.config.timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    print("   🔄 断路器进入半开状态")
                    return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return True

        return False

    def _trigger_callbacks(self, strategy: RecoveryStrategy, state: str):
        """触发回调"""
        for callback in self._callbacks:
            try:
                callback(strategy, state)
            except Exception as e:
                print(f"断路器回调错误: {e}")

    def on_state_change(self, callback: Callable):
        """注册状态变化回调"""
        self._callbacks.append(callback)


class RollbackManager:
    """
    回滚管理器

    记录操作历史，支持在失败时回滚到之前的状态。
    """

    def __init__(self):
        self._snapshots: Dict[str, Any] = {}
        self._history: list[tuple[str, Any, datetime]] = []

    def save_snapshot(self, key: str, value: Any):
        """保存快照"""
        self._snapshots[key] = value
        self._history.append((key, value, datetime.now()))
        print(f"   📸 快照已保存: {key}")

    def rollback(self, key: str) -> Optional[Any]:
        """回滚到指定快照"""
        if key in self._snapshots:
            value = self._snapshots[key]
            print(f"   ↩️ 回滚: {key}")
            return value
        print(f"   ⚠️ 未找到快照: {key}")
        return None

    def get_snapshot(self, key: str) -> Optional[Any]:
        """获取快照"""
        return self._snapshots.get(key)

    def clear(self):
        """清空快照"""
        self._snapshots = {}
        self._history = []


class RecoveryOrchestrator:
    """
    恢复协调器

    协调多种恢复策略：重试、断路器、回滚、降级。
    """

    def __init__(
        self,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    ):
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker = CircuitBreaker(circuit_breaker_config)
        self.rollback_manager = RollbackManager()
        self._fallback_handlers: Dict[str, Callable] = {}

    def register_fallback(self, operation: str, handler: Callable):
        """注册降级处理函数"""
        self._fallback_handlers[operation] = handler
        print(f"   ✅ 降级处理器已注册: {operation}")

    async def execute_with_recovery(
        self, operation: str, func: Callable[..., Awaitable[Any]], *args, **kwargs
    ) -> Any:
        """
        执行操作并应用恢复策略

        顺序：断路器检查 → 重试循环 → 降级处理
        """
        if not self.circuit_breaker.can_execute():
            fallback = self._fallback_handlers.get(operation)
            if fallback:
                print(f"   🔄 断路器打开，执行降级: {operation}")
                return await fallback(*args, **kwargs)
            raise Exception(f"断路器打开，操作不可执行: {operation}")

        attempt = 0
        last_error = None

        while attempt < self.retry_config.max_attempts:
            attempt += 1

            try:
                print(f"   🔄 执行尝试 {attempt}/{self.retry_config.max_attempts}")
                result = await func(*args, **kwargs)
                self.circuit_breaker.record_success()
                return result

            except Exception as e:
                last_error = e
                print(f"   ❌ 尝试 {attempt} 失败: {e}")
                self.circuit_breaker.record_failure()

                if attempt < self.retry_config.max_attempts:
                    delay = self.retry_config.get_delay(attempt)
                    print(f"   ⏳ 等待 {delay:.1f}s 后重试...")
                    time.sleep(delay)

        fallback = self._fallback_handlers.get(operation)
        if fallback:
            print(f"   🔄 所有重试失败，执行降级: {operation}")
            return await fallback(*args, **kwargs)

        raise last_error or Exception(f"操作失败: {operation}")

    def get_status(self) -> Dict[str, Any]:
        """获取恢复系统状态"""
        return {
            "circuit_breaker": {
                "state": self.circuit_breaker.state.value,
                "failure_count": self.circuit_breaker.failure_count,
                "last_failure": (
                    self.circuit_breaker.last_failure_time.isoformat()
                    if self.circuit_breaker.last_failure_time
                    else None
                ),
            },
            "rollback_snapshots": len(self.rollback_manager._snapshots),
            "fallback_handlers": list(self._fallback_handlers.keys()),
        }
