"""
测试生产级 Agent
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from src.core.agent import get_agent


async def test_agent():
    """测试 Agent"""

    print("=" * 50)
    print("测试生产级 Agent")
    print("=" * 50)

    agent = get_agent()

    # 测试1：简单对话
    print("\n1. 测试简单对话...")
    result1 = await agent.chat("你好，我叫小明")
    print(f"   会话ID: {result1['session_id']}")
    print(f"   AI回复: {result1['reply']}")

    session_id = result1['session_id']

    # 测试2：连续对话（测试记忆）
    print("\n2. 测试连续对话...")
    result2 = await agent.chat("我叫什么名字？", session_id)
    print(f"   AI回复: {result2['reply']}")

    # 测试3：获取会话历史
    print("\n3. 获取会话历史...")
    history = await agent.get_session_history(session_id)
    print(f"   消息数: {history['message_count']}")
    print(f"   标题: {history['title']}")

    # 测试4：列出会话
    print("\n4. 列出会话...")
    sessions = await agent.list_sessions()
    print(f"   会话数: {len(sessions)}")

    print("\n" + "=" * 50)
    print("✅ Agent 测试完成！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_agent())