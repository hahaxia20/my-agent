"""
产业链图谱工具
用于查询和展示产业链结构
"""

from src.tools.base import BaseTool
from src.storage.neo4j import get_neo4j
import logging

logger = logging.getLogger(__name__)


class QueryIndustryChainTool(BaseTool):
    """查询产业链图谱工具"""
    
    def __init__(self):
        super().__init__()
        self.name = "query_industry_chain"
        self.description = "查询指定产业链的完整结构和图谱。支持的产业链：氢能、核能、生物制造、量子科技、具身智能、航空航天、新材料、大宗、新能源、储能、6G、脑机接口、低空经济。当用户询问产业链、行业结构、上下游关系、产业环节时使用此工具，而不是使用网络搜索。"
        self.neo4j = get_neo4j()
        
        # 定义工具参数
        self.parameters = {
            "type": "object",
            "properties": {
                "industry": {
                    "type": "string",
                    "description": "产业链名称，如：氢能、核能、新能源、生物制造、量子科技等"
                }
            },
            "required": ["industry"]
        }
    
    async def execute(self, industry: str, **kwargs) -> dict:
        """
        查询产业链图谱
        
        Args:
            industry: 产业链名称（如"氢能"、"核能"、"新能源"等）
            kwargs: 其他参数
        
        Returns:
            产业链图谱数据
        """
        try:
            if not self.neo4j:
                return {
                    "success": False,
                    "error": "Neo4j 未连接，图谱功能不可用",
                    "industry": industry
                }
            
            logger.info(f"🔍 [图谱查询] 产业链: {industry}")
            
            # 查询完整产业链
            result = await self.neo4j.query_industry_chain(
                chain_name=industry,
                include_codes=True
            )
            
            if not result.get("success"):
                # 如果找不到，列出所有可用的产业链
                all_chains = await self.neo4j.list_all_chains()
                
                return {
                    "success": False,
                    "error": f"未找到产业链: {industry}",
                    "industry": industry,
                    "available_chains": all_chains,
                    "suggestion": f"可用的产业链: {', '.join(all_chains[:10])}"
                }
            
            # 生成文字描述
            description = self._generate_description(result)
            
            logger.info(f"✅ [图谱查询] {industry}: {result['stats']['total_segments']} 个环节")
            
            # 附加 JSON 格式的图谱数据（供前端渲染）
            # 使用明确的分隔标记，便于前端提取
            graph_json = f"\n\n[GRAPH_DATA_START]\n```json\n{self._format_graph_json(result)}\n```\n[GRAPH_DATA_END]"
            
            return {
                "success": True,
                "industry": industry,
                "description": description + graph_json,
                "graph": result["graph"],
                "stats": result["stats"]
            }
            
        except Exception as e:
            logger.error(f"❌ [图谱查询] 失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "industry": industry
            }
    
    def _generate_description(self, result: dict) -> str:
        """生成产业链文字描述"""
        chain_name = result["chain_name"]
        stats = result["stats"]
        graph = result["graph"]
        
        # 按位置分类统计
        position_stats = {}
        for node in graph["nodes"]:
            position = node.get("position", "")
            if position not in position_stats:
                position_stats[position] = []
            position_stats[position].append(node["name"])
        
        # 生成描述
        desc = f"**{chain_name}产业链** 共包含 {stats['total_segments']} 个环节，分为 {stats['total_positions']} 个主要阶段：\n\n"
        
        for position, segments in position_stats.items():
            desc += f"**{position}** ({len(segments)}个环节)\n"
            for seg in segments[:5]:  # 最多显示5个
                desc += f"  - {seg}\n"
            if len(segments) > 5:
                desc += f"  - ... 等{len(segments)}个环节\n"
            desc += "\n"
        
        # 添加依赖关系说明
        edge_count = len(graph["edges"])
        if edge_count > 0:
            desc += f"环节之间存在 {edge_count} 个依赖关系，形成完整的产业链条。"
        
        return desc
    
    def _format_graph_json(self, result: dict) -> str:
        """格式化图谱数据为 JSON 字符串"""
        import json
        
        graph_data = {
            "industry": result["chain_name"],
            "chain_name": result["chain_name"],
            "stats": result["stats"],
            "graph": result["graph"]
        }
        
        return json.dumps(graph_data, ensure_ascii=False, indent=2)


class ListIndustryChainsTool(BaseTool):
    """列出所有产业链工具"""
    
    def __init__(self):
        super().__init__()
        self.name = "list_industry_chains"
        self.description = "列出系统中所有可用的产业链名称，用于查询产业链结构"
        self.neo4j = get_neo4j()
        self.parameters = {
            "type": "object",
            "properties": {}
        }
    
    async def execute(self, **kwargs) -> dict:
        """列出所有产业链"""
        try:
            if not self.neo4j:
                return {
                    "success": False,
                    "error": "Neo4j 未连接"
                }
            
            chains = await self.neo4j.list_all_chains()
            
            logger.info(f"📋 [产业链列表] 共 {len(chains)} 个产业链")
            
            return {
                "success": True,
                "chains": chains,
                "count": len(chains),
                "description": f"系统中共有 {len(chains)} 个产业链：{', '.join(chains)}"
            }
            
        except Exception as e:
            logger.error(f"❌ [产业链列表] 失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }


class FindUpstreamTool(BaseTool):
    """查找上游依赖工具"""
    
    def __init__(self):
        super().__init__()
        self.name = "find_upstream_dependencies"
        self.description = "查找指定产业链环节的上游依赖链，用于分析供应链关系"
        self.neo4j = get_neo4j()
        self.parameters = {
            "type": "object",
            "properties": {
                "industry": {
                    "type": "string",
                    "description": "产业链名称"
                },
                "segment_name": {
                    "type": "string",
                    "description": "环节名称"
                }
            },
            "required": ["industry", "segment_name"]
        }
    
    async def execute(
        self,
        industry: str,
        segment: str,
        depth: int = 3,
        **kwargs
    ) -> dict:
        """
        查找上游依赖
        
        Args:
            industry: 产业链名称
            segment: 环节名称
            depth: 查询深度（默认3层）
        
        Returns:
            上游依赖图谱
        """
        try:
            if not self.neo4j:
                return {
                    "success": False,
                    "error": "Neo4j 未连接"
                }
            
            logger.info(f"🔍 [上游依赖] {industry} -> {segment} (深度: {depth})")
            
            result = await self.neo4j.find_upstream_dependencies(
                chain_name=industry,
                segment_name=segment,
                depth=depth
            )
            
            if result.get("success"):
                node_count = len(result["graph"]["nodes"])
                logger.info(f"✅ [上游依赖] 找到 {node_count} 个上游环节")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [上游依赖] 失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
