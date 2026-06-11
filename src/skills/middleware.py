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
        skill_name: The name of the skill to load (e.g., "web-content-analyzer", "data-analysis")
    """
    logger.info(f"📥 [加载 Skill] {skill_name}")

    skill = skill_registry.get_skill(skill_name)

    if not skill:
        available = ", ".join(s.name for s in skill_registry.get_all())
        return f"Skill '{skill_name}' not found. Available skills: {available}"

    # 检查启用状态
    if not getattr(skill, 'enabled', True):
        return (
            f"Skill '{skill_name}' 当前已禁用，无法加载。"
            "请联系管理员通过 Skill 管理接口启用后再使用。"
        )

    # 获取完整指令
    if hasattr(skill, 'config') and hasattr(skill.config, 'instructions'):
        content = skill.config.instructions
    elif hasattr(skill, 'prompt_template'):
        content = skill.prompt_template
    else:
        content = str(skill)

    # 指令长度保护（与 manager.py 中的 _build_system_prompt 保持一致）
    max_tokens = getattr(skill, 'max_tokens', None)
    if max_tokens:
        estimated_chars = max_tokens * 3
        if len(content) > estimated_chars:
            logger.warning(
                f"⚠️ [Skill 指令截断] {skill_name} 长度 {len(content)} > "
                f"max_tokens={max_tokens}（约 {estimated_chars} 字符）"
            )
            content = content[:estimated_chars] + "\n\n...（指令已截断，完整内容请查看 SKILL.md）"

    logger.info(f"✅ [Skill 加载成功] {skill_name} ({len(content)} 字符)")

    # 构建响应：指令 + 绑定工具提示（渐进式引导）
    result_parts = [f"Loaded skill: {skill_name}\n\n{content}"]

    resolved_tools = getattr(skill, 'resolved_tools', [])
    if resolved_tools:
        tools_str = ', '.join(f'`{t}`' for t in resolved_tools)
        result_parts.append(
            f"\n\n---\n🔧 **本技能配套工具**: {tools_str}\n"
            "请在执行任务时优先使用以上工具。"
        )
        logger.info(f"🔧 [Skill 绑定工具] {skill_name} → {resolved_tools}")

    return "".join(result_parts)


class SkillMiddleware(AgentMiddleware):
    """Middleware that injects skill descriptions into the system prompt."""

    tools = [load_skill]

    def __init__(self):
        """Initialize and generate the skills prompt from registry."""
        self._refresh_skills_prompt()
        logger.info(
            f"📦 SkillMiddleware 初始化，"
            f"已启用 {len(skill_registry.get_active_skills())} / "
            f"共 {len(skill_registry.get_all())} 个 Skills"
        )

    def _refresh_skills_prompt(self):
        """从 registry 重新生成 skills_prompt（reload / enable / disable 后调用）"""
        self.skills_prompt = skill_registry.get_skills_metadata_list()

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Sync: Inject skill descriptions into system prompt."""
        # 每次调用前刷新，确保反映最新状态（热重载 / 启禁用后生效）
        self._refresh_skills_prompt()
        return self._inject_skills(request, handler)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Async: Inject skill descriptions into system prompt."""
        # 每次调用前刷新，确保反映最新状态
        self._refresh_skills_prompt()
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
