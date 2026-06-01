"""
产业链 Excel 数据导入 Neo4j
支持先清空再全量导入
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import logging
from src.storage.neo4j import get_neo4j

logger = logging.getLogger(__name__)


def import_industry_chains_from_excel(excel_file: str, clear_first: bool = True) -> bool:
    """
    从 Excel 文件导入产业链数据到 Neo4j

    Args:
        excel_file:  Excel 文件路径
        clear_first: 导入前是否清空所有数据

    Returns:
        是否成功
    """
    try:
        logger.info(f"📂 读取 Excel 文件: {excel_file}")
        excel_data = pd.read_excel(excel_file, sheet_name=None)
        logger.info(f"📊 找到 {len(excel_data)} 个产业链: {list(excel_data.keys())}")

        neo4j = get_neo4j()
        if not neo4j:
            logger.error("❌ Neo4j 连接失败")
            return False

        # 清空旧数据
        if clear_first:
            logger.info("🗑️ 清空 Neo4j 现有数据...")
            neo4j.clear_all_data()

        success_count = 0

        for chain_name, df in excel_data.items():
            logger.info(f"\n{'='*60}")
            logger.info(f"📦 处理产业链: {chain_name}")
            logger.info(f"{'='*60}")

            # 逐行转为 segment 列表（每行一个小类）
            segments = []
            for _, row in df.iterrows():
                segments.append({
                    "sequence":    int(row["序号"]),
                    "position":    str(row["位置"]),
                    "name":        str(row["环节"]),
                    "dependencies": str(row["环节依赖关系"]),
                    "codes":       [str(row["小类"])],
                })

            logger.info(f"   行数: {len(segments)}")
            logger.info(f"   位置分布: {df['位置'].value_counts().to_dict()}")

            # 同步导入
            if neo4j.import_industry_chain(chain_name, segments):
                success_count += 1
                logger.info(f"✅ {chain_name} 导入成功")
            else:
                logger.error(f"❌ {chain_name} 导入失败")

        # 输出统计
        stats = neo4j.get_stats()
        logger.info(f"\n{'='*60}")
        logger.info(f"🎉 导入完成: {success_count}/{len(excel_data)} 个产业链成功")
        logger.info(f"📊 图谱统计: 节点 {stats['nodes']} | 关系 {stats['relationships']} | 产业链 {stats['chains']}")
        logger.info(f"{'='*60}")

        return success_count > 0

    except Exception as e:
        logger.error(f"❌ 导入失败: {e}", exc_info=True)
        return False


def main():
    """主函数"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )

    # Excel 文件路径
    excel_file = "data/产业链（结构）标签-0429.xlsx"

    if not Path(excel_file).exists():
        logger.error(f"❌ Excel 文件不存在: {excel_file}")
        return

    success = import_industry_chains_from_excel(excel_file, clear_first=True)
    if success:
        logger.info("✅ 所有产业链导入成功！")
    else:
        logger.error("❌ 部分或全部导入失败")


if __name__ == "__main__":
    main()
