"""
Neo4j 图数据库管理器
用于产业链图谱存储和查询
"""

from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
import logging
from src.config import get_settings_safe

logger = logging.getLogger(__name__)


class Neo4jManager:
    """Neo4j 图数据库管理器"""
    
    def __init__(
        self,
        uri: str = None,
        username: str = None,
        password: str = None,
        database: str = None
    ):
        """初始化 Neo4j 连接"""
        settings = get_settings_safe()
        
        self.uri = uri or settings.NEO4J_URI
        self.username = username or settings.NEO4J_USERNAME
        self.password = password or settings.NEO4J_PASSWORD
        self.database = database or settings.NEO4J_DATABASE
        
        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password)
        )
        
        self._verify_connection()
        
        logger.info(f"✅ Neo4j 已连接: {self.uri}")
        logger.info(f"📊 数据库: {self.database}")
    
    def _verify_connection(self):
        """验证连接"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 AS num")
                record = result.single()
                if record and record["num"] == 1:
                    logger.info("🔗 Neo4j 连接验证成功")
                else:
                    raise Exception("连接验证失败")
        except Exception as e:
            logger.error(f"❌ Neo4j 连接失败: {e}")
            raise
    
    async def close(self):
        """关闭连接"""
        try:
            self.driver.close()
            logger.info("🔌 Neo4j 连接已关闭")
        except Exception as e:
            logger.error(f"❌ 关闭 Neo4j 连接失败: {e}")
    
    # ═══════════════════════════════════════
    # 产业链数据导入
    # ═══════════════════════════════════════
    
    async def import_industry_chain(
        self,
        chain_name: str,
        segments: List[Dict[str, Any]]
    ) -> bool:
        """
        导入产业链数据
        
        Args:
            chain_name: 产业链名称（如"氢能"）
            segments: 环节列表
                [
                    {
                        "sequence": 1,
                        "position": "上游：制氢",
                        "name": "制氢原料与能源",
                        "dependencies": "0",
                        "codes": ["0610 烟煤和无烟煤开采洗选", ...]
                    }
                ]
        
        Returns:
            是否成功
        """
        try:
            with self.driver.session(database=self.database) as session:
                # 1. 创建产业链节点
                session.run("""
                    MERGE (chain:IndustryChain {name: $chain_name})
                    SET chain.updated_at = timestamp()
                """, chain_name=chain_name)
                
                # 2. 创建环节节点和关系
                for segment in segments:
                    # 创建环节节点
                    session.run("""
                        MATCH (chain:IndustryChain {name: $chain_name})
                        MERGE (segment:IndustrySegment {
                            chain: $chain_name,
                            sequence: $sequence,
                            name: $name
                        })
                        SET segment.position = $position,
                            segment.codes = $codes,
                            segment.chain_name = $chain_name
                        MERGE (chain)-[:HAS_SEGMENT]->(segment)
                    """,
                    chain_name=chain_name,
                    sequence=segment["sequence"],
                    name=segment["name"],
                    position=segment["position"],
                    codes=segment.get("codes", [])
                    )
                    
                    # 创建依赖关系
                    if segment.get("dependencies") and segment["dependencies"] != "0":
                        deps = [int(d.strip()) for d in str(segment["dependencies"]).split(",") if d.strip()]
                        
                        for dep_seq in deps:
                            session.run("""
                                MATCH (a:IndustrySegment {chain: $chain_name, sequence: $seq})
                                MATCH (b:IndustrySegment {chain: $chain_name, sequence: $dep_seq})
                                MERGE (a)-[:DEPENDS_ON {type: "环节依赖"}]->(b)
                            """,
                            chain_name=chain_name,
                            seq=segment["sequence"],
                            dep_seq=dep_seq
                            )
                
                logger.info(f"✅ 导入产业链: {chain_name} ({len(segments)} 个环节)")
                return True
                
        except Exception as e:
            logger.error(f"❌ 导入产业链失败: {chain_name} - {e}")
            return False
    
    # ═══════════════════════════════════════
    # 图谱查询
    # ═══════════════════════════════════════
    
    async def query_industry_chain(
        self,
        chain_name: str,
        include_codes: bool = True
    ) -> Dict[str, Any]:
        """
        查询完整产业链图谱
        
        Args:
            chain_name: 产业链名称
            include_codes: 是否包含行业分类代码
        
        Returns:
            图谱数据（nodes + edges）
        """
        try:
            with self.driver.session(database=self.database) as session:
                # 查询所有节点和关系
                result = session.run("""
                    MATCH (chain:IndustryChain {name: $chain_name})
                    -[:HAS_SEGMENT]->(segment:IndustrySegment)
                    OPTIONAL MATCH (segment)-[r:DEPENDS_ON]->(target:IndustrySegment)
                    RETURN segment, r, target
                    ORDER BY segment.sequence
                """, chain_name=chain_name)
                
                nodes = []
                edges = []
                seen_nodes = set()
                
                for record in result:
                    # 添加节点
                    segment = dict(record["segment"])
                    node_id = f"{chain_name}_{segment['sequence']}_{segment['name']}"
                    
                    if node_id not in seen_nodes:
                        node_data = {
                            "id": node_id,
                            "name": segment["name"],
                            "position": segment.get("position", ""),
                            "sequence": segment["sequence"],
                            "category": self._extract_category(segment.get("position", ""))
                        }
                        
                        if include_codes and segment.get("codes"):
                            node_data["codes"] = segment["codes"]
                        
                        nodes.append(node_data)
                        seen_nodes.add(node_id)
                    
                    # 添加边
                    if record["r"] is not None:
                        target = dict(record["target"])
                        target_id = f"{chain_name}_{target['sequence']}_{target['name']}"
                        
                        edges.append({
                            "source": node_id,
                            "target": target_id,
                            "type": "depends_on",
                            "label": "依赖"
                        })
                
                # 获取统计信息
                stats_result = session.run("""
                    MATCH (chain:IndustryChain {name: $chain_name})
                    -[:HAS_SEGMENT]->(segment:IndustrySegment)
                    RETURN 
                        count(segment) as total_segments,
                        count(DISTINCT segment.position) as total_positions
                """, chain_name=chain_name)
                
                stats = stats_result.single()
                
                logger.info(f"🔍 查询产业链: {chain_name} ({stats['total_segments']} 个环节)")
                
                return {
                    "success": True,
                    "chain_name": chain_name,
                    "graph": {
                        "nodes": nodes,
                        "edges": edges
                    },
                    "stats": {
                        "total_segments": stats["total_segments"],
                        "total_positions": stats["total_positions"]
                    }
                }
                
        except Exception as e:
            logger.error(f"❌ 查询产业链失败: {chain_name} - {e}")
            return {
                "success": False,
                "error": str(e),
                "graph": {"nodes": [], "edges": []}
            }
    
    async def query_related_chains(self, industry_code: str) -> List[str]:
        """
        根据行业分类代码查询相关产业链
        
        Args:
            industry_code: 行业分类代码（如"0610"）
        
        Returns:
            相关产业链名称列表
        """
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                    MATCH (segment:IndustrySegment)
                    WHERE any(code IN segment.codes WHERE code STARTS WITH $code)
                    RETURN DISTINCT segment.chain_name as chain_name
                """, code=industry_code)
                
                chains = [record["chain_name"] for record in result]
                
                logger.info(f"🔍 查询相关产业链: {industry_code} -> {len(chains)} 个")
                return chains
                
        except Exception as e:
            logger.error(f"❌ 查询相关产业链失败: {e}")
            return []
    
    async def find_upstream_dependencies(
        self,
        chain_name: str,
        segment_name: str,
        depth: int = 3
    ) -> Dict[str, Any]:
        """
        查找上游依赖链
        
        Args:
            chain_name: 产业链名称
            segment_name: 环节名称
            depth: 查询深度
        
        Returns:
            上游依赖图谱
        """
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                    MATCH path = (target:IndustrySegment {chain: $chain, name: $name})
                    <-[:DEPENDS_ON*1..$depth]-(upstream)
                    RETURN path
                """, chain=chain_name, name=segment_name, depth=depth)
                
                nodes = []
                edges = []
                seen = set()
                
                for record in result:
                    path = record["path"]
                    
                    # 提取路径中的节点和边
                    for node in path.nodes:
                        node_dict = dict(node)
                        node_id = f"{node_dict['chain']}_{node_dict['sequence']}_{node_dict['name']}"
                        
                        if node_id not in seen:
                            nodes.append({
                                "id": node_id,
                                "name": node_dict["name"],
                                "position": node_dict.get("position", ""),
                                "sequence": node_dict["sequence"],
                                "is_target": node_dict["name"] == segment_name
                            })
                            seen.add(node_id)
                    
                    for i in range(0, len(path.nodes) - 1):
                        source = path.nodes[i]
                        target = path.nodes[i + 1]
                        
                        edges.append({
                            "source": f"{source['chain']}_{source['sequence']}_{source['name']}",
                            "target": f"{target['chain']}_{target['sequence']}_{target['name']}",
                            "type": "depends_on"
                        })
                
                return {
                    "success": True,
                    "target": segment_name,
                    "graph": {"nodes": nodes, "edges": edges}
                }
                
        except Exception as e:
            logger.error(f"❌ 查找上游依赖失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def list_all_chains(self) -> List[str]:
        """列出所有产业链"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                    MATCH (chain:IndustryChain)
                    RETURN chain.name as name
                    ORDER BY name
                """)
                
                chains = [record["name"] for record in result]
                return chains
                
        except Exception as e:
            logger.error(f"❌ 列出产业链失败: {e}")
            return []
    
    async def delete_chain(self, chain_name: str) -> bool:
        """删除产业链"""
        try:
            with self.driver.session(database=self.database) as session:
                session.run("""
                    MATCH (chain:IndustryChain {name: $chain_name})
                    DETACH DELETE chain
                """, chain_name=chain_name)
                
                logger.info(f"🗑️ 删除产业链: {chain_name}")
                return True
                
        except Exception as e:
            logger.error(f"❌ 删除产业链失败: {e}")
            return False
    
    def _extract_category(self, position: str) -> str:
        """从位置字符串提取分类（上游/中游/下游/消费）"""
        if "上游" in position:
            return "上游"
        elif "中游" in position:
            return "中游"
        elif "下游" in position:
            return "下游"
        elif "消费" in position:
            return "消费"
        return "其他"


# 全局单例
_neo4j_manager = None


def get_neo4j() -> Neo4jManager:
    """获取 Neo4j 管理器（单例）"""
    global _neo4j_manager
    if _neo4j_manager is None:
        try:
            _neo4j_manager = Neo4jManager()
        except Exception as e:
            logger.warning(f"⚠️ Neo4j 连接失败（图谱功能将不可用）: {e}")
            return None
    return _neo4j_manager
