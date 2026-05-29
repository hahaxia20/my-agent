"""
产业链图谱工具 - 仅保留 SmartGraphQueryTool（LLM 自动生成 Cypher 灵活查询）
"""

from src.tools.base import BaseTool
from src.storage.neo4j import get_neo4j
import logging

logger = logging.getLogger(__name__)


class SmartGraphQueryTool(BaseTool):
    """图谱智能查询工具 - LLM 自动生成 Cypher 查询"""

    def __init__(self):
        super().__init__()
        self.name = "smart_graph_query"
        self.description = (
            "用自然语言灵活查询产业链图谱。支持：模糊查询产业链名称、"
            "查询某个行业代码属于哪些产业链、跨产业链分析、"
            "查找特定环节的上游/下游关系、统计查询等。"
            "当问题较为灵活、不确定具体产业链名称时使用此工具。"
        )
        self.neo4j = get_neo4j()
        self.parameters = {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "自然语言查询问题，如：'用到稀土的产业链有哪些'、'氢能源的上游环节'、'各产业链环节数量统计'",
                }
            },
            "required": ["question"],
        }

    async def execute(self, question: str, **kwargs) -> dict:
        """
        用自然语言查询图谱

        Args:
            question: 自然语言问题

        Returns:
            查询结果
        """
        try:
            if not self.neo4j:
                return {
                    "success": False,
                    "error": "Neo4j 未连接，图谱功能不可用",
                    "question": question,
                }

            logger.info(f"🧠 [smart_query] 问题: {question}")

            # 调用 Neo4jManager 的 smart_query 方法
            answer = self.neo4j.smart_query(question)

            logger.info(f"✅ [smart_query] 答案长度: {len(answer)} 字符")

            return {
                "success": True,
                "question": question,
                "answer": answer,
                "description": answer,
            }

        except Exception as e:
            logger.error(f"❌ [smart_query] 失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "question": question,
            }
