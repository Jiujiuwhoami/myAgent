"""myAgent 单元测试"""

import os
import sys

import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBackendEngine:
    """测试后端引擎"""

    def test_user_role_enum(self):
        """测试用户角色枚举"""
        from myAgent.backend.engine import UserRole

        assert UserRole.ADMIN.value == "admin"
        assert UserRole.USER.value == "user"
        assert UserRole.GUEST.value == "guest"

    def test_task_priority_enum(self):
        """测试任务优先级枚举"""
        from myAgent.backend.engine import TaskPriority

        assert TaskPriority.LOW.value == 1
        assert TaskPriority.CRITICAL.value == 4

    def test_task_state_enum(self):
        """测试任务状态枚举"""
        from myAgent.backend.engine import TaskState

        assert TaskState.PENDING.value == "pending"
        assert TaskState.RUNNING.value == "running"
        assert TaskState.COMPLETED.value == "completed"


class TestCoreTypes:
    """测试核心类型"""

    def test_task_status(self):
        """测试任务状态"""
        from myAgent.core.types import TaskStatus

        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.COMPLETED.value == "completed"

    def test_event_type(self):
        """测试事件类型"""
        from myAgent.core.types import EventType

        # 检查 EventType 存在
        assert hasattr(EventType, "START")
        assert hasattr(EventType, "COMPLETE")


class TestIntegration:
    """集成测试"""

    def test_import_myAgent(self):
        """测试 myAgent 可以导入"""
        import myAgent

        assert hasattr(myAgent, "__version__")
        print(f"✅ myAgent 版本: {myAgent.__version__}")

    def test_import_backend_engine(self):
        """测试后端引擎可以导入"""
        from myAgent.backend.engine import MultiUserEngine, UserRuntime

        assert MultiUserEngine is not None
        assert UserRuntime is not None

    def test_import_core_memory(self):
        """测试 MemoryOS 可以导入"""
        from myAgent.core.memory import MemoryOS

        assert MemoryOS is not None

    def test_import_llm_client(self):
        """测试 LLMClient 可以导入"""
        from myAgent.llm.client import LLMClient

        assert LLMClient is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
