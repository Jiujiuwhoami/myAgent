"""用户级 Skill 管理器 - 支持多租户隔离

每个用户拥有独立的 Skill 目录，实现完全隔离。
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class UserSkillManager:
    """用户级技能管理器

    每个用户拥有独立的技能目录：
        ~/.hermes/skills/<user_id>/
        ├── code_review/
        ├── data_analyzer/
        └── my_custom_skill/

    与全局技能目录分离，实现完全隔离。
    """

    def __init__(
        self,
        user_id: str,
        base_dir: Optional[str] = None,
        global_skill_dir: Optional[str] = None,
    ):
        """初始化用户级技能管理器

        Args:
            user_id: 用户 ID
            base_dir: 用户技能基础目录（默认 ~/.hermes/skills/<user_id>）
            global_skill_dir: 全局技能目录（默认 skills/，作为共享库）
        """
        self.user_id = user_id

        # 用户级技能目录
        if base_dir:
            self.user_skill_dir = Path(base_dir)
        else:
            home = os.environ.get("HOME", Path.home())
            self.user_skill_dir = Path(home) / ".hermes" / "skills" / user_id

        # 全局技能目录（只读共享库）
        if global_skill_dir:
            self.global_skill_dir = Path(global_skill_dir)
        else:
            self.global_skill_dir = Path("myAgent/skills")

        # 确保用户目录存在
        self.user_skill_dir.mkdir(parents=True, exist_ok=True)

        # 技能缓存
        self._user_skills: Dict[str, Any] = {}
        self._global_skills: Dict[str, Any] = {}

    def _discover_skills(self, skill_dir: Path) -> List[str]:
        """扫描技能目录"""
        if not skill_dir.exists():
            return []

        skills = []
        for item in skill_dir.iterdir():
            if item.is_dir() and (item / "skill.json").exists():
                skills.append(item.name)
        return skills

    def discover(self) -> List[str]:
        """发现所有可用技能（用户级 + 全局共享）"""
        # 发现用户级技能
        user_skills = self._discover_skills(self.user_skill_dir)
        for name in user_skills:
            if name not in self._user_skills:
                self._user_skills[name] = {
                    "name": name,
                    "path": str(self.user_skill_dir / name),
                    "scope": "user",  # 用户级
                }

        # 发现全局共享技能
        global_skills = self._discover_skills(self.global_skill_dir)
        for name in global_skills:
            if name not in self._global_skills:
                self._global_skills[name] = {
                    "name": name,
                    "path": str(self.global_skill_dir / name),
                    "scope": "global",  # 全局共享
                }

        # 返回所有技能（用户级优先）
        all_skills = list(self._user_skills.keys())
        for name in self._global_skills:
            if name not in all_skills:
                all_skills.append(name)

        return all_skills

    def get_skill(self, name: str) -> Optional[Dict]:
        """获取技能信息（优先返回用户级技能）"""
        # 优先查找用户级技能
        if name in self._user_skills:
            return self._user_skills[name]

        # 回退到全局共享技能
        if name in self._global_skills:
            return self._global_skills[name]

        return None

    def is_user_skill(self, name: str) -> bool:
        """判断技能是否为用户级"""
        return name in self._user_skills

    def get_user_skills(self) -> List[str]:
        """获取用户级技能列表"""
        return list(self._user_skills.keys())

    def get_global_skills(self) -> List[str]:
        """获取全局共享技能列表"""
        return list(self._global_skills.keys())

    def install_skill(self, name: str, source_dir: Optional[str] = None) -> bool:
        """安装技能到用户目录（从全局或指定源）"""
        source = Path(source_dir) if source_dir else self.global_skill_dir / name

        if not source.exists():
            return False

        target = self.user_skill_dir / name
        import shutil

        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)

        # 重新发现
        self.discover()
        return True

    def uninstall_skill(self, name: str) -> bool:
        """卸载用户级技能（不影响全局共享）"""
        target = self.user_skill_dir / name
        if not target.exists():
            return False

        import shutil

        shutil.rmtree(target)

        # 从缓存移除
        self._user_skills.pop(name, None)
        return True

    def create_skill(self, skill_name: str, **kwargs) -> Path:
        """在用户目录创建新技能"""
        from myAgent.skills import create_skill_scaffold

        return create_skill_scaffold(
            skill_name=skill_name, output_dir=str(self.user_skill_dir), **kwargs
        )

    def list_skills(self, scope: Optional[str] = None) -> List[Dict]:
        """列出技能（可选按作用域过滤）"""
        if scope == "user":
            return list(self._user_skills.values())
        elif scope == "global":
            return list(self._global_skills.values())
        else:
            # 返回所有（用户级在前）
            all_skills = list(self._user_skills.values())
            for name, info in self._global_skills.items():
                if name not in self._user_skills:
                    all_skills.append(info)
            return all_skills

    def get_status(self) -> Dict:
        """获取状态信息"""
        return {
            "user_id": self.user_id,
            "user_skill_dir": str(self.user_skill_dir),
            "global_skill_dir": str(self.global_skill_dir),
            "user_skills_count": len(self._user_skills),
            "global_skills_count": len(self._global_skills),
            "user_skills": list(self._user_skills.keys()),
            "global_skills": list(self._global_skills.keys()),
        }


# ========== 全局用户级 Skill 管理器注册 ==========

_user_skill_managers: Dict[str, UserSkillManager] = {}


def get_user_skill_manager(user_id: str) -> UserSkillManager:
    """获取或创建用户级技能管理器"""
    if user_id not in _user_skill_managers:
        _user_skill_managers[user_id] = UserSkillManager(user_id)
    return _user_skill_managers[user_id]


def remove_user_skill_manager(user_id: str):
    """移除用户级技能管理器"""
    _user_skill_managers.pop(user_id, None)
