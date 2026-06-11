"""
GraphExecutor - 产业链图谱直达执行器

针对产业链图谱单次查询的快捷路径，
直接调用 SmartGraphQueryTool，跳过完整 ReAct 循环，
大幅减少不必要的 LLM 调用。

Neo4j 不可用时，自动回退到 SimpleExecutor。
"""

from __future__ import annotations

import logging
import time
from typing import AsyncIterator, TYPE_CHECKING

from src.core.executors.base import BaseExecutor, ExecutorContext

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class GraphExecutor(BaseExecutor):
    """
    产业链图谱直达执行器

    直接从 tool_manager 获取 SmartGraphQueryTool，
    以用户原始查询作为 question 参数调用，
    将结果以流式 chunk 形式输出。
    """

    async def execute(
        self,
        query: str,
        ctx: ExecutorContext,
    ) -> AsyncIterator[str]:
        """
        执行图谱查询并流式返回响应

        Args:
            query: 用户查询（自然语言问题）
            ctx: 执行上下文

        Yields:
            str: 流式响应 chunk
        """
        agent = ctx.agent
        session_id = ctx.session_id

        logger.info("📊 [GraphExecutor] 图谱直达查询")

        # ── 获取 SmartGraphQueryTool 实例 ──
        graph_tool = None
        try:
            from src.tools.industry_graph import SmartGraphQueryTool
            # 尝试从已注册工具中查找
            for tool in agent.tool_manager.get_all():
                if isinstance(tool, SmartGraphQueryTool):
                    graph_tool = tool
                    break

            # 如果未找到，尝试新建
            if not graph_tool:
                graph_tool = SmartGraphQueryTool()
                if not graph_tool.neo4j:
                    logger.warning("⚠️ [GraphExecutor] Neo4j 未连接，回退到 simple")
                    yield "⚠️ 产业链图谱功能不可用（Neo4j 未连接），切换到常规模式。\n\n"
                    from src.core.executors.simple_executor import SimpleExecutor
                    fallback = SimpleExecutor()
                    async for chunk in fallback.execute(query, ctx):
                        yield chunk
                    return

        except ImportError as e:
            logger.warning(f"⚠️ [GraphExecutor] SmartGraphQueryTool 导入失败: {e}，回退到 simple")
            yield "⚠️ 产业链图谱工具未加载，切换到常规模式。\n\n"
            from src.core.executors.simple_executor import SimpleExecutor
            fallback = SimpleExecutor()
            async for chunk in fallback.execute(query, ctx):
                yield chunk
            return

        # ── 执行图谱查询 ──
        logger.info(f"📊 [GraphExecutor] 查询: {query[:80]}")
        yield "📊 正在查询产业链图谱...\n\n"

        request_start = time.time()

        try:
            # SmartGraphQueryTool.execute() 是异步方法
            result = await graph_tool.execute(question=query)

            elapsed = time.time() - request_start

            if result.get("success"):
                answer = result.get("answer", "")
                logger.info(
                    f"✅ [GraphExecutor] 查询完成 - "
                    f"耗时: {elapsed:.2f}s - 答案长度: {len(answer)} 字符"
                )

                # 逐段输出答案（模拟流式）
                # 对于图谱查询结果，通常是一次性返回，分段输出体验更好
                chunk_size = 100
                for i in range(0, len(answer), chunk_size):
                    yield answer[i:i + chunk_size]

                # 保存到数据库
                await agent.db.add_message(session_id, "user", query)
                await agent.db.add_message(
                    session_id, "assistant", answer,
                    metadata={"route": "graph_only", "tool": "smart_graph_query"}
                )

                # 输出元数据注释
                yield f"\n<!-- route=graph_only, duration={elapsed:.2f}s -->"

            else:
                error_msg = result.get("error", "未知错误")
                logger.warning(
                    f"⚠️ [GraphExecutor] 查询失败: {error_msg} - "
                    f"耗时: {elapsed:.2f}s，回退到 simple"
                )
                yield f"⚠️ 图谱查询失败：{error_msg}，切换到常规模式。\n\n"
                from src.core.executors.simple_executor import SimpleExecutor
                fallback = SimpleExecutor()
                async for chunk in fallback.execute(query, ctx):
                    yield chunk

        except Exception as e:
            elapsed = time.time() - request_start
            logger.error(
                f"❌ [GraphExecutor] 异常: {e} - 耗时: {elapsed:.2f}s，回退到 simple",
                exc_info=True
            )
            yield f"⚠️ 图谱查询异常：{str(e)[:150]}，切换到常规模式。\n\n"
            from src.core.executors.simple_executor import SimpleExecutor
            fallback = SimpleExecutor()
            async for chunk in fallback.execute(query, ctx):
                yield chunk
