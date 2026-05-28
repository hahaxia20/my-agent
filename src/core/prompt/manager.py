"""系统提示词管理器"""

from typing import Optional
from src.core.prompt.system_prompts import SYSTEM_PROMPTS, load_from_file, reload_prompts
import logging

logger = logging.getLogger(__name__)


class SystemPromptManager:
    """系统提示词管理器"""
    
    def __init__(self, version: Optional[str] = None):
        """
        初始化提示词管理器
        
        Args:
            version: 提示词版本号（可选）
        """
        if version:
            self.prompts = load_from_file(version=version)
        else:
            self.prompts = SYSTEM_PROMPTS
    
    def get_prompt(self, model: Optional[str] = None) -> str:
        """
        获取系统提示词
        
        Args:
            model: 模型名称（如 "qwen", "gpt-4"）
        
        Returns:
            系统提示词模板
        """
        # 1. 根据模型查找匹配的版本
        if model:
            for key, prompt_data in self.prompts.items():
                prompt_model = prompt_data.get("model", "")
                # 支持包含匹配："qwen" 可以匹配 "qwen3.6-plus"
                if prompt_model and prompt_model in model:
                    logger.info(f"📝 使用系统提示词: {key} v{prompt_data['version']} ({prompt_data['description']})")
                    return prompt_data["template"]
        
        # 2. 使用默认版本
        default_prompt = self.prompts.get("default")
        if default_prompt:
            logger.info(f"📝 使用系统提示词: default v{default_prompt['version']}")
            return default_prompt["template"]
        
        # 3. 使用第一个可用的版本
        first_key = next(iter(self.prompts))
        logger.info(f"📝 使用系统提示词: {first_key}")
        return self.prompts[first_key]["template"]
    
    def list_prompts(self) -> list:
        """列出所有可用的系统提示词版本"""
        return [
            {
                "key": key,
                "version": data["version"],
                "description": data["description"],
                "model": data.get("model", "all"),
                "created_at": data["created_at"]
            }
            for key, data in self.prompts.items()
        ]
    
    def reload(self, version: Optional[str] = None):
        """重新加载提示词"""
        reload_prompts(version=version)
        # 更新本地缓存
        from src.core.prompt.system_prompts import SYSTEM_PROMPTS
        self.prompts = SYSTEM_PROMPTS
        logger.info(f"🔄 提示词已重新加载: {len(self.prompts)} 个版本")


# 全局实例
system_prompt_manager = SystemPromptManager()
