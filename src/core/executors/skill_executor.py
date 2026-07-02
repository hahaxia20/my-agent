"""
SkillExecutor - Skill 直达执行器

路由直达指定 Skill，将 Skill 指令注入 ReAct Agent，
保留完整工具调用能力（web_scraper、web_search 等），
通过 astream_events 流式输出并过滤 Cypher、监控工具调用。
"""

from __future__ import annotations

import logging
import time
from typing import AsyncIterator, Dict, Optional, TYPE_CHECKING

from src.core.executors.base import BaseExecutor, ExecutorContext
from src.core.router.route_types import RouteDecision
from src.core.stream.manager import (
    StreamBuffer, StreamChunk, StreamEventType,
    StreamCypherFilter, StreamFormatter, StreamMetrics
)
from src.core.tool_adapter import safe_truncate as _safe_truncate

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SkillExecutor(BaseExecutor):
    """
    Skill 直达执行器

    将 Skill 指令作为 SystemMessage 注入 ReAct Agent，
    Agent 拥有完整工具集，可真正执行 web_scraper / web_search 等工具，
    通过 astream_events 流式输出结果。
    """

    async def execute(
        self,
        query: str,
        ctx: ExecutorContext,
    ) -> AsyncIterator[str]:
        """
        执行指定 Skill 并流式返回响应

        Args:
            query: 用户查询
            ctx: 执行上下文（route_decision.skill_name 指定目标 Skill）

        Yields:
            str: 流式响应 chunk
        """
        agent = ctx.agent
        session_id = ctx.session_id
        decision = ctx.route_decision

        if not decision or not decision.skill_name:
            logger.error("❌ [SkillExecutor] 缺少 skill_name，回退到 simple")
            yield "⚠️ 路由决策缺少 skill_name，无法执行 Skill。\n"
            from src.core.executors.simple_executor import SimpleExecutor
            fallback = SimpleExecutor()
            async for chunk in fallback.execute(query, ctx):
                yield chunk
            return

        skill_name = decision.skill_name
        skill = agent.skill_registry.get_skill(skill_name)

        # ── 检查 Skill 是否存在 ──
        if not skill:
            available = ", ".join(s.name for s in agent.skill_registry.get_all())
            logger.warning(f"⚠️ [SkillExecutor] Skill 不存在: {skill_name}，可用: {available}")
            yield f"⚠️ 技能 `{skill_name}` 不存在。可用技能: {available}\n"
            from src.core.executors.simple_executor import SimpleExecutor
            fallback = SimpleExecutor()
            async for chunk in fallback.execute(query, ctx):
                yield chunk
            return

        # ── 检查 Skill 是否启用 ──
        if not getattr(skill, 'enabled', True):
            logger.warning(f"⚠️ [SkillExecutor] Skill 已禁用: {skill_name}")
            yield f"⚠️ 技能 `{skill_name}` 当前已禁用，请联系管理员启用。\n"
            from src.core.executors.simple_executor import SimpleExecutor
            fallback = SimpleExecutor()
            async for chunk in fallback.execute(query, ctx):
                yield chunk
            return

        # ── 执行 Skill（通过 ReAct Agent，保留工具调用能力）──
        logger.info(f"🎯 [SkillExecutor] 直达执行 Skill: {skill_name}")
        yield f"🎯 正在使用技能 **{skill_name}** 处理...\n\n"

        request_start = time.time()
        full_response = ""

        try:
            # 构建 Skill 指令
            if hasattr(skill, '_build_system_prompt'):
                skill_prompt = skill._build_system_prompt()
            elif hasattr(skill, 'config') and hasattr(skill.config, 'instructions'):
                skill_prompt = f"# Skill: {skill.name}\n{skill.description}\n\n{skill.config.instructions}"
            else:
                skill_prompt = f"# Skill: {skill.name}\n{skill.description}"

            # 构建带对话历史的消息列表，注入 Skill 指令作为额外 SystemMessage
            from langchain_core.messages import SystemMessage

            input_messages = await agent.conversation_context.load_context(
                session_id=session_id,
                current_message=query
            )

            # 在消息列表开头插入 Skill 指令（作为附加 SystemMessage）
            skill_message = SystemMessage(
                content=f"[当前激活技能: {skill_name}]\n\n{skill_prompt}"
            )
            # 将 Skill 指令插入到第一条消息之前（但在原始 system prompt 之后）
            messages_with_skill = [input_messages[0], skill_message] + list(input_messages[1:])
            agent.log_prompt_messages(f"skill_executor:{skill_name}", messages_with_skill)

            config = ctx.build_runnable_config()

            metrics = StreamMetrics() if ctx.enable_metrics else None
            if metrics:
                metrics.start()

            buffer = StreamBuffer(
                max_size=ctx.buffer_size,
                flush_interval=ctx.flush_interval
            )
            cypher_filter = StreamCypherFilter()
            current_tool: Optional[str] = None
            tool_start_time: Optional[float] = None
            used_tools: list = []
            used_skills: list = [skill_name]

            logger.info(f"🎯 [SkillExecutor] 开始 ReAct Agent 流式调用: {skill_name}")

            async with agent._semaphore:
                scoped_agent = agent.get_scoped_agent(ctx.route_decision)
                async for event in scoped_agent.astream_events(
                    {"messages": messages_with_skill},
                    config=config,
                    version="v2"
                ):
                    event_type = event["event"]

                    # ── LLM 流式输出 ──
                    if event_type == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
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

                        if tool_name not in used_tools:
                            used_tools.append(tool_name)
                            logger.info(f"🔧 [SkillExecutor] 使用工具: {tool_name}")

                        if metrics:
                            metrics.record_tool_call(tool_name)

                        buffered = buffer.flush()
                        if buffered:
                            full_response += buffered
                            yield buffered
                        yield f"\n🔧 正在调用工具: **{tool_name}**...\n"

                    # ── 工具调用结束 ──
                    elif event_type == "on_tool_end":
                        elapsed = time.time() - (tool_start_time or time.time())
                        if current_tool:
                            logger.info(f"✅ [SkillExecutor] 工具完成: {current_tool} - {elapsed:.2f}s")
                            agent._record_tool_call(current_tool, elapsed, success=True)
                            yield f"\n✅ 工具 **{current_tool}** 调用完成 ({elapsed:.1f}s)\n"
                            current_tool = None
                            tool_start_time = None

                    # ── 工具错误 ──
                    elif event_type == "on_tool_error":
                        error = event.get('data', {}).get('error', '未知错误')
                        tool_name = event.get('name', 'unknown')
                        elapsed = time.time() - (tool_start_time or time.time())
                        logger.error(f"❌ [SkillExecutor] 工具失败: {tool_name} - {elapsed:.2f}s - {error}")
                        agent._record_tool_call(tool_name, elapsed, success=False)
                        yield f"\n❌ 工具 **{tool_name}** 调用失败\n"
                        current_tool = None

                # 刷新 Cypher 过滤器和缓冲区
                cypher_remaining = cypher_filter.flush()
                if cypher_remaining and cypher_remaining.strip():
                    buffered = buffer.add(
                        StreamChunk(type=StreamEventType.TEXT, content=cypher_remaining)
                    )
                    if buffered:
                        full_response += buffered
                        yield buffered

                remaining = buffer.flush()
                if remaining:
                    full_response += remaining
                    yield remaining

            total_elapsed = time.time() - request_start
            logger.info(
                f"✅ [SkillExecutor] Skill 完成: {skill_name} - "
                f"耗时: {total_elapsed:.2f}s - 长度: {len(full_response)} 字符 - "
                f"工具: {used_tools or '无'}"
            )

            if metrics and agent.config.debug:
                metrics.finish()
                stats_data = metrics.get_stats()
                if stats_data.get('tools_called'):
                    yield f"\n\n📊 调用的工具: {', '.join(stats_data['tools_called'])}"

            if not full_response:
                error_msg = "抱歉，Skill 执行未返回有效响应。请稍后重试。"
                full_response = error_msg
                yield error_msg

            # 保存到数据库
            await agent.db.add_message(session_id, "user", query)
            await agent.db.add_message(
                session_id, "assistant", full_response,
                metadata={"skill_used": skill_name, "route": "skill_direct", "tools": used_tools}
            )

            # 输出元数据注释
            tools_called = metrics.get_tool_names() if metrics else []
            metadata = StreamFormatter.format_metadata(
                session_id=session_id,
                chunk_count=metrics.chunk_count if metrics else 0,
                duration=metrics.duration if metrics else 0,
                tools_called=tools_called,
                skills_called=used_skills
            )
            yield f"\n<!-- {metadata} -->"

        except Exception as e:
            elapsed = time.time() - request_start
            logger.error(
                f"❌ [SkillExecutor] Skill 执行失败: {skill_name} - "
                f"耗时: {elapsed:.2f}s - 错误: {e}",
                exc_info=True
            )
            yield f"\n\n❌ 技能 `{skill_name}` 执行失败：{str(e)[:200]}"

            if full_response:
                await agent.db.add_message(session_id, "user", query)
                await agent.db.add_message(
                    session_id, "assistant",
                    full_response + f"\n\n❌ 执行中断: {str(e)[:100]}",
                    metadata={"skill_used": skill_name, "error": str(e)}
                )
