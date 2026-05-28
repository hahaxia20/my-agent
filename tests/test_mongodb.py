"""
测试 MongoDB 连接和基本操作
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from src.storage.mongodb import get_mongodb


async def test_mongodb():
    """测试 MongoDB"""

    print("=" * 50)
    print("测试 MongoDB 连接")
    print("=" * 50)

    # 1. 获取 MongoDB 管理器
    db = get_mongodb()

    # 2. 测试连接
    print("\n1. 测试连接...")
    connected = await db.ping()
    if connected:
        print("   ✅ MongoDB 连接成功！")
    else:
        print("   ❌ MongoDB 连接失败！")
        print("   请确保 MongoDB 已启动：mongod")
        return

    # 3. 创建会话
    print("\n2. 创建会话...")
    session_id = await db.create_session(
        user_id="test-user",
        title="测试会话"
    )
    print(f"   ✅ 会话创建成功: {session_id}")

    # 4. 添加消息
    print("\n3. 添加消息...")
    await db.add_message(session_id, "user", "你好，我叫小明")
    await db.add_message(session_id, "assistant", "你好小明！很高兴认识你")
    await db.add_message(session_id, "user", "我喜欢编程")
    await db.add_message(session_id, "assistant", "编程很有趣！你最喜欢什么语言？")
    print("   ✅ 添加了 4 条消息")

    # 5. 读取会话
    print("\n4. 读取会话...")
    session = await db.get_session(session_id)
    if session:
        print(f"   ✅ 会话ID: {session['_id']}")
        print(f"   ✅ 标题: {session['title']}")
        print(f"   ✅ 消息数: {session['metadata']['message_count']}")

        print("\n   消息列表：")
        for i, msg in enumerate(session['messages'], 1):
            print(f"   {i}. [{msg['role']}] {msg['content']}")

    # 6. 只获取最近消息
    print("\n5. 获取最近 2 条消息...")
    recent = await db.get_messages(session_id, limit=2)
    print(f"   ✅ 最近消息数: {len(recent)}")
    for msg in recent:
        print(f"   - [{msg['role']}] {msg['content']}")

    # 7. 列出所有会话
    print("\n6. 列出用户会话...")
    sessions = await db.list_sessions(user_id="test-user")
    print(f"   ✅ 会话数: {len(sessions)}")
    for s in sessions:
        print(f"   - {s['_id']}: {s['title']}")

    # 8. 删除会话
    print("\n7. 删除会话...")
    deleted = await db.delete_session(session_id)
    if deleted:
        print(f"   ✅ 会话已删除: {session_id}")

    print("\n" + "=" * 50)
    print("✅ 所有测试通过！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_mongodb())