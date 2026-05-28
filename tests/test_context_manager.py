"""
测试系统提示词上下文管理器
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from src.core.context.context import SystemPromptContextManager


async def test_system_prompt_context_manager():
    """测试系统提示词上下文管理器"""
    # 测试默认模型
    manager = SystemPromptContextManager()
    prompt = manager._build_system_prompt()
    
    print("=" * 60)
    print("测试：默认模型的系统提示词")
    print("=" * 60)
    print(f"提示词长度: {len(prompt)} 字符")
    print(f"提示词前 100 字符: {prompt[:100]}")
    print()
    
    # 测试 qwen 模型
    manager_qwen = SystemPromptContextManager(model="qwen3.6-plus")
    prompt_qwen = manager_qwen._build_system_prompt()
    
    print("=" * 60)
    print("测试：Qwen 模型的系统提示词")
    print("=" * 60)
    print(f"提示词长度: {len(prompt_qwen)} 字符")
    print(f"提示词前 100 字符: {prompt_qwen[:100]}")
    print()
    
    print("✅ 测试完成！")


if __name__ == "__main__":
    asyncio.run(test_system_prompt_context_manager())
