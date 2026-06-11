"""
ComplexExecutor - 复杂任务执行器

封装 Sub-Agent 编排系统的流式执行逻辑，
复用 agent.complex_chat() + progress_callback 机制。
从 StreamHandler.stream_complex_task() 提取。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, TYPE_CHECKING

from src.core.executors.base import BaseExecutor, ExecutorContext

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ComplexExecutor(BaseExecutor):
    """
    复杂任务执行器

    通过 SubAgentOrchestrator 进行任务分解、并行执行和结果合成，
    通过 asyncio.Queue 将进度事件转换为 SSE 流。
    """

    async def execute(
        self,
        query: str,
        ctx: ExecutorContext,
    ) -> AsyncIterator[str]:
        """
        执行复杂任务并流式返回进度/结果

        Args:
            query: 用户查询（复杂任务描述）
            ctx: 执行上下文

        Yields:
            str: SSE JSON 事件（进度 + final_result）
        """
        agent = ctx.agent
        session_id = ctx.session_id
        user_id = ctx.user_id

        logger.info(f"🎭 [ComplexExecutor] 复杂任务 → Sub-Agent 编排器")

        queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(event_type: str, data: dict):
            """进度回调：将事件推入队列"""
            await queue.put(json.dumps(
                {"type": event_type, "data": data}, ensure_ascii=False
            ))

        async def execute_task():
            """后台任务：调用 complex_chat 并将结果推入队列"""
            try:
                result = await agent.complex_chat(
                    user_query=query,
                    session_id=session_id,
                    user_id=user_id,
                    progress_callback=progress_callback
                )

                logger.info(
                    f"📦 [ComplexExecutor] complex_chat 返回: "
                    f"success={result.get('success')}, "
                    f"reply长度={len(result.get('reply', ''))}"
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

                logger.info("✅ [ComplexExecutor] final_result 已推入队列")

            except Exception as e:
                logger.error(f"❌ [ComplexExecutor] 执行失败: {e}", exc_info=True)
                await queue.put(json.dumps({
                    "type": "error",
                    "data": {"error": str(e)}
                }, ensure_ascii=False))

        # 启动后台任务
        task = asyncio.create_task(execute_task())

        # 从队列中读取事件并 yield
        while not task.done() or not queue.empty():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.5)
                yield f"data: {event}\n\n"
            except asyncio.TimeoutError:
                continue

        await task
