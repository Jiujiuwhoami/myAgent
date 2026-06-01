"""子图嵌套支持 - 支持 DAG 的层次化嵌套

允许将子 DAG 作为节点嵌入到父 DAG 中，形成层次化工作流。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ..core.dag import DAG, DAGNode, DAGScheduler


@dataclass
class SubDAGNode(DAGNode):
    """子 DAG 节点

    与普通 DAGNode 的区别：
    - 内部包含一个完整的子 DAG
    - 执行时运行子 DAG 的所有节点
    - 支持状态传递（输入/输出映射）
    """

    sub_dag: Optional[DAG] = None  # 子 DAG 引用
    input_mapping: Dict[str, str] = field(default_factory=dict)  # 父→子状态映射
    output_mapping: Dict[str, str] = field(default_factory=dict)  # 子→父状态映射

    def to_dict(self) -> Dict:
        base = super().to_dict()
        base["type"] = "sub_dag"
        base["sub_dag_name"] = self.sub_dag.name if self.sub_dag else None
        base["input_mapping"] = self.input_mapping
        base["output_mapping"] = self.output_mapping
        return base


@dataclass
class NestedDAGExecutionResult:
    """嵌套 DAG 执行结果"""

    success: bool
    output_data: Dict[str, Any]
    sub_dag_results: Dict[str, Dict]  # 各子 DAG 的执行结果
    execution_time: float
    error: Optional[str] = None


class NestedDAG:
    """支持嵌套的 DAG

    扩展普通 DAG，支持：
    - 子 DAG 作为节点
    - 状态传递（输入/输出映射）
    - 层次化执行
    - 嵌套多层（子 DAG 也可以有子 DAG）

    示例:
        # 创建子 DAG
        sub_dag = DAG(name="数据清洗")
        sub_dag.add_node("clean", {"tool": "cleaner"})
        sub_dag.add_node("validate", {"tool": "validator"})
        sub_dag.add_edge("clean", "validate")

        # 创建父 DAG
        parent = NestedDAG(name="主流程")

        # 添加子 DAG 作为节点
        parent.add_sub_dag_node(
            node_id="process_data",
            sub_dag=sub_dag,
            input_mapping={"input": "raw_data"},
            output_mapping={"cleaned": "output"},
        )

        # 执行
        result = await parent.execute({"raw_data": {...}})
    """

    def __init__(self, name: str = "NestedDAG"):
        """初始化嵌套 DAG"""
        self.name = name
        self.nodes: Dict[str, DAGNode] = {}
        self.sub_dags: Dict[str, DAG] = {}  # 子 DAG 集合
        self.edges: Dict[str, Set[str]] = {}  # 边：node_id -> set of target ids
        self._entry_point: Optional[str] = None
        self._finish_points: Set[str] = set()

    def add_node(self, node_id: str, metadata: Dict[str, Any]) -> DAGNode:
        """添加普通节点"""
        node = DAGNode(
            node_id=node_id,
            node_type="task",
            metadata=metadata,
        )
        self.nodes[node_id] = node
        self.edges[node_id] = set()
        return node

    def add_sub_dag_node(
        self,
        node_id: str,
        sub_dag: DAG,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SubDAGNode:
        """添加子 DAG 节点

        Args:
            node_id: 节点 ID
            sub_dag: 子 DAG 实例
            input_mapping: 父状态→子状态的映射
            output_mapping: 子状态→父状态的映射
            metadata: 额外元数据

        Returns:
            SubDAGNode
        """
        node = SubDAGNode(
            node_id=node_id,
            node_type="sub_dag",
            sub_dag=sub_dag,
            input_mapping=input_mapping or {},
            output_mapping=output_mapping or {},
            metadata=metadata or {},
        )

        self.nodes[node_id] = node
        self.sub_dags[node_id] = sub_dag
        self.edges[node_id] = set()

        return node

    def add_edge(self, source: str, target: str):
        """添加边"""
        if source not in self.edges:
            self.edges[source] = set()
        self.edges[source].add(target)

    def set_entry_point(self, node_id: str):
        """设置入口点"""
        self._entry_point = node_id

    def set_finish_point(self, node_id: str):
        """设置结束点"""
        self._finish_points.add(node_id)

    def _map_input(
        self,
        parent_state: Dict[str, Any],
        mapping: Dict[str, str],
    ) -> Dict[str, Any]:
        """将父状态映射到子状态"""
        sub_state = {}
        for parent_key, sub_key in mapping.items():
            if parent_key in parent_state:
                sub_state[sub_key] = parent_state[parent_key]
        return sub_state

    def _map_output(
        self,
        sub_state: Dict[str, Any],
        mapping: Dict[str, str],
    ) -> Dict[str, Any]:
        """将子状态映射到父状态"""
        parent_state = {}
        for sub_key, parent_key in mapping.items():
            if sub_key in sub_state:
                parent_state[parent_key] = sub_state[sub_key]
        return parent_state

    async def _execute_sub_dag(
        self,
        sub_dag: DAG,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """执行子 DAG"""
        # 创建子 DAG 调度器
        scheduler = DAGScheduler(sub_dag, max_parallel=4)

        # 执行
        success = await scheduler.run(input_data=input_data)

        return {
            "success": success,
            "output": scheduler.get_final_output(),
        }

    async def execute(
        self,
        input_data: Dict[str, Any],
        max_steps: int = 100,
    ) -> NestedDAGExecutionResult:
        """执行嵌套 DAG

        Args:
            input_data: 输入数据
            max_steps: 最大步骤数

        Returns:
            NestedDAGExecutionResult
        """
        import time

        start_time = time.time()

        # 当前状态
        current_state = input_data.copy()

        # 已执行节点
        executed: Set[str] = set()

        # 待执行节点（拓扑排序）
        pending: List[str] = [self._entry_point] if self._entry_point else []

        sub_dag_results: Dict[str, Dict] = {}

        step = 0
        while pending and step < max_steps:
            step += 1
            node_id = pending.pop(0)

            if node_id in executed:
                continue

            node = self.nodes.get(node_id)
            if not node:
                continue

            # 检查依赖是否已满足
            # （简化：假设按拓扑顺序执行）

            # 执行节点
            if node.node_type == "sub_dag" and isinstance(node, SubDAGNode):
                # 执行子 DAG
                sub_input = self._map_input(current_state, node.input_mapping)

                result = await self._execute_sub_dag(node.sub_dag, sub_input)

                # 映射输出
                output_mapping = self._map_output(
                    result.get("output", {}),
                    node.output_mapping,
                )
                current_state.update(output_mapping)

                sub_dag_results[node_id] = result

            else:
                # 普通节点（这里简化处理，实际需要调用 Executor）
                # 在实际项目中，这里会调用工具执行器
                pass

            executed.add(node_id)

            # 添加后续节点
            for target in self.edges.get(node_id, set()):
                if target not in executed:
                    pending.append(target)

        elapsed = time.time() - start_time

        return NestedDAGExecutionResult(
            success=len(executed) > 0,
            output_data=current_state,
            sub_dag_results=sub_dag_results,
            execution_time=elapsed,
        )

    def get_all_sub_dags(self) -> List[DAG]:
        """获取所有子 DAG"""
        return list(self.sub_dags.values())

    def get_depth(self) -> int:
        """获取嵌套深度"""
        if not self.sub_dags:
            return 1

        max_depth = 1
        for sub_dag in self.sub_dags.values():
            if isinstance(sub_dag, NestedDAG):
                max_depth = max(max_depth, 1 + sub_dag.get_depth())

        return max_depth

    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "name": self.name,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": {nid: list(targets) for nid, targets in self.edges.items()},
            "entry_point": self._entry_point,
            "finish_points": list(self._finish_points),
            "sub_dag_count": len(self.sub_dags),
            "depth": self.get_depth(),
        }


def create_nested_example() -> NestedDAG:
    """创建嵌套 DAG 示例

    演示：
    - 子 DAG：数据清洗流程
    - 父 DAG：主业务流程
    """
    # ========== 子 DAG：数据清洗 ==========
    clean_dag = DAG(name="数据清洗")
    clean_dag.add_node("validate_format", {"tool": "format_validator"})
    clean_dag.add_node("remove_duplicates", {"tool": "deduplicator"})
    clean_dag.add_node("normalize", {"tool": "normalizer"})
    clean_dag.add_edge("validate_format", "remove_duplicates")
    clean_dag.add_edge("remove_duplicates", "normalize")
    clean_dag.set_entry_point("validate_format")
    clean_dag.set_finish_point("normalize")

    # ========== 子 DAG：数据分析 ==========
    analyze_dag = DAG(name="数据分析")
    analyze_dag.add_node("statistics", {"tool": "stats_calculator"})
    analyze_dag.add_node("trend_analysis", {"tool": "trend_analyzer"})
    analyze_dag.add_node("report", {"tool": "report_generator"})
    analyze_dag.add_edge("statistics", "trend_analysis")
    analyze_dag.add_edge("trend_analysis", "report")
    analyze_dag.set_entry_point("statistics")
    analyze_dag.set_finish_point("report")

    # ========== 父 DAG：主流程 ==========
    parent = NestedDAG(name="数据处理主流程")

    # 添加子 DAG 节点
    parent.add_sub_dag_node(
        node_id="clean",
        sub_dag=clean_dag,
        input_mapping={"raw": "input"},
        output_mapping={"cleaned": "output"},
    )

    parent.add_sub_dag_node(
        node_id="analyze",
        sub_dag=analyze_dag,
        input_mapping={"cleaned": "input"},
        output_mapping={"report": "output"},
    )

    # 添加普通节点
    parent.add_node("init", {"tool": "initializer"})
    parent.add_node("finalize", {"tool": "finalizer"})

    # 添加边
    parent.add_edge("init", "clean")
    parent.add_edge("clean", "analyze")
    parent.add_edge("analyze", "finalize")

    parent.set_entry_point("init")
    parent.set_finish_point("finalize")

    return parent
