"""
测试 Neo4j 图谱查询（GraphRAG Entity/Community 结构）+ GraphCypherQAChain 智能查询
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from src.storage.neo4j import get_neo4j


async def test_neo4j():
    """测试 Neo4j 图谱功能"""

    print("=" * 60)
    print("测试 Neo4j 图谱查询（Smart Query 模式）")
    print("=" * 60)

    # ── 1. 连接测试 ──────────────────────────────────────
    print("\n[1] 测试 Neo4j 连接...")
    neo4j = get_neo4j()
    if not neo4j:
        print("   ❌ Neo4j 连接失败，请确认：")
        print("      docker run -d -p 7474:7474 -p 7687:7687 \\")
        print("        -e NEO4J_AUTH=neo4j/neo4j123456 neo4j:5")
        return
    print("   ✅ Neo4j 连接成功")

    # ── 2. smart_query 统计查询 ───────────────────────────
    print("\n[2] 智能查询（统计实体数量）...")
    print("   问题：How many Entity nodes are there in the graph?")
    try:
        answer = neo4j.smart_query("How many Entity nodes are there in the graph?")
        print(f"   ✅ 答案：")
        for line in answer.strip().split("\n"):
            print(f"      {line}")
    except Exception as e:
        print(f"   ❌ 智能查询失败: {e}")

    # ── 3. smart_query 灵活查询 ───────────────────────────
    print("\n[3] 智能查询（灵活查询产业链）...")
    question = "与'制氢'最直接相关的实体有哪些？"
    print(f"   问题：{question}")
    try:
        answer = neo4j.smart_query(question)
        print(f"   ✅ 答案：")
        for line in answer.strip().split("\n"):
            print(f"      {line}")
    except Exception as e:
        print(f"   ❌ 查询失败: {e}")

    # ── 4. smart_query 上下游关系 ─────────────────────────
    print("\n[4] 智能查询（上下游关系）...")
    question = "氢能产业链中，哪些实体是上游的？它们指向哪些中游实体？"
    print(f"   问题：{question}")
    try:
        answer = neo4j.smart_query(question)
        print(f"   ✅ 答案：")
        for line in answer.strip().split("\n"):
            print(f"      {line}")
    except Exception as e:
        print(f"   ❌ 查询失败: {e}")

    # ── 5. 实体详情查询 ──────────────────────────────────
    print("\n[5] 实体详情查询（get_entity_detail）...")
    # 先用 smart_query 找到一个实体名
    try:
        answer = neo4j.smart_query("List the title of one Entity node related to hydrogen energy.")
        print(f"   找到实体：{answer.strip()[:80]}")
    except Exception:
        answer = "制氢"
    
    # 尝试查询实体详情
    test_entity = answer.strip().split("\n")[0][:50]  # 取第一个实体名
    print(f"   查询实体详情: '{test_entity}'...")
    detail = await neo4j.get_entity_detail(test_entity)
    if detail.get("success"):
        entity = detail["entity"]
        print(f"   ✅ 实体类型: {entity.get('type', '')}")
        print(f"   入边: {len(detail['incoming'])} 条")
        print(f"   出边: {len(detail['outgoing'])} 条")
        print(f"   所属社区: {len(detail['communities'])} 个")
    else:
        print(f"   ⚠️  未找到实体（可忽略）: {detail.get('error')}")

    print("\n" + "=" * 60)
    print("✅ Neo4j Smart Query 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_neo4j())
