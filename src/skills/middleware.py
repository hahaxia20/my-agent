"""Skill middleware exposing lightweight skill metadata to the model."""

from __future__ import annotations

import logging
from typing import Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain.messages import SystemMessage
from langchain.tools import tool

from src.skills.manager import skill_registry

logger = logging.getLogger(__name__)


@tool
def load_skill(skill_name: str) -> str:
    """Load lightweight runtime guidance for a skill."""
    logger.info("load skill: %s", skill_name)
    skill = skill_registry.get_skill(skill_name)
    if not skill:
        available = ", ".join(s.name for s in skill_registry.get_all())
        return f"Skill '{skill_name}' not found. Available skills: {available}"
    if not getattr(skill, "enabled", True):
        return f"Skill '{skill_name}' is disabled."
    if hasattr(skill, "build_runtime_prompt"):
        return skill.build_runtime_prompt()
    return f"Skill: {skill.name}\nDescription: {skill.description}"


class SkillMiddleware(AgentMiddleware):
    tools = [load_skill]

    def __init__(self):
        self._refresh_skills_prompt()
        logger.info(
            "SkillMiddleware initialized: %s active / %s total",
            len(skill_registry.get_active_skills()),
            len(skill_registry.get_all()),
        )

    def _refresh_skills_prompt(self):
        self.skills_prompt = skill_registry.get_skills_metadata_list()

    def _build_addendum(self) -> str:
        return (
            "\n\n## Available Skills\n"
            f"{self.skills_prompt}\n\n"
            "Skills are lightweight routing metadata. Use `load_skill` only when you need a skill's runtime strategy. "
            "Prefer tool execution over loading long skill content."
        )

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        self._refresh_skills_prompt()
        return self._inject_skills(request, handler)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        self._refresh_skills_prompt()
        new_content = list(request.system_message.content_blocks) + [
            {"type": "text", "text": self._build_addendum()}
        ]
        modified_request = request.override(system_message=SystemMessage(content=new_content))
        return await handler(modified_request)

    def _inject_skills(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        new_content = list(request.system_message.content_blocks) + [
            {"type": "text", "text": self._build_addendum()}
        ]
        modified_request = request.override(system_message=SystemMessage(content=new_content))
        return handler(modified_request)
