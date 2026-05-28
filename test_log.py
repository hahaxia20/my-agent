"""测试日志功能"""
import asyncio
from src.core.agent import MyAgent, AgentConfig
from src.core.logging_config import setup_logging

# 初始化日志
setup_logging(
    log_level="DEBUG",
    log_to_console=True,
    log_to_file=False,
    enable_emoji=True
)

async def test():
    # 创建 Agent（debug 模式）
    agent = MyAgent(config=AgentConfig(debug=True))
    
    print("\n" + "="*80)
    print("开始测试流式对话...")
    print("="*80 + "\n")
    
    # 测试流式对话
    async for chunk in agent.stream(
        user_query="帮我分析这个网页: https://example.com",
        session_id="test_session_001"
    ):
        print(chunk, end="", flush=True)
    
    print("\n" + "="*80)
    print("测试完成")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test())
