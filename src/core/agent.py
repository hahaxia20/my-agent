"""
生产级 AI Agent 核心模块
基于 LangGraph ReAct 架构实现

主要功能:
- 单 Agent 对话 (流式/非流式)
- 工具调用与管理
- 技能系统集成
- 会话管理与持久化
- 健康检查与监控
"""

# ═══════════════════════════════════════════════════════════
# 1. 导入依赖
# ═══════════════════════════════════════════════════════════

# 标准库
import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, AsyncIterator, cast

# 第三方库
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import StructuredTool
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.mongodb import MongoDBSaver
from langsmith import traceable
from pydantic import SecretStr, BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# 项目模块
from src.config import get_settings_safe
from src.core.context import SystemPromptContextManager, ConversationContextManager
from src.core.logging.decorator import log_method_call
from src.core.stream.manager import StreamFormatter
from src.core.helpers.intent_classifier import classify_intent
from src.core.helpers.chat_helpers import (
    check_input_security,
    format_subtask_results,
    handle_timeout,
    handle_chat_error,
)
from src.core.security import InputSecurityFilter
from src.core.tool_adapter import (
    safe_truncate as _safe_truncate,
    convert_to_langchain_tool, get_tool_type
)
from src.storage.mongodb import get_mongodb
from src.tools.manager import tool_manager
from src.skills.manager import skill_registry
from src.core.sub_agent import SubAgentOrchestrator
from src.core.sub_agent.models import SubAgentConfig
from src.core.stream.handler import StreamHandler

# 日志初始化 (注意: 只在主入口调用 setup_logging)
logger = logging.getLogger(__name__)


class AgentConfig(BaseModel):
    """Agent 运行时配置"""
    
    # 并发与超时
    max_concurrent_requests: int = Field(default=10, description="最大并发请求数")
    request_timeout: int = Field(default=120, description="请求超时 (秒)")
    tool_call_timeout: int = Field(default=60, description="工具调用超时 (秒)")
    
    # 重试与限制
    max_retries: int = Field(default=3, description="最大重试次数")
    recursion_limit: int = Field(default=50, description="递归深度限制")
    
    # 上下文管理
    context_window_size: int = Field(default=20, description="短期上下文窗口大小")
    
    # 功能开关
    enable_streaming: bool = Field(default=True, description="启用流式输出")
    enable_checkpoint: bool = Field(default=True, description="启用检查点持久化")
    debug: bool = Field(default=False, description="调试模式")

# ═══════════════════════════════════════════════════════════
# MyAgent 核心类
# ═══════════════════════════════════════════════════════════

class MyAgent:
    """
    生产级 ReAct Agent
    
    主要职责:
    - 管理 LLM 对话 (流式/非流式)
    - 工具调用与监控
    - 会话管理与持久化
    - 健康检查与统计
    """

    # ───────────────────────────────────────────────────────
    # 4.1 初始化与配置
    # ───────────────────────────────────────────────────────

    def __init__(self, config: Optional[AgentConfig] = None):
        """初始化 Agent"""
        logger.info("🔧 初始化生产级 Agent...")
        
        # 基础配置
        self.config = config or AgentConfig()
        self.settings = get_settings_safe()
        
        # 核心组件
        self.context_manager = SystemPromptContextManager(model=self.settings.MODEL_NAME)
        self.db = get_mongodb()
        self.tool_manager = tool_manager
        self.skill_registry = skill_registry
        
        # 对话上下文管理器（从配置读取）
        self.conversation_context = ConversationContextManager(
            db_manager=self.db,
            max_messages=self.settings.CONV_CTX_MAX_MESSAGES,
            max_tokens=self.settings.CONV_CTX_MAX_TOKENS,
            enable_compression=self.settings.CONV_CTX_ENABLE_COMPRESSION,
            keep_recent_messages=self.settings.CONV_CTX_KEEP_RECENT_MESSAGES,
            enable_ai_summary=self.settings.CONV_CTX_ENABLE_AI_SUMMARY,
            summary_max_length=self.settings.CONV_CTX_SUMMARY_MAX_LENGTH,
            chinese_token_ratio=self.settings.CONV_CTX_CHINESE_TOKEN_RATIO,
            english_token_ratio=self.settings.CONV_CTX_ENGLISH_TOKEN_RATIO
        )
        
        # 并发控制
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        
        # 调用统计
        self.tool_call_stats: Dict[str, Dict[str, Any]] = {}
        
        # 初始化 LLM、工具、检查点
        self.llm = self._init_llm()
        self.tools = self._init_tools()
        self.checkpointer = self._init_checkpointer() if self.config.enable_checkpoint else None
        
        # 初始化产业链图谱工具（如果 Neo4j 可用）
        self._init_industry_graph_tools()
        
        # 初始化 Sub-Agent 编排器
        self.sub_agent_orchestrator = self._init_sub_agent_orchestrator()
        
        # 流式处理器（委托模式，避免 agent.py 体量过大）
        self._stream_handler = StreamHandler(self)
        
        # 创建 ReAct Agent
        self.agent = self._create_agent()
        
        logger.info(f"✅ Agent 初始化完成 - 已加载 {len(self.tools)} 个工具")
        self._print_available_capabilities()

    # ───────────────────────────────────────────────────────
    # 4.2 私有方法: 初始化组件
    # ───────────────────────────────────────────────────────

    def _print_available_capabilities(self):
        """打印可用能力清单 (工具和技能)"""
        logger.info("\n" + "=" * 60)
        logger.info("📋 可用能力清单")
        logger.info("=" * 60)

        # 打印工具列表
        tools = self.tool_manager.get_all()
        if tools:
            logger.info("\n🔧 工具:")
            for tool in tools:
                logger.info(f"  - {tool.name}: {tool.description[:50]}...")

        # 打印技能列表
        skills = self.skill_registry.get_all()
        if skills:
            logger.info("\n🎯 技能 (通过中间件提供):")
            for skill in skills:
                logger.info(f"  - {skill.name}: {skill.description[:50]}...")

        logger.info("=" * 60 + "\n")

    def _init_llm(self) -> ChatOpenAI:
        """初始化 LLM 客户端"""
        logger.info(f"初始化 LLM: {self.settings.MODEL_NAME}")
        return ChatOpenAI(
            model=self.settings.MODEL_NAME,
            api_key=SecretStr(self.settings.OPENAI_API_KEY),
            base_url=self.settings.API_BASE_URL,
            temperature=self.settings.TEMPERATURE,
            timeout=self.config.request_timeout,
            max_retries=self.config.max_retries
        )

    def _init_tools(self) -> List[StructuredTool]:
        """
        初始化工具系统
        将 BaseTool 转换为 LangChain StructuredTool
        """
        tools = []

        for tool in self.tool_manager.get_all():
            try:
                langchain_tool = convert_to_langchain_tool(tool)
                tools.append(langchain_tool)
                logger.info(f"✅ 注册工具: {tool.name} (类型: {get_tool_type(tool)}, has_schema: {hasattr(langchain_tool, 'args_schema')})")
            except Exception as e:
                logger.error(f" 注册工具失败 {tool.name}: {e}", exc_info=True)

        # 注意: Skill 不再转换为工具，而是通过 SkillMiddleware 提供
        return tools

    def _record_tool_call(self, tool_name: str, duration: float, success: bool = True):
        """记录工具调用统计信息"""
        if tool_name not in self.tool_call_stats:
            self.tool_call_stats[tool_name] = {"count": 0, "total_time": 0.0, "errors": 0}

        self.tool_call_stats[tool_name]["count"] += 1
        self.tool_call_stats[tool_name]["total_time"] += duration
        if not success:
            self.tool_call_stats[tool_name]["errors"] += 1

    def _init_checkpointer(self) -> Optional[MongoDBSaver]:
        """初始化 MongoDB 检查点 (用于会话状态持久化)"""
        try:
            from pymongo import MongoClient

            sync_client = MongoClient(self.settings.MONGODB_URL)
            checkpointer = MongoDBSaver(
                client=sync_client,
                db_name="agent_checkpoints",
                collection_name="checkpoints"
            )

            logger.info("✅ MongoDB 检查点已启用")
            return checkpointer

        except Exception as e:
            logger.warning(f"检查点初始化失败，将使用内存存储: {e}")
            return None

    def _init_industry_graph_tools(self):
        """初始化产业链图谱工具（Neo4j）"""
        try:
            from src.tools.industry_graph import SmartGraphQueryTool

            # 注册图谱智能查询工具
            tool = SmartGraphQueryTool()
            self.tool_manager.register(tool)
            langchain_tool = convert_to_langchain_tool(tool)
            self.tools.append(langchain_tool)
            logger.info(f"✅ 注册图谱工具: {tool.name}")

            logger.info("📊 产业链图谱工具已加载 (1 个)")

        except Exception as e:
            logger.warning(f"⚠️ 产业链图谱工具加载失败（Neo4j 可能未启动）: {e}")
            logger.warning("💡 提示：启动 Neo4j 后可自动启用图谱功能")

    def _get_system_prompt(self) -> str:
        """获取系统提示词 (通过 system_prompt_context_manager 统一管理)"""
        return self.context_manager._build_system_prompt()

    def _create_agent(self):
        """创建 LangGraph ReAct Agent"""
        from src.skills.middleware import SkillMiddleware

        system_prompt = self._get_system_prompt()

        # 调试模式: 打印系统提示词
        if self.config.debug:
            logger.debug("=" * 80)
            logger.debug("📝 [系统提示词]")
            logger.debug(system_prompt)
            logger.debug("=" * 80)

        return create_agent(
            model=self.llm,
            tools=self.tools,
            checkpointer=self.checkpointer,
            system_prompt=system_prompt,
            middleware=[SkillMiddleware()],
            debug=self.config.debug,
            name="my_agent"
        )

    def _init_sub_agent_orchestrator(self) -> SubAgentOrchestrator:
        """初始化 Sub-Agent 编排器"""
        sub_agent_config = SubAgentConfig(
            max_concurrent_agents=5,
            sub_agent_timeout=300,
            max_retries=2,
            enable_decomposition=True,
            max_sub_tasks=10,
            enable_synthesis=True,
            synthesis_format="markdown",
            debug=self.config.debug
        )
        
        orchestrator = SubAgentOrchestrator(
            llm=self.llm,
            tools=self.tools,
            config=sub_agent_config
        )
        
        logger.info("✅ Sub-Agent 编排器已初始化")
        return orchestrator

    # ───────────────────────────────────────────────────────
    # 4.3 公共辅助方法
    # ───────────────────────────────────────────────────────

    def _check_input_security(self, user_query: str, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """检查输入安全性（委托到 chat_helpers 模块）"""
        return check_input_security(user_query, session_id)

    async def _ensure_session(self, session_id: Optional[str], user_id: str, title: str) -> str:
        """确保会话存在，不存在则创建"""
        if not session_id:
            session_id = await self.db.create_session(user_id=user_id, title=title)
            logger.info(f"📝 创建新会话: {session_id}")
        return session_id

    @staticmethod
    def _format_subtask_results(sub_agent_results) -> List[Dict[str, Any]]:
        """格式化子任务结果列表（委托到 chat_helpers 模块）"""
        return format_subtask_results(sub_agent_results)

    def _classify_intent(self, query: str) -> str:
        """意图分类（委托到 intent_classifier 模块）"""
        return classify_intent(query)

    async def _build_history_context(self, session_id: str) -> Optional[str]:
        """
        构建对话历史背景摘要
        
        仅返回纯历史摘要字符串，供 Decomposer 理解用户意图。
        不包含当前任务，当前任务由 complex_chat 单独传入。
        
        Returns:
            历史摘要字符串；无历史时返回 None
        """
        if not session_id:
            return None
        
        try:
            messages = await self.db.get_messages(session_id)
            if not messages:
                return None
            
            # 取最近的消息（偶数条，保证问答配对）
            max_history = 6
            recent = messages[-max_history:] if len(messages) > max_history else messages
            
            context_lines = []
            for msg in recent:
                role = "用户" if msg.get("role") == "user" else "助手"
                content = msg.get("content", "")[:150]
                context_lines.append(f"- {role}: {content}")
            
            history_summary = "\n".join(context_lines)
            
            logger.info(
                f"📚 [历史上下文] 已加载 {len(recent)} 条历史消息作为背景"
            )
            return history_summary
            
        except Exception as e:
            logger.warning(f"⚠️ 加载历史上下文失败: {e}")
            return None

    # ───────────────────────────────────────────────────────
    # 4.4 核心方法: 对话处理
    # ───────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((Exception,))
    )
    @traceable(name="agent_chat", tags=["production"])
    @log_method_call(prefix="[Agent-对话] ", log_duration=True)
    async def chat(
            self,
            user_query: str,
            session_id: Optional[str] = None,
            user_id: str = "anonymous",
            metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        普通对话 (非流式)
        
        Args:
            user_query: 用户查询
            session_id: 会话 ID (可选)
            user_id: 用户 ID
            metadata: 额外元数据
        
        Returns:
            包含回复、会话 ID、状态等信息的字典
        """
        logger.info(f"💬 [对话开始] session_id={session_id}, user_id={user_id}")
        logger.debug(f"   用户查询: {_safe_truncate(user_query, 500)}")

        # 🔒 安全检查
        security_block = self._check_input_security(user_query, session_id)
        if security_block:
            return security_block

        request_start = time.time()
        session_id = await self._ensure_session(session_id, user_id, user_query[:30])

        # 构建 Runnable 配置
        config = self._build_runnable_config(session_id, user_id, metadata)

        # 执行对话 (带并发控制和超时)
        async with self._semaphore:
            try:
                async with asyncio.timeout(self.config.request_timeout):
                    return await self._execute_chat(
                        user_query, session_id, config, request_start
                    )
            except asyncio.TimeoutError:
                return self._handle_timeout(session_id, request_start)
            except Exception as e:
                return self._handle_chat_error(session_id, e, request_start)

    @log_method_call(prefix="[Agent-执行] ", log_duration=True)
    async def _execute_chat(
            self, 
            user_query: str, 
            session_id: str, 
            config: RunnableConfig,
            request_start: float
    ) -> Dict[str, Any]:
        """执行对话逻辑"""
        logger.info(f"🤖 调用 Agent 处理请求: {session_id}")
            
        # 使用对话上下文管理器加载历史消息
        input_messages = await self.conversation_context.load_context(
            session_id=session_id,
            current_message=user_query
        )
            
        # 记录上下文统计信息
        stats = self.conversation_context.get_context_stats(input_messages)
        logger.info(f"📊 上下文统计: {stats}")
    
        result = await self.agent.ainvoke(
            cast(Any, {"messages": input_messages}),
            config=config
        )

        # 提取回复
        last_message = result["messages"][-1]
        reply = last_message.content if hasattr(last_message, 'content') else str(last_message)

        elapsed = time.time() - request_start

        # 记录日志
        logger.info(
            f"✅ [对话完成] session={session_id} - "
            f"耗时: {elapsed:.2f}s - "
            f"消息数: {len(result['messages'])} - "
            f"回复长度: {len(reply)} 字符"
        )

        # 打印工具调用统计
        self._log_tool_call_stats()

        # 保存消息
        await self.db.add_message(session_id, "user", user_query)
        await self.db.add_message(session_id, "assistant", reply)

        return {
            "reply": reply,
            "session_id": session_id,
            "success": True,
            "token_usage": result.get("total_usage", {}),
            "message_count": len(result["messages"]),
            "elapsed_time": elapsed
        }

    def _handle_timeout(self, session_id: str, request_start: float) -> Dict[str, Any]:
        """处理超时错误（委托到 chat_helpers 模块）"""
        return handle_timeout(session_id, request_start)

    def _handle_chat_error(self, session_id: str, error: Exception, request_start: float) -> Dict[str, Any]:
        """处理对话错误（委托到 chat_helpers 模块）"""
        return handle_chat_error(session_id, error, request_start)

    def _build_runnable_config(
            self,
            session_id: str,
            user_id: str,
            metadata: Optional[Dict[str, Any]] = None,
            tags: List[str] = None
    ) -> RunnableConfig:
        """构建 LangChain Runnable 配置"""
        return RunnableConfig(
            configurable={"thread_id": session_id},
            metadata={
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
                **(metadata or {})
            },
            tags=tags or ["production"],
            recursion_limit=self.config.recursion_limit
        )

    def _log_tool_call_stats(self):
        """打印工具调用统计信息"""
        if self.tool_call_stats:
            logger.info(f"📊 [调用统计] 工具: {len(self.tool_call_stats)} 个")
            for tool_name, stats in self.tool_call_stats.items():
                avg_time = stats["total_time"] / stats["count"] if stats["count"] > 0 else 0
                logger.debug(
                    f"   工具 [{tool_name}]: 调用{stats['count']}次, "
                    f"平均{avg_time:.2f}s, 错误{stats['errors']}次"
                )

    # ───────────────────────────────────────────────────────
    # 4.4 复杂任务处理 (Sub-Agent 编排)
    # ───────────────────────────────────────────────────────

    @log_method_call(prefix="[Agent-复杂任务] ", log_duration=True)
    async def complex_chat(
            self,
            user_query: str,
            session_id: Optional[str] = None,
            user_id: str = "anonymous",
            decomposition_strategy: str = "auto",
            progress_callback=None  # 新增：进度回调
    ) -> Dict[str, Any]:
        """
        复杂任务对话 (使用 Sub-Agent 编排)
        
        适用于需要多步骤、多工具协作的复杂任务，例如：
        - 深度研究与分析
        - 多主题对比
        - 综合报告生成
        - 数据处理流水线
        
        Args:
            user_query: 复杂任务描述
            session_id: 会话 ID
            user_id: 用户 ID
            decomposition_strategy: 分解策略 (parallel/sequential/hybrid/auto)
            progress_callback: 进度回调函数
        
        Returns:
            包含合成结果、子任务详情等信息的字典
        """
        logger.info(f"🎭 [复杂任务] 开始处理: {user_query[:100]}...")
        
        # 🔒 安全检查
        security_block = self._check_input_security(user_query, session_id)
        if security_block:
            return security_block
        
        request_start = time.time()
        session_id = await self._ensure_session(session_id, user_id, f"[复杂] {user_query[:20]}")
        
        try:
            # 主 Agent 负责上下文管理：加载历史作为背景（不含当前任务）
            history_context = await self._build_history_context(session_id)
            
            # 使用 Sub-Agent 编排器执行
            # task = 纯任务（当前问题）；context = 纯背景（历史）
            result = await self.sub_agent_orchestrator.execute(
                task=user_query,
                session_id=session_id,
                user_id=user_id,
                decomposition_strategy=decomposition_strategy,
                progress_callback=progress_callback,
                context=history_context
            )
            
            elapsed = time.time() - request_start
            
            # 保存到数据库
            await self.db.add_message(session_id, "user", user_query)
            
            # 格式化子任务结果
            sub_tasks = self._format_subtask_results(result.sub_agent_results)
            
            # 保存 AI 回复，并附加子任务元数据
            subtask_metadata = {
                "is_complex_task": True,
                "sub_tasks": sub_tasks,
                "total_duration": result.total_duration,
                "parallel_efficiency": result.parallel_efficiency,
                "decomposition_strategy": result.decomposition.decomposition_strategy if result.decomposition else None
            }
            
            # 若编排器返回失败且没有合成结果，提供有意义的错误信息
            reply = result.synthesized_result
            if not result.success and not reply:
                error_detail = result.error if result.error else "所有子任务执行失败"
                reply = f"复杂任务执行失败：{error_detail}"

            # 保存 AI 回复（用处理后的 reply，避免存入空值）
            await self.db.add_message(
                session_id,
                "assistant",
                reply,
                metadata=subtask_metadata
            )

            logger.info(
                f"✅ [复杂任务] 完成 - "
                f"耗时: {elapsed:.2f}s, "
                f"子任务数: {len(result.sub_agent_results)}, "
                f"成功: {sum(1 for r in result.sub_agent_results if r.status.value == 'completed')}"
            )

            return {
                "reply": reply,
                "session_id": session_id,
                "success": result.success,
                "elapsed_time": elapsed,
                "sub_tasks": sub_tasks,
                "metadata": {
                    "total_duration": result.total_duration,
                    "parallel_efficiency": result.parallel_efficiency,
                    "decomposition_strategy": result.decomposition.decomposition_strategy if result.decomposition else None
                }
            }
            
        except Exception as e:
            elapsed = time.time() - request_start
            logger.error(f"💥 [复杂任务] 失败: {e}", exc_info=True)
            
            return {
                "reply": f"复杂任务执行失败：{str(e)}",
                "session_id": session_id,
                "success": False,
                "error": str(e),
                "elapsed_time": elapsed
            }

    # ========== 流式对话（委托给 StreamHandler） ==========

    async def stream(
            self,
            user_query: str,
            session_id: Optional[str] = None,
            user_id: str = "anonymous",
            enable_metrics: bool = True,
            buffer_size: int = 5,
            flush_interval: float = 0.05
    ) -> AsyncIterator[str]:
        """流式对话（委托给 StreamHandler）"""
        async for chunk in self._stream_handler.stream(
            user_query=user_query,
            session_id=session_id,
            user_id=user_id,
            enable_metrics=enable_metrics,
            buffer_size=buffer_size,
            flush_interval=flush_interval
        ):
            yield chunk

    # ========== 会话管理 ==========

    @traceable(name="agent_continue", tags=["production"])
    async def continue_chat(
            self,
            session_id: str,
            user_id: str = "anonymous"
    ) -> Dict[str, Any]:
        """继续之前的对话（从检查点恢复）"""

        logger.info(f"🔄 [继续对话] session_id={session_id}, user_id={user_id}")

        config = RunnableConfig(
            configurable={"thread_id": session_id},
            metadata={"user_id": user_id},
            tags=["production", "continue"]
        )

        try:
            state = await self.agent.aget_state(config)

            if not state or not state.values:
                logger.warning(f"⚠️ 未找到会话: {session_id}")
                return {
                    "reply": "未找到之前的对话记录。",
                    "success": False,
                    "error": "session_not_found"
                }

            logger.info(f"📊 恢复会话状态，当前消息数: {len(state.values.get('messages', []))}")

            result = await self.agent.ainvoke(None, config=config)
            last_message = result["messages"][-1]

            logger.info(f"✅ 继续对话完成: {session_id}")

            return {
                "reply": last_message.content,
                "success": True
            }

        except Exception as e:
            logger.error(f"💥 继续对话失败: {e}", exc_info=True)
            return {
                "reply": f"恢复对话失败：{str(e)}",
                "success": False,
                "error": str(e)
            }

    async def get_state(self, session_id: str, user_id: str = "anonymous") -> Dict[str, Any]:
        """获取会话状态"""
        config = RunnableConfig(
            configurable={"thread_id": session_id},
            metadata={"user_id": user_id}
        )

        try:
            state = await self.agent.aget_state(config)
            if state and state.values:
                messages = state.values.get("messages", [])
                logger.debug(f"获取会话状态: {session_id}, 消息数: {len(messages)}")
                return {
                    "success": True,
                    "message_count": len(messages),
                    "last_message": messages[-1].content if messages else None,
                    "has_more": bool(state.next)
                }
            logger.warning(f"未找到会话状态: {session_id}")
            return {"success": False, "error": "session_not_found"}
        except Exception as e:
            logger.error(f"获取会话状态失败: {e}")
            return {"success": False, "error": str(e)}

    async def get_session_history(
            self,
            session_id: str,
            user_id: str = "anonymous"
    ) -> Dict[str, Any]:
        """获取会话历史（业务数据库）"""
        session = await self.db.get_session(session_id)
        if not session or session.get("user_id") != user_id:
            logger.warning(f"无权访问会话: {session_id}, user={user_id}")
            return {"success": False, "error": "无权访问"}

        logger.info(f"获取会话历史: {session_id}, 消息数: {session['metadata']['message_count']}")

        return {
            "success": True,
            "session_id": str(session["_id"]),
            "title": session["title"],
            "messages": session["messages"],
            "message_count": session["metadata"]["message_count"],
            "created_at": session["metadata"]["created_at"],
            "updated_at": session["metadata"]["updated_at"]
        }

    async def list_sessions(
            self,
            user_id: str = "anonymous",
            limit: int = 20,
            offset: int = 0
    ) -> List[Dict[str, Any]]:
        """列出用户的所有会话"""
        sessions = await self.db.list_sessions(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        logger.info(f"列出用户会话: {user_id}, 数量: {len(sessions)}")

        return [{
            "session_id": str(s["_id"]),
            "title": s["title"],
            "message_count": s["metadata"]["message_count"],
            "updated_at": s["metadata"]["updated_at"]
        } for s in sessions]

    async def delete_session(self, session_id: str, user_id: str = "anonymous") -> bool:
        """删除会话"""
        session = await self.db.get_session(session_id)
        if not session or session.get("user_id") != user_id:
            logger.warning(f"无权删除会话: {session_id}, user={user_id}")
            return False

        await self.db.delete_session(session_id)

        if self.checkpointer:
            try:
                await self.checkpointer.adelete_thread(session_id)
                logger.info(f"✅ 删除会话检查点: {session_id}")
            except Exception as e:
                logger.warning(f"删除检查点失败: {e}")

        logger.info(f"✅ 删除会话: {session_id}")
        return True

    # ========== 统计与健康检查 ==========

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        logger.info("🏥 执行健康检查")

        checks = {
            "llm": False,
            "mongodb": False,
            "tools": False,
            "checkpointer": False
        }

        try:
            await self.llm.ainvoke("ping")
            checks["llm"] = True
            logger.debug("✅ LLM 健康检查通过")
        except Exception as e:
            logger.error(f"❌ LLM 健康检查失败: {e}")

        try:
            await self.db.ping()
            checks["mongodb"] = True
            logger.debug("✅ MongoDB 健康检查通过")
        except Exception as e:
            logger.error(f"❌ MongoDB 健康检查失败: {e}")

        checks["tools"] = len(self.tools) > 0
        checks["checkpointer"] = self.checkpointer is not None

        all_healthy = all(checks.values())

        status = "healthy" if all_healthy else "unhealthy"
        logger.info(f"🏥 健康检查结果: {status}")

        return {
            "status": status,
            "checks": checks,
            "timestamp": datetime.now().isoformat()
        }

    async def get_call_stats(self) -> Dict[str, Any]:
        """获取工具/技能调用统计"""
        return {
            "tools": self.tool_call_stats,
            "total_tool_calls": sum(s["count"] for s in self.tool_call_stats.values()),
            "tool_error_rate": sum(s["errors"] for s in self.tool_call_stats.values()) / max(1, sum(
                s["count"] for s in self.tool_call_stats.values()))
        }

    async def reset_stats(self):
        """重置调用统计"""
        self.tool_call_stats.clear()
        logger.info("📊 调用统计已重置")


# ====================== 单例模式 ======================
_agent: Optional[MyAgent] = None
_agent_lock = asyncio.Lock()


async def get_agent() -> MyAgent:
    """异步获取 Agent 单例"""
    global _agent
    if _agent is None:
        async with _agent_lock:
            if _agent is None:
                _agent = MyAgent()
    return _agent


def get_agent_sync() -> MyAgent:
    """同步获取 Agent 单例（用于非异步上下文）"""
    global _agent
    if _agent is None:
        _agent = MyAgent()
    return _agent