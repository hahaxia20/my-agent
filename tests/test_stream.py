"""
测试流式输出
"""

import httpx
import json

async def test_stream():
    """测试流式对话"""
    
    url = "http://localhost:8000/chat/stream"
    data = {
        "message": "请用5句话介绍一下人工智能",
        "session_id": "test-001"
    }
    
    print("开始流式对话...\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream("POST", url, json=data) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    json_str = line[6:]  # 去掉 "data: " 前缀
                    data = json.loads(json_str)
                    
                    if data["type"] == "chunk":
                        # 逐字打印
                        print(data["content"], end="", flush=True)
                    elif data["type"] == "done":
                        print("\n\n✅ 完成！")
                        print(f"会话ID: {data['session_id']}")
                        print(f"消息数: {data['message_count']}")
                    elif data["type"] == "error":
                        print(f"\n❌ 错误: {data['message']}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_stream())