"""
测试基于 Agent Skills 规范的 Skill 系统
"""

import asyncio
from pathlib import Path
from src.skills.skill_parser import SkillParser
from src.skills.markdown_skill import MarkdownSkill
from src.skills.manager import skill_manager


def test_skill_parser():
    """测试 SKILL.md 解析器"""
    print("\n" + "="*60)
    print("📝 测试 1: SKILL.md 解析器")
    print("="*60)
    
    skill_path = Path(__file__).parent / "web-content-analyzer"
    
    # 验证 Skill
    is_valid, errors = SkillParser.validate_skill(skill_path)
    
    if is_valid:
        print("✅ Skill 验证通过")
    else:
        print("❌ Skill 验证失败:")
        for error in errors:
            print(f"   - {error}")
        return
    
    # 解析 Skill
    config = SkillParser.parse_skill_md(skill_path)
    
    print(f"\n📋 Skill 元数据:")
    print(f"   名称: {config.metadata.name}")
    print(f"   描述: {config.metadata.description[:80]}...")
    print(f"   许可证: {config.metadata.license}")
    print(f"   指令长度: {len(config.instructions)} 字符")
    print(f"   脚本文件: {len(config.scripts)} 个")
    print(f"   参考文档: {len(config.references)} 个")
    
    if config.metadata.metadata:
        print(f"\n🏷️  自定义元数据:")
        for key, value in config.metadata.metadata.items():
            print(f"   {key}: {value}")
    
    print(f"\n✅ 解析测试完成\n")


def test_skill_manager():
    """测试 SkillManager 自动加载"""
    print("\n" + "="*60)
    print("📦 测试 2: SkillManager 自动加载")
    print("="*60)
    
    # 获取所有已注册的 Skills
    all_skills = skill_manager.get_all()
    
    print(f"\n🎯 已注册 {len(all_skills)} 个 Skills:\n")
    
    for skill in all_skills:
        skill_type = "📝 Markdown" if hasattr(skill, 'skill_path') else "💻 Code"
        print(f"   {skill_type} [{skill.name}]")
        print(f"      描述: {skill.description[:80]}...")
        
        # 如果是 Markdown Skill，显示更多信息
        if hasattr(skill, 'get_skill_info'):
            info = skill.get_skill_info()
            if info.get('has_scripts'):
                print(f"      📁 包含脚本文件")
            if info.get('has_references'):
                print(f"      📚 包含参考文档")
        print()
    
    print(f"✅ SkillManager 测试完成\n")


async def test_skill_execution():
    """测试 Skill 执行（需要 LLM）"""
    print("\n" + "="*60)
    print("🚀 测试 3: Skill 执行")
    print("="*60)
    
    # 查找 web-content-analyzer skill
    skill = skill_manager.get_skill("web-content-analyzer")
    
    if not skill:
        print("⚠️  未找到 web-content-analyzer skill，跳过执行测试")
        return
    
    print(f"🎯 找到 Skill: {skill.name}")
    print(f"   类型: {'MarkdownSkill' if hasattr(skill, 'skill_path') else 'Code Skill'}")
    
    # 创建模拟的 LLM 和 settings (LangChain 方式)
    class MockAIMessage:
        content = "✅ 这是一个模拟的网页分析结果。\n\n## 📊 网页分析报告\n\n### 基本信息\n- **页面标题**: Example Domain\n- **主要内容类型**: 示例页面\n- **预估字数**: 50 字\n\n### 内容摘要\n这是一个用于示例的网页，内容简单明了。"
    
    class MockLLM:
        @staticmethod
        async def ainvoke(messages):
            return MockAIMessage()
    
    class MockSettings:
        MODEL_NAME = "qwen-plus"
        MAX_TOKENS = 4096
    
    # 执行 Skill
    print(f"\n📝 执行 Skill: {skill.name}")
    result = await skill.execute(
        user_query="请帮我分析这个网页: https://example.com",
        llm=MockLLM(),
        settings=MockSettings()
    )
    
    print(f"\n📊 执行结果:")
    print(f"   成功: {result.get('success')}")
    print(f"   Skill: {result.get('skill')}")
    if result.get('result'):
        print(f"   结果: {result['result'][:100]}...")
    if result.get('error'):
        print(f"   错误: {result['error']}")
    
    print(f"\n✅ Skill 执行测试完成\n")


def test_skill_info():
    """测试 Skill 信息查询"""
    print("\n" + "="*60)
    print("ℹ️  测试 4: Skill 详细信息")
    print("="*60)
    
    skill = skill_manager.get_skill("web-content-analyzer")
    
    if not skill:
        print("⚠️  未找到 web-content-analyzer skill")
        return
    
    if hasattr(skill, 'get_skill_info'):
        info = skill.get_skill_info()
        
        print(f"\n📋 Skill 详细信息:")
        print(f"   名称: {info['name']}")
        print(f"   路径: {info['path']}")
        print(f"   描述: {info['description'][:80]}...")
        print(f"   指令长度: {info['instructions_length']} 字符")
        print(f"   有脚本: {'✅' if info['has_scripts'] else '❌'}")
        print(f"   有参考: {'✅' if info['has_references'] else '❌'}")
        print(f"   有资源: {'✅' if info['has_assets'] else '❌'}")
        
        if info.get('metadata'):
            print(f"\n🏷️  元数据:")
            for key, value in info['metadata'].items():
                print(f"   {key}: {value}")
    
    print(f"\n✅ Skill 信息查询测试完成\n")


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("🧪 Agent Skills 规范测试套件")
    print("="*60)
    
    try:
        # 测试 1: 解析器
        test_skill_parser()
        
        # 测试 2: Manager
        test_skill_manager()
        
        # 测试 3: 执行
        await test_skill_execution()
        
        # 测试 4: 信息查询
        test_skill_info()
        
        print("\n" + "="*60)
        print("✅ 所有测试完成!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
