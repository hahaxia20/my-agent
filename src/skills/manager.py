"""Skill registry and lightweight metadata model."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, model_validator, field_validator

logger = logging.getLogger(__name__)


@dataclass
class LoadReport:
    loaded: List[str] = field(default_factory=list)
    failed: List[Dict[str, str]] = field(default_factory=list)

    @property
    def total_attempted(self) -> int:
        return len(self.loaded) + len(self.failed)

    def summary(self) -> str:
        parts = [f"loaded {len(self.loaded)}/{self.total_attempted} skills"]
        if self.failed:
            fail_details = "; ".join(f"{f['name']}: {f['error']}" for f in self.failed)
            parts.append(f"failed: [{fail_details}]")
        return " | ".join(parts)


@dataclass
class ReloadReport:
    added: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    reloaded: List[str] = field(default_factory=list)
    failed: List[Dict[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        parts: List[str] = []
        if self.added:
            parts.append(f"added: {self.added}")
        if self.removed:
            parts.append(f"removed: {self.removed}")
        if self.reloaded:
            parts.append(f"reloaded: {len(self.reloaded)}")
        if self.failed:
            parts.append(f"failed: {[f['name'] for f in self.failed]}")
        return " | ".join(parts) if parts else "no changes"


class SkillMetadata(BaseModel):
    name: str = Field(..., description="Skill name")
    description: str = Field(..., description="What the skill is for")
    trigger_keywords: List[str] = Field(default_factory=list, description="Routing keywords")
    use_strategy: Optional[str] = Field(None, description="Short runtime strategy")
    allowed_tools: List[str] = Field(default_factory=list, description="Allowed runtime tools")
    version: str = Field(default="1.0.0", description="Semantic version")
    license: Optional[str] = Field(None, description="License")
    compatibility: Optional[str] = Field(None, description="Compatibility notes")
    enabled: bool = Field(True, description="Whether the skill is enabled")
    max_tokens: Optional[int] = Field(None, description="Legacy prompt guard")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata")

    @model_validator(mode="before")
    @classmethod
    def lift_legacy_metadata_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        metadata = data.get("metadata")
        if isinstance(metadata, dict):
            if not data.get("version") and metadata.get("version"):
                data["version"] = str(metadata["version"])
            metadata.pop("version", None)
        return data

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value:
            raise ValueError("name cannot be empty")
        if len(value) > 64:
            raise ValueError("name cannot exceed 64 characters")
        if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", value):
            raise ValueError("name must contain lowercase letters, numbers, or hyphens")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("description cannot be empty")
        if len(value) > 1024:
            raise ValueError("description cannot exceed 1024 characters")
        return value.strip()

    @field_validator("trigger_keywords", "allowed_tools", mode="before")
    @classmethod
    def split_csv_like_values(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return list(value)

    @field_validator("use_strategy", mode="before")
    @classmethod
    def normalize_strategy(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value).strip()

    @field_validator("version", mode="before")
    @classmethod
    def normalize_version(cls, value: Any) -> str:
        if value is None or str(value).strip() == "":
            return "1.0.0"
        return str(value).strip()

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("metadata must be a YAML object when provided")
        return value


class SkillConfig(BaseModel):
    metadata: SkillMetadata
    instructions: str = Field(default="", description="Legacy raw body content")
    skill_path: Path = Field(..., description="Skill directory path")
    scripts: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    assets: List[str] = Field(default_factory=list)
    resolved_tools: List[str] = Field(default_factory=list)


class BaseSkill(ABC):
    name: str
    description: str
    enabled: bool = True

    @abstractmethod
    async def execute(self, user_query: str, **kwargs) -> Any:
        raise NotImplementedError


class MarkdownSkill(BaseSkill):
    """Skill backed by SKILL.md frontmatter metadata."""

    def __init__(self, skill_path: Path):
        self.config = self._parse_skill_md(skill_path)
        self.name = self.config.metadata.name
        self.description = self.config.metadata.description
        self.enabled = self.config.metadata.enabled
        self.max_tokens = self.config.metadata.max_tokens
        self.version = self.config.metadata.version
        self.license = self.config.metadata.license
        self.extra_metadata = dict(self.config.metadata.metadata)
        self.resolved_tools = self.config.resolved_tools
        self.allowed_tools = list(self.config.metadata.allowed_tools)
        self.trigger_keywords = list(self.config.metadata.trigger_keywords)
        self.use_strategy = self._resolve_use_strategy()
        self.instruction_summary = self._build_instruction_summary()
        self.has_declared_tools = bool(self.config.metadata.allowed_tools)
        self.skill_path = skill_path
        self.scripts = self.config.scripts
        self.references = self.config.references
        self.assets = self.config.assets
        logger.info(
            "loaded skill metadata: %s (enabled=%s, version=%s, tools=%s)",
            self.name,
            self.enabled,
            self.version,
            self.resolved_tools,
        )

    def _parse_skill_md(self, skill_path: Path) -> SkillConfig:
        md_file = skill_path / "SKILL.md"
        if not md_file.exists():
            raise FileNotFoundError(f"SKILL.md missing: {md_file}")

        content = md_file.read_text(encoding="utf-8-sig")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
        if not match:
            raise ValueError(f"SKILL.md frontmatter missing: {md_file}")

        frontmatter_yaml = match.group(1)
        instructions = match.group(2).strip()

        try:
            metadata_dict = yaml.safe_load(frontmatter_yaml)
        except yaml.YAMLError as exc:
            raise ValueError(f"SKILL.md YAML parse failed: {md_file} -> {exc}") from exc

        if not isinstance(metadata_dict, dict):
            raise ValueError(f"SKILL.md frontmatter must be a YAML object: {md_file}")

        metadata = SkillMetadata(**metadata_dict)
        scripts = self._extract_file_links(instructions, r"\[\$\.scripts/(.+?)\]")
        references = self._extract_file_links(instructions, r"\[\$\.references/(.+?)\]")
        assets = self._extract_file_links(instructions, r"\[\$\.assets/(.+?)\]")

        resolved_tools: List[str] = []
        if metadata.allowed_tools:
            from src.tools.manager import tool_manager

            for tool_name in metadata.allowed_tools:
                if tool_manager.has_tool(tool_name):
                    resolved_tools.append(tool_name)
                else:
                    logger.warning("skill '%s' declares missing tool '%s'", metadata.name, tool_name)

        return SkillConfig(
            metadata=metadata,
            instructions=instructions,
            skill_path=skill_path,
            scripts=scripts,
            references=references,
            assets=assets,
            resolved_tools=resolved_tools,
        )

    @staticmethod
    def _extract_file_links(text: str, pattern: str) -> List[str]:
        return re.findall(pattern, text)

    def _resolve_use_strategy(self) -> str:
        strategy = (self.config.metadata.use_strategy or "").strip()
        return strategy

    def _build_instruction_summary(self) -> str:
        instructions = (self.config.instructions or "").strip()
        if not instructions:
            return ""

        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", instructions) if part.strip()]
        for paragraph in paragraphs:
            if paragraph.startswith("#"):
                continue
            if paragraph.startswith("```"):
                continue
            if paragraph.startswith("- "):
                continue
            compact = re.sub(r"\s+", " ", paragraph).strip()
            if compact:
                return compact[:220] + ("..." if len(compact) > 220 else "")

        fallback = re.sub(r"\s+", " ", instructions).strip()
        return fallback[:220] + ("..." if len(fallback) > 220 else "") if fallback else ""

    def build_runtime_prompt(self) -> str:
        lines = [f"# Skill: {self.name}", self.description]
        if self.trigger_keywords:
            lines.append(f"Trigger keywords: {', '.join(self.trigger_keywords)}")
        if self.use_strategy:
            lines.append(f"Use strategy: {self.use_strategy}")
        elif self.instruction_summary:
            lines.append(f"Instruction summary: {self.instruction_summary}")
        if self.version and self.version != "1.0.0":
            lines.append(f"Version: {self.version}")
        if self.resolved_tools:
            lines.append(f"Allowed tools: {', '.join(self.resolved_tools)}")
        elif self.has_declared_tools:
            lines.append("Declared tools are currently unavailable in runtime. Do not pretend the tool calls succeeded.")
        return "\n".join(lines)

    async def execute(self, user_query: str, **kwargs) -> Any:
        llm = kwargs.get("llm")
        if not llm:
            return {"skill": self.name, "error": "missing llm", "success": False}

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=self.build_runtime_prompt()),
                HumanMessage(content=user_query),
            ]
            response = await llm.ainvoke(messages)
            return {
                "skill": self.name,
                "result": response.content,
                "success": True,
                "metadata": {
                    "version": self.version,
                    "author": self.extra_metadata.get("author"),
                },
            }
        except Exception as exc:
            logger.error("skill execution failed: %s - %s", self.name, exc, exc_info=True)
            return {"skill": self.name, "error": str(exc), "success": False}

    def _build_system_prompt(self) -> str:
        return self.build_runtime_prompt()


def _parse_version(version: Optional[str]) -> tuple:
    if not version:
        return (0,)
    try:
        return tuple(int(x) for x in str(version).split("."))
    except ValueError:
        return (0,)


class SkillRegistry:
    def __init__(self):
        self.skills: Dict[str, BaseSkill] = {}

    def get_skill(self, skill_name: str) -> Optional[BaseSkill]:
        return self.skills.get(skill_name)

    def has_skill(self, skill_name: str) -> bool:
        return skill_name in self.skills

    def enable(self, skill_name: str) -> bool:
        skill = self.skills.get(skill_name)
        if not skill:
            return False
        skill.enabled = True
        logger.info("skill enabled: %s", skill_name)
        return True

    def disable(self, skill_name: str) -> bool:
        skill = self.skills.get(skill_name)
        if not skill:
            return False
        skill.enabled = False
        logger.info("skill disabled: %s", skill_name)
        return True

    def get_active_skills(self) -> List[BaseSkill]:
        return [skill for skill in self.skills.values() if skill.enabled]

    def get_skills_metadata_list(self) -> str:
        active = self.get_active_skills()
        if not active:
            return "No active skills"

        lines: List[str] = []
        for skill in active:
            parts = [f"- **{skill.name}**: {skill.description}"]

            trigger_keywords = getattr(skill, "trigger_keywords", [])[:6]
            if trigger_keywords:
                parts.append(f"triggers: {', '.join(trigger_keywords)}")

            resolved_tools = getattr(skill, "resolved_tools", [])
            if resolved_tools:
                parts.append(f"tools: {', '.join(resolved_tools)}")

            strategy = re.sub(r"\s+", " ", getattr(skill, "use_strategy", "")).strip()
            if strategy:
                if len(strategy) > 120:
                    strategy = strategy[:117] + "..."
                parts.append(f"strategy: {strategy}")

            version = getattr(skill, "version", "1.0.0")
            if version and version != "1.0.0":
                parts.append(f"version: {version}")

            lines.append(" | ".join(parts))
        return "\n".join(lines)

    def get_allowed_tools(self, skill_name: str) -> List[str]:
        skill = self.get_skill(skill_name)
        if not skill or not getattr(skill, "enabled", True):
            return []
        return list(getattr(skill, "resolved_tools", []))

    def get_all(self) -> List[BaseSkill]:
        return list(self.skills.values())

    def load_from_directory(self, skills_dir: Path) -> LoadReport:
        report = LoadReport()
        if not skills_dir.exists():
            logger.warning("skills directory missing: %s", skills_dir)
            return report

        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("__"):
                continue
            if not (skill_dir / "SKILL.md").exists():
                continue

            dir_name = skill_dir.name
            try:
                skill = MarkdownSkill(skill_dir)
                if skill.name in self.skills:
                    existing = self.skills[skill.name]
                    old_ver_str = getattr(existing, "version", None)
                    new_ver_str = skill.version
                    if _parse_version(new_ver_str) >= _parse_version(old_ver_str):
                        logger.warning("duplicate skill '%s', replacing older version", skill.name)
                        self.skills[skill.name] = skill
                else:
                    self.skills[skill.name] = skill
                report.loaded.append(skill.name)
                logger.info("loaded skill: %s", skill.name)
            except FileNotFoundError as exc:
                report.failed.append({"name": dir_name, "error": f"missing file: {exc}"})
            except yaml.YAMLError as exc:
                report.failed.append({"name": dir_name, "error": f"yaml error: {exc}"})
            except ValueError as exc:
                report.failed.append({"name": dir_name, "error": f"validation failed: {exc}"})
            except Exception as exc:
                report.failed.append({"name": dir_name, "error": str(exc)})
                logger.error("unexpected skill load failure: %s - %s", dir_name, exc, exc_info=True)

        logger.info("%s <- %s", report.summary(), skills_dir)
        return report

    def reload(self, skills_dir: Optional[Path] = None) -> ReloadReport:
        if skills_dir is None:
            skills_dir = Path(__file__).parent

        old_names = set(self.skills.keys())
        self.skills.clear()
        load_report = self.load_from_directory(skills_dir)
        new_names = set(self.skills.keys())
        report = ReloadReport(
            added=sorted(new_names - old_names),
            removed=sorted(old_names - new_names),
            reloaded=sorted(new_names & old_names),
            failed=load_report.failed,
        )
        logger.info("skills reloaded: %s", report.summary())
        return report


skill_registry = SkillRegistry()
SKILLS_DIR = Path(__file__).parent
_init_report = skill_registry.load_from_directory(SKILLS_DIR)
logger.info("skill bootstrap complete: %s skills, failed=%s", len(skill_registry.get_all()), len(_init_report.failed))
