# src/tools/base.py
"""
工具基类 - 生产级实现
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, Awaitable
import asyncio
import logging
from datetime import datetime
from functools import wraps

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """工具执行错误"""
    pass


class BaseTool(ABC):
    """生产级工具基类"""
    
    def __init__(self):
        self.name: str = ""
        self.description: str = ""
        self.parameters: Dict[str, Any] = {}
        self.timeout: int = 30  # 默认超时30秒
        self.retry_count: int = 2  # 默认重试2次
    
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """异步执行工具（子类必须实现）"""
        pass
    
    async def execute_with_retry(self, **kwargs) -> Any:
        """带重试的执行"""
        last_error = None
        
        for attempt in range(self.retry_count + 1):
            try:
                # 带超时的执行
                result = await asyncio.wait_for(
                    self.execute(**kwargs),
                    timeout=self.timeout
                )
                
                if attempt > 0:
                    logger.info(f"工具 {self.name} 重试成功 (attempt {attempt})")
                
                return result
                
            except asyncio.TimeoutError:
                last_error = ToolExecutionError(f"工具 {self.name} 执行超时 ({self.timeout}s)")
                logger.warning(f"工具 {self.name} 超时，重试 {attempt}/{self.retry_count}")
                
            except Exception as e:
                last_error = e
                logger.error(f"工具 {self.name} 执行失败 (attempt {attempt}): {e}")
                
            # 如果不是最后一次尝试，等待后重试
            if attempt < self.retry_count:
                await asyncio.sleep(2 ** attempt)  # 指数退避
        
        raise last_error or ToolExecutionError(f"工具 {self.name} 执行失败")
    
    def to_langchain_tool(self):
        """转换为 LangChain 工具格式"""
        from langchain_core.tools import StructuredTool
        
        return StructuredTool(
            name=self.name,
            description=self.description,
            coroutine=self.execute_with_retry,  # 使用带重试的异步方法
            args_schema=self._get_pydantic_schema(),
        )
    
    def _get_pydantic_schema(self):
        """从 parameters 生成 Pydantic schema"""
        from pydantic import BaseModel, create_model
        
        fields = {}
        properties = self.parameters.get("properties", {})
        required = self.parameters.get("required", [])
        
        for field_name, field_info in properties.items():
            field_type = self._json_type_to_python(field_info.get("type", "string"))
            default = field_info.get("default")
            description = field_info.get("description", "")
            
            if field_name in required:
                fields[field_name] = (field_type, ...)
            else:
                fields[field_name] = (field_type, default)
        
        return create_model(f"{self.name}_schema", **fields)
    
    @staticmethod
    def _json_type_to_python(json_type: str):
        """JSON 类型转 Python 类型"""
        type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        return type_map.get(json_type, str)