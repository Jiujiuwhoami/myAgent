"""Skill 系统 V2 - Codex 兼容版本

Skill = 可复用的工作流/程序（如 "代码审查"、"部署服务"）

目录结构：
    skills/
    ├── __init__.py          # 本文件（导出接口）
    ├── v2.py                # V2 核心模块
    ├── cli.py               # 技能管理 CLI
    ├── code_review/         # 代码审查技能示例
    │   ├── SKILL.md         # 主说明书（LLM 直接阅读）
    │   ├── skill.json       # 配置
    │   ├── skill.py         # 执行代码
    │   ├── references/       # 参考资料
    │   └── scripts/          # 辅助脚本
    └── <other_skills>/      # 其他技能...

使用示例：
    from myAgent.skills import SkillManager, SkillTriggerEngine, SkillConfigV2

    manager = SkillManager()
    manager.discover()
    manager.load("code_review")
    result = await manager.run_skill("code_review", file_path="test.py")
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

# V2 核心模块导入（Codex 兼容格式）
from skills.v2 import (
    SkillConfigV2,
    SkillLoader,
    SkillTrigger,
    SkillTriggerEngine,
)


class SkillStatus:
    """技能状态"""

    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


class SkillCategory:
    """技能分类"""

    DEVOPS = "devops"
    DEVELOPMENT = "development"
    DATA = "data"
    RESEARCH = "research"
    AUTOMATION = "automation"
    SECURITY = "security"
    CUSTOM = "custom"


class SkillManager:
    """技能管理器 - 统一管理技能的生命周期"""

    def __init__(self, skill_dir: str = "skills"):
        self.skill_dir = Path(skill_dir)
        self._skills: Dict[str, SkillConfigV2] = {}
        self._engine = SkillTriggerEngine()
        self._loader = SkillLoader(str(self.skill_dir))
        self._usage_count: Dict[str, int] = {}

    def discover(self) -> List[str]:
        """发现所有技能"""
        discovered = self._loader.discover()
        for name in discovered:
            config = self._loader.load(name)
            if config:
                self._skills[name] = config
                self._engine.register_skill(config)
        return discovered

    def load(self, name: str) -> Optional[SkillConfigV2]:
        """加载指定技能"""
        if name in self._skills:
            return self._skills[name]
        return self._loader.load(name)

    def unload(self, name: str):
        """卸载指定技能"""
        self._skills.pop(name, None)
        self._engine.unregister_skill(name)

    def reload(self, name: str) -> Optional[SkillConfigV2]:
        """重新加载技能"""
        self.unload(name)
        return self.load(name)

    def enable(self, name: str):
        """启用技能"""
        if name in self._skills:
            self._skills[name].enabled = True
            # 重新注册到引擎
            self._engine.register_skill(self._skills[name])

    def disable(self, name: str):
        """禁用技能"""
        if name in self._skills:
            self._skills[name].enabled = False
            # 重新注册到引擎
            self._engine.register_skill(self._skills[name])

    def list_all(self) -> List[SkillConfigV2]:
        """列出所有技能"""
        return list(self._skills.values())

    def list_skills(self) -> List[str]:
        """列出所有技能名称"""
        return list(self._skills.keys())

    def get_skill_info(self, name: str) -> Optional[Any]:
        """获取技能信息"""
        config = self._skills.get(name)
        if not config:
            return None
        usage = self._usage_count.get(name, 0)
        return SkillInfo(config, usage)

    def get_trigger_engine(self) -> SkillTriggerEngine:
        """获取触发引擎"""
        return self._engine

    def should_trigger(self, task_description: str, name: str) -> tuple[bool, float]:
        """判断是否应该触发指定技能"""
        config = self._skills.get(name)
        if not config:
            return False, 0.0
        return self._engine.should_trigger(task_description, config)

    def find_best_match(self, task_description: str) -> Optional[tuple[str, SkillConfigV2, float]]:
        """为任务找到最佳匹配的技能"""
        return self._engine.find_best_match(task_description)

    async def run_skill(self, name: str, **kwargs) -> Any:
        """运行技能"""
        config = self._skills.get(name)
        if not config:
            raise ValueError(f"技能不存在: {name}")

        self._usage_count[name] = self._usage_count.get(name, 0) + 1

        skill_dir = Path(config.path)
        skill_py = skill_dir / "skill.py"

        if not skill_py.exists():
            return {"success": False, "error": f"技能执行文件不存在: {skill_py}"}

        import importlib.util

        spec = importlib.util.spec_from_file_location(f"skill_{name}", skill_py)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, "run"):
            return await module.run(**kwargs)
        elif hasattr(module, "main"):
            return await module.main(**kwargs)
        else:
            return {"success": False, "error": f"技能 {name} 没有 run 或 main 函数"}

    def print_status(self):
        """打印技能状态"""
        print(f"\n📦 技能状态 ({len(self._skills)} 个)\n")
        for name, config in self._skills.items():
            status = "✅" if config.enabled else "❌"
            print(f"  {status} {config.display_name} ({name})")
            print(f"     版本: {config.version}")
            print(f"     分类: {config.category}")
            print(f"     触发关键词: {', '.join(config.trigger.trigger_keywords[:5])}")
            if config.trigger.negative_keywords:
                print(f"     否定关键词: {', '.join(config.trigger.negative_keywords[:3])}")
            print()


class SkillInfo:
    """技能信息包装器"""

    def __init__(self, config: SkillConfigV2, usage_count: int = 0):
        self.config = config
        self.usage_count = usage_count
        self.status = SkillStatus.ENABLED if config.enabled else SkillStatus.DISABLED


# 导入创建模板函数
from skills.scaffold import create_mcp_tool_template, create_skill_scaffold

__all__ = [
    # V2 核心类
    "SkillTrigger",
    "SkillConfigV2",
    "SkillTriggerEngine",
    "SkillLoader",
    # 状态和分类
    "SkillStatus",
    "SkillCategory",
    # 管理器
    "SkillManager",
    "SkillInfo",
    # 模板生成
    "create_skill_scaffold",
    "create_mcp_tool_template",
]
