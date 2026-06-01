# My Agent - 生产级 AI Agent 系统

<p align="center">
  <strong>基于 LangGraph ReAct 架构的多模态 AI Agent 平台</strong>
</p>

<p align="center">
  <a href="#核心特性">特性</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#架构设计">架构</a> •
  <a href="#api-文档">API</a> •
  <a href="#产业链图谱">产业链图谱</a> •
  <a href="#技术栈">技术栈</a>
</p>

---

## 核心特性

### 🤖 智能对话
- **流式输出 (SSE)**：实时生成，打字机效果
- **上下文管理**：智能对话历史压缩与重要性筛选
- **多轮对话**：支持连续对话，保持上下文一致性
- **会话持久化**：MongoDB 存储，独立 SessionManager 管理

### 🔗 产业链图谱
- **Neo4j 知识图谱**：13 条产业链、576 个节点、1500+ 条关系
- **语义智能查询**：LLM 理解自然语言意图，自动生成 Cypher 并返回纯净答案
- **ECharts 力导向图**：交互式可视化，节点拖拽，边自动跟随
- **双 Tab 界面**：对话与图谱独立 Tab，职责分离
- **关键词联动**：对话中识别产业链术语，一键跳转图谱
- **快捷入口**：新建会话留白区域显示产业链快捷按钮

### 🧩 Sub-Agent 编排系统
- **任务分解**：自动将复杂任务拆分为多个子任务
- **并行执行**：支持子任务并发执行，提升效率
- **结果合成**：智能整合多个子任务结果
- **流式进度**：实时展示子任务执行进度

### 🎯 插件化 Skills 系统
- **配置化定义**：基于 Markdown（SKILL.md）文件配置
- **自动加载**：热插拔，无需重启服务
- **中间件注入**：通过 SkillMiddleware 运行时注入提示词

### 🛠️ 内置工具集
- **Smart Graph Query**：产业链图谱语义查询（LLM 自动生成 Cypher）
- **Web Search**：Tavily / DuckDuckGo 搜索引擎集成
- **Web Scraper**：网页内容抓取与分析
- **Calculator**：数学计算工具
- **Time Tools**：时间日期处理

### 🔐 安全与认证
- **JWT 认证**：安全的用户身份验证
- **CORS 保护**：生产环境强制配置域名白名单，禁止通配符
- **安全提示词**：结构化安全边界，防止提示注入
- **线程安全**：Agent 单例采用双重检查锁（异步锁 + 同步线程锁）

---

## 快速开始

### 环境要求

- Python 3.10+
- MongoDB 4.4+
- Neo4j 5.x（产业链图谱功能）
- OpenAI API Key（或兼容的 LLM API，如阿里云通义千问）
- Docker + Docker Desktop（生产部署时需要）

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/YOUR_USERNAME/my-agent.git
cd my-agent

# 2. 创建并激活虚拟环境
conda create -n my-deerflow python=3.12
conda activate my-deerflow

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API Key 和数据库配置
```

### 配置示例（.env）

```env
# LLM 配置
OPENAI_API_KEY=your-api-key-here
API_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o

# MongoDB 配置
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=myagent

# Neo4j 配置（产业链图谱）
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j

# 搜索配置（可选）
TAVILY_API_KEY=your-tavily-key

# JWT 密钥
JWT_SECRET_KEY=your-secret-key

# 生产环境必须配置 CORS 白名单（禁止使用 *）
CORS_ORIGINS=["https://yourdomain.com"]
```

### 启动服务

#### 开发模式（本地运行）

```bash
# 方式一：使用启动脚本
python run.py

# 方式二：uvicorn 直接启动
uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload
```

访问：
- **主界面**：http://localhost:8001/
- **登录页**：http://localhost:8001/login
- **API 文档**：http://localhost:8001/docs

#### 生产部署（Docker Compose）

整体架构：

```
浏览器
  │
  ▼  :80
Nginx（静态文件 + 反向代理）
  ├── /static/*  → 直接返回（缓存 7 天）
  ├── /api/*     → proxy_pass → backend:8001
  └── /*         → proxy_pass → backend:8001（页面路由）
                      │
              FastAPI（Uvicorn × 2 workers）
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
  MongoDB（宿主机容器）    Neo4j（宿主机容器）
```

**部署文件说明：**

| 文件 | 作用 |
|------|------|
| `Dockerfile` | 多阶段构建，Python 3.12-slim 镜像，Uvicorn 双 worker |
| `docker-compose.yml` | 编排 backend + nginx，自动重启 |
| `nginx/default.conf` | 反向代理、SSE 流式支持、静态资源缓存 |
| `.env.example` | 环境变量参考模板（敏感值已脱敏） |
| `.dockerignore` | 排除无关文件，减小镜像体积 |

**部署步骤：**

```bash
# 1. 复制环境配置
cp .env.example .env
```

编辑 `.env`，**必填项**：

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | LLM API Key（或阿里云通义千问等兼容 API） |
| `API_BASE_URL` | API 地址（如 `https://dashscope.aliyuncs.com/compatible-mode/v1`） |
| `MODEL_NAME` | 模型名称 |
| `JWT_SECRET_KEY` | JWT 签名密钥（生产环境建议 32 位以上随机字符串） |
| `MONGODB_URL` | 改为 `mongodb://admin:密码@host.docker.internal:27017` |
| `NEO4J_URI` | 改为 `bolt://host.docker.internal:7687` |
| `CORS_ORIGINS` | 改为具体域名，如 `["https://yourdomain.com"]`（禁止 `*`） |

```bash
# 2. 确保 MongoDB 和 Neo4j 容器已在运行

# 3. 构建并启动（后台运行）
docker compose up --build -d

# 4. 查看服务状态
docker compose ps

# 5. 查看实时日志
docker compose logs -f
```

**常用运维命令：**

```bash
# 重启服务（不重建镜像）
docker compose restart

# 更新代码后重新部署
docker compose up --build -d

# 停止服务
docker compose down

# 仅查看 backend 日志
docker compose logs -f backend
```

**访问地址：**

| 地址 | 说明 |
|------|------|
| http://localhost | 主界面 |
| http://localhost/login | 登录页 |
| http://localhost/docs | API 文档（Swagger UI） |
| http://localhost/health | 健康检查 |

---

## 架构设计

```
┌──────────────────────────────────────────────────┐
│                  Frontend                        │
│      index.html / login.html / static/           │
│           (Vanilla JS + SSE + ECharts)           │
└──────────────────────┬───────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼───────────────────────────┐
│                FastAPI Server                    │
│   ┌──────────┐  ┌──────────┐  ┌───────────────┐ │
│   │ Auth API │  │ Chat API │  │ Complex Tasks │ │
│   └──────────┘  └──────────┘  └───────────────┘ │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│              Core Agent Layer                    │
│   ┌──────────────────┐  ┌──────────────────────┐ │
│   │  Single Agent    │  │  Sub-Agent           │ │
│   │  (ReAct + Tools) │  │  Orchestrator        │ │
│   │  • Context Mgmt  │  │  • Decomposer        │ │
│   │  • Tool Calling  │  │  • Worker Pool       │ │
│   └──────────────────┘  │  • Synthesizer       │ │
│                         └──────────────────────┘ │
│   ┌──────────────────┐  ┌──────────────────────┐ │
│   │ Session Manager  │  │  Stream Handler      │ │
│   │ • 会话 CRUD      │  │  • SSE 流式处理      │ │
│   │ • 权限验证       │  │  • Cypher 过滤       │ │
│   └──────────────────┘  └──────────────────────┘ │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│            Plugins & Tools Layer                 │
│   ┌──────────────────┐  ┌──────────────────────┐ │
│   │  Skills          │  │  Tools               │ │
│   │  • Markdown 配置 │  │  • Smart Graph Query │ │
│   │  • 中间件注入    │  │  • Web Search        │ │
│   └──────────────────┘  │  • Web Scraper       │ │
│                         │  • Calculator / Time │ │
│                         └──────────────────────┘ │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│                Storage Layer                     │
│   ┌──────────────────┐  ┌──────────────────────┐ │
│   │  MongoDB         │  │  Neo4j               │ │
│   │  • Sessions      │  │  • IndustryChain     │ │
│   │  • Messages      │  │  • Segment / Code    │ │
│   │  • Checkpoints   │  │  • DEPENDS_ON 关系   │ │
│   └──────────────────┘  └──────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### 核心模块

| 模块 | 路径 | 职责 |
|------|------|------|
| API 路由 | `src/api/routes/` | RESTful 接口（Chat、Auth、Complex Tasks） |
| Agent 核心 | `src/core/agent.py` | LangGraph ReAct Agent，工具调用与上下文管理 |
| 会话管理 | `src/core/session_manager.py` | 会话 CRUD、权限验证、检查点管理（独立模块） |
| Sub-Agent | `src/core/sub_agent/` | 复杂任务分解、并行执行、结果合成 |
| 流式输出 | `src/core/stream/` | SSE 流式对话、Cypher 过滤、格式化 |
| 上下文管理 | `src/core/context/` | 对话历史压缩、重要性筛选、系统提示词注入 |
| 系统提示词 | `src/core/prompt/` | 多模型模板管理（default / qwen / gpt-4） |
| 工具集 | `src/tools/` | Smart Graph Query、搜索、爬虫、计算器等 |
| Skills | `src/skills/` | 插件化技能系统，Markdown 配置 + 中间件注入 |
| 存储层 | `src/storage/` | MongoDB（会话持久化）、Neo4j（产业链图谱） |

---

## API 文档

### 认证

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "your-password"
}
```

### 普通对话（流式 SSE）

```http
POST /api/v1/chat/stream
Authorization: Bearer {token}
Content-Type: application/json

{
  "message": "氢能产业链的上游有哪些环节？",
  "session_id": "optional-session-id"
}

Response: Server-Sent Events
data: __SESSION_ID__:session_123
data: 氢能产业链的上游环节包括...
data: [DONE]
```

### 复杂任务（流式 SSE）

```http
POST /api/v1/complex-chat/stream
Authorization: Bearer {token}
Content-Type: application/json

{
  "task": "对比分析氢能与储能产业链的上游重叠环节",
  "session_id": "optional-session-id"
}

Response: Server-Sent Events
data: {"type": "decompose_start"}
data: {"type": "decompose_complete", "data": {"sub_tasks_count": 3}}
data: {"type": "subtask_start", "data": {"task_id": "1", "task_name": "..."}}
data: {"type": "subtask_complete", "data": {"task_id": "1"}}
data: {"type": "synthesis_complete", "data": {"final_result": "..."}}
data: [DONE]
```

### 会话管理

```http
GET    /api/v1/sessions          # 会话列表
GET    /api/v1/sessions/{id}     # 会话详情
DELETE /api/v1/sessions/{id}     # 删除会话
```

完整 API 文档：http://localhost:8001/docs

---

## 产业链图谱

### 数据模型

图谱数据存储在 Neo4j 中，节点和关系如下：

| 节点类型 | 属性 | 说明 |
|---------|------|------|
| `IndustryChain` | `name` | 产业链主节点（氢能、核能、量子科技等） |
| `Segment` | `sid`, `name`, `sequence`, `position`, `chain` | 产业链环节 |
| `Position` | `name` | 位置标签（上游 / 中游 / 下游 / 消费） |
| `IndustryCode` | `code`, `full_name` | 国家行业分类小类代码 |

| 关系类型 | 方向 | 说明 |
|---------|------|------|
| `BELONGS_TO_CHAIN` | Segment → IndustryChain | 环节属于哪条产业链 |
| `AT_POSITION` | Segment → Position | 环节的位置分类 |
| `HAS_CODE` | Segment → IndustryCode | 环节包含的行业代码 |
| `DEPENDS_ON` | Segment → Segment | 环节间上下游依赖 |

### 数据导入

```bash
# 从 Excel 导入（自动先清空再全量重建）
python scripts/import_industry_chains.py

# 导入完成后统计
# 节点: 576 | 关系: 1501 | 产业链: 13
```

### 语义查询原理

`SmartGraphQueryTool` 基于 **GraphCypherQAChain** 实现语义查询，流程如下：

```
用户自然语言问题
      ↓
LLM 理解意图 + 图谱 Schema
      ↓
自动生成 Cypher 查询
      ↓
执行查询获取结果
      ↓
LLM 转写为纯净自然语言答案
```

无需预定义查询模板，支持模糊匹配、跨链分析、统计类问题。

---

## Skills 系统

Skills 是基于 Markdown 配置的插件化能力扩展系统，通过 SkillMiddleware 在运行时注入提示词，无需编写代码即可为 Agent 添加新能力。

### 目录结构

```
src/skills/
├── manager.py              # Skill 自动加载管理器
├── middleware.py           # Skill 中间件（运行时注入提示词）
├── web-content-analyzer/   # 网页内容分析 Skill
│   └── SKILL.md
└── data-analysis/          # 数据分析 Skill
    └── SKILL.md
```

### 创建新 Skill

```bash
mkdir src/skills/my-skill
cat > src/skills/my-skill/SKILL.md << 'EOF'
---
name: my-skill
description: 我的自定义技能
---

# My Skill

## 使用场景
- 场景一
- 场景二

## 执行步骤
1. 第一步
2. 第二步
EOF
```

创建后重启服务即可自动加载。详细指南见 [SKILLS_GUIDE.md](SKILLS_GUIDE.md)。

---

## 技术栈

| 层次 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.109.0 + Uvicorn |
| LLM 框架 | LangChain + LangGraph（ReAct 架构） |
| LLM Provider | OpenAI / 阿里云通义千问（兼容 OpenAI API） |
| 图数据库 | Neo4j 5.x + langchain-neo4j（GraphCypherQAChain） |
| 文档数据库 | MongoDB（Motor 异步驱动）+ LangGraph Checkpoint |
| 认证 | PyJWT + bcrypt |
| 搜索 | Tavily API + DuckDuckGo |
| 爬虫 | BeautifulSoup4 + Requests |
| 前端 | Vanilla JS + SSE + ECharts 5.4.3（力导向图） |
| 配置 | pydantic-settings + python-dotenv |

---

## 项目结构

```
my-agent/
├── src/
│   ├── api/                          # API 层
│   │   ├── middleware/               # 中间件（Auth、CORS）
│   │   └── routes/                   # 路由（chat、auth、complex_tasks）
│   ├── core/                         # 核心业务逻辑
│   │   ├── agent.py                  # LangGraph ReAct Agent 主体
│   │   ├── session_manager.py        # 会话管理器（独立模块，降低耦合）
│   │   ├── tool_adapter.py           # 工具适配器（BaseTool → LangChain StructuredTool）
│   │   ├── security.py               # 安全策略（输入过滤、提示注入防护）
│   │   ├── context/                  # 上下文管理
│   │   │   ├── context.py            # 系统提示词上下文管理器
│   │   │   └── conversation.py       # 对话历史上下文管理器
│   │   ├── stream/                   # 流式输出
│   │   │   ├── handler.py            # 流式对话处理器（SSE + Cypher 过滤）
│   │   │   └── manager.py            # 流式格式化与 Cypher 检测
│   │   ├── sub_agent/                # Sub-Agent 编排
│   │   │   ├── decomposer.py         # 任务分解器
│   │   │   ├── worker.py             # 子任务执行器
│   │   │   ├── synthesizer.py        # 结果合成器
│   │   │   ├── orchestrator.py       # 编排主控制
│   │   │   └── models.py             # 数据模型
│   │   ├── prompt/                   # 系统提示词
│   │   │   ├── manager.py            # 提示词管理器（按模型选择模板）
│   │   │   ├── system_prompts.py     # 提示词加载器
│   │   │   └── system_prompts_v1.0.json  # 提示词模板
│   │   ├── helpers/                  # 辅助工具
│   │   │   ├── intent_classifier.py  # 意图分类器
│   │   │   └── chat_helpers.py       # 聊天辅助函数
│   │   └── logging/                  # 日志模块
│   │       ├── config.py             # 日志配置
│   │       └── decorator.py          # 日志装饰器
│   ├── tools/                        # 工具集
│   │   ├── base.py                   # BaseTool 基类
│   │   ├── manager.py                # 工具管理器
│   │   ├── industry_graph.py         # 产业链语义查询工具（Neo4j）
│   │   ├── web_search.py             # Web 搜索（Tavily + DuckDuckGo）
│   │   ├── web_scraper.py            # 网页抓取
│   │   ├── calculator.py             # 计算器
│   │   └── time.py                   # 时间工具
│   ├── skills/                       # Skills 插件系统
│   │   ├── manager.py                # Skill 自动加载管理器
│   │   ├── middleware.py             # Skill 中间件（运行时注入提示词）
│   │   ├── web-content-analyzer/     # 网页内容分析 Skill
│   │   │   └── SKILL.md
│   │   └── data-analysis/            # 数据分析 Skill
│   │       └── SKILL.md
│   ├── storage/                      # 存储层
│   │   ├── mongodb.py                # MongoDB 连接（会话持久化 + 检查点）
│   │   └── neo4j.py                  # Neo4j 管理器（数据导入 + 语义查询）
│   ├── config.py                     # pydantic-settings 配置
│   └── main.py                       # FastAPI 应用入口
├── static/                           # 静态资源
│   ├── css/                          # 样式（styles.css、login.css）
│   ├── html/                         # 模块化 HTML 片段
│   └── js/                           # JS（app、chat、message、login、utils）
├── scripts/
│   ├── import_industry_chains.py     # 产业链 Excel 数据导入脚本
│   └── start_industry_graph.py       # 图谱服务启动脚本
├── tests/                            # 测试用例
├── .github/workflows/ci.yml          # GitHub Actions CI 配置
├── index.html                        # 主界面
├── login.html                        # 登录页面
├── run.py                            # 启动脚本
├── requirements.txt                  # Python 依赖
└── .env                              # 环境变量配置
```

---

## 开发指南

### 添加新工具

```python
# src/tools/my_tool.py
from src.tools.base import BaseTool

class MyTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "my_tool"
        self.description = "工具描述"
        self.parameters = {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "输入参数"}
            },
            "required": ["input"],
        }

    async def execute(self, input: str, **kwargs) -> dict:
        return {"success": True, "result": "..."}
```

在 `src/tools/manager.py` 中导入并注册即可自动加载。

### 添加新 Skill

创建 `src/skills/my-skill/SKILL.md` 文件，重启服务自动加载。

---

## 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 使用 pytest.ini 配置（已预设参数）
python -m pytest
```

---

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建功能分支（`git checkout -b feature/AmazingFeature`）
3. 提交更改（`git commit -m 'Add AmazingFeature'`）
4. 推送到分支（`git push origin feature/AmazingFeature`）
5. 提交 Pull Request

---

## 🙏 技术参考

- **LangChain** — LLM 应用开发框架
- **LangGraph** — 状态图编排框架
- **FastAPI** — 现代异步 Web 框架
- **Neo4j** — 图数据库
- **Agent Skills 规范** — 插件化技能系统设计

---

## ⚠️ 免责声明

**本项目仅供学习和研究使用，请勿用于任何违法用途。**

1. **使用风险**：用户使用本项目产生的任何直接或间接损失，本项目不承担任何责任
2. **内容准确性**：AI 生成的内容可能存在不准确、不完整或过时的情况，用户应自行核实
3. **数据隐私**：用户应妥善保管 API Key、数据库凭证等敏感信息，避免泄露
4. **合规使用**：使用本项目时应遵守当地法律法规，不得用于任何违法违规行为
5. **第三方服务**：本项目依赖的第三方服务（OpenAI、Tavily 等）的使用条款由其提供方制定
6. **无担保**：本项目按"现状"提供，不提供任何形式的明示或暗示担保

---

<p align="center">
  <strong>⭐ 如果这个项目对你有帮助，请给个 Star 支持一下！</strong>
</p>
