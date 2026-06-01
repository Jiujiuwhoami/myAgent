"""
记忆系统 - Working Memory, Episodic Memory, Semantic Memory
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


class WorkingMemory:
    """工作记忆 - 短期上下文"""

    def __init__(self, max_size: int = 10):
        self.max_size = max_size
        self._memory: Dict[str, Any] = {}
        self._history: List[Dict] = []

    def write(self, key: str, value: Any):
        """写入记忆"""
        self._memory[key] = value
        self._history.append({"action": "write", "key": key, "timestamp": datetime.now()})

        # 如果超过大小，清理最早的
        while len(self._memory) > self.max_size:
            oldest_key = next(iter(self._memory.keys()))
            del self._memory[oldest_key]

    def read(self, key: str) -> Optional[Any]:
        """读取记忆"""
        return self._memory.get(key)

    def clear(self):
        """清空"""
        self._memory = {}

    def get_all(self) -> Dict[str, Any]:
        """获取所有"""
        return self._memory.copy()

    def get_status(self) -> Dict:
        return {"size": len(self._memory), "max": self.max_size}


class EpisodicMemory:
    """情景记忆 - 记录任务执行历史"""

    def __init__(self, max_items: int = 100):
        self.max_items = max_items
        self._memory: List[Dict] = []

    def add(self, task_id: str, task_name: str, status: str, metadata: Optional[Dict] = None):
        """添加记忆"""
        self._memory.append(
            {
                "task_id": task_id,
                "task_name": task_name,
                "status": status,
                "timestamp": datetime.now(),
                "metadata": metadata or {},
            }
        )

        # 如果超过大小，移除最早的
        while len(self._memory) > self.max_items:
            self._memory.pop(0)

    def query(self, task_id: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """查询记忆"""
        results = []
        for item in reversed(self._memory):
            if task_id is None or item["task_id"] == task_id:
                results.append(item)
                if len(results) >= limit:
                    break
        return results

    def get_status(self) -> Dict:
        return {"count": len(self._memory), "max": self.max_items}


class SemanticMemory:
    """语义记忆 - 长期知识库"""

    def __init__(self):
        self._memory: Dict[str, Dict] = {}

    def add_knowledge(self, key: str, value: str, category: str = "general"):
        """添加知识"""
        self._memory[key] = {"value": value, "category": category, "added_at": datetime.now()}

    def get_knowledge(self, key: str) -> Optional[Dict]:
        """获取知识"""
        return self._memory.get(key)

    def query_by_category(self, category: str) -> List[Dict]:
        """按类别查询"""
        return [
            {"key": key, **info}
            for key, info in self._memory.items()
            if info["category"] == category
        ]

    def get_status(self) -> Dict:
        return {"count": len(self._memory)}


class MemoryOS:
    """
    记忆操作系统

    整合三层记忆
    """

    def __init__(self):
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self._active_task_id: Optional[str] = None

    def start_task(self, task_id: str):
        """开始任务上下文"""
        self._active_task_id = task_id
        self.working.write("task_id", task_id)
        print(f"   📝 开始任务上下文: {task_id}")

    def end_task(self, task_id: str, task: Any):
        """结束任务，归档到情景记忆"""
        self.episodic.add(
            task_id=task_id,
            task_name=task.name,
            status=task.status.value,
            metadata={"input": task.input_data, "output": task.output_data},
        )
        self.working.clear()
        print(f"   📋 任务归档: {task.name} -> Episodic Memory")

    def get_status(self) -> Dict:
        return {
            "working_memory": self.working.get_status(),
            "episodic_memory": self.episodic.get_status(),
            "semantic_memory": self.semantic.get_status(),
        }
