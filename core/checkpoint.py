"""
检查点系统 - 状态持久化和恢复
"""

import os
import pickle
from datetime import datetime
from typing import Dict, Optional


class CheckpointManager:
    """
    检查点管理器

    保存和恢复系统状态
    """

    def __init__(self, directory: str = "checkpoints", max_checkpoints: int = 10):
        self.directory = directory
        self.max_checkpoints = max_checkpoints
        self._checkpoints: Dict[str, Dict] = {}

        # 创建目录
        if not os.path.exists(directory):
            os.makedirs(directory)

    def create_checkpoint(self, state: Dict, name: Optional[str] = None) -> str:
        """
        创建检查点

        返回检查点ID
        """
        checkpoint_id = name or f"cp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        self._checkpoints[checkpoint_id] = {
            "id": checkpoint_id,
            "state": state,
            "created_at": datetime.now(),
        }

        # 保存到文件
        filepath = os.path.join(self.directory, f"{checkpoint_id}.pkl")
        try:
            with open(filepath, "wb") as f:
                pickle.dump(state, f)
            print(f"   ✅ 创建检查点: {checkpoint_id}")
        except Exception as e:
            print(f"   ⚠️ 检查点保存失败: {e}")

        # 检查是否超过最大数量
        if len(self._checkpoints) > self.max_checkpoints:
            oldest_id = sorted(
                self._checkpoints.keys(), key=lambda k: self._checkpoints[k]["created_at"]
            )[0]
            del self._checkpoints[oldest_id]
            old_file = os.path.join(self.directory, f"{oldest_id}.pkl")
            if os.path.exists(old_file):
                os.remove(old_file)

        return checkpoint_id

    def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict]:
        """加载检查点"""
        if checkpoint_id in self._checkpoints:
            return self._checkpoints[checkpoint_id]["state"]

        # 从文件加载
        filepath = os.path.join(self.directory, f"{checkpoint_id}.pkl")
        if os.path.exists(filepath):
            try:
                with open(filepath, "rb") as f:
                    state = pickle.load(f)
                    self._checkpoints[checkpoint_id] = {
                        "id": checkpoint_id,
                        "state": state,
                        "created_at": datetime.fromtimestamp(os.path.getmtime(filepath)),
                    }
                    return state
            except Exception as e:
                print(f"   ⚠️ 检查点加载失败: {e}")
                return None

        return None

    def list_checkpoints(self) -> list[Dict]:
        """列出所有检查点"""
        return [
            {"id": cp["id"], "created_at": cp["created_at"]}
            for cp in sorted(
                self._checkpoints.values(), key=lambda x: x["created_at"], reverse=True
            )
        ]

    def get_status(self) -> Dict:
        return {"count": len(self._checkpoints), "max": self.max_checkpoints}
