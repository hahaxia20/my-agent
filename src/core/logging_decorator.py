"""
通用日志装饰器

提供统一的方法调用日志记录功能
"""

import functools
import logging
import time
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


def log_method_call(
    log_level: int = logging.INFO,
    log_args: bool = False,
    log_result: bool = False,
    log_duration: bool = True,
    prefix: str = ""
):
    """
    方法调用日志装饰器
    
    Args:
        log_level: 日志级别 (默认 INFO)
        log_args: 是否记录参数 (默认 False，避免敏感信息泄露)
        log_result: 是否记录返回值 (默认 False，避免大对象)
        log_duration: 是否记录执行时长 (默认 True)
        prefix: 日志前缀 (默认空)
        
    Returns:
        装饰器函数
        
    示例:
        @log_method_call(prefix="用户操作")
        def create_user(self, name: str):
            pass
            
        # 输出:
        # [用户操作] 开始调用: create_user
        # [用户操作] 完成调用: create_user - 耗时: 0.12s
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 提取方法名
            method_name = func.__name__
            class_name = args[0].__class__.__name__ if args else ""
            full_name = f"{class_name}.{method_name}" if class_name else method_name
            
            # 开始日志
            start_time = time.time()
            logger.log(log_level, f"{prefix}开始调用: {full_name}")
            
            if log_args and args:
                # 跳过 self 参数
                args_str = ", ".join(str(arg) for arg in args[1:] if not hasattr(arg, '__dict__'))
                kwargs_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
                all_args = ", ".join(filter(None, [args_str, kwargs_str]))
                if all_args:
                    logger.debug(f"{prefix}参数: {all_args}")
            
            try:
                # 执行方法
                result = await func(*args, **kwargs)
                
                # 成功日志
                duration = time.time() - start_time
                duration_str = f" - 耗时: {duration:.3f}s" if log_duration else ""
                
                if log_result and result is not None:
                    result_str = str(result)[:200]  # 限制长度
                    logger.log(log_level, f"{prefix}完成调用: {full_name}{duration_str} - 结果: {result_str}")
                else:
                    logger.log(log_level, f"{prefix}完成调用: {full_name}{duration_str}")
                
                return result
                
            except Exception as e:
                # 异常日志
                duration = time.time() - start_time
                duration_str = f" - 耗时: {duration:.3f}s" if log_duration else ""
                logger.error(f"{prefix}调用失败: {full_name}{duration_str} - 错误: {str(e)}", exc_info=True)
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 提取方法名
            method_name = func.__name__
            class_name = args[0].__class__.__name__ if args else ""
            full_name = f"{class_name}.{method_name}" if class_name else method_name
            
            # 开始日志
            start_time = time.time()
            logger.log(log_level, f"{prefix}开始调用: {full_name}")
            
            if log_args and args:
                args_str = ", ".join(str(arg) for arg in args[1:] if not hasattr(arg, '__dict__'))
                kwargs_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
                all_args = ", ".join(filter(None, [args_str, kwargs_str]))
                if all_args:
                    logger.debug(f"{prefix}参数: {all_args}")
            
            try:
                # 执行方法
                result = func(*args, **kwargs)
                
                # 成功日志
                duration = time.time() - start_time
                duration_str = f" - 耗时: {duration:.3f}s" if log_duration else ""
                
                if log_result and result is not None:
                    result_str = str(result)[:200]
                    logger.log(log_level, f"{prefix}完成调用: {full_name}{duration_str} - 结果: {result_str}")
                else:
                    logger.log(log_level, f"{prefix}完成调用: {full_name}{duration_str}")
                
                return result
                
            except Exception as e:
                # 异常日志
                duration = time.time() - start_time
                duration_str = f" - 耗时: {duration:.3f}s" if log_duration else ""
                logger.error(f"{prefix}调用失败: {full_name}{duration_str} - 错误: {str(e)}", exc_info=True)
                raise
        
        # 判断是否是异步方法
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
