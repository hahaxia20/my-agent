"""
SimpleExecutor - 简单查询执行器

封装 ReAct Agent 流式逻辑，处理简单问答、闲聊、定义解释等查询。
从 StreamHandler.stream() 第 183-385 行提取，保持行为一致。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator, Dict, Optional, TYPE_CHECKING

from langchain_core.runnables import RunnableConfig

from src.core.executors.base import BaseExecutor, ExecutorContext
from src.core.stream.manager import (
    StreamBuffer, StreamMetrics, StreamChunk,
    StreamEventType, StreamCypherFilter, StreamFormatter
)
from src.core.tool_adapter import safe_truncate as _safe_truncate

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SimpleExecutor(BaseExecutor):
    """
    简单查询执行器

    直接调用 ReAct Agent 的 astream_events，
    保持 Cypher 过滤、工具调用监控、消息持久化等现有功能。
    """

    async def execute(
        self,
        query: str,
        ctx: ExecutorContext,
    ) -> AsyncIterator[str]:
        """
        执行简单查询并流式返回响应

        Args:
            query: 用户查询
            ctx: 执行上下文

        Yields:
            str: 流式响应 chunk
        """
        agent = ctx.agent
        session_id = ctx.session_id

        logger.info("💬 [SimpleExecutor] 简单查询 → ReAct Agent")

        metrics: Optional[StreamMetrics] = None

        try:
            metrics = StreamMetrics() if ctx.enable_metrics else None
            if metrics:
                metrics.start()

            buffer = StreamBuffer(
                max_size=ctx.buffer_size,
                flush_interval=ctx.flush_interval
            )

            config = ctx.build_runnable_config()

            full_response = ""
            total_tokens: Dict[str, int] = {"prompt": 0, "completion": 0, "total": 0}
            current_tool: Optional[str] = None
            tool_start_time: Optional[float] = None
            cypher_filter = StreamCypherFilter()

            async with agent._semaphore:
                request_start = time.time()
                logger.info(f"🚀 [SimpleExecutor] 开始流式处理: {session_id}")

                used_tools: list = []
                used_skills: list = []
                llm_start = time.time()
                llm_first_token_logged = False

                input_messages = await agent.conversation_context.load_context(
                    session_id=session_id,
                    current_message=query
                )
                stats = agent.conversation_context.get_context_stats(input_messages)
                logger.info(f"📊 [SimpleExecutor] 上下文统计: {stats}")

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
                            logger.info(f"⏱️ [SimpleExecutor] LLM 首字耗时: {time.time() - llm_start:.2f}s")

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
                                logger.info(f"🎯 [SimpleExecutor] 使用技能: {skill_name}")
                        elif tool_name not in used_tools:
                            used_tools.append(tool_name)
                            logger.info(f"🔧 [SimpleExecutor] 使用工具: {tool_name}")

                        if metrics:
                            metrics.record_tool_call(tool_name)

                        logger.info(f"🔧 [SimpleExecutor] 工具调用开始: {tool_name}")

                        buffered = buffer.flush()
                        if buffered:
                            full_response += buffered
                            yield buffered
                        yield f"\n🔧 正在调用工具: **{tool_name}**...\n"

                    # ── 工具调用结束 ──
                    elif event_type == "on_tool_end":
                        elapsed = time.time() - (tool_start_time or time.time())
                        if current_tool:
                            logger.info(f"✅ [SimpleExecutor] 工具完成: {current_tool} - {elapsed:.2f}s")
                            agent._record_tool_call(current_tool, elapsed, success=True)
                            yield f"\n✅ 工具 **{current_tool}** 调用完成 ({elapsed:.1f}s)\n"
                            current_tool = None
                            tool_start_time = None

                    # ── 工具错误 ──
                    elif event_type == "on_tool_error":
                        error = event.get('data', {}).get('error', '未知错误')
                        tool_name = event.get('name', 'unknown')
                        elapsed = time.time() - (tool_start_time or time.time())
                        logger.error(f"❌ [SimpleExecutor] 工具失败: {tool_name} - {elapsed:.2f}s - {error}")
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
                    f"✅ [SimpleExecutor] 完成 - {session_id} - "
                    f"耗时: {total_elapsed:.2f}s - 回复长度: {len(full_response)} 字符"
                )

                if used_tools or used_skills:
                    logger.info(
                        f"📊 [SimpleExecutor] 工具: {used_tools or '无'}, 技能: {used_skills or '无'}"
                    )

                if metrics and agent.config.debug:
                    metrics.finish()
                    stats_data = metrics.get_stats()
                    logger.info(f"📊 [SimpleExecutor] 统计: {stats_data}")
                    if stats_data.get('tools_called'):
                        yield f"\n\n📊 调用的工具: {', '.join(stats_data['tools_called'])}"
                    if stats_data.get('skills_called'):
                        yield f"\n🎯 调用的技能: {', '.join(stats_data['skills_called'])}"

                if not full_response:
                    error_msg = "抱歉，我没有收到有效响应。请稍后重试。"
                    full_response = error_msg
                    yield error_msg

            # 保存到数据库
            await agent.db.add_message(session_id, "user", query)
            await agent.db.add_message(session_id, "assistant", full_response)

            # 输出元数据
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
            logger.info(f"🛑 [SimpleExecutor] 会话被取消: {session_id}")
            yield "\n<!-- cancelled -->"

        except asyncio.TimeoutError:
            logger.error(f"⏰ [SimpleExecutor] 超时: {session_id}")
            yield "\n抱歉，响应超时，请稍后重试。"

        except Exception as e:
            logger.error(f"💥 [SimpleExecutor] 错误: {e}", exc_info=True)
            if metrics:
                metrics.record_error()
            from src.core.stream.handler import StreamHandler
            yield StreamHandler.format_stream_error(e)
