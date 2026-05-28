"""Skill 中间件 - 自动注入 Skill 元数据到系统提示词"""

from typing import Callable
from langchain.agents.middleware import ModelRequest, ModelResponse, AgentMiddleware
from langchain.messages import SystemMessage
from langchain.tools import tool
from src.skills.manager import skill_registry
import logging

logger = logging.getLogger(__name__)


@tool
def load_skill(skill_name: str) -> str:
    """Load the full content of a skill into the agent's context.

    Use this when you need detailed information about how to handle a specific
    type of request. This will provide you with comprehensive instructions,
    policies, and guidelines for the skill area.

    Args:
        skill_name: The name of the skill to load (e.g., "web-content-analyzer", "code-analysis", "data-analysis")
    """
    logger.info(f"📥 [加载 Skill] {skill_name}")
    
    skill = skill_registry.get_skill(skill_name)
    
    if not skill:
        available = ", ".join(s.name for s in skill_registry.get_all())
        return f"Skill '{skill_name}' not found. Available skills: {available}"
    
    # 获取完整指令
    if hasattr(skill, 'config') and hasattr(skill.config, 'instructions'):
        content = skill.config.instructions
    elif hasattr(skill, 'prompt_template'):
        content = skill.prompt_template
    else:
        content = str(skill)
    
    logger.info(f"✅ [Skill 加载成功] {skill_name} ({len(content)} 字符)")
    
    return f"Loaded skill: {skill_name}\n\n{content}"


class SkillMiddleware(AgentMiddleware):
    """Middleware that injects skill descriptions into the system prompt."""
    
    tools = [load_skill]
    
    def __init__(self):
        """Initialize and generate the skills prompt from registry."""
        skills_list = []
        for skill in skill_registry.get_all():
            skills_list.append(f"- **{skill.name}**: {skill.description}")
        
        self.skills_prompt = "\n".join(skills_list)
        logger.info(f"📦 SkillMiddleware 初始化，加载 {len(skills_list)} 个 Skills")
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Sync: Inject skill descriptions into system prompt."""
        return self._inject_skills(request, handler)
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Async: Inject skill descriptions into system prompt."""
        skills_addendum = (
            f"\n\n## 可用技能\n\n{self.skills_prompt}\n\n"
            "使用 `load_skill` 工具加载技能的完整指令。"
        )
        
        # 追加到系统消息
        new_content = list(request.system_message.content_blocks) + [
            {"type": "text", "text": skills_addendum}
        ]
        new_system_message = SystemMessage(content=new_content)
        
        modified_request = request.override(system_message=new_system_message)
        return await handler(modified_request)
    
    def _inject_skills(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Inject skill descriptions into system prompt."""
        skills_addendum = (
            f"\n\n## 可用技能\n\n{self.skills_prompt}\n\n"
            "使用 `load_skill` 工具加载技能的完整指令。"
        )
        
        # 追加到系统消息
        new_content = list(request.system_message.content_blocks) + [
            {"type": "text", "text": skills_addendum}
        ]
        new_system_message = SystemMessage(content=new_content)
        
        modified_request = request.override(system_message=new_system_message)
        return handler(modified_request)
