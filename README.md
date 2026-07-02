# My Agent

基于 LangGraph ReAct 架构的多模态智能体平台，围绕 **Skill（边界）→ Tool（执行）→ Workflow（流程）** 三层模型构建。

## 核心能力

| 类别 | 能力 |
|---|---|
| 智能对话 | SSE 流式响应、上下文压缩、会话持久化 |
| 产业链图谱 | Neo4j 知识图谱 + LLM 语义 Cypher 查询 |
| 复杂任务编排 | Sub-Agent 任务分解 / 并行执行 / 结果合成 |
| 意图路由 | 本地 Ollama 小模型路由 + 关键词兜底，支持 5 条执行路径 |
| 多技能系统 | Markdown 配置 + 热重载 + 中间件注入 |

## 架构概览

```
用户请求
  │
  ▼
┌─────────────┐
│  Router 层   │  Ollama LLM 意图路由 (skill_direct / workflow / simple / complex / graph_only)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Executor 层  │  SkillExecutor / WorkflowExecutor / SimpleExecutor / ComplexExecutor / GraphExecutor
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Tool 层    │  calculator / web_search / web_scraper / image_tool / imagegen_tool / pdf_tool / time / industry_graph
└─────────────┘
```

## 路由模型

| 路径 | 说明 | Executor |
|---|---|---|
| `skill_direct` | 命中特定 Skill | `SkillExecutor` |
| `workflow` | 命中固定业务流程 | `WorkflowExecutor` |
| `simple` | 普通问答、轻任务 | `SimpleExecutor` |
| `complex` | 开放式深度分析、多步推理 | `ComplexExecutor`（Sub-Agent 编排） |
| `graph_only` | 产业链图谱直达查询 | `GraphExecutor` |

## 当前 Skills

| Skill | 职责 |
|---|---|
| `pdf` | PDF 处理与分析 |
| `image-analysis` | 分析已有图片内容 |
| `imagegen` | 生成海报、主视觉等位图 |
| `stock-analysis` | 股票 K 线、均线等技术图分析 |
| `web-content-analyzer` | 网页内容解读 |
| `seo-audit` | SEO 基础审查 |
| `marketing-research` | 市场与竞品调研 |
| `content-planner` | 内容规划 |
| `marketing-copywriting` | 营销文案 |
| `social-creative` | 社媒创意与营销视觉方向 |

### Workflow

- `marketing-workflow`：调研 → 规划 → 文案 → 社媒创意的固定营销流程

## 工具集

| 工具 | 说明 |
|---|---|
| `calculator` | 数学表达式计算 |
| `get_current_time` | 获取当前时间 |
| `web_search` | 网络搜索（Tavily / DuckDuckGo） |
| `web_scraper` | 网页内容抓取 |
| `image_tool` | 图像理解与分析 |
| `imagegen_tool` | AI 图像生成 |
| `pdf_tool` | PDF 处理（合并、拆分、提取） |
| `smart_graph_query` | 产业链图谱语义查询 |

## 产业链图谱

基于 Neo4j 图数据库，支持对产业链结构的自然语言查询：

- 查询某产业链的全部环节（上游→中游→下游→消费）
- 按位置分类筛选（如"上游有哪些环节"）
- 上下游依赖关系查询
- 行业代码关联查询
- 多产业链统计对比

导入数据：

```bash
python scripts/import_industry_chains.py
```

## 快速启动

```bash
# 环境
conda activate my-deerflow
pip install -r requirements.txt

# 启动
python run.py
# 或: uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload
```

访问：

- 前端：`http://localhost:8001/`
- API 文档：`http://localhost:8001/docs`

## 关键配置

核心环境变量（复制 `.env.example` 为 `.env` 后修改）：

| 配置项 | 说明 |
|---|---|
| `OPENAI_API_KEY` | LLM API Key |
| `API_BASE_URL` | LLM API 地址 |
| `MODEL_NAME` | 主模型名称 |
| `INTENT_CLASSIFIER_ENABLED` | 是否启用 Ollama 路由（关闭则用关键词兜底） |
| `INTENT_CLASSIFIER_MODEL` | 路由小模型（如 `qwen3:8b`） |
| `MONGODB_URL` | MongoDB 连接（会话与消息存储） |
| `NEO4J_URI` | Neo4j 连接（产业链图谱，可选） |

## Docker 部署

```bash
docker compose up --build -d
```

## Skill 边界原则

新增 Skill 时需满足：

- 有明确的职责边界，不与已有 Skill 重叠
- 绑定清晰的 `allowed_tools`
- 不能只靠大而泛的关键词触发

详细规范见 [docs/skill-governance.md](docs/skill-governance.md)。

## 相关文档

- [docs/skill-governance.md](docs/skill-governance.md) — Skill 治理规范
- [docs/multi-agent-architecture.md](docs/multi-agent-architecture.md) — 多 Agent 架构设计
- [SKILLS_GUIDE.md](SKILLS_GUIDE.md) — Skill 开发指南