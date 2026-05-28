"""系统提示词加载器 - 根据版本号从文件加载"""

import json
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# 提示词目录
PROMPT_DIR = Path(__file__).parent

# 全局提示词数据
SYSTEM_PROMPTS: Dict = {}


def get_prompt_file_path(version: Optional[str] = None) -> Path:
    """
    获取提示词文件路径
    
    Args:
        version: 版本号（如 "1.0", "1.1"）
    
    Returns:
        文件路径
    """
    if version:
        filename = f"system_prompts_v{version}.json"
    else:
        # 如果没有指定版本，尝试从配置读取
        try:
            from src.config import get_settings_safe
            settings = get_settings_safe()
            version = settings.SYSTEM_PROMPT_VERSION
            filename = f"system_prompts_v{version}.json"
        except Exception:
            # 配置读取失败，使用默认版本
            filename = "system_prompts_v1.0.json"
    
    return PROMPT_DIR / filename


def load_from_file(filepath: Optional[str] = None, version: Optional[str] = None) -> Dict:
    """
    从文件加载提示词
    
    Args:
        filepath: 文件路径（可选，如果提供则直接使用）
        version: 版本号（可选，如 "1.0", "1.1"）
    
    Returns:
        提示词字典
    """
    global SYSTEM_PROMPTS
    
    try:
        # 确定文件路径
        if filepath:
            prompt_path = Path(filepath)
        else:
            prompt_path = get_prompt_file_path(version)
        
        # 检查文件是否存在
        if not prompt_path.exists():
            logger.error(f"❌ 提示词文件不存在: {prompt_path}")
            return SYSTEM_PROMPTS
        
        # 加载 JSON 文件
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompts = json.load(f)
        
        # 验证格式
        if not isinstance(prompts, dict):
            logger.error(f"❌ 提示词格式错误: 必须是字典")
            return SYSTEM_PROMPTS
        
        # 更新全局提示词
        SYSTEM_PROMPTS = prompts
        logger.info(f"✅ 系统提示词已加载: {prompt_path.name} ({len(SYSTEM_PROMPTS)} 个版本)")
        
        return SYSTEM_PROMPTS
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON 格式错误: {e}")
        return SYSTEM_PROMPTS
    
    except Exception as e:
        logger.error(f"❌ 加载提示词文件失败: {e}")
        return SYSTEM_PROMPTS


def reload_prompts(version: Optional[str] = None):
    """
    重新加载提示词
    
    Args:
        version: 版本号（可选）
    """
    global SYSTEM_PROMPTS
    SYSTEM_PROMPTS = load_from_file(version=version)
    logger.info(f"🔄 系统提示词已重新加载")


def get_prompts() -> Dict:
    """获取当前系统提示词"""
    return SYSTEM_PROMPTS


# 启动时自动加载默认提示词（从配置文件读取版本号）
SYSTEM_PROMPTS = load_from_file()
