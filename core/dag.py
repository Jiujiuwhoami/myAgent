"""
DAG (有向无环图) 和调度器
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from myAgent.core.types import NodeStatus


@dataclass
class DAGNode:
    """DAG 节点"""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    node_type: str = "task"
    status: NodeStatus = NodeStatus.READY
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    dependencies: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.name:
            self.name = f"node_{self.id}"
        # 如果 id 是短字符串（来自配置），不要替换为随机ID
        if self.id and len(self.id) <= 8 and self.id.replace("_", "").isalnum():
            pass  # 使用配置的ID

    def is_ready(self, completed_nodes: Set[str]) -> bool:
        """检查节点是否可执行"""
        if self.status != NodeStatus.READY:
            return False
        return self.dependencies.issubset(completed_nodes)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "node_type": self.node_type,
            "status": self.status.value,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "dependencies": list(self.dependencies),
            "metadata": self.metadata,
        }


class DAG:
    """
    有向无环图

    管理节点和依赖关系
    """

    def __init__(self, name: str = "DAG"):
        self.name = name
        self._nodes: Dict[str, DAGNode] = {}
        self._edges: Dict[str, Set[str]] = {}

    @property
    def nodes(self) -> Dict[str, DAGNode]:
        return self._nodes.copy()

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def add_node(self, node: DAGNode) -> "DAG":
        """添加节点"""
        self._nodes[node.id] = node
        if node.id not in self._edges:
            self._edges[node.id] = set()
        return self

    def add_edge(self, from_node_id: str, to_node_id: str) -> "DAG":
        """添加边（表示 to_node 依赖 from_node）"""
        if from_node_id not in self._nodes:
            raise ValueError(f"节点不存在: {from_node_id}")
        if to_node_id not in self._nodes:
            raise ValueError(f"节点不存在: {to_node_id}")

        self._nodes[to_node_id].dependencies.add(from_node_id)
        self._edges[from_node_id].add(to_node_id)

        return self

    def get_node(self, node_id: str) -> Optional[DAGNode]:
        """获取节点"""
        return self._nodes.get(node_id)

    def has_cycle(self) -> bool:
        """检测是否有环"""
        visited = set()
        rec_stack = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)

            for dependent_id in self._edges.get(node_id, set()):
                if dependent_id not in visited:
                    if dfs(dependent_id):
                        return True
                elif dependent_id in rec_stack:
                    return True

            rec_stack.remove(node_id)
            return False

        for node_id in self._nodes:
            if node_id not in visited:
                if dfs(node_id):
                    return True
        return False

    def topological_sort(self) -> List[str]:
        """拓扑排序"""
        if self.has_cycle():
            raise ValueError("DAG 包含环，无法拓扑排序")

        in_degree = {node_id: 0 for node_id in self._nodes}
        for node_id, node in self._nodes.items():
            in_degree[node_id] = len(node.dependencies)

        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)

            for next_id in self._edges.get(node_id, set()):
                in_degree[next_id] -= 1
                if in_degree[next_id] == 0:
                    queue.append(next_id)

        return result


class DAGScheduler:
    """
    DAG 调度器

    负责按依赖关系执行节点
    """

    def __init__(self, dag: DAG, max_parallel: int = 4):
        self.dag = dag
        self.max_parallel = max_parallel
        self._node_executors: Dict[str, Any] = {}
        self._results: Dict[str, Dict] = {}
        self._event_callback: Optional[Any] = None

    def register_node_executor(self, node_id: str, executor: Any):
        """注册节点执行器"""
        self._node_executors[node_id] = executor

    def register_event_callback(self, callback: Any):
        """注册事件回调"""
        self._event_callback = callback

    async def run(self) -> Dict[str, Dict]:
        """执行整个 DAG"""
        completed_nodes: Set[str] = set()
        all_results: Dict[str, Dict] = {}
        errors: List[str] = []
        node_outputs: Dict[str, Dict] = {}

        print(f"\n🚀 开始执行 DAG: {self.dag.name}")
        print(f"   节点数: {self.dag.node_count}")
        print(f"   最大并行: {self.max_parallel}")

        round_num = 0
        while len(completed_nodes) < self.dag.node_count:
            round_num += 1

            ready_nodes = [
                node for node in self.dag.nodes.values() if node.is_ready(completed_nodes)
            ]

            if not ready_nodes:
                break

            print(f"\n   第 {round_num} 轮: 执行 {len(ready_nodes)} 个节点")

            # 并发执行这一轮的节点
            async def exec_node(node: DAGNode) -> None:
                node.status = NodeStatus.RUNNING
                print(f"      📌 {node.name}")

                try:
                    # 注入上游节点的输出作为输入
                    merged_input = dict(node.input_data)
                    for dep_id in node.dependencies:
                        if dep_id in node_outputs:
                            merged_input[f"dep_{dep_id}"] = node_outputs[dep_id]

                    executor = self._node_executors.get(node.id)
                    if executor:
                        result = await executor(node, merged_input)
                        node.output_data = result
                        node_outputs[node.id] = result
                        all_results[node.id] = {"success": True, "output_data": result}
                    else:
                        node.output_data = {"message": "no executor registered"}
                        node_outputs[node.id] = node.output_data
                        all_results[node.id] = {"success": True, "output_data": node.output_data}

                    node.status = NodeStatus.COMPLETED
                    completed_nodes.add(node.id)

                except Exception as e:
                    node.status = NodeStatus.FAILED
                    errors.append(f"{node.name}: {str(e)}")
                    all_results[node.id] = {"success": False, "error": str(e)}

            # 并发执行，限制并行度
            tasks = [exec_node(n) for n in ready_nodes]
            for i in range(0, len(tasks), self.max_parallel):
                batch = tasks[i:i+self.max_parallel]
                await asyncio.gather(*batch, return_exceptions=True)

        success = len(errors) == 0
        print(f"\n{'✅' if success else '⚠️'} DAG 执行完成: {len(completed_nodes)}/{self.dag.node_count} 节点成功")
        if errors:
            for e in errors:
                print(f"   ❌ {e}")

        return all_results
