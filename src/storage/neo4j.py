"""
Neo4j 图数据库管理器
适配 GraphRAG 写入的 Entity / Community / RELATIONSHIP / BELONGS_TO 结构
仅提供 smart_query（GraphCypherQAChain 灵活查询）和实体详情查询
"""

from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
import logging
from src.config import get_settings_safe

logger = logging.getLogger(__name__)


class Neo4jManager:
    """Neo4j 图数据库管理器（GraphRAG 数据结构）"""

    def __init__(
        self,
        uri: str = None,
        username: str = None,
        password: str = None,
        database: str = None,
    ):
        settings = get_settings_safe()
        self.uri = uri or settings.NEO4J_URI
        self.username = username or settings.NEO4J_USERNAME
        self.password = password or settings.NEO4J_PASSWORD
        self.database = database or settings.NEO4J_DATABASE

        self.driver = GraphDatabase.driver(
            self.uri, auth=(self.username, self.password)
        )
        self._verify_connection()
        logger.info(f"✅ Neo4j 已连接: {self.uri}")
        logger.info(f"📊 数据库: {self.database}")

    # ─────────────────────────────────────────
    # 连接管理
    # ─────────────────────────────────────────

    def _verify_connection(self):
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
        try:
            self.driver.close()
            logger.info("🔌 Neo4j 连接已关闭")
        except Exception as e:
            logger.error(f"❌ 关闭 Neo4j 连接失败: {e}")

    # ─────────────────────────────────────────
    # 实体详情查询
    # ─────────────────────────────────────────

    async def get_entity_detail(self, entity_title: str) -> Dict[str, Any]:
        """
        查询单个实体的详细信息：属性 + 所有入边/出边 + 所属 Community。
        """
        try:
            with self.driver.session(database=self.database) as session:
                # 实体属性
                er = session.run(
                    "MATCH (e:Entity {title: $t}) RETURN e", t=entity_title
                ).single()
                if not er:
                    return {"success": False, "error": f"未找到实体: {entity_title}"}
                entity = dict(er["e"])

                # 出边
                out_r = session.run(
                    """
                    MATCH (e:Entity {title: $t})-[r:RELATIONSHIP]->(target:Entity)
                    RETURN target.title AS target, r.weight AS weight, r.description AS desc
                    ORDER BY r.weight DESC
                    """,
                    t=entity_title,
                )
                outgoing = [dict(r) for r in out_r]

                # 入边
                in_r = session.run(
                    """
                    MATCH (source:Entity)-[r:RELATIONSHIP]->(e:Entity {title: $t})
                    RETURN source.title AS source, r.weight AS weight, r.description AS desc
                    ORDER BY r.weight DESC
                    """,
                    t=entity_title,
                )
                incoming = [dict(r) for r in in_r]

                # 所属 Community
                c_r = session.run(
                    """
                    MATCH (e:Entity {title: $t})-[:BELONGS_TO]->(c:Community)
                    RETURN c.title AS title, c.summary AS summary, c.level AS level
                    """,
                    t=entity_title,
                )
                communities = [dict(r) for r in c_r]

                return {
                    "success": True,
                    "entity": entity,
                    "outgoing": outgoing,
                    "incoming": incoming,
                    "communities": communities,
                }

        except Exception as e:
            logger.error(f"❌ 查询实体详情失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # ─────────────────────────────────────────
    # GraphCypherQAChain 智能查询
    # ─────────────────────────────────────────

    def get_langchain_graph(self):
        """返回 LangChain 兼容的 Neo4jGraph 对象，用于 GraphCypherQAChain"""
        from langchain_neo4j import Neo4jGraph
        return Neo4jGraph(
            url=self.uri,
            username=self.username,
            password=self.password,
            database=self.database,
        )

    def smart_query(self, question: str) -> str:
        """
        LLM 自动生成 Cypher 并执行，返回自然语言答案。
        适用于模糊查询、跨产业链分析、统计等灵活场景。
        """
        from langchain_neo4j import GraphCypherQAChain
        from langchain_openai import ChatOpenAI
        from src.config import get_settings_safe
        from pydantic import SecretStr

        try:
            settings = get_settings_safe()
            graph = self.get_langchain_graph()

            chain = GraphCypherQAChain.from_llm(
                llm=ChatOpenAI(
                    model=settings.MODEL_NAME,
                    api_key=SecretStr(settings.OPENAI_API_KEY),
                    base_url=settings.API_BASE_URL,
                    temperature=0,
                ),
                graph=graph,
                verbose=True,
                validate_cypher=True,
                allow_dangerous_requests=True,
                cypher_prompt=None,
                qa_prompt=None,
                return_intermediate_steps=False,
            )

            response = chain.invoke({"query": question})
            answer = response["result"] if isinstance(response, dict) else str(response)
            logger.info(f"✅ [smart_query] 问题: {question[:50]}... 答案长度: {len(answer)}")
            return answer

        except Exception as e:
            logger.error(f"❌ [smart_query] 失败: {e}", exc_info=True)
            return f"图谱智能查询失败：{str(e)}"


# ─────────────────────────────────────────
# 全局单例
# ─────────────────────────────────────────

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
