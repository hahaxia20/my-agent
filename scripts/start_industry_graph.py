"""
快速启动脚本
1. 导入产业链数据到 Neo4j
2. 启动服务
"""

import asyncio
import subprocess
import sys
from pathlib import Path

async def main():
    print("\n" + "="*60)
    print("🚀 产业链图谱系统启动脚本")
    print("="*60 + "\n")
    
    # 检查 Excel 文件
    excel_file = "data/产业链（结构）标签-0429.xlsx"
    
    if not Path(excel_file).exists():
        print(f"❌ Excel 文件不存在: {excel_file}")
        print(f"💡 请将 Excel 文件放到项目根目录")
        return
    
    print(f"✅ 找到 Excel 文件: {excel_file}")
    
    # 导入数据
    print("\n📦 步骤 1: 导入产业链数据到 Neo4j...")
    print("-" * 60)
    
    from scripts.import_industry_chains import import_industry_chains_from_excel
    
    success = await import_industry_chains_from_excel(excel_file)
    
    if not success:
        print("\n❌ 数据导入失败，请检查 Neo4j 是否启动")
        print("💡 启动 Neo4j: docker run -d -p 7474:7474 -p 7687:7687 neo4j")
        return
    
    print("\n✅ 数据导入成功！")
    
    # 启动服务
    print("\n📦 步骤 2: 启动 FastAPI 服务...")
    print("-" * 60)
    print("\n💡 服务启动后访问:")
    print("   - API 文档: http://localhost:8001/docs")
    print("   - 图谱查询: POST /api/v1/industry/query")
    print("   - 产业链列表: GET /api/v1/industry/chains")
    print("\n按 Ctrl+C 停止服务\n")
    
    # 启动 uvicorn
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "src.main:app",
        "--host", "0.0.0.0",
        "--port", "8001",
        "--reload"
    ])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
