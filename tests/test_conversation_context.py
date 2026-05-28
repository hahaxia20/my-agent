"""
测试对话历史上下文管理器
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from src.core.context.conversation import ConversationContextManager


class MockDBManager:
    """模拟数据库管理器"""
    
    async def get_messages(self, session_id: str):
        """模拟获取消息"""
        # 模拟返回一些历史消息
        return [
            {"role": "user", "content": "你好，我想了解一下 Python"},
            {"role": "assistant", "content": "Python 是一门非常流行的编程语言..."},
            {"role": "user", "content": "它有什么特点？"},
            {"role": "assistant", "content": "Python 的主要特点包括：简单易学、功能强大..."},
            {"role": "user", "content": "适合做什么？"},
            {"role": "assistant", "content": "Python 适合 Web 开发、数据分析、人工智能..."},
        ]


async def test_conversation_context_manager():
    """测试对话上下文管理器"""
    
    print("=" * 60)
    print("测试 1：基础功能 - 加载历史消息")
    print("=" * 60)
    
    # 创建管理器
    db = MockDBManager()
    manager = ConversationContextManager(
        db_manager=db,
        max_messages=50,
        max_tokens=8000,
        enable_compression=False
    )
    
    # 加载上下文
    context = await manager.load_context(
        session_id="test-session-123",
        current_message="Python 和 Java 有什么区别？"
    )
    
    print(f"加载的消息数量: {len(context)}")
    for i, msg in enumerate(context, 1):
        content_preview = msg.content[:50] if hasattr(msg, 'content') else ""
        print(f"  {i}. [{type(msg).__name__}] {content_preview}...")
    
    # 获取统计信息
    stats = manager.get_context_stats(context)
    print(f"\n上下文统计: {stats}")
    
    print("\n" + "=" * 60)
    print("测试 2：Token 限制")
    print("=" * 60)
    
    # 创建带有严格限制的管理器
    manager_limited = ConversationContextManager(
        db_manager=db,
        max_messages=3,  # 只保留最近 3 条
        max_tokens=200,  # 严格 token 限制
        enable_compression=False
    )
    
    context_limited = await manager_limited.load_context(
        session_id="test-session-123",
        current_message="Python 和 Java 有什么区别？"
    )
    
    print(f"限制后的消息数量: {len(context_limited)}")
    stats_limited = manager_limited.get_context_stats(context_limited)
    print(f"限制后统计: {stats_limited}")
    
    print("\n" + "=" * 60)
    print("测试 3：上下文压缩（模拟）")
    print("=" * 60)
    
    # 创建启用压缩的管理器
    manager_compressed = ConversationContextManager(
        db_manager=db,
        max_messages=50,
        max_tokens=8000,
        enable_compression=True
    )
    
    context_compressed = await manager_compressed.load_context(
        session_id="test-session-123",
        current_message="Python 和 Java 有什么区别？"
    )
    
    print(f"压缩后的消息数量: {len(context_compressed)}")
    for i, msg in enumerate(context_compressed, 1):
        content_preview = msg.content[:80] if hasattr(msg, 'content') else ""
        print(f"  {i}. [{type(msg).__name__}] {content_preview}...")
    
    print("\n✅ 所有测试完成！")


if __name__ == "__main__":
    asyncio.run(test_conversation_context_manager())
