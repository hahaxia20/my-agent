"""系统提示词上下文管理器 - 构建和管理系统提示词"""

from src.config import get_settings_safe
from src.core.prompt import system_prompt_manager
from typing import Optional


class SystemPromptContextManager:
    """系统提示词上下文管理器
    
    负责根据模型类型选择合适的系统提示词，
    为 LLM 提供角色设定和行为准则。
    """

    def __init__(self, model: Optional[str] = None):
        self.settings = get_settings_safe()
        self.model = model  # 模型名称，如 "qwen", "gpt-4"
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词（使用提示词模板）"""
        return system_prompt_manager.get_prompt(model=self.model)
