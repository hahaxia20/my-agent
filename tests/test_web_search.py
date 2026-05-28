"""
测试 web_search 工具
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tools.web_search import WebSearchTool


async def test_basic_search():
    """测试基本搜索功能"""
    print("\n" + "="*60)
    print("🔍 测试 1: 基本搜索")
    print("="*60)
    
    tool = WebSearchTool()
    
    query = "2024年人工智能最新进展"
    print(f"\n📝 搜索查询: {query}")
    print(f"📊 结果数量: 3")
    print(f"🎯 搜索深度: basic\n")
    
    result = await tool.execute(
        query=query,
        num_results=3,
        search_depth="basic"
    )
    
    if result.get("success"):
        print(f"✅ 搜索成功!")
        print(f"📊 返回结果数: {result['count']}")
        print(f"⏱️  执行时间: {result['execution_time']}s")
        print(f"\n📋 搜索结果:")
        for idx, item in enumerate(result['results'], 1):
            print(f"\n  [{idx}] {item['title']}")
            print(f"      URL: {item['url']}")
            print(f"      摘要: {item['snippet'][:100]}...")
            print(f"      相关度: {item['score']}")
    else:
        print(f"❌ 搜索失败: {result.get('error')}")
    
    return result.get("success")


async def test_advanced_search():
    """测试高级搜索"""
    print("\n" + "="*60)
    print("🔍 测试 2: 高级搜索 (advanced depth)")
    print("="*60)
    
    tool = WebSearchTool()
    
    query = "Python FastAPI 最佳实践"
    print(f"\n📝 搜索查询: {query}")
    print(f"📊 结果数量: 5")
    print(f"🎯 搜索深度: advanced\n")
    
    result = await tool.execute(
        query=query,
        num_results=5,
        search_depth="advanced"
    )
    
    if result.get("success"):
        print(f"✅ 搜索成功!")
        print(f"📊 返回结果数: {result['count']}")
        print(f"⏱️  执行时间: {result['execution_time']}s")
        print(f"\n📋 搜索结果:")
        for idx, item in enumerate(result['results'], 1):
            print(f"\n  [{idx}] {item['title']}")
            print(f"      URL: {item['url'][:80]}...")
            print(f"      摘要: {item['snippet'][:80]}...")
    else:
        print(f"❌ 搜索失败: {result.get('error')}")
    
    return result.get("success")


async def test_empty_query():
    """测试空查询"""
    print("\n" + "="*60)
    print("🔍 测试 3: 空查询（应该失败）")
    print("="*60)
    
    tool = WebSearchTool()
    
    result = await tool.execute(query="")
    
    if not result.get("success"):
        print(f"✅ 正确拒绝了空查询")
        print(f"❌ 错误信息: {result.get('error')}")
        return True
    else:
        print(f"❌ 应该拒绝空查询但成功了")
        return False


async def test_concurrent_search():
    """测试并发搜索"""
    print("\n" + "="*60)
    print("🔍 测试 4: 并发搜索 (3个同时执行)")
    print("="*60)
    
    tool = WebSearchTool()
    
    queries = [
        "Python 3.12 新特性",
        "LangChain 教程",
        "MongoDB 最佳实践"
    ]
    
    print(f"\n📝 并发执行 {len(queries)} 个搜索任务...\n")
    
    start_time = asyncio.get_event_loop().time()
    
    # 并发执行多个搜索
    tasks = [
        tool.execute(query=q, num_results=2, search_depth="basic")
        for q in queries
    ]
    
    results = await asyncio.gather(*tasks)
    
    end_time = asyncio.get_event_loop().time()
    total_time = end_time - start_time
    
    print(f"⏱️  总执行时间: {total_time:.2f}s")
    print(f"\n📊 搜索结果:")
    
    success_count = 0
    for idx, (query, result) in enumerate(zip(queries, results), 1):
        if result.get("success"):
            success_count += 1
            print(f"\n  ✅ [{idx}] {query}")
            print(f"      结果数: {result['count']}")
            print(f"      耗时: {result['execution_time']}s")
        else:
            print(f"\n  ❌ [{idx}] {query}")
            print(f"      错误: {result.get('error')}")
    
    print(f"\n📈 成功率: {success_count}/{len(queries)}")
    
    return success_count == len(queries)


async def test_tool_manager():
    """测试通过 ToolManager 使用"""
    print("\n" + "="*60)
    print("🔍 测试 5: 通过 ToolManager 使用")
    print("="*60)
    
    from src.tools.manager import tool_manager
    
    # 检查工具是否已注册
    if tool_manager.has_tool("web_search"):
        print("✅ web_search 工具已注册")
    else:
        print("❌ web_search 工具未注册")
        return False
    
    # 执行搜索
    result = await tool_manager.execute_tool(
        "web_search",
        query="OpenAI GPT 最新模型",
        num_results=3,
        search_depth="basic"
    )
    
    if result.get("success"):
        print(f"✅ 通过 ToolManager 搜索成功")
        print(f"📊 结果数: {result['count']}")
        print(f"⏱️  耗时: {result['execution_time']}s")
        
        # 显示第一条结果
        if result['results']:
            first = result['results'][0]
            print(f"\n📋 第一条结果:")
            print(f"   标题: {first['title']}")
            print(f"   URL: {first['url'][:80]}...")
    else:
        print(f"❌ 搜索失败: {result.get('error')}")
    
    return result.get("success")


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("🧪 Web Search Tool 测试套件")
    print("="*60)
    
    test_results = []
    
    try:
        # 测试 1: 基本搜索
        result1 = await test_basic_search()
        test_results.append(("基本搜索", result1))
        
        # 测试 2: 高级搜索
        result2 = await test_advanced_search()
        test_results.append(("高级搜索", result2))
        
        # 测试 3: 空查询
        result3 = await test_empty_query()
        test_results.append(("空查询验证", result3))
        
        # 测试 4: 并发搜索
        result4 = await test_concurrent_search()
        test_results.append(("并发搜索", result4))
        
        # 测试 5: ToolManager 集成
        result5 = await test_tool_manager()
        test_results.append(("ToolManager 集成", result5))
        
        # 打印总结
        print("\n" + "="*60)
        print("📊 测试总结")
        print("="*60)
        
        passed = sum(1 for _, result in test_results if result)
        total = len(test_results)
        
        for test_name, result in test_results:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"  {status} - {test_name}")
        
        print(f"\n📈 总计: {passed}/{total} 通过")
        
        if passed == total:
            print("\n🎉 所有测试通过! Web Search Tool 工作正常!")
        else:
            print(f"\n⚠️  {total - passed} 个测试失败，请检查上方错误信息")
        
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ 测试过程出现异常: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
