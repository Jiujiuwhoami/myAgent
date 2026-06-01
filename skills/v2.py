"""Skill 系统 V2 - Codex 兼容版本

新增特性：
- SKILL.md 主说明书支持（LLM 直接阅读）
- references/ 参考资料目录
- scripts/ 辅助脚本目录
- 自动触发引擎（根据任务描述匹配 Skill）
- Codex 格式兼容（trigger_keywords, auto_trigger）
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class SkillTrigger:
    """技能触发配置"""

    auto_trigger: bool = True
    trigger_keywords: List[str] = field(default_factory=list)
    negative_keywords: List[str] = field(default_factory=list)
    match_mode: str = "any"
    priority: int = 10
    min_confidence: float = 0.7


@dataclass
class SkillConfigV2:
    """技能配置 V2 - Codex 兼容"""

    meta: dict
    trigger: SkillTrigger
    parameters: List[dict] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    scripts: Dict[str, str] = field(default_factory=dict)
    tools: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    compatibility: Dict[str, bool] = field(default_factory=dict)
    enabled: bool = True
    path: str = ""

    @classmethod
    def from_file(cls, path: Path) -> "SkillConfigV2":
        """从 skill.json 加载配置"""
        if not path.exists():
            raise FileNotFoundError(f"技能配置文件不存在: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        trigger_data = data.get("trigger", {})
        trigger = SkillTrigger(
            auto_trigger=trigger_data.get("auto_trigger", True),
            trigger_keywords=trigger_data.get("trigger_keywords", []),
            negative_keywords=trigger_data.get("negative_keywords", []),
            match_mode=trigger_data.get("match_mode", "any"),
            priority=trigger_data.get("priority", 10),
            min_confidence=trigger_data.get("min_confidence", 0.7),
        )

        return cls(
            meta=data.get("meta", {}),
            trigger=trigger,
            parameters=data.get("parameters", data.get("params", [])),
            references=data.get("references", []),
            scripts=data.get("scripts", {}),
            tools=data.get("tools", []),
            dependencies=data.get("dependencies", []),
            compatibility=data.get("compatibility", {}),
            enabled=data.get("enabled", True),
            path=str(path.parent),
        )

    @property
    def name(self) -> str:
        return self.meta.get("name", "")

    @property
    def description(self) -> str:
        return self.meta.get("description", "")

    @property
    def display_name(self) -> str:
        return self.meta.get("display_name", self.name.replace("_", " ").title())

    @property
    def version(self) -> str:
        return self.meta.get("version", "1.0.0")

    @property
    def category(self) -> str:
        return self.meta.get("category", "custom")

    def get_skill_md_path(self) -> Optional[Path]:
        """获取 SKILL.md 路径"""
        skill_dir = Path(self.path)
        md_path = skill_dir / "SKILL.md"
        return md_path if md_path.exists() else None

    def get_references_dir(self) -> Optional[Path]:
        """获取 references 目录路径"""
        ref_dir = Path(self.path) / "references"
        return ref_dir if ref_dir.exists() else None

    def get_skill_instructions(self) -> Optional[str]:
        """获取主说明书内容（SKILL.md）"""
        md_path = self.get_skill_md_path()
        if md_path:
            return md_path.read_text(encoding="utf-8")
        return None


class SkillTriggerEngine:
    """技能自动触发引擎

    根据任务描述自动匹配最佳技能
    """

    def __init__(self):
        self._skills: Dict[str, SkillConfigV2] = {}

    def register_skill(self, config: SkillConfigV2):
        """注册技能"""
        self._skills[config.name] = config

    def unregister_skill(self, name: str):
        """注销技能"""
        self._skills.pop(name, None)

    def should_trigger(self, task_description: str, config: SkillConfigV2) -> tuple[bool, float]:
        """判断是否应该触发该技能

        返回: (should_trigger, confidence)
        """
        # 检查是否启用
        if not config.enabled:
            return False, 0.0

        if not config.trigger.auto_trigger:
            return False, 0.0

        task_lower = task_description.lower()

        # 检查否定关键词
        for neg_kw in config.trigger.negative_keywords:
            if neg_kw.lower() in task_lower:
                return False, 0.0

        # 检查触发关键词
        if config.trigger.trigger_keywords:
            matched_keywords = []
            for keyword in config.trigger.trigger_keywords:
                if keyword.lower() in task_lower:
                    matched_keywords.append(keyword)

            if matched_keywords:
                base_confidence = 0.6
                keyword_bonus = min(0.4, len(matched_keywords) * 0.1)
                confidence = min(0.95, base_confidence + keyword_bonus)

                # 多词短语奖励
                for kw in matched_keywords:
                    if len(kw) > 3:
                        confidence = min(0.95, confidence + 0.1)

                if config.trigger.match_mode == "any" and matched_keywords:
                    return True, confidence
                elif config.trigger.match_mode == "all" and len(matched_keywords) == len(
                    config.trigger.trigger_keywords
                ):
                    return True, confidence

        # 语义匹配（描述匹配）
        desc_lower = config.description.lower()
        desc_words = set(re.findall(r"\b\w+\b", desc_lower))
        task_words = set(re.findall(r"\b\w+\b", task_lower))

        if desc_words and task_words:
            overlap = desc_words & task_words
            semantic_score = len(overlap) / max(len(desc_words), len(task_words))
            if semantic_score > 0.3:
                return True, semantic_score * 0.8

        return False, 0.0

    def find_best_match(self, task_description: str) -> Optional[tuple[str, SkillConfigV2, float]]:
        """为任务找到最佳匹配的技能

        返回: (skill_name, config, confidence)
        """
        candidates = []

        for name, config in self._skills.items():
            if not config.enabled:
                continue
            should_trigger, confidence = self.should_trigger(task_description, config)
            if should_trigger and confidence >= config.trigger.min_confidence:
                candidates.append((name, config, confidence))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (x[1].trigger.priority, x[2]), reverse=True)
        return candidates[0]

    def list_skills(self) -> List[str]:
        """列出所有注册的技能"""
        return list(self._skills.keys())

    def get_skill(self, name: str) -> Optional[SkillConfigV2]:
        """获取技能配置"""
        return self._skills.get(name)


class SkillLoader:
    """技能加载器

    从目录发现和加载技能
    """

    def __init__(self, skill_dir: str = "skills"):
        self.skill_dir = Path(skill_dir)
        self._discovered: Dict[str, SkillConfigV2] = {}

    def discover(self) -> List[str]:
        """发现所有技能"""
        discovered = []

        if not self.skill_dir.exists():
            return discovered

        for skill_path in self.skill_dir.iterdir():
            if not skill_path.is_dir():
                continue

            config_file = skill_path / "skill.json"
            if not config_file.exists():
                continue

            try:
                config = SkillConfigV2.from_file(config_file)
                self._discovered[config.name] = config
                discovered.append(config.name)
            except Exception as e:
                print(f"[WARN] 加载技能失败: {skill_path.name} - {e}")

        return discovered

    def load(self, name: str) -> Optional[SkillConfigV2]:
        """加载指定技能"""
        return self._discovered.get(name)

    def list_all(self) -> List[SkillConfigV2]:
        """列出所有发现的技能"""
        return list(self._discovered.values())
