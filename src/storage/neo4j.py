"""
Neo4j 图数据库管理器
产业链结构化数据导入（IndustryChain / Segment / Position / IndustryCode）
语义智能查询（GraphCypherQAChain，LLM 理解自然语言意图后自动生成 Cypher）
"""

from neo4j import GraphDatabase
import logging

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
    _QA_PROMPT_TEMPLATE = """你是一个专业的产业链分析师。根据图谱查询结果，结合你的领域知识，用结构化 Markdown 格式回答用户的问题。

## 输出格式要求
1. **严禁输出 Cypher**：禁止出现 MATCH、RETURN、WHERE、CONTAINS、LIMIT、ORDER BY 等任何数据库关键词或查询语句，违者视为失败
2. 禁止输出查询过程、调试信息、"根据查询结果"等元信息
3. 使用 Markdown 格式：用 `##` 标题、`🔹` emoji、`**加粗**` 和缩进列表组织内容
4. 图谱中的环节名称是骨架，你必须用领域知识为每个环节补充 1-2 句简要说明（技术路线、典型产品等），但不要编造不存在的环节
5. 如果查询结果为空，直接说"图谱中暂未找到与该问题匹配的数据，请尝试换一种描述方式。"
6. 必须完整呈现所有返回的环节，不得截断、省略或归纳为"几个环节"
7. **针对性回答**：若用户问的是某个特定位置（如"上游""中游"），只回答该位置的内容，不要给出全景；只有当用户问整个产业链时，才依次介绍全部位置分类
8. **严禁重复**：同一内容只说一遍，禁止先总结再展开
9. **禁止空洞套话**：不得添加"形成了完整体系""相当完整的闭环"等评价性废话；结尾若要有内容，必须是有信息量的行业判断（如技术趋势、关键瓶颈）

## 示例

查询结果: [name:制氢技术与装备, position:上游：制氢], [name:制氢原料与能源, position:上游：制氢]
问题: 氢能产业链的上游有哪些环节？
回答:
🔹 **氢能上游 — 制氢环节**

- **制氢原料与能源**：包括煤炭、天然气等化石原料，以及可再生能源电解水所需的电力供应
- **制氢技术与装备**：涵盖碱性电解（ALK）、质子交换膜电解（PEM）等核心制氢设备与工艺

上游解决的是"氢从哪里来"的问题。当前主流的灰氢（化石制氢）成本较低但碳排放高，绿氢（电解水制氢）是产业转型方向，降低绿电成本是规模化的核心关键。

---

查询结果: [name:制氢技术与装备, position:上游：制氢], [name:制氢原料与能源, position:上游：制氢], [name:储运技术与装备, position:中游：储运与加氢], [name:加氢站与基础设施, position:中游：储运与加氢], [name:燃料电池系统, position:中游：应用装备], [name:氢能交通, position:下游：交通应用], [name:固定式发电与工业用氢, position:下游：非交通应用], [name:碳交易、安全与标准, position:消费：配套], [name:检测认证与标准, position:消费：配套]
问题: 氢能的产业链有哪些？
回答:
## 氢能产业链全景

🔹 **上游 — 制氢环节**

- **制氢原料与能源**：包括煤炭、天然气等化石原料，以及可再生能源电解水所需的电力供应
- **制氢技术与装备**：涵盖碱性电解（ALK）、质子交换膜电解（PEM）等核心制氢设备与工艺

🔹 **中游 — 储运与应用装备**

- **储运技术与装备**：高压气态储氢瓶、低温液态储氢、长管拖车及管道输氢等
- **加氢站与基础设施**：压缩机、加氢机、储氢罐等加氢站核心设备
- **燃料电池系统**：膜电极（MEA）、质子交换膜、催化剂等燃料电池核心部件

🔹 **下游 — 应用环节**

- **氢能交通**：燃料电池乘用车、商用车、船舶等交通应用
- **固定式发电与工业用氢**：氢燃料电池热电联供、氢冶金、化工用氢等工业场景

🔹 **消费配套**

- **碳交易、安全与标准**：氢能碳减排核算、安全规范及行业标准制定
- **检测认证与标准**：氢气纯度检测、设备安全认证等质量保障体系

目前氢能产业正处于从灰氢（化石制氢）向绿氢（电解水制氢）转型的关键阶段，储运成本仍是产业发展的主要瓶颈。

---

查询结果: [name:袘变资源开采, position:上游：资源开采], [name:聚变资源开采, position:上游：资源开采], [name:核能通用材料冶炼与压延, position:中游：制造与流通], [name:核能发电与输配, position:下游：终端应用], [name:核技术应用服务, position:消费：技术服务]
问题: 核能的产业链有哪些？
回答:
## 核能产业链全景

🔹 **上游 — 资源开采**：包括袘变资源开采（铀矿等裂变燃料）、聚变资源开采（氘、氚等聚变燃料原料）

🔹 **中游 — 制造与流通**：核能通用材料冶炼与压延，涵盖核级钢材、锆合金等核能专用材料的加工制造

🔹 **下游 — 终端应用**：核能发电与输配，即核电站运营及电力输送

🔹 **消费 — 技术服务**：核技术应用服务，包括核医学、工业辐照、核检测等非电力领域的核技术应用

---

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


    # ── 输出清洗规则（已废弃，smart_query 手动两步后不再需要） ──

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
        手动两步：① LLM 生成 Cypher 并执行 ② 只用查询结果调 QA LLM
        QA LLM 完全看不到 Cypher，从根源杜绝泄漏，无需正则清洗。
        """
        from langchain_neo4j import Neo4jGraph
        from langchain_core.prompts import PromptTemplate
        from langchain_openai import ChatOpenAI
        from pydantic import SecretStr

        try:
            settings = get_settings_safe()
            llm = ChatOpenAI(
                model=settings.MODEL_NAME,
                api_key=SecretStr(settings.OPENAI_API_KEY),
                base_url=settings.API_BASE_URL,
                temperature=0,
            )
            graph = Neo4jGraph(
                url=self.uri, username=self.username,
                password=self.password, database=self.database,
            )

            # ── Step 1: 生成 Cypher ──
            cypher_prompt = PromptTemplate(
                template=self._CYPHER_PROMPT_TEMPLATE,
                input_variables=["schema", "question"],
            )
            cypher_chain = cypher_prompt | llm
            cypher_response = cypher_chain.invoke({
                "schema": graph.get_schema,
                "question": question,
            })
            cypher_query = cypher_response.content.strip()
            # 剥离可能的 markdown 代码块包裹
            if cypher_query.startswith("```"):
                lines = cypher_query.split("\n")
                cypher_query = "\n".join(
                    line for line in lines
                    if not line.strip().startswith("```")
                ).strip()
            logger.info(f"🔍 [smart_query Cypher]: {cypher_query}")

            # ── Step 2: 执行 Cypher ──
            with self.driver.session(database=self.database) as session:
                result = session.run(cypher_query)
                records = [record.data() for record in result]
            logger.info(f"📊 [smart_query 返回行数]: {len(records)}")

            if not records:
                return "图谱中暂未找到与该问题匹配的数据，请尝试换一种描述方式。"

            # ── Step 3: 只用查询结果调 QA LLM（不传 Cypher） ──
            context_str = str(records)
            qa_prompt = PromptTemplate(
                template=self._QA_PROMPT_TEMPLATE,
                input_variables=["context", "question"],
            )
            qa_chain = qa_prompt | llm
            qa_response = qa_chain.invoke({
                "context": context_str,
                "question": question,
            })
            answer = qa_response.content.strip()
            logger.info(f"✅ [smart_query] 问题: {question[:50]}... 答案长度: {len(answer)}")
            return answer

        except Exception as e:
            logger.error(f"❌ [smart_query] 失败: {e}", exc_info=True)
            return f"图谱智能查询失败：{str(e)}"


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
