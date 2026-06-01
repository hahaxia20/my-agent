"""
流式对话处理器

从 agent.py 中独立抽取的流式逻辑，包括：
- 简单查询的 ReAct 流式输出
- 复杂任务的 SSE 事件流式推送
- 流式错误格式化

设计原则：
  StreamHandler 持有 MyAgent 实例，复用其核心组件（agent、db、config 等），
  agent.py 保持精简，只负责调度。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING, AsyncIterator, Dict, Any, Optional

from src.core.helpers.intent_classifier import classify_intent
from src.core.helpers.chat_helpers import check_input_security

from langchain_core.runnables import RunnableConfig

from src.core.logging.decorator import log_method_call
from src.core.stream.manager import (
    StreamBuffer, StreamFormatter, StreamMetrics,
    StreamChunk, StreamEventType, StreamCypherFilter
)
from src.core.tool_adapter import safe_truncate as _safe_truncate

if TYPE_CHECKING:
    from src.core.agent import MyAgent

logger = logging.getLogger(__name__)


class StreamHandler:
    """流式对话处理器

    职责：
    - 处理简单查询的流式输出（ReAct Agent astream_events）
    - 处理复杂任务的 SSE 事件流（Sub-Agent 进度推送）
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
    # 简单查询流式输出（ReAct Agent）
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
        """生产级流式对话

        流程：
        1. 安全检查
        2. 意图分类：complex → stream_complex_task；simple → ReAct astream_events
        3. 逐 chunk 输出，过滤 Cypher，记录工具调用
        4. 保存消息到数据库
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

        # 🔍 意图分类：自动路由到简单/复杂路径
        intent = classify_intent(user_query)
        if intent == "complex":
            logger.info("🚀 [路由] 复杂任务 → Sub-Agent 编排器")
            yield f"__SESSION_ID__:{session_id}\n"
            yield json.dumps({"type": "routing", "data": {"mode": "complex"}}) + "\n"
            async for chunk in self.stream_complex_task(user_query, session_id, user_id):
                yield chunk
            return

        # ── 简单查询 → ReAct Agent 直接处理 ──────────────
        logger.info("💬 [路由] 简单查询 → ReAct Agent")
        metrics: Optional[StreamMetrics] = None

        try:
            metrics = StreamMetrics() if enable_metrics else None
            if metrics:
                metrics.start()

            buffer = StreamBuffer(max_size=buffer_size, flush_interval=flush_interval)

            config = RunnableConfig(
                configurable={"thread_id": session_id},
                metadata={"user_id": user_id},
                tags=["production", "stream"],
                recursion_limit=agent.config.recursion_limit
            )

            full_response = ""
            total_tokens: Dict[str, int] = {"prompt": 0, "completion": 0, "total": 0}
            current_tool: Optional[str] = None
            tool_start_time: Optional[float] = None
            cypher_filter = StreamCypherFilter()

            async with agent._semaphore:
                request_start = time.time()
                logger.info(f"🚀 开始流式处理: {session_id}")

                used_tools: list = []
                used_skills: list = []
                llm_start = time.time()
                llm_first_token_logged = False
                logger.info("️ [性能] 开始调用 LLM...")

                input_messages = await agent.conversation_context.load_context(
                    session_id=session_id,
                    current_message=user_query
                )
                stats = agent.conversation_context.get_context_stats(input_messages)
                logger.info(f"📊 流式对话上下文统计: {stats}")

                async for event in agent.agent.astream_events(
                    {"messages": input_messages},
                    config=config,
                    version="v2"
                ):
                    event_type = event["event"]

                    # ── LLM 流式输出 ──
                    if event_type == "on_chat_model_stream":
                        if not llm_first_token_logged:
                            llm_first_token_logged = True
                            logger.info(f"⏱️ [性能] LLM 首字耗时: {time.time() - llm_start:.2f}s")

                        chunk = event["data"]["chunk"]
                        usage_metadata = getattr(chunk, 'usage_metadata', None)
                        if usage_metadata:
                            total_tokens["prompt"] = usage_metadata.get("input_tokens", 0)
                            total_tokens["completion"] = usage_metadata.get("output_tokens", 0)
                            total_tokens["total"] = usage_metadata.get("total_tokens", 0)

                        is_empty = not chunk.content or not chunk.content.strip()
                        if metrics:
                            metrics.record_chunk(chunk.content or "", is_empty)

                        if chunk.content and chunk.content.strip():
                            filtered = cypher_filter.process(chunk.content)
                            if not filtered or not filtered.strip():
                                continue
                            buffered = buffer.add(
                                StreamChunk(type=StreamEventType.TEXT, content=filtered)
                            )
                            if buffered:
                                full_response += buffered
                                yield buffered

                    # ── 工具调用开始 ──
                    elif event_type == "on_tool_start":
                        tool_name = event.get('name', 'unknown')
                        tool_start_time = time.time()
                        current_tool = tool_name

                        if tool_name == "load_skill":
                            tool_input = event.get('data', {}).get('input', {})
                            skill_name = (
                                tool_input.get('skill_name', '')
                                if isinstance(tool_input, dict) else ''
                            )
                            if skill_name and skill_name not in used_skills:
                                used_skills.append(skill_name)
                                logger.info(f"🎯 [使用技能] {skill_name}")
                        elif tool_name not in used_tools:
                            used_tools.append(tool_name)
                            logger.info(f"🔧 [使用工具] {tool_name}")

                        if metrics:
                            metrics.record_tool_call(tool_name)

                        logger.info(f"🔧 [工具调用开始] {tool_name}")
                        logger.debug(f"   工具参数: {event.get('data', {}).get('input', {})}")

                        buffered = buffer.flush()
                        if buffered:
                            full_response += buffered
                            yield buffered
                        yield f"\n🔧 正在调用工具: **{tool_name}**...\n"

                    # ── 工具调用结束 ──
                    elif event_type == "on_tool_end":
                        elapsed = time.time() - (tool_start_time or time.time())
                        if current_tool:
                            logger.info(f"✅ [工具调用完成] {current_tool} - 耗时: {elapsed:.2f}s")
                            logger.debug(
                                f"   工具返回: "
                                f"{_safe_truncate(str(event.get('data', {}).get('output', '')), 300)}"
                            )
                            agent._record_tool_call(current_tool, elapsed, success=True)
                            yield f"\n✅ 工具 **{current_tool}** 调用完成 ({elapsed:.1f}s)\n"
                            current_tool = None
                            tool_start_time = None

                    # ── 工具错误 ──
                    elif event_type == "on_tool_error":
                        error = event.get('data', {}).get('error', '未知错误')
                        tool_name = event.get('name', 'unknown')
                        elapsed = time.time() - (tool_start_time or time.time())
                        logger.error(
                            f"❌ [工具调用失败] {tool_name} - "
                            f"耗时: {elapsed:.2f}s - 错误: {str(error)}"
                        )
                        agent._record_tool_call(tool_name, elapsed, success=False)
                        yield f"\n❌ 工具 **{tool_name}** 调用失败\n"
                        current_tool = None

                # 刷新 Cypher 过滤器剩余内容
                cypher_remaining = cypher_filter.flush()
                if cypher_remaining and cypher_remaining.strip():
                    buffered = buffer.add(
                        StreamChunk(type=StreamEventType.TEXT, content=cypher_remaining)
                    )
                    if buffered:
                        full_response += buffered
                        yield buffered

                # 刷新剩余缓冲区
                remaining = buffer.flush()
                if remaining:
                    full_response += remaining
                    yield remaining

                total_elapsed = time.time() - request_start
                logger.info(
                    f"✅ [流式对话完成] session={session_id} - "
                    f"总耗时: {total_elapsed:.2f}s - 回复长度: {len(full_response)} 字符"
                )

                if used_tools or used_skills:
                    logger.info(
                        f"📊 [本次调用] 工具: {used_tools or '无'}, 技能: {used_skills or '无'}"
                    )

                if metrics and agent.config.debug:
                    metrics.finish()
                    stats_data = metrics.get_stats()
                    logger.info(f"📊 [流式统计] 会话:{session_id} - {stats_data}")
                    if stats_data.get('tools_called'):
                        yield f"\n\n📊 调用的工具: {', '.join(stats_data['tools_called'])}"
                    if stats_data.get('skills_called'):
                        yield f"\n🎯 调用的技能: {', '.join(stats_data['skills_called'])}"

                if not full_response:
                    error_msg = "抱歉，我没有收到有效响应。请稍后重试。"
                    full_response = error_msg
                    yield error_msg

            # 保存到数据库
            await agent.db.add_message(session_id, "user", user_query)
            await agent.db.add_message(session_id, "assistant", full_response)

            tools_called = metrics.get_tool_names() if metrics else []
            skills_called = metrics.get_skill_names() if metrics else []
            metadata = StreamFormatter.format_metadata(
                session_id=session_id,
                chunk_count=metrics.chunk_count if metrics else 0,
                duration=metrics.duration if metrics else 0,
                tools_called=tools_called,
                skills_called=skills_called
            )
            yield f"\n<!-- {metadata} -->"

        except asyncio.CancelledError:
            logger.info(f"🛑 [流式取消] 会话被取消: {session_id}")
            yield "\n<!-- cancelled -->"

        except asyncio.TimeoutError:
            logger.error(f"⏰ [流式超时] {session_id}")
            yield "\n抱歉，响应超时，请稍后重试。"

        except Exception as e:
            logger.error(f"💥 [流式错误] {e}", exc_info=True)
            if metrics:
                metrics.record_error()
            yield self.format_stream_error(e)
