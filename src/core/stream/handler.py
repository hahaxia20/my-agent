from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, AsyncIterator, Optional

from src.core.executors import ExecutorContext, get_executor
from src.core.helpers.chat_helpers import check_input_security
from src.core.logging.decorator import log_method_call
from src.core.router import RouteType, route_query
from src.core.tool_adapter import safe_truncate as _safe_truncate
from src.core.workflows import workflow_registry

if TYPE_CHECKING:
    from src.core.agent import MyAgent

logger = logging.getLogger(__name__)


class StreamHandler:
    """Stream orchestration entrypoint for Router + Executor flows."""

    def __init__(self, agent: 'MyAgent'):
        self._agent = agent

    @staticmethod
    def format_stream_error(error: Exception) -> str:
        error_msg = str(error)
        if '403' in error_msg or 'PermissionDenied' in error_msg:
            if 'free tier' in error_msg.lower() or 'quota' in error_msg.lower():
                return '\nAPI quota exhausted. Please check the configured API key or account quota.'
            return '\nAPI access was denied. Please verify the configured API key and permissions.'
        if '401' in error_msg or 'Authentication' in error_msg:
            return '\nAPI authentication failed. Please verify the configured API key.'
        if '429' in error_msg or 'rate limit' in error_msg.lower():
            return '\nToo many requests. Please retry in a moment.'
        return f'\nRequest failed: {error_msg[:200]}'

    async def stream_complex_task(
        self,
        user_query: str,
        session_id: str,
        user_id: str,
    ) -> AsyncIterator[str]:
        agent = self._agent
        queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(event_type: str, data: dict):
            await queue.put(json.dumps({'type': event_type, 'data': data}, ensure_ascii=False))

        async def execute():
            try:
                result = await agent.complex_chat(
                    user_query=user_query,
                    session_id=session_id,
                    user_id=user_id,
                    progress_callback=progress_callback,
                )
                await queue.put(json.dumps({
                    'type': 'final_result',
                    'data': {
                        'success': result.get('success', False),
                        'reply': result.get('reply', ''),
                        'duration': result.get('elapsed_time', 0),
                        'sub_tasks': result.get('sub_tasks', []),
                        'metadata': result.get('metadata', {}),
                    },
                }, ensure_ascii=False))
            except Exception as exc:
                logger.error('[stream_complex_task] error: %s', exc, exc_info=True)
                await queue.put(json.dumps({'type': 'error', 'data': {'error': str(exc)}}, ensure_ascii=False))

        task = asyncio.create_task(execute())
        while not task.done() or not queue.empty():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.5)
                yield f'data: {event}\n\n'
            except asyncio.TimeoutError:
                continue
        await task

    @log_method_call(prefix='[Agent-stream] ', log_duration=True)
    async def stream(
        self,
        user_query: str,
        session_id: Optional[str] = None,
        user_id: str = 'anonymous',
        enable_metrics: bool = True,
        buffer_size: int = 5,
        flush_interval: float = 0.05,
    ) -> AsyncIterator[str]:
        agent = self._agent

        logger.info('[stream] start session_id=%s user_id=%s', session_id, user_id)
        logger.debug('[stream] query=%s', _safe_truncate(user_query, 500))

        security_block = check_input_security(user_query, session_id)
        if security_block:
            yield security_block['reply']
            return

        session_id = await agent._ensure_session(session_id, user_id, user_query[:30])
        history_summary = await agent._build_history_context(session_id)
        skills_info = agent.skill_registry.get_skills_metadata_list()
        workflows_info = workflow_registry.get_workflows_metadata_list()

        route_decision = await route_query(
            query=user_query,
            context_summary=history_summary,
            loaded_skills=skills_info,
            loaded_workflows=workflows_info,
        )
        target = route_decision.workflow_name or route_decision.skill_name
        logger.info(
            '[stream] route=%s%s confidence=%.2f | %s',
            route_decision.route,
            f'({target})' if target else '',
            route_decision.confidence,
            route_decision.reason,
        )

        exec_ctx = ExecutorContext(
            agent=agent,
            session_id=session_id,
            user_id=user_id,
            route_decision=route_decision,
            enable_metrics=enable_metrics,
            buffer_size=buffer_size,
            flush_interval=flush_interval,
        )

        route_value = route_decision.route
        if isinstance(route_value, str):
            try:
                route_value = RouteType(route_value)
            except ValueError:
                route_value = RouteType.SIMPLE

        if route_value == RouteType.COMPLEX:
            yield f'__SESSION_ID__:{session_id}\n'

        executor = get_executor(route_decision)
        async for chunk in executor.execute(user_query, exec_ctx):
            yield chunk