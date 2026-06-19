"""DAG Checkpoint Manager - Supports node-level breakpoint recovery

Features:
- DAG execution progress checkpoints
- Node-level recovery
- Execution history
- Incremental checkpoints
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from myAgent.core.dag import DAG
from myAgent.core.types import NodeStatus


class CheckpointType(Enum):
    """Checkpoint type"""

    FULL = "full"
    INCREMENTAL = "incremental"
    EMERGENCY = "emergency"


@dataclass
class NodeCheckpoint:
    """Node checkpoint"""

    node_id: str
    node_name: str
    status: str
    completed_at: Optional[str] = None
    output_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    retry_count: int = 0


@dataclass
class DAGCheckpoint:
    """DAG checkpoint"""

    dag_name: str
    checkpoint_id: str
    checkpoint_type: str
    created_at: str
    completed_nodes: List[str] = field(default_factory=list)
    running_nodes: List[str] = field(default_factory=list)
    pending_nodes: List[str] = field(default_factory=list)
    failed_nodes: List[str] = field(default_factory=list)
    node_checkpoints: Dict[str, dict] = field(default_factory=dict)
    dag_snapshot: Optional[dict] = None
    interrupted: bool = False

    def to_dict(self) -> dict:
        result = asdict(self)
        result["checkpoint_type"] = self.checkpoint_type
        return result


class DAGCheckpointManager:
    """
    DAG Checkpoint Manager

    Example:
        manager = DAGCheckpointManager(checkpoint_dir="checkpoints/dag")

        # Create checkpoint before starting DAG
        checkpoint_id = manager.create_checkpoint(dag, checkpoint_type="full")

        # Periodically save during execution
        manager.save_progress(dag, completed_nodes={"node1", "node2"})

        # Restore after interrupt
        if manager.has_checkpoint("my_dag"):
            state = manager.load_checkpoint("my_dag")
            manager.restore_dag(dag, state)
    """

    def __init__(
        self,
        checkpoint_dir: str = "checkpoints/dag",
        max_checkpoints: int = 10,
        auto_save: bool = True,
        save_interval: int = 5,
    ):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.max_checkpoints = max_checkpoints
        self.auto_save = auto_save
        self.save_interval = save_interval
        self._current_checkpoint: Optional[DAGCheckpoint] = None
        self._node_execution_count = 0

        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def create_checkpoint(
        self, dag, checkpoint_type: str = "full", metadata: Optional[dict] = None
    ) -> str:
        """
        Create checkpoint for DAG

        Args:
            dag: DAG instance
            checkpoint_type: Checkpoint type (full/incremental/emergency)
            metadata: Extra metadata

        Returns:
            checkpoint_id
        """
        checkpoint_id = f"dag_{dag.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        completed = []
        running = []
        pending = []
        failed = []
        node_checkpoints = {}

        for node_id, node in dag.nodes.items():
            status = node.status.value if hasattr(node.status, "value") else str(node.status)

            if status == NodeStatus.COMPLETED.value:
                completed.append(node_id)
                node_checkpoints[node_id] = NodeCheckpoint(
                    node_id=node_id,
                    node_name=node.name,
                    status=status,
                    completed_at=datetime.now().isoformat(),
                    output_data=node.output_data,
                ).__dict__
            elif status == NodeStatus.RUNNING.value:
                running.append(node_id)
            elif status == NodeStatus.FAILED.value:
                failed.append(node_id)
            else:
                pending.append(node_id)

        dag_snapshot = None
        if checkpoint_type == CheckpointType.FULL.value:
            dag_snapshot = {
                "name": dag.name,
                "nodes": [node.to_dict() for node in dag.nodes.values()],
                "edges": {k: list(v) for k, v in dag._edges.items()},
            }

        checkpoint = DAGCheckpoint(
            dag_name=dag.name,
            checkpoint_id=checkpoint_id,
            checkpoint_type=checkpoint_type,
            created_at=datetime.now().isoformat(),
            completed_nodes=completed,
            running_nodes=running,
            pending_nodes=pending,
            failed_nodes=failed,
            node_checkpoints=node_checkpoints,
            dag_snapshot=dag_snapshot,
        )

        self._current_checkpoint = checkpoint
        self._save_to_file(checkpoint)

        print(f"   [OK] DAG checkpoint created: {checkpoint_id}")
        print(
            f"      Completed: {len(completed)}, Running: {len(running)}, Pending: {len(pending)}, Failed: {len(failed)}"
        )

        return checkpoint_id

    def save_progress(
        self,
        dag,
        completed_nodes: Set[str],
        running_node: Optional[str] = None,
        node_result: Optional[dict] = None,
    ) -> str:
        """
        Save execution progress (incremental checkpoint)

        Args:
            dag: DAG instance
            completed_nodes: Set of completed node IDs
            running_node: Currently running node
            node_result: Current node execution result

        Returns:
            checkpoint_id
        """
        self._node_execution_count += 1

        checkpoint_id = f"dag_{dag.name}_progress_{self._node_execution_count}"

        pending = []
        failed = []
        node_checkpoints = {}

        for node_id, node in dag.nodes.items():
            status = node.status.value if hasattr(node.status, "value") else str(node.status)

            if node_id in completed_nodes:
                node_checkpoints[node_id] = NodeCheckpoint(
                    node_id=node_id,
                    node_name=node.name,
                    status=NodeStatus.COMPLETED.value,
                    completed_at=datetime.now().isoformat(),
                    output_data=node.output_data,
                ).__dict__
            elif status == NodeStatus.FAILED.value:
                failed.append(node_id)
                node_checkpoints[node_id] = NodeCheckpoint(
                    node_id=node_id,
                    node_name=node.name,
                    status=status,
                    error=getattr(node, "error", None),
                ).__dict__
            else:
                pending.append(node_id)

        checkpoint = DAGCheckpoint(
            dag_name=dag.name,
            checkpoint_id=checkpoint_id,
            checkpoint_type=CheckpointType.INCREMENTAL.value,
            created_at=datetime.now().isoformat(),
            completed_nodes=list(completed_nodes),
            running_nodes=[running_node] if running_node else [],
            pending_nodes=pending,
            failed_nodes=failed,
            node_checkpoints=node_checkpoints,
        )

        self._current_checkpoint = checkpoint
        self._save_to_file(checkpoint)

        return checkpoint_id

    def mark_interrupted(self):
        """Mark checkpoint as interrupted"""
        if self._current_checkpoint:
            self._current_checkpoint.interrupted = True
            self._save_to_file(self._current_checkpoint, suffix="emergency")

    def has_checkpoint(self, dag_name: str) -> bool:
        """Check if there is a recoverable checkpoint"""
        checkpoint_files = list(self.checkpoint_dir.glob(f"dag_{dag_name}_*.json"))
        return len(checkpoint_files) > 0

    def get_latest_checkpoint(self, dag_name: str) -> Optional[str]:
        """Get the latest checkpoint ID"""
        checkpoint_files = list(self.checkpoint_dir.glob(f"dag_{dag_name}_*.json"))
        if not checkpoint_files:
            return None

        latest = max(checkpoint_files, key=lambda f: f.stat().st_mtime)
        return latest.stem.replace(f"dag_{dag_name}_", "")

    def load_checkpoint(self, dag_name: str, checkpoint_id: Optional[str] = None) -> Optional[dict]:
        """
        Load checkpoint

        Args:
            dag_name: DAG name
            checkpoint_id: Checkpoint ID (latest if not specified)

        Returns:
            Checkpoint data or None
        """
        if checkpoint_id:
            filepath = self.checkpoint_dir / f"dag_{dag_name}_{checkpoint_id}.json"
        else:
            checkpoint_files = list(self.checkpoint_dir.glob(f"dag_{dag_name}_*.json"))
            if not checkpoint_files:
                return None
            latest = max(checkpoint_files, key=lambda f: f.stat().st_mtime)
            filepath = latest

        if not filepath.exists():
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"   [ERROR] Failed to load checkpoint: {e}")
            return None

    def restore_dag(self, dag, checkpoint_data: dict) -> Set[str]:
        """
        Restore DAG state from checkpoint

        Args:
            dag: DAG instance
            checkpoint_data: Checkpoint data

        Returns:
            Set of node IDs that need to be retried
        """
        completed_nodes = set()

        node_checkpoints = checkpoint_data.get("node_checkpoints", {})
        pending_nodes = checkpoint_data.get("pending_nodes", [])
        failed_nodes = checkpoint_data.get("failed_nodes", [])

        for node_id, node in dag.nodes.items():
            if node_id in node_checkpoints:
                cp = node_checkpoints[node_id]
                node.status = NodeStatus(cp["status"])
                node.output_data = cp.get("output_data", {})
                if cp.get("completed_at"):
                    node.metadata["completed_at"] = cp["completed_at"]
                completed_nodes.add(node_id)
            elif node_id in failed_nodes:
                node.status = NodeStatus.READY
                node.error = None
            else:
                node.status = NodeStatus.READY

        nodes_to_retry = set(pending_nodes) | set(failed_nodes)

        print("   [RESTORED] DAG restored:")
        print(f"      Has results: {len(completed_nodes)} nodes")
        print(f"      Need retry: {len(nodes_to_retry)} nodes")

        return nodes_to_retry

    def list_checkpoints(self, dag_name: Optional[str] = None) -> List[dict]:
        """List checkpoints"""
        if dag_name:
            pattern = f"dag_{dag_name}_*.json"
        else:
            pattern = "dag_*.json"

        checkpoints = []
        for f in self.checkpoint_dir.glob(pattern):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    checkpoints.append(
                        {
                            "dag_name": data.get("dag_name"),
                            "checkpoint_id": data.get("checkpoint_id"),
                            "checkpoint_type": data.get("checkpoint_type"),
                            "created_at": data.get("created_at"),
                            "completed_nodes": len(data.get("completed_nodes", [])),
                            "interrupted": data.get("interrupted", False),
                        }
                    )
            except:
                pass

        return sorted(checkpoints, key=lambda x: x.get("created_at", ""), reverse=True)

    def delete_checkpoint(self, dag_name: str, checkpoint_id: Optional[str] = None):
        """Delete checkpoint"""
        if checkpoint_id:
            filepath = self.checkpoint_dir / f"dag_{dag_name}_{checkpoint_id}.json"
            if filepath.exists():
                filepath.unlink()
        else:
            for f in self.checkpoint_dir.glob(f"dag_{dag_name}_*.json"):
                f.unlink()

    def _save_to_file(self, checkpoint: DAGCheckpoint, suffix: str = ""):
        """Save checkpoint to file"""
        filename = f"{checkpoint.checkpoint_id}{suffix}.json"
        filepath = self.checkpoint_dir / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(checkpoint.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"   [ERROR] Failed to save checkpoint: {e}")

        self._cleanup_old_checkpoints(checkpoint.dag_name)

    def _cleanup_old_checkpoints(self, dag_name: str):
        """Cleanup old checkpoints"""
        checkpoint_files = list(self.checkpoint_dir.glob(f"dag_{dag_name}_*.json"))

        if len(checkpoint_files) <= self.max_checkpoints:
            return

        files_with_time = [(f, f.stat().st_mtime) for f in checkpoint_files]
        files_with_time.sort(key=lambda x: x[1])

        for f, _ in files_with_time[: -self.max_checkpoints]:
            f.unlink()


class InterruptibleDAGScheduler:
    """
    Interruptible DAG Scheduler

    Combines DAGScheduler + DAGCheckpointManager + GracefulShutdown

    Example:
        scheduler = InterruptibleDAGScheduler(dag, checkpoint_manager)
        result = await scheduler.run_with_checkpoint()
    """

    def __init__(self, dag: DAG, checkpoint_manager: DAGCheckpointManager, max_parallel: int = 4):
        self.dag = dag
        self.checkpoint_manager = checkpoint_manager
        self.max_parallel = max_parallel
        self._node_executors: Dict[str, Callable] = {}
        self._results: Dict[str, Any] = {}
        self._interrupted = False
        self._completed_nodes: Set[str] = set()

    def register_node_executor(self, node_id: str, executor: Callable):
        """Register node executor"""
        self._node_executors[node_id] = executor

    async def run_with_checkpoint(self, interrupt_check_interval: int = 1) -> Dict[str, Any]:
        """
        Run with checkpoint

        Args:
            interrupt_check_interval: Interrupt check interval (seconds)

        Returns:
            All node results
        """
        self._completed_nodes = set()

        self.checkpoint_manager.create_checkpoint(
            self.dag, checkpoint_type=CheckpointType.FULL.value
        )

        sorted_nodes = self.dag.topological_sort()

        for node_id in sorted_nodes:
            if self._interrupted:
                print(
                    f"\n[WARNING] Execution interrupted, completed {len(self._completed_nodes)}/{len(sorted_nodes)} nodes"
                )
                self.checkpoint_manager.save_progress(
                    self.dag, completed_nodes=self._completed_nodes, running_node=node_id
                )
                break

            node = self.dag.get_node(node_id)
            if not node:
                continue

            if node_id in self._completed_nodes:
                continue

            if not node.is_ready(self._completed_nodes):
                continue

            node.status = NodeStatus.RUNNING
            executor = self._node_executors.get(node_id)

            try:
                if executor:
                    result = await executor(node)
                    node.output_data = result
                    node.status = NodeStatus.COMPLETED
                    self._completed_nodes.add(node_id)
                    self._results[node_id] = result
                else:
                    print(f"   [WARNING] Node {node_id} has no registered executor")

            except Exception as e:
                node.status = NodeStatus.FAILED
                node.error = str(e)
                print(f"   [ERROR] Node {node_id} execution failed: {e}")

            if len(self._completed_nodes) % self.checkpoint_manager.save_interval == 0:
                self.checkpoint_manager.save_progress(
                    self.dag, completed_nodes=self._completed_nodes
                )

        if len(self._completed_nodes) == len(sorted_nodes):
            print(f"   [OK] DAG execution completed ({len(self._completed_nodes)} nodes)")

        return self._results

    def mark_interrupted(self):
        """Mark as interrupted"""
        self._interrupted = True
        self.checkpoint_manager.mark_interrupted()


def demo():
    """Demo"""
    print("=" * 60)
    print("DAG Checkpoint Manager Demo")
    print("=" * 60)

    from .dag import DAG, DAGNode

    dag = DAG(name="demo_dag")
    dag.add_node(DAGNode(id="n1", name="step1"))
    dag.add_node(DAGNode(id="n2", name="step2", dependencies={"n1"}))
    dag.add_node(DAGNode(id="n3", name="step3", dependencies={"n2"}))

    manager = DAGCheckpointManager()

    print("\n1. Create checkpoint:")
    cp_id = manager.create_checkpoint(dag)
    print(f"   Checkpoint ID: {cp_id}")

    print("\n2. Simulate execution progress:")
    manager.save_progress(dag, completed_nodes={"n1"})

    print("\n3. List checkpoints:")
    checkpoints = manager.list_checkpoints("demo_dag")
    print(f"   Found {len(checkpoints)} checkpoints")

    print("\n4. Restore DAG:")
    dag2 = DAG(name="demo_dag")
    dag2.add_node(DAGNode(id="n1", name="step1"))
    dag2.add_node(DAGNode(id="n2", name="step2", dependencies={"n1"}))
    dag2.add_node(DAGNode(id="n3", name="step3", dependencies={"n2"}))

    state = manager.load_checkpoint("demo_dag")
    to_retry = manager.restore_dag(dag2, state)
    print(f"   Nodes to retry: {to_retry}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    demo()
