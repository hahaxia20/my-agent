"""
演示日志装饰器的实际输出
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import logging
from src.core.logging_decorator import log_method_call

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


class UserService:
    """用户服务 - 演示日志装饰器"""
    
    @log_method_call(prefix="[用户服务] ")
    async def create_user(self, username: str, email: str):
        """创建用户"""
        await asyncio.sleep(0.5)  # 模拟数据库操作
        return {"id": 1, "username": username, "email": email}
    
    @log_method_call(prefix="[用户服务] ", log_args=True)
    async def get_user(self, user_id: int):
        """获取用户（记录参数）"""
        await asyncio.sleep(0.2)
        return {"id": user_id, "username": "test", "email": "test@example.com"}
    
    @log_method_call(prefix="[用户服务] ", log_result=True)
    def list_users(self, limit: int = 10):
        """列出用户（记录返回值）"""
        return [{"id": i, "name": f"user{i}"} for i in range(limit)]
    
    @log_method_call(prefix="[用户服务] ")
    async def delete_user(self, user_id: int):
        """删除用户（会失败）"""
        await asyncio.sleep(0.1)
        raise ValueError(f"用户 {user_id} 不存在")


async def main():
    """主函数"""
    
    print("=" * 70)
    print("演示：日志装饰器的实际输出")
    print("=" * 70)
    print()
    
    service = UserService()
    
    # 1. 基本日志（记录开始、完成、耗时）
    print("1️ 基本日志输出：")
    print("-" * 70)
    result = await service.create_user("张三", "zhangsan@example.com")
    print(f"返回: {result}")
    print()
    
    # 2. 带参数的日志
    print("2️⃣ 带参数的日志输出：")
    print("-" * 70)
    result = await service.get_user(123)
    print(f"返回: {result}")
    print()
    
    # 3. 带返回值的日志
    print("3️⃣ 带返回值的日志输出：")
    print("-" * 70)
    result = service.list_users(3)
    print(f"返回: {result}")
    print()
    
    # 4. 异常日志
    print("4️⃣ 异常日志输出：")
    print("-" * 70)
    try:
        await service.delete_user(999)
    except ValueError as e:
        print(f"捕获异常: {e}")
    print()
    
    print("=" * 70)
    print("✅ 演示完成！")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
