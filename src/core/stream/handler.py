"""
流式对话处理器

从 agent.py 中独立抽取的流式逻辑，包括：
- Router + Executor 架构的路由与执行
- 复杂任务的 SSE 事件流式推送（保留旧接口兼容）
- 流式错误格式化

设计原则：
  StreamHandler 持有 MyAgent 实例，复用其核心组件（agent、db、config 等），
  agent.py 保持精简，只负责调度。
  路由决策由 router 模块负责，执行由各 Executor 负责。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING, AsyncIterator, Dict, Any, Optional

from src.core.router import route_query, RouteType
from src.core.executors import get_executor, ExecutorContext
from src.core.helpers.chat_helpers import check_input_security

from langchain_core.runnables import RunnableConfig

from src.core.logging.decorator import log_method_call
from src.core.tool_adapter import safe_truncate as _safe_truncate

if TYPE_CHECKING:
    from src.core.agent import MyAgent

logger = logging.getLogger(__name__)


class StreamHandler:
    """流式对话处理器

    职责：
    - 通过 Router 做意图路由（skill_direct / simple / complex / graph_only）
    - 通过 Executor 执行具体任务并流式返回响应
    - 保留 stream_complex_task 旧接口供向后兼容
    - 格式化流式错误信息
    """

    def __init__(self, agent: "MyAgent"):
        """
        Args:
            agent: MyAgent 实例，用于访问核心组件
        """
        self._agent = agent

    # ─────────────────────────────────────────────────────
    # 公共工具方法
    # ─────────────────────────────────────────────────────

    @staticmethod
    def format_stream_error(error: Exception) -> str:
        """根据错误类型返回友好的流式错误提示"""
        error_msg = str(error)
        if "403" in error_msg or "PermissionDenied" in error_msg:
            if "free tier" in error_msg.lower() or "quota" in error_msg.lower():
                return "\n❌ API 额度已用完，请检查你的 API Key 配置或联系管理员。"
            return "\n❌ API 访问被拒绝，请检查 API Key 是否正确。"
        elif "401" in error_msg or "Authentication" in error_msg:
            return "\n❌ API Key 无效，请检查配置。"
        elif "429" in error_msg or "rate limit" in error_msg.lower():
            return "\n⏳ 请求过于频繁，请稍后重试。"
        else:
            return f"\n抱歉，出现错误：{error_msg[:200]}"

    # ─────────────────────────────────────────────────────
    # 复杂任务流式推送（SSE JSON 事件）
    # ─────────────────────────────────────────────────────

    async def stream_complex_task(
        self,
        user_query: str,
        session_id: str,
        user_id: str,
    ) -> AsyncIterator[str]:
        """流式输出复杂任务进度（SSE JSON 事件）

        将 complex_chat 的执行过程通过 asyncio.Queue 转换为 SSE 事件流，
        支持实时推送子任务进度，最后推送 final_result。
        """
        agent = self._agent
        queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(event_type: str, data: dict):
            await queue.put(json.dumps(
                {"type": event_type, "data": data}, ensure_ascii=False
            ))

        async def execute():
            try:
                result = await agent.complex_chat(
                    user_query=user_query,
                    session_id=session_id,
                    user_id=user_id,
                    progress_callback=progress_callback
                )
                logger.info(
                    f"📦 [流式复杂任务] complex_chat 返回: "
                    f"success={result.get('success')}, reply长度={len(result.get('reply', ''))}"
                )
                await queue.put(json.dumps({
                    "type": "final_result",
                    "data": {
                        "success": result.get("success", False),
                        "reply": result.get("reply", ""),
                        "duration": result.get("elapsed_time", 0),
                        "sub_tasks": result.get("sub_tasks", []),
                        "metadata": result.get("metadata", {})
                    }
                }, ensure_ascii=False))
                logger.info("✅ [流式复杂任务] final_result 已推入队列")
            except Exception as e:
                logger.error(f"❌ 流式复杂任务失败: {e}", exc_info=True)
                await queue.put(json.dumps({
                    "type": "error",
                    "data": {"error": str(e)}
                }, ensure_ascii=False))

        task = asyncio.create_task(execute())
        while not task.done() or not queue.empty():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.5)
                yield f"data: {event}\n\n"
            except asyncio.TimeoutError:
                continue
        await task

    # ─────────────────────────────────────────────────────
    # 主入口：Router + Executor 流式对话
    # ─────────────────────────────────────────────────────

    @log_method_call(prefix="[Agent-流式] ", log_duration=True)
    async def stream(
        self,
        user_query: str,
        session_id: Optional[str] = None,
        user_id: str = "anonymous",
        enable_metrics: bool = True,
        buffer_size: int = 5,
        flush_interval: float = 0.05
    ) -> AsyncIterator[str]:
        """生产级流式对话（Router + Executor 架构）

        流程：
        1. 安全检查
        2. 路由决策（route_query）：根据查询 + 历史 + Skills 决定路由
        3. 构建 ExecutorContext，通过 get_executor() 获取执行器
        4. 逐 chunk 输出（各 Executor 内部处理消息保存等逻辑）
        """
        agent = self._agent

        logger.info(f"🌊 [流式对话开始] session_id={session_id}, user_id={user_id}")
        logger.debug(f"   用户查询: {_safe_truncate(user_query, 500)}")

        # 🔒 安全检查
        security_block = check_input_security(user_query, session_id)
        if security_block:
            yield security_block["reply"]
            return

        request_start = time.time()
        session_id = await agent._ensure_session(session_id, user_id, user_query[:30])

        # 🔍 意图路由：使用小模型做结构化路由决策
        # 获取对话历史摘要供路由决策
        history_summary = await agent._build_history_context(session_id)
        # 获取已加载 Skills 信息
        skills_info = agent.skill_registry.get_skills_metadata_list()
        # 路由决策
        route_decision = await route_query(
            query=user_query,
            context_summary=history_summary,
            loaded_skills=skills_info
        )
        logger.info(
            f"🔀 [路由决策] route={route_decision.route}"
            f"{'(' + str(route_decision.skill_name) + ')' if route_decision.skill_name else ''} "
            f"confidence={route_decision.confidence:.2f} "
            f"| {route_decision.reason}"
        )

        # ── 构建 Executor 上下文 ──
        exec_ctx = ExecutorContext(
            agent=agent,
            session_id=session_id,
            user_id=user_id,
            route_decision=route_decision,
            enable_metrics=enable_metrics,
            buffer_size=buffer_size,
            flush_interval=flush_interval,
        )

        # ── 复杂任务需要特殊的 SSE 格式 ──
        route_value = route_decision.route
        if isinstance(route_value, str):
            try:
                route_value = RouteType(route_value)
            except ValueError:
                route_value = RouteType.SIMPLE

        if route_value == RouteType.COMPLEX:
            # ComplexExecutor 输出 SSE JSON 事件，需要 session_id 前缀
            yield f"__SESSION_ID__:{session_id}\n"

        # ── 通过 Executor 工厂获取执行器并执行 ──
        executor = get_executor(route_decision)
        async for chunk in executor.execute(user_query, exec_ctx):
            yield chunk
