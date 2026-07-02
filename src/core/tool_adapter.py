"""
工具适配模块

负责将自定义工具转换为 LangChain StructuredTool，
并提供工具调用日志装饰器。
"""

import asyncio
import inspect
import logging
import time
from functools import wraps
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import create_model, Field

logger = logging.getLogger(__name__)


def _tool_debug_enabled() -> bool:
    try:
        from src.config import get_settings_safe
        return bool(getattr(get_settings_safe(), "TOOL_DEBUG", False))
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def safe_truncate(text: str, max_length: int = 500) -> str:
    """安全截断文本，避免日志过长"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


# ═══════════════════════════════════════════════════════════
# 工具调用日志装饰器
# ═══════════════════════════════════════════════════════════

def log_tool_call(tool_name: str):
    """
    工具调用日志装饰器
    自动记录工具调用的开始、成功/失败、耗时等信息
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            logger.info(f"🔧 [工具调用开始] {tool_name} - 参数: {safe_truncate(str(kwargs), 200)}")
            
            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.info(
                    f"✅ [工具调用成功] {tool_name} - "
                    f"耗时: {elapsed:.2f}s - "
                    f"结果长度: {len(str(result))} 字符"
                )
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(
                    f"❌ [工具调用失败] {tool_name} - "
                    f"耗时: {elapsed:.2f}s - "
                    f"错误: {str(e)}",
                    exc_info=True
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            logger.info(f"🔧 [工具调用开始] {tool_name} - 参数: {safe_truncate(str(kwargs), 200)}")
            
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.info(
                    f"✅ [工具调用成功] {tool_name} - "
                    f"耗时: {elapsed:.2f}s - "
                    f"结果长度: {len(str(result))} 字符"
                )
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(
                    f"❌ [工具调用失败] {tool_name} - "
                    f"耗时: {elapsed:.2f}s - "
                    f"错误: {str(e)}",
                    exc_info=True
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# ═══════════════════════════════════════════════════════════
# Args Schema 构建
# ═══════════════════════════════════════════════════════════

# JSON Schema 类型到 Python 类型的映射
_TYPE_MAP = {
    'integer': int,
    'number': float,
    'boolean': bool,
    'string': str,
}


def build_args_schema(tool_name: str, parameters: dict):
    """
    根据工具的 parameters (JSON Schema) 构建 Pydantic args_schema
    
    Args:
        tool_name: 工具名称
        parameters: JSON Schema 格式的参数定义
    
    Returns:
        Pydantic model 或 None
    """
    if not parameters:
        return None
    
    properties = parameters.get('properties', {})
    required = parameters.get('required', [])
    
    if not properties:
        return None
    
    fields = {}
    for param_name, param_info in properties.items():
        field_type = _TYPE_MAP.get(param_info.get('type'), str)
        description = param_info.get('description', '')
        
        if param_name in required:
            fields[param_name] = (field_type, Field(description=description))
        else:
            fields[param_name] = (Optional[field_type], Field(default=None, description=description))
    
    if fields:
        schema = create_model(f"{tool_name.title()}Schema", **fields)
        logger.debug(f"为工具 {tool_name} 创建 args_schema: {list(fields.keys())}")
        return schema
    
    return None


# ═══════════════════════════════════════════════════════════
# 工具转换
# ═══════════════════════════════════════════════════════════

def get_tool_type(tool) -> str:
    """获取工具类型 (async/sync)"""
    if hasattr(tool, 'execute'):
        if inspect.iscoroutinefunction(tool.execute):
            return "async"
        else:
            return "sync"
    return "unknown"


def convert_to_langchain_tool(tool) -> StructuredTool:
    """
    将自定义工具转换为 LangChain StructuredTool
    支持异步和同步工具，自动添加日志装饰器
    
    Args:
        tool: 自定义工具实例，需有 name、description、execute 属性
    
    Returns:
        LangChain StructuredTool
    """
    tool_name = tool.name

    # 如果工具自带转换方法，直接使用
    if hasattr(tool, 'to_langchain_tool'):
        logger.debug(f"使用工具自带的转换方法: {tool_name}")
        return tool.to_langchain_tool()

    # 构建 args_schema
    parameters = getattr(tool, 'parameters', None)
    args_schema = build_args_schema(tool_name, parameters) if parameters else None

    # 异步工具
    if hasattr(tool, 'execute') and inspect.iscoroutinefunction(tool.execute):
        @log_tool_call(tool_name)
        async def logged_execute(**kwargs):
            logger.debug(f"执行异步工具 {tool_name}, kwargs: {kwargs}")
            return await tool.execute(**kwargs)

        structured_tool = StructuredTool(
            name=tool_name,
            description=tool.description,
            coroutine=logged_execute,
            args_schema=args_schema
        )
        
        logger.debug(f"工具 {tool_name}: name={structured_tool.name}, has_args_schema={structured_tool.args_schema is not None}")
        return structured_tool
    
    # 同步工具
    elif hasattr(tool, 'execute'):
        @log_tool_call(tool_name)
        def logged_execute(**kwargs):
            logger.debug(f"执行同步工具 {tool_name}, kwargs: {kwargs}")
            return tool.execute(**kwargs)

        structured_tool = StructuredTool(
            name=tool_name,
            description=tool.description,
            func=logged_execute,
            args_schema=args_schema
        )
        
        logger.debug(f"工具 {tool_name}: name={structured_tool.name}, has_args_schema={structured_tool.args_schema is not None}")
        return structured_tool
    else:
        raise ValueError(f"工具 {tool_name} 没有 execute 方法")
