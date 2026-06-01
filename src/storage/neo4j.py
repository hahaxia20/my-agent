"""
Neo4j 图数据库管理器
产业链结构化数据导入（IndustryChain / Segment / Position / IndustryCode）
语义智能查询（GraphCypherQAChain，LLM 理解自然语言意图后自动生成 Cypher）
"""

from neo4j import GraphDatabase
import logging
import io
import re
import contextlib
from src.config import get_settings_safe

logger = logging.getLogger(__name__)


class Neo4jManager:
    """Neo4j 图数据库管理器"""

    # ── Cypher 生成提示词 ──────────────────────────────────────
    _CYPHER_PROMPT_TEMPLATE = """你的任务是将用户的自然语言问题转换为 Neo4j Cypher 查询语句。

## 图谱 Schema

节点类型：
- IndustryChain: 产业链主节点，属性：name（如"氢能"、"核能"、"量子科技"、"具身智能"等）
- Segment: 产业链环节，属性：
  - sid: 唯一标识，格式为"产业链名_序号_环节名"
  - name: 环节名称（如"制氢技术与装备"、"燃料电池系统"、"核电工程建设"等）
  - sequence: 序号（整数，表示在产业链中的顺序）
  - position: 位置标签（如"上游：制氢"、"中游：储运与加氢"、"下游：交通应用"、"消费：配套"等）
  - chain: 所属产业链名称
- Position: 位置标签节点，属性：name（如"上游：资源开采"、"中游：核心制造"、"下游：终端应用"、"消费：配套与标准"、"消费：技术服务"等）
- IndustryCode: 行业小类代码，属性：code（4位数字代码）、full_name（行业名称，如"放射性金属矿采选"）

关系类型：
- BELONGS_TO_CHAIN: (Segment)-[:BELONGS_TO_CHAIN]->(IndustryChain) 环节属于哪个产业链
- AT_POSITION:      (Segment)-[:AT_POSITION]->(Position) 环节的位置分类
- HAS_CODE:         (Segment)-[:HAS_CODE]->(IndustryCode) 环节包含的行业小类代码
- DEPENDS_ON:       (Segment)-[:DEPENDS_ON]->(Segment) 环节间的上下游依赖关系

## 查询规则

1. 查询某产业链的环节：MATCH (s:Segment)-[:BELONGS_TO_CHAIN]->(c:IndustryChain {{name: '氢能'}}) RETURN s.name, s.position, s.sequence ORDER BY s.sequence
2. 查询上游/中游/下游/消费环节：MATCH (s:Segment) WHERE s.chain = '氢能' AND s.position CONTAINS '上游' RETURN s.name, s.position
   注：position 包含四大类：上游、中游、下游、消费，均可用 CONTAINS 查询
3. **重要：当用户询问整个产业链（如"核能的产业链有哪些"、"氢能产业链结构"等），不加任何 position 过滤，必须返回该产业链的全部环节（上中下游+消费）**
4. 使用 CONTAINS 进行模糊匹配，不要用 = 精确匹配产业链名称
5. 查询上下游依赖关系：MATCH (a:Segment)-[:DEPENDS_ON]->(b:Segment) WHERE a.chain = '氢能' RETURN a.name, b.name
6. 查询行业代码：MATCH (s:Segment)-[:HAS_CODE]->(ic:IndustryCode) RETURN s.name, ic.code, ic.full_name
7. 查询有哪些产业链：MATCH (c:IndustryChain) RETURN c.name
8. 查询结果优先返回 name、position、sequence、chain
9. 只生成只读查询，禁止 CREATE/MERGE/DELETE

## 示例

问：核能的产业链有哪些？
答：MATCH (s:Segment) WHERE s.chain CONTAINS '核能' RETURN s.name, s.position, s.sequence ORDER BY s.sequence

问：氢能产业链的上游有哪些环节？
答：MATCH (s:Segment) WHERE s.chain CONTAINS '氢能' AND s.position CONTAINS '上游' RETURN s.name, s.position, s.sequence ORDER BY s.sequence

问：氢能产业链有哪些下游应用？
答：MATCH (s:Segment) WHERE s.chain CONTAINS '氢能' AND s.position CONTAINS '下游' RETURN s.name, s.position, s.sequence ORDER BY s.sequence

问：氢能产业链的消费环节有哪些？
答：MATCH (s:Segment) WHERE s.chain CONTAINS '氢能' AND s.position CONTAINS '消费' RETURN s.name, s.position, s.sequence ORDER BY s.sequence

问：图谱中有哪些产业链？
答：MATCH (c:IndustryChain) RETURN c.name

问：核能产业链各环节的依赖关系是什么？
答：MATCH (a:Segment)-[:DEPENDS_ON]->(b:Segment) WHERE a.chain CONTAINS '核能' RETURN a.name, a.sequence, b.name, b.sequence ORDER BY a.sequence

问：用到稀土的产业链有哪些？
答：MATCH (s:Segment)-[:HAS_CODE]->(ic:IndustryCode) WHERE ic.full_name CONTAINS '稀土' RETURN DISTINCT s.chain, s.name, ic.full_name

问：各产业链的环节数量统计？
答：MATCH (s:Segment) RETURN s.chain, count(s) AS segment_count ORDER BY segment_count DESC

## 当前图谱 Schema
{schema}

## 用户问题
{question}

请只输出 Cypher 查询语句，不要有任何其他文字。"""

    # ── QA 提示词 ──────────────────────────────────────────────
    _QA_PROMPT_TEMPLATE = """你是一个专业的知识图谱问答助手。根据提供的查询结果，用纯自然语言回答用户的问题。

## 严格要求
1. 只输出自然语言答案，禁止输出任何 Cypher 查询语句、MATCH/RETURN/WHERE/LIMIT 等关键词
2. 禁止输出任何技术细节、查询过程、调试信息
3. 如果查询结果为空或无法回答，直接说“图谱中暂未找到与该问题匹配的数据，请尝试换一种描述方式。”
4. 不要提及“根据查询结果”、“基于图谱数据”等元信息
5. 必须完整呈现所有返回的数据，不得截断、省略或自行归纳为“两个环节”“几大环节”等概括性说法
6. 当查询结果包含上游、中游、下游、消费四个位置分类时，必须四个分类全部介绍，不得只说其中一部分
7. 不得自行推断或补充查询结果中没有出现的信息
8. 禁止说出“主要分为X个环节”这类总结性计数，直接按分类依次介绍即可

## 示例

查询结果: [name:制氢技术与装备, position:上游：制氢], [name:制氢原料与能源, position:上游：制氢]
问题: 氢能产业链的上游有哪些环节？
回答: 氢能产业链的上游环节包括制氢原料与能源、制氢技术与装备。

查询结果: [name:袘变资源开采, position:上游：资源开采], [name:聚变资源开采, position:上游：资源开采], [name:核能通用材料冶炼与压延, position:中游：制造与流通], [name:核能发电与输配, position:下游：终端应用], [name:核技术应用服务, position:消费：技术服务]
问题: 核能的产业链有哪些？
回答: 核能产业链包含以下环节：上游的资源开采环节包括袘变资源开采、聚变资源开采；中游的制造与流通环节包括核能通用材料冶炼与压延；下游的终端应用环节包括核能发电与输配；消费环节包括核技术应用服务。

查询结果: [name:核能, chain:核能], [name:氢能, chain:氢能]
问题: 图谱中有哪些产业链？
回答: 图谱中包含核能、氢能等产业链。

查询结果: []
问题: 光伏产业链有哪些环节？
回答: 图谱中暂未找到与该问题匹配的数据，请尝试换一种描述方式。

## 当前查询结果
{context}

## 用户问题
{question}

## 回答"""

    # ── 输出清洗规则 ──────────────────────────────────────────
    # 匹配完整 Cypher 语句（MATCH...RETURN...）
    _CYPHER_PATTERN = re.compile(
        r"(?:(?:MATCH|CALL|WITH|UNWIND)\b[\s\S]*?RETURN\b[^\u4e00-\u9fff\n]*)",
        re.IGNORECASE,
    )
    # 匹配孤立的 Cypher 片段（只有 RETURN 没有 MATCH，不跨行、不匹配中文）
    _RETURN_FRAGMENT = re.compile(
        r"RETURN[ \t]+[a-zA-Z_][a-zA-Z0-9_.\,\[ \t]*(?:ORDER BY[a-zA-Z0-9_.\,\[ \t]+)?(?:LIMIT[ \t]+\d+)?",
        re.IGNORECASE,
    )
    _EMPTY_ANSWERS = {
        "我不知道答案。", "我不知道答案",
        "i don't know", "i don't know the answer", "i don't know the answer.",
    }
    _MEANINGLESS_PREFIXES = ("我不知道答案", "我无法回答", "I don't know")

    # ══════════════════════════════════════════════════════════
    # 连接管理
    # ══════════════════════════════════════════════════════════

    def __init__(self, uri: str = None, username: str = None,
                 password: str = None, database: str = None):
        settings = get_settings_safe()
        self.uri = uri or settings.NEO4J_URI
        self.username = username or settings.NEO4J_USERNAME
        self.password = password or settings.NEO4J_PASSWORD
        self.database = database or settings.NEO4J_DATABASE
        self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        self._verify_connection()
        logger.info(f"✅ Neo4j 已连接: {self.uri} | 数据库: {self.database}")

    def _verify_connection(self):
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 AS num")
                if not (result.single() or {}).get("num"):
                    raise Exception("连接验证失败")
            logger.info("🔗 Neo4j 连接验证成功")
        except Exception as e:
            logger.error(f"❌ Neo4j 连接失败: {e}")
            raise

    async def close(self):
        try:
            self.driver.close()
            logger.info("🔌 Neo4j 连接已关闭")
        except Exception as e:
            logger.error(f"❌ 关闭 Neo4j 连接失败: {e}")

    # ══════════════════════════════════════════════════════════
    # 数据管理
    # ══════════════════════════════════════════════════════════

    def clear_all_data(self) -> bool:
        """清空 Neo4j 中所有节点和关系"""
        try:
            with self.driver.session(database=self.database) as session:
                session.run("MATCH (n) DETACH DELETE n")
            logger.info("🗑️ Neo4j 所有数据已清空")
            return True
        except Exception as e:
            logger.error(f"❌ 清空数据失败: {e}")
            return False

    def get_stats(self) -> dict:
        """返回当前图谱节点/关系统计"""
        try:
            with self.driver.session(database=self.database) as session:
                nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
                rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
                chains = session.run("MATCH (c:IndustryChain) RETURN count(c) AS c").single()["c"]
                return {"nodes": nodes, "relationships": rels, "chains": chains}
        except Exception as e:
            logger.error(f"❌ 获取统计失败: {e}")
            return {"nodes": 0, "relationships": 0, "chains": 0}

    # ══════════════════════════════════════════════════════════
    # 产业链数据导入
    # ══════════════════════════════════════════════════════════

    def import_industry_chain(self, chain_name: str, segments: list) -> bool:
        """
        导入单条产业链数据到 Neo4j

        节点：IndustryChain / Segment / Position / IndustryCode
        关系：BELONGS_TO_CHAIN / AT_POSITION / HAS_CODE / DEPENDS_ON
        """
        try:
            with self.driver.session(database=self.database) as session:
                # 1. 创建唯一约束（幂等）
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:IndustryChain) REQUIRE c.name IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Segment) REQUIRE s.sid IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (ic:IndustryCode) REQUIRE ic.code IS UNIQUE")

                # 2. 创建产业链主节点（显式消费确保提交）
                session.run("MERGE (c:IndustryChain {name: $name})", name=chain_name).consume()

                # 3. 解析原始数据
                seg_map, seq_to_keys, code_list, positions = self._parse_segments(segments, chain_name)

                # 4. 写入图谱
                self._write_positions(session, positions)
                self._write_segments(session, seg_map, chain_name)
                self._write_codes(session, code_list, seg_map)
                self._write_dependencies(session, seg_map, seq_to_keys)

            logger.info(f"✅ 产业链 [{chain_name}] 导入完成：{len(seg_map)} 个环节，{len(code_list)} 个行业代码")
            return True
        except Exception as e:
            logger.error(f"❌ 导入产业链 [{chain_name}] 失败: {e}", exc_info=True)
            return False

    @staticmethod
    def _parse_segments(segments: list, chain_name: str):
        """将原始行数据解析为结构化集合"""
        seg_map = {}          # (seq, name) -> info dict
        seq_to_keys = {}      # seq -> [(seq, name), ...]
        code_list = []        # [(seq, seg_name, code_str), ...]
        positions = set()

        for seg in segments:
            seq = int(seg["sequence"])
            name = seg["name"]
            key = (seq, name)
            seg_map[key] = {
                "sequence": seq,
                "position": seg["position"],
                "name": name,
                "dependencies": seg.get("dependencies", "0"),
                "sid": f"{chain_name}_{seq}_{name}",
            }
            seq_to_keys.setdefault(seq, []).append(key)
            positions.add(seg["position"])
            for c in seg.get("codes", []):
                code_list.append((seq, name, c.strip()))

        return seg_map, seq_to_keys, code_list, positions

    @staticmethod
    def _write_positions(session, positions: set):
        """创建 Position 节点"""
        for pos in positions:
            session.run("MERGE (p:Position {name: $name})", name=pos)

    @staticmethod
    def _write_segments(session, seg_map: dict, chain_name: str):
        """创建 Segment 节点，挂载 BELONGS_TO_CHAIN 和 AT_POSITION"""
        for info in seg_map.values():
            session.run(
                """
                MERGE (s:Segment {sid: $sid})
                SET s.name = $name, s.sequence = $sequence,
                    s.position = $position, s.chain = $chain
                WITH s
                MATCH (c:IndustryChain {name: $chain})
                MERGE (s)-[:BELONGS_TO_CHAIN]->(c)
                MERGE (p:Position {name: $position})
                MERGE (s)-[:AT_POSITION]->(p)
                """,
                sid=info["sid"], name=info["name"],
                sequence=info["sequence"], position=info["position"],
                chain=chain_name,
            )

    @staticmethod
    def _write_codes(session, code_list: list, seg_map: dict):
        """创建 IndustryCode 节点及 HAS_CODE 关系"""
        for seq, seg_name, code_str in code_list:
            if not code_str:
                continue
            parts = code_str.split(" ", 1)
            code, full_name = parts[0], parts[1] if len(parts) == 2 else parts[0]
            seg_info = seg_map.get((seq, seg_name))
            if not seg_info:
                continue
            session.run(
                """
                MERGE (ic:IndustryCode {code: $code})
                SET ic.full_name = $full_name
                WITH ic
                MATCH (s:Segment {sid: $sid})
                MERGE (s)-[:HAS_CODE]->(ic)
                """,
                code=code, full_name=full_name, sid=seg_info["sid"],
            )

    @staticmethod
    def _write_dependencies(session, seg_map: dict, seq_to_keys: dict):
        """根据环节依赖关系创建 DEPENDS_ON 边"""
        for info in seg_map.values():
            deps_str = str(info["dependencies"]).strip()
            if deps_str in ("0", "", "nan"):
                continue
            dep_seqs = [int(x.strip()) for x in deps_str.split(",") if x.strip().isdigit()]
            for dep_seq in dep_seqs:
                for dep_key in seq_to_keys.get(dep_seq, []):
                    dep_info = seg_map[dep_key]
                    session.run(
                        """
                        MATCH (a:Segment {sid: $from_sid})
                        MATCH (b:Segment {sid: $to_sid})
                        MERGE (a)-[:DEPENDS_ON]->(b)
                        """,
                        from_sid=info["sid"], to_sid=dep_info["sid"],
                    )

    # ══════════════════════════════════════════════════════════
    # 语义智能查询（GraphCypherQAChain）
    # ══════════════════════════════════════════════════════════

    def smart_query(self, question: str) -> str:
        """
        LLM 自动生成 Cypher 并执行，返回纯自然语言答案。
        verbose=False + redirect_stdout + _clean_answer 三重保障输出纯净。
        """
        from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
        from langchain_core.prompts import PromptTemplate
        from langchain_openai import ChatOpenAI
        from pydantic import SecretStr

        try:
            settings = get_settings_safe()
            graph = Neo4jGraph(
                url=self.uri, username=self.username,
                password=self.password, database=self.database,
            )
            chain = GraphCypherQAChain.from_llm(
                llm=ChatOpenAI(
                    model=settings.MODEL_NAME,
                    api_key=SecretStr(settings.OPENAI_API_KEY),
                    base_url=settings.API_BASE_URL,
                    temperature=0,
                ),
                graph=graph,
                cypher_prompt=PromptTemplate(
                    template=self._CYPHER_PROMPT_TEMPLATE,
                    input_variables=["schema", "question"],
                ),
                qa_prompt=PromptTemplate(
                    template=self._QA_PROMPT_TEMPLATE,
                    input_variables=["context", "question"],
                ),
                verbose=False,
                validate_cypher=True,
                allow_dangerous_requests=True,
                return_intermediate_steps=True,
                top_k=100,
            )

            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                response = chain.invoke({"query": question})

            # 记录中间步骤（生成的 Cypher 和实际返回行数）用于调试
            steps = response.get("intermediate_steps", [])
            for step in steps:
                if "query" in step:
                    logger.info(f"🔍 [smart_query Cypher]: {step['query']}")
                if "context" in step:
                    ctx = step["context"]
                    row_count = len(ctx) if isinstance(ctx, list) else "N/A"
                    logger.info(f"📊 [smart_query 返回行数]: {row_count}")

            if captured.getvalue().strip():
                logger.debug(f"[smart_query debug]\n{captured.getvalue().strip()}")

            raw = response["result"] if isinstance(response, dict) else str(response)
            answer = self._clean_answer(raw)
            logger.info(f"✅ [smart_query] 问题: {question[:50]}... 答案长度: {len(answer)}")
            return answer

        except Exception as e:
            logger.error(f"❌ [smart_query] 失败: {e}", exc_info=True)
            return f"图谱智能查询失败：{str(e)}"

    def _clean_answer(self, raw: str) -> str:
        """剥离泄漏的 Cypher，处理空结果降级"""
        # 第一步：清理完整 Cypher 语句（MATCH...RETURN...）
        cleaned = self._CYPHER_PATTERN.sub("", raw).strip()
        # 第二步：清理孤立的 RETURN 片段（如 RETURN s.name, s.position...）
        cleaned = self._RETURN_FRAGMENT.sub("", cleaned).strip()
        # 第三步：清理多余空行
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if (
            not cleaned
            or cleaned.rstrip("。.") in self._EMPTY_ANSWERS
            or any(cleaned.startswith(p) for p in self._MEANINGLESS_PREFIXES)
        ):
            return "图谱中暂未找到与该问题匹配的数据。请尝试换一种描述方式，例如使用具体的产业链名称或实体名称进行查询。"
        return cleaned


# ══════════════════════════════════════════════════════════════
# 全局单例
# ══════════════════════════════════════════════════════════════

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
