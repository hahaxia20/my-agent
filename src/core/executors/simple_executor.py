"""Simple executor for direct ReAct-style streaming queries."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator, Dict, Optional, TYPE_CHECKING

from src.core.executors.base import BaseExecutor, ExecutorContext
from src.core.stream.manager import (
    StreamBuffer,
    StreamChunk,
    StreamCypherFilter,
    StreamEventType,
    StreamFormatter,
    StreamMetrics,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SimpleExecutor(BaseExecutor):
    """Executor for simple one-agent queries."""

    async def execute(
        self,
        query: str,
        ctx: ExecutorContext,
    ) -> AsyncIterator[str]:
        """Execute a simple query and stream the response."""
        agent = ctx.agent
        session_id = ctx.session_id

        logger.info('[SimpleExecutor] simple query -> ReAct agent')

        metrics: Optional[StreamMetrics] = None

        try:
            metrics = StreamMetrics() if ctx.enable_metrics else None
            if metrics:
                metrics.start()

            buffer = StreamBuffer(max_size=ctx.buffer_size, flush_interval=ctx.flush_interval)
            config = ctx.build_runnable_config()

            full_response = ''
            total_tokens: Dict[str, int] = {'prompt': 0, 'completion': 0, 'total': 0}
            current_tool: Optional[str] = None
            tool_start_time: Optional[float] = None
            cypher_filter = StreamCypherFilter()

            async with agent._semaphore:
                request_start = time.time()
                logger.info('[SimpleExecutor] start streaming: %s', session_id)

                used_tools: list = []
                used_skills: list = []
                llm_start = time.time()
                llm_first_token_logged = False

                input_messages = await agent.conversation_context.load_context(
                    session_id=session_id,
                    current_message=query,
                )
                agent.log_prompt_messages('simple_executor', input_messages)
                stats = agent.conversation_context.get_context_stats(input_messages)
                logger.info('[SimpleExecutor] context stats: %s', stats)

                scoped_agent = agent.get_scoped_agent(ctx.route_decision)
                async for event in scoped_agent.astream_events(
                    {'messages': input_messages},
                    config=config,
                    version='v2',
                ):
                    event_type = event['event']

                    if event_type == 'on_chat_model_stream':
                        if not llm_first_token_logged:
                            llm_first_token_logged = True
                            logger.info('[SimpleExecutor] first token latency: %.2fs', time.time() - llm_start)

                        chunk = event['data']['chunk']
                        usage_metadata = getattr(chunk, 'usage_metadata', None)
                        if usage_metadata:
                            total_tokens['prompt'] = usage_metadata.get('input_tokens', 0)
                            total_tokens['completion'] = usage_metadata.get('output_tokens', 0)
                            total_tokens['total'] = usage_metadata.get('total_tokens', 0)

                        is_empty = not chunk.content or not chunk.content.strip()
                        if metrics:
                            metrics.record_chunk(chunk.content or '', is_empty)

                        if chunk.content and chunk.content.strip():
                            filtered = cypher_filter.process(chunk.content)
                            if not filtered or not filtered.strip():
                                continue
                            buffered = buffer.add(StreamChunk(type=StreamEventType.TEXT, content=filtered))
                            if buffered:
                                full_response += buffered
                                yield buffered

                    elif event_type == 'on_tool_start':
                        tool_name = event.get('name', 'unknown')
                        tool_start_time = time.time()
                        current_tool = tool_name

                        if tool_name == 'load_skill':
                            tool_input = event.get('data', {}).get('input', {})
                            skill_name = tool_input.get('skill_name', '') if isinstance(tool_input, dict) else ''
                            if skill_name and skill_name not in used_skills:
                                used_skills.append(skill_name)
                                logger.info('[SimpleExecutor] using skill: %s', skill_name)
                        elif tool_name not in used_tools:
                            used_tools.append(tool_name)
                            logger.info('[SimpleExecutor] using tool: %s', tool_name)

                        if metrics:
                            metrics.record_tool_call(tool_name)

                        logger.info('[SimpleExecutor] tool start: %s', tool_name)

                        buffered = buffer.flush()
                        if buffered:
                            full_response += buffered
                            yield buffered
                        yield f'\nUsing tool: **{tool_name}**...\n'

                    elif event_type == 'on_tool_end':
                        elapsed = time.time() - (tool_start_time or time.time())
                        if current_tool:
                            logger.info('[SimpleExecutor] tool complete: %s - %.2fs', current_tool, elapsed)
                            agent._record_tool_call(current_tool, elapsed, success=True)
                            yield f'\nTool **{current_tool}** completed ({elapsed:.1f}s)\n'
                            current_tool = None
                            tool_start_time = None

                    elif event_type == 'on_tool_error':
                        error = event.get('data', {}).get('error', 'unknown error')
                        tool_name = event.get('name', 'unknown')
                        elapsed = time.time() - (tool_start_time or time.time())
                        logger.error('[SimpleExecutor] tool failed: %s - %.2fs - %s', tool_name, elapsed, error)
                        agent._record_tool_call(tool_name, elapsed, success=False)
                        yield f'\nTool **{tool_name}** failed\n'
                        current_tool = None

                cypher_remaining = cypher_filter.flush()
                if cypher_remaining and cypher_remaining.strip():
                    buffered = buffer.add(StreamChunk(type=StreamEventType.TEXT, content=cypher_remaining))
                    if buffered:
                        full_response += buffered
                        yield buffered

                remaining = buffer.flush()
                if remaining:
                    full_response += remaining
                    yield remaining

                total_elapsed = time.time() - request_start
                logger.info(
                    '[SimpleExecutor] complete - %s - duration: %.2fs - reply length: %s chars',
                    session_id,
                    total_elapsed,
                    len(full_response),
                )

                if used_tools or used_skills:
                    logger.info('[SimpleExecutor] tools: %s, skills: %s', used_tools or 'none', used_skills or 'none')

                if metrics and agent.config.debug:
                    metrics.finish()
                    stats_data = metrics.get_stats()
                    logger.info('[SimpleExecutor] metrics: %s', stats_data)
                    if stats_data.get('tools_called'):
                        yield f"\n\nTools called: {', '.join(stats_data['tools_called'])}"
                    if stats_data.get('skills_called'):
                        yield f"\nSkills called: {', '.join(stats_data['skills_called'])}"

                if not full_response:
                    error_msg = 'No valid response was produced. Please try again later.'
                    full_response = error_msg
                    yield error_msg

            await agent.db.add_message(session_id, 'user', query)
            await agent.db.add_message(session_id, 'assistant', full_response)

            tools_called = metrics.get_tool_names() if metrics else []
            skills_called = metrics.get_skill_names() if metrics else []
            metadata = StreamFormatter.format_metadata(
                session_id=session_id,
                chunk_count=metrics.chunk_count if metrics else 0,
                duration=metrics.duration if metrics else 0,
                tools_called=tools_called,
                skills_called=skills_called,
            )
            yield f'\n<!-- {metadata} -->'

        except asyncio.CancelledError:
            logger.info('[SimpleExecutor] session cancelled: %s', session_id)
            yield '\n<!-- cancelled -->'

        except asyncio.TimeoutError:
            logger.error('[SimpleExecutor] timeout: %s', session_id)
            yield '\nThe request timed out. Please try again later.'

        except Exception as exc:
            logger.error('[SimpleExecutor] error: %s', exc, exc_info=True)
            if metrics:
                metrics.record_error()
            from src.core.stream.handler import StreamHandler

            yield StreamHandler.format_stream_error(exc)
