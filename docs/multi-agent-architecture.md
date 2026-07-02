# Multi-Agent Architecture

这份文档定义当前项目如何从“单个多技能 Agent”演进到“多个独立 Agent 并列使用”的架构。

目标不是把所有能力再塞回一个总控 Agent，而是让每个 Agent 都有自己的边界、技能集、工具集和工作流。

## 1. 设计目标

我们要支持这种使用方式：

- 一个前端
- 多个独立 Agent
- 每个 Agent 只服务自己的领域
- 用户在会话开始前先选择 Agent
- 每个会话天然绑定一个 Agent
- 后端按 Agent 加载不同的 `skill / tool / workflow`

最终形态不是“一个万能 Agent”，而是：

- `content-agent`
- `marketing-agent`
- `research-agent`
- 未来可扩展 `code-agent`、`ops-agent`

但当前项目最适合先拆成 2 个主 Agent：

- `content-intelligence-agent`
- `marketing-agent`

## 2. 单 Agent 边界

### 2.1 Content Intelligence Agent

职责：

- PDF 处理与分析
- 图片分析
- 股票图分析
- 网页内容分析
- SEO 审查
- 可选图谱查询

建议绑定：

- skills
  - `pdf`
  - `image-analysis`
  - `stock-analysis`
  - `web-content-analyzer`
  - `seo-audit`
- tools
  - `pdf_tool`
  - `image_tool`
  - `web_search`
  - `web_scraper`
  - 可选 `smart_graph_query`
- workflows
  - 暂时可以为空

### 2.2 Marketing Agent

职责：

- 市场调研
- 内容规划
- 营销文案
- 社媒创意
- 海报与主视觉生成
- 固定营销工作流

建议绑定：

- skills
  - `marketing-research`
  - `content-planner`
  - `marketing-copywriting`
  - `social-creative`
  - `imagegen`
- tools
  - `web_search`
  - `web_scraper`
  - `imagegen_tool`
- workflows
  - `marketing-workflow`

## 3. 总体架构

推荐采用“并列 Agent + 上层选择入口”的结构。

```text
Frontend
  -> agent selector
  -> session scoped to one agent

API Layer
  -> receives agent_id
  -> resolves target runtime

Agent Runtime Factory
  -> loads one agent profile
  -> builds scoped skills/tools/workflows
  -> returns isolated MyAgent instance

Execution Layer
  -> router
  -> executor
  -> tools
```

核心原则：

- 每个 Agent 是独立 runtime
- 每个 runtime 有自己的 skill 视图
- 每个 runtime 有自己的 tool 视图
- 每个 runtime 有自己的 workflow 视图
- session 必须带 `agent_id`

## 4. 前端如何选择 Agent

当前前端是单入口聊天页，没有 Agent 维度。建议这样改。

### 4.1 UI 位置

推荐把 Agent 选择器放在左侧栏顶部，位于 `New Chat` 上方或下方。

可用样式：

- 下拉框
- 横向 tabs
- 卡片切换器

建议最小版本先用下拉框。

示例：

- `Content Intelligence`
- `Marketing`

### 4.2 前端行为

前端维护一个 `currentAgentId`：

- 创建新会话时，携带 `agent_id`
- 加载会话列表时，按 `agent_id` 过滤或分组
- 切换 agent 时，默认切换到该 agent 的会话视图
- 当前会话若属于其他 agent，不允许直接混用

### 4.3 需要改的前端点位

当前关键文件：

- `static/js/chat.js`
- `static/js/message.js`

建议新增：

- `currentAgentId`
- agent selector 初始化逻辑
- 请求体里传 `agent_id`
- session list 只展示当前 agent 的会话

## 5. 后端如何按 Agent 加载不同 skill / tool / workflow

这是最关键的一层。

### 5.1 当前问题

当前项目主要还是“单 Agent 单实例”模型：

- `get_agent()` 返回单例 Agent
- `tool_manager` 是全局注册
- `skill_registry` 是全局注册
- workflow registry 也是全局加载
- session 数据结构没有 `agent_id`

这意味着：

- 所有会话默认共用一个 Agent runtime
- 所有 skill 默认都在一个池子里
- 多 agent 只能靠 prompt 区分，不是真隔离

### 5.2 目标改造

需要引入 `AgentProfile`。

一个 AgentProfile 至少包含：

- `agent_id`
- `name`
- `description`
- `skill_names`
- `tool_names`
- `workflow_names`
- `system_prompt_version` 或 prompt patch
- 可选 `route_policy`

示例：

```yaml
agent_id: marketing-agent
name: Marketing Agent
description: Focused on marketing research, copywriting, social creative, and visual generation.
skill_names:
  - marketing-research
  - content-planner
  - marketing-copywriting
  - social-creative
  - imagegen
tool_names:
  - web_search
  - web_scraper
  - imagegen_tool
workflow_names:
  - marketing-workflow
```

### 5.3 Profile 存放位置

建议新增目录：

```text
src/agents/profiles/
  content-intelligence.yaml
  marketing-agent.yaml
```

### 5.4 Runtime Factory

建议新增一个工厂层：

- `AgentRuntimeFactory`

职责：

- 读取 `AgentProfile`
- 构建该 Agent 的 scoped tool list
- 构建该 Agent 的 scoped skill registry
- 构建该 Agent 的 scoped workflow registry
- 缓存 runtime 实例

建议新增文件：

- `src/core/agent_profiles.py`
- `src/core/agent_factory.py`

### 5.5 Skill 作用域

当前 `SkillRegistry` 已经能从目录加载 skill。

下一步建议不是改 skill 文件位置，而是增加“按名称筛选”的能力：

- 先加载全部 skill metadata
- 再按 `AgentProfile.skill_names` 过滤可见 skill

建议新增接口：

- `SkillRegistry.clone_scoped(skill_names: list[str])`

这样不用复制 skill 目录，也不会破坏你现在的 skill 管理逻辑。

### 5.6 Tool 作用域

当前 `tool_manager` 是全局工具池。

建议同样引入 scoped 视图：

- 先注册全部工具
- 再按 `AgentProfile.tool_names` 返回 scoped tool list

也就是现在已有的“按名字裁剪工具”思路，提升为 Agent 级别默认配置。

### 5.7 Workflow 作用域

当前 workflow 也是全局 registry。

建议和 skill 一样：

- 全量加载
- 按 `workflow_names` 过滤可见 workflow

建议新增：

- `WorkflowRegistry.clone_scoped(workflow_names: list[str])`

## 6. 会话与存储怎么改

这块必须改，不然前端切了 Agent，历史会话还是混在一起。

### 6.1 Session 增加 agent_id

当前 session 至少应该加上：

- `agent_id`

MongoDB session 文档建议变成：

```json
{
  "_id": "session-xxxx",
  "user_id": "u1",
  "agent_id": "marketing-agent",
  "title": "给我做一套营销方案",
  "messages": [...],
  "created_at": "...",
  "updated_at": "..."
}
```

### 6.2 查询逻辑

这些接口都应该支持 `agent_id`：

- `GET /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}`
- `POST /api/v1/chat/stream`

建议策略：

- 创建新 session 时必须写入 `agent_id`
- 列表接口默认只返回当前 `agent_id` 的会话
- 读取旧 session 时校验其 `agent_id`

## 7. API 怎么改

### 7.1 ChatRequest 增加 agent_id

当前 `src/api/routes/chat.py` 里 `ChatRequest` 只有：

- `message`
- `session_id`

建议增加：

- `agent_id`

例如：

```json
{
  "message": "请分析这份 PDF",
  "session_id": null,
  "agent_id": "content-intelligence-agent"
}
```

### 7.2 get_agent 改成按 profile 获取

当前：

- `get_agent()`

建议演进成：

- `get_agent(agent_id: str)`
- 内部走 `AgentRuntimeFactory`

### 7.3 会话列表接口

建议增加 query 参数：

- `/api/v1/sessions?agent_id=marketing-agent`

这样前端切 Agent 时不用再拉全量会话。

## 8. 路由层怎么理解

多 Agent 之后，路由不是取消，而是分两层：

### 第一层：Agent 选择

判断这次请求进入哪个 Agent。

当前建议先由前端显式选择，不要先做模型自动选 Agent。

### 第二层：Agent 内部路由

进入某个 Agent 之后，再走当前已有的：

- `workflow`
- `skill_direct`
- `simple`
- `complex`
- `graph_only`

也就是：

- Agent 级路由解决“去哪一个 Agent”
- 当前 Router 解决“这个 Agent 内部怎么执行”

## 9. 以后怎么扩展成 Orchestrator 模式

并列 Agent 跑稳之后，再考虑总控。

### 9.1 Orchestrator 的职责

Orchestrator 不应该持有一堆业务 skill。

它只负责：

- 理解总任务
- 选择需要哪些 Agent
- 安排执行顺序
- 汇总各 Agent 输出

### 9.2 推荐模式

```text
User Request
  -> Orchestrator
    -> Marketing Agent
    -> Content Agent
    -> maybe Research Agent
  -> Final Merge
```

### 9.3 Agent 间调用方式

建议用结构化 contract，而不是 prompt 硬拼。

每个 Agent 的输入输出建议标准化：

```json
{
  "agent_id": "marketing-agent",
  "task": "Generate campaign concepts",
  "input": {
    "topic": "企业服务 AI 工作流",
    "audience": "中小企业负责人"
  }
}
```

输出也结构化：

```json
{
  "success": true,
  "agent_id": "marketing-agent",
  "summary": "...",
  "artifacts": [...],
  "structured_output": {...}
}
```

## 10. 建议的实施顺序

不要一次改完，按阶段走。

### Phase 1：文档和边界先固定

- 确定有哪些 Agent
- 确定每个 Agent 的 skill / tool / workflow
- 固定 `agent_id` 命名

### Phase 2：前端增加 Agent 选择

- 加 selector
- 当前会话绑定 `agent_id`
- session list 支持按 agent 过滤

### Phase 3：后端增加 AgentProfile 和 AgentRuntimeFactory

- profile 配置文件
- runtime 缓存
- scoped skill/tool/workflow

### Phase 4：会话存储增加 agent_id

- MongoDB schema 增加字段
- 旧数据兼容迁移

### Phase 5：Orchestrator 作为独立层加入

- 先做串行分发
- 再做多 Agent 汇总

## 11. 对当前代码最小可行改造点

如果按最小成本推进，优先改这些文件：

- `src/api/routes/chat.py`
  - 请求体增加 `agent_id`
  - session 查询增加 `agent_id`
- `src/core/agent.py`
  - 从单全局 agent 过渡到按 profile 构造 agent
- `src/skills/manager.py`
  - 增加 scoped registry 能力
- `src/core/workflows/registry.py`
  - 增加 scoped registry 能力
- `src/storage/mongodb.py`
  - session 增加 `agent_id`
- `static/js/chat.js`
  - 增加 agent selector 和 session 过滤
- `static/js/message.js`
  - 发消息时带 `agent_id`

## 12. 当前结论

当前项目完全可以和其他 Agent 一起使用，而且更适合这么做。

最合理的方向不是继续把功能都堆进一个 Agent，而是：

- 每个 Agent 独立
- 每个 Agent 有自己的边界
- skill / tool / workflow 都按 Agent 隔离
- 前端先选 Agent
- 后端按 AgentProfile 构造 runtime
- 后续再在上层加 orchestrator

这是比“一个大 Agent 挂所有 skill”更稳、更清晰、也更容易长期维护的方案。