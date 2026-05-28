#  My Agent - 生产级 AI Agent 系统

<p align="center">
  <strong>基于 LangGraph ReAct 架构的多模态 AI Agent 平台</strong>
</p>

<p align="center">
  <a href="#features">特性</a> •
  <a href="#quick-start">快速开始</a> •
  <a href="#architecture">架构</a> •
  <a href="#api-docs">API</a> •
  <a href="#skills-system">Skills 系统</a> •
  <a href="#tech-stack">技术栈</a>
</p>

---

##  核心特性

### 🤖 智能对话
- **流式输出 (SSE)**: 实时生成,打字机效果
- **上下文管理**: 智能对话历史压缩与重要性筛选
- **多轮对话**: 支持连续对话,保持上下文一致性
- **会话持久化**: MongoDB 存储,支持会话管理

###  Sub-Agent 编排系统
- **任务分解**: 自动将复杂任务拆分为多个子任务
- **并行执行**: 支持子任务并发执行,提升效率
- **结果合成**: 智能整合多个子任务结果
- **流式进度**: 实时展示子任务执行进度

### 🎯 插件化 Skills 系统
- **配置化定义**: 基于 Markdown (SKILL.md) 文件配置
- **自动加载**: 热插拔,无需重启服务
- **支持资源**: 脚本、参考文档、静态资源
- **向后兼容**: 同时支持代码 Skill 和 Markdown Skill

### 🛠️ 内置工具集
- **Web Search**: Tavily 搜索引擎集成
- **Web Scraper**: 网页内容抓取与分析
- **Calculator**: 数学计算工具
- **Time Tools**: 时间日期处理

### 🔐 安全与认证
- **JWT 认证**: 安全的用户身份验证
- **CORS 配置**: 跨域资源共享控制
- **配置管理**: 环境变量驱动的配置系统

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- MongoDB 4.4+
- OpenAI API Key (或兼容的 LLM API)

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/YOUR_USERNAME/my-agent.git
cd my-agent

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件,填入你的 API Key 和数据库配置
```

### 配置示例 (.env)

```env
# LLM 配置
OPENAI_API_KEY=your-api-key-here
API_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o

# MongoDB 配置
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=myagent

# 搜索配置 (可选)
TAVILY_API_KEY=your-tavily-key

# JWT 密钥
JWT_SECRET_KEY=your-secret-key
```

### 启动服务

```bash
# 启动后端
python run.py

# 或使用 uvicorn 直接启动
uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload
```

访问:
- **API 文档**: http://localhost:8001/docs
- **前端界面**: 打开 `frontend.html` 文件
- **健康检查**: http://localhost:8001/health

---

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────┐
│                  Frontend                       │
│         (HTML/JS/CSS - SSE Streaming)           │
└────────────────────────────────────────────────┘
                 │ HTTP/SSE
┌────────────────▼────────────────────────────────┐
│              FastAPI Server                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │ Auth API │  │ Chat API │  │ Complex Task │ │
│  │          │  │          │  │     API      │ │
│  └──────────┘  └──────────┘  └──────────────┘ │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│              Core Agent Layer                   │
│  ┌──────────────────┐  ┌────────────────────┐  │
│  │ Single Agent     │  │ Sub-Agent          │  │
│  │ (ReAct + Tools)  │  │ Orchestrator       │  │
│  │                  │  │  • Decomposer      │  │
│  │ • Context Mgmt   │  │  • Worker Pool     │  │
│  │ • Tool Calling   │  │  • Synthesizer     │  │
│  └──────────────────┘  ────────────────────┘  │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│           Plugins & Tools Layer                 │
│  ┌──────────────┐  ┌──────────────────────┐    │
│  │ Skills       │  │ Tools                │    │
│  │ • Markdown   │  │ • Web Search         │    │
│  │ • Code-based │  │ • Web Scraper        │    │
│  │ • Auto-load  │  │ • Calculator         │    │
│  └──────────────┘  └──────────────────────┘    │
└────────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│              Storage Layer                      │
│  ──────────────────┐  ┌────────────────────┐  │
│  │ MongoDB          │  │ LangGraph          │  │
│  │ • Sessions       │  │ Checkpoint Saver   │  │
│  │ • Messages       │  │ (Conversation State)│ │
│  └──────────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### 核心模块

| 模块 | 路径 | 功能 |
|------|------|------|
| **API Routes** | `src/api/routes/` | RESTful API 接口 (Chat, Auth, Complex Tasks) |
| **Core Agent** | `src/core/agent.py` | LangGraph ReAct Agent 实现 |
| **Sub-Agent** | `src/core/sub_agent/` | 多 Agent 编排系统 |
| **Context** | `src/core/context/` | 对话上下文管理 |
| **Tools** | `src/tools/` | 内置工具集 (搜索、爬虫、计算等) |
| **Skills** | `src/skills/` | 插件化技能系统 |
| **Storage** | `src/storage/` | MongoDB 数据持久化 |

---

## 📖 API 文档

### 认证接口

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "your-password"
}

Response:
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

### 普通对话 (流式)

```http
POST /api/v1/chat/stream
Authorization: Bearer {token}
Content-Type: application/json

{
  "message": "你好,介绍一下你自己",
  "session_id": "optional-session-id"
}

Response: Server-Sent Events (SSE)
data: __SESSION_ID__:session_123
data: 你好!我是...
data: 一个AI助手...
data: [DONE]
```

### 复杂任务 (流式)

```http
POST /api/v1/complex-chat/stream
Authorization: Bearer {token}
Content-Type: application/json

{
  "task": "对比分析 Python 和 Java 的优缺点",
  "session_id": "optional-session-id",
  "decomposition_strategy": "auto"
}

Response: Server-Sent Events (SSE)
data: {"type": "decompose_start"}
data: {"type": "decompose_complete", "data": {"sub_tasks_count": 3}}
data: {"type": "subtask_start", "data": {"task_id": "1", "task_name": "Python分析"}}
data: {"type": "subtask_complete", "data": {"task_id": "1", "duration": 5.2}}
data: {"type": "synthesis_start"}
data: {"type": "synthesis_complete", "data": {"final_result": "..."}}
data: [DONE]
```

### 会话管理

```http
GET /api/v1/sessions              # 获取会话列表
GET /api/v1/sessions/{id}         # 获取会话详情
DELETE /api/v1/sessions/{id}      # 删除会话
```

完整 API 文档请访问: http://localhost:8001/docs

---

##  Skills 系统

### 什么是 Skills?

Skills 是基于 [Agent Skills 规范](https://agentskills.io/specification) 的插件化能力扩展系统。通过 Markdown 文件配置,无需编写代码即可为 Agent 添加新能力。

### 目录结构

```
src/skills/
├── web-content-analyzer/          # Skill 目录
│   ├── SKILL.md                   # 必需: 元数据 + 指令
│   ├── scripts/                   # 可选: 可执行脚本
│   │   ── analyze.py
│   └── references/                # 可选: 参考文档
│       ── REFERENCE.md
├── data-analysis/                 # 另一个 Skill
│   └── SKILL.md
```

### SKILL.md 示例

```markdown
---
name: web-content-analyzer
description: 分析网页内容,提取关键信息,总结内容并检测 SEO 问题
license: MIT
metadata:
  author: Your Name
  version: "1.0.0"
---

# Web Content Analyzer

## 使用场景
- 分析网页内容和结构
- 提取关键信息和摘要
- 检测 SEO 问题

## 执行步骤
1. 使用 web_scraper 工具获取网页内容
2. 分析页面结构和关键元素
3. 生成内容摘要和分析报告
4. 输出结构化结果
```

### 创建新 Skill

```bash
# 1. 创建目录
mkdir src/skills/my-custom-skill

# 2. 创建 SKILL.md
cat > src/skills/my-custom-skill/SKILL.md << 'EOF'
---
name: my-custom-skill
description: 我的自定义 Skill
---

# My Custom Skill

## 功能
...

## 使用方法
...
EOF

# 3. 重启服务,自动加载
python run.py
```

详细使用指南: [SKILLS_GUIDE.md](SKILLS_GUIDE.md)

---

## 🛠️ 技术栈

### 后端
- **Web Framework**: [FastAPI](https://fastapi.tiangolo.com/) 0.109.0
- **ASGI Server**: [Uvicorn](https://www.uvicorn.org/) 0.27.0
- **LLM Framework**: [LangChain](https://python.langchain.com/) + [LangGraph](https://langchain-ai.github.io/langgraph/)
- **LLM Provider**: OpenAI / 阿里云通义千问 (兼容 OpenAI API)

### 数据存储
- **Database**: [MongoDB](https://www.mongodb.com/) 4.4+
- **Driver**: Motor (异步) + PyMongo
- **Checkpoint**: LangGraph MongoDB Checkpoint Saver

### 认证与安全
- **JWT**: PyJWT 2.8.0
- **Password Hashing**: bcrypt 4.1.2
- **CORS**: FastAPI CORS Middleware

### 外部服务
- **Web Search**: [Tavily](https://tavily.com/) API
- **Web Scraping**: BeautifulSoup4 + Requests

### 前端
- **Vanilla JS**: 原生 JavaScript (无框架)
- **SSE**: Server-Sent Events 流式传输
- **Markdown**: marked.js 渲染

---

## 📦 项目结构

```
my-agent/
├── src/
│   ├── api/                    # API 层
│   │   ├── middleware/         # 中间件 (Auth, CORS)
│   │   └── routes/             # 路由 (Chat, Auth, Complex Tasks)
│   ├── core/                   # 核心业务逻辑
│   │   ├── agent.py            # 主 Agent 实现
│   │   ├── context/            # 上下文管理
│   │   ├── sub_agent/          # Sub-Agent 编排系统
│   │   ├── prompt/             # 系统提示词管理
│   │   ── stream_manager.py   # 流式输出管理
│   ├── tools/                  # 工具集
│   │   ├── web_search.py       # Web 搜索工具
│   │   ├── web_scraper.py      # 网页抓取工具
│   │   ├── calculator.py       # 计算器工具
│   │   └── time.py             # 时间工具
│   ├── skills/                 # Skills 插件系统
│   │   ├── manager.py          # Skill 管理器
│   │   └── */SKILL.md          # Skill 定义文件
│   ├── storage/                # 存储层
│   │   └── mongodb.py          # MongoDB 连接管理
│   ├── config.py               # 配置管理
│   └── main.py                 # 应用入口
├── tests/                      # 测试用例
├── logs/                       # 日志文件
├── frontend.html               # 前端界面
├── login.html                  # 登录页面
├── run.py                      # 启动脚本
├── requirements.txt            # Python 依赖
├── .env                        # 环境变量配置
└── SKILLS_GUIDE.md             # Skills 使用指南
```

---

##  测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试
python tests/test_agent.py
python tests/test_skills.py
python tests/test_stream.py
```

---

## 📝 开发指南

### 添加新工具

```python
# src/tools/my_tool.py
from src.tools.base import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "我的工具描述"
    
    async def execute(self, **kwargs):
        # 实现工具逻辑
        return {"result": "success"}

# 在 __init__.py 中注册
from src.tools.my_tool import MyTool
tool_manager.register(MyTool())
```

### 添加新 Skill

参考 [Skills 系统](#-skills-系统) 章节,创建 `src/skills/my-skill/SKILL.md` 文件即可。

### 自定义上下文策略

```python
# src/core/context/context.py
class MyContextManager(SystemPromptContextManager):
    def custom_strategy(self):
        # 实现自定义上下文管理逻辑
        pass
```

---

## 📊 监控与日志

### 日志配置

```env
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR
LOG_TO_FILE=true        # 是否写入文件
LOG_FILE_PATH=logs/agent.log
JSON_FORMAT=false       # JSON 格式日志
ENABLE_EMOJI=true       # 启用 Emoji 图标
```

### 日志查看

```bash
# 实时查看日志
tail -f logs/agent.log

# 搜索特定日志
grep "工具调用" logs/agent.log
```

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request!

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

---



## 🙏 技术参考

本项目在开发过程中参考了以下开源项目的优秀设计理念:

- **LangChain** - LLM 应用开发框架
- **LangGraph** - 状态图编排框架
- **FastAPI** - 现代 Web 框架
- **Agent Skills 规范** - 插件化技能系统设计

---

<p align="center">
  <strong>⭐ 如果这个项目对你有帮助,请给个 Star 支持一下!</strong>
</p>

---

## ⚠️ 免责声明

**本项目仅供学习和研究使用,请勿用于任何违法用途。**

### 责任声明

1. **使用风险**: 用户在使用本项目时产生的任何直接或间接损失,本项目不承担任何责任
2. **内容准确性**: AI 生成的内容可能存在不准确、不完整或过时的情况,用户应自行核实
3. **数据隐私**: 用户应妥善保管自己的 API Key、数据库凭证等敏感信息,避免泄露
4. **合规使用**: 用户在使用本项目时应遵守当地法律法规,不得用于任何违法违规行为
5. **第三方服务**: 本项目依赖的第三方服务(如 OpenAI、Tavily 等)的使用条款由其提供方制定,用户应自行遵守
6. **无担保**: 本项目按"现状"提供,不提供任何形式的明示或暗示担保,包括但不限于适销性、特定用途适用性等

### 使用建议

- ✅ 用于学习 AI Agent 开发技术
- ✅ 用于个人项目和技术研究
- ✅ 用于内部测试和原型验证
- ❌ 不要用于生产环境的关键业务
- ❌ 不要存储敏感或个人隐私数据
-  不要用于生成虚假或有害内容
