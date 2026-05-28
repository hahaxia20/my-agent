"""
Sub-Agent 编排系统测试脚本

测试 Sub-Agent 系统的核心功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.agent import get_agent
from src.core.logging_config import setup_logging


async def test_sub_agent_system():
    """测试 Sub-Agent 编排系统"""
    
    # 初始化日志
    setup_logging(
        log_level="INFO",
        log_to_console=True,
        log_to_file=False,
        enable_emoji=True
    )
    
    print("\n" + "="*80)
    print("🧪 Sub-Agent 编排系统测试")
    print("="*80 + "\n")
    
    # 获取 Agent
    print("📦 加载 Agent...")
    agent = await get_agent()
    print("✅ Agent 加载完成\n")
    
    # 测试用例 1: 简单对比分析
    print("\n" + "="*80)
    print("📝 测试用例 1: 简单对比分析")
    print("="*80)
    
    task1 = "对比分析 Python、JavaScript、Go 三种编程语言的优缺点"
    print(f"\n任务: {task1}\n")
    
    result1 = await agent.complex_chat(
        user_query=task1,
        decomposition_strategy="parallel"
    )
    
    print(f"\n✅ 执行结果:")
    print(f"   成功: {result1['success']}")
    print(f"   耗时: {result1['elapsed_time']:.2f}s")
    print(f"   子任务数: {len(result1['sub_tasks'])}")
    print(f"   回复长度: {len(result1['reply'])} 字符")
    
    if result1.get('metadata'):
        print(f"   并行效率: {result1['metadata'].get('parallel_efficiency', 0):.2%}")
    
    # 测试用例 2: 深度研究
    print("\n" + "="*80)
    print("📝 测试用例 2: 深度研究任务")
    print("="*80)
    
    task2 = "研究 2024 年 AI Agent 领域的主要框架，包括 LangChain、AutoGen、CrewAI、DeerFlow，分析它们的架构特点、适用场景和性能表现"
    print(f"\n任务: {task2}\n")
    
    result2 = await agent.complex_chat(
        user_query=task2,
        decomposition_strategy="auto"
    )
    
    print(f"\n✅ 执行结果:")
    print(f"   成功: {result2['success']}")
    print(f"   耗时: {result2['elapsed_time']:.2f}s")
    print(f"   子任务数: {len(result2['sub_tasks'])}")
    
    if result2['sub_tasks']:
        print(f"\n📊 子任务详情:")
        for i, st in enumerate(result2['sub_tasks'], 1):
            print(f"   {i}. {st['task_id']} - {st['status']} ({st['duration']:.2f}s)")
    
    # 测试用例 3: 使用默认 chat (对比)
    print("\n" + "="*80)
    print("📝 测试用例 3: 使用普通 chat (对比)")
    print("="*80)
    
    task3 = "简述 Python 的优点"
    print(f"\n任务: {task3}\n")
    
    result3 = await agent.chat(user_query=task3)
    
    print(f"\n✅ 执行结果:")
    print(f"   成功: {result3['success']}")
    print(f"   耗时: {result3['elapsed_time']:.2f}s")
    print(f"   回复长度: {len(result3['reply'])} 字符")
    
    print("\n" + "="*80)
    print("✅ 测试完成")
    print("="*80 + "\n")
    
    # 总结
    print("📈 测试总结:")
    print(f"   - Sub-Agent 系统: {'✅ 正常' if result1['success'] else '❌ 失败'}")
    print(f"   - 复杂任务处理: {'✅ 正常' if result2['success'] else '❌ 失败'}")
    print(f"   - 普通对话: {'✅ 正常' if result3['success'] else '❌ 失败'}")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(test_sub_agent_system())
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
