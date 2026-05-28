"""
测试日志装饰器
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from src.core.logging_decorator import log_method_call


class TestService:
    """测试服务类"""
    
    @log_method_call(prefix="[测试] ")
    async def async_method(self, name: str, age: int):
        """异步方法测试"""
        await asyncio.sleep(0.1)
        return f"Hello {name}, age {age}"
    
    @log_method_call(prefix="[测试] ", log_args=True)
    def sync_method(self, value: int):
        """同步方法测试"""
        return value * 2
    
    @log_method_call(prefix="[错误测试] ")
    async def error_method(self):
        """异常方法测试"""
        raise ValueError("测试异常")


async def test_logging_decorator():
    """测试日志装饰器"""
    
    print("=" * 60)
    print("测试 1：异步方法")
    print("=" * 60)
    
    service = TestService()
    result = await service.async_method("张三", 25)
    print(f"返回结果: {result}\n")
    
    print("=" * 60)
    print("测试 2：同步方法（带参数日志）")
    print("=" * 60)
    
    result = service.sync_method(10)
    print(f"返回结果: {result}\n")
    
    print("=" * 60)
    print("测试 3：异常方法")
    print("=" * 60)
    
    try:
        await service.error_method()
    except ValueError as e:
        print(f"捕获异常: {e}\n")
    
    print("✅ 所有测试完成！")


if __name__ == "__main__":
    asyncio.run(test_logging_decorator())
