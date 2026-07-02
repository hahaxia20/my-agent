from __future__ import annotations

import logging
import re
import time
from typing import AsyncIterator, Dict, List, TYPE_CHECKING

from langchain_core.messages import SystemMessage

from src.core.executors.base import BaseExecutor, ExecutorContext
from src.core.router.route_types import RouteDecision, RouteType
from src.core.stream.manager import StreamFormatter
from src.core.workflows import workflow_registry

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class WorkflowExecutor(BaseExecutor):
    """Executor for fixed multi-step workflows."""

    async def execute(self, query: str, ctx: ExecutorContext) -> AsyncIterator[str]:
        agent = ctx.agent
        session_id = ctx.session_id
        decision = ctx.route_decision

        workflow_name = getattr(decision, 'workflow_name', None)
        if not workflow_name:
            logger.warning('[WorkflowExecutor] missing workflow_name, fallback to simple')
            from src.core.executors.simple_executor import SimpleExecutor

            fallback = SimpleExecutor()
            async for chunk in fallback.execute(query, ctx):
                yield chunk
            return

        workflow = workflow_registry.get_workflow(workflow_name)
        if not workflow:
            logger.warning('[WorkflowExecutor] workflow not found: %s', workflow_name)
            from src.core.executors.simple_executor import SimpleExecutor

            fallback = SimpleExecutor()
            async for chunk in fallback.execute(query, ctx):
                yield chunk
            return

        logger.info('[WorkflowExecutor] workflow route -> %s', workflow.name)
        yield f"Executing workflow **{workflow.name}**...\n\n"

        request_start = time.time()
        step_outputs: List[Dict[str, str]] = []
        combined_sections: List[str] = []
        config = ctx.build_runnable_config()

        try:
            for index, step in enumerate(workflow.steps, start=1):
                skill = agent.skill_registry.get_skill(step.skill_name)
                if not skill:
                    raise ValueError(f'workflow step skill missing: {step.skill_name}')
                if not getattr(skill, 'enabled', True):
                    raise ValueError(f'workflow step skill disabled: {step.skill_name}')

                yield f"## Step {index}/{len(workflow.steps)}: {step.name}\n"
                yield f"Using skill **{step.skill_name}**\n\n"

                step_input = self._build_step_input(query, workflow.name, step.description, step_outputs)
                input_messages = await agent.conversation_context.load_context(
                    session_id=session_id,
                    current_message=step_input,
                )

                skill_prompt = skill._build_system_prompt() if hasattr(skill, '_build_system_prompt') else f'# Skill: {skill.name}\n{skill.description}'
                workflow_message = SystemMessage(
                    content=(
                        f'[Current workflow: {workflow.name}]\n'
                        f'[Current step: {step.name}]\n'
                        f'{step.description}'
                    )
                )
                skill_message = SystemMessage(content=f'[Current skill: {skill.name}]\n\n{skill_prompt}')
                messages_with_step = [input_messages[0], workflow_message, skill_message] + list(input_messages[1:])
                agent.log_prompt_messages(f'workflow_executor:{workflow.name}:{step.skill_name}', messages_with_step)

                step_decision = RouteDecision(
                    route=RouteType.SKILL_DIRECT,
                    skill_name=step.skill_name,
                    workflow_name=workflow.name,
                    confidence=1.0,
                    reason=f'workflow step: {step.name}',
                )
                scoped_agent = agent.get_scoped_agent(step_decision)
                result = await scoped_agent.ainvoke({'messages': messages_with_step}, config=config)
                last_message = result['messages'][-1]
                step_reply = agent._stringify_message_content(getattr(last_message, 'content', '')) or str(last_message)
                step_reply = step_reply.strip()

                step_outputs.append({
                    'step_name': step.name,
                    'skill_name': step.skill_name,
                    'reply': step_reply,
                })
                combined_sections.append(f'## {step.name}\n\n{step_reply}')

                yield f'{step_reply}\n\n'

            full_response = '\n\n'.join(combined_sections).strip()
            duration = time.time() - request_start

            await agent.db.add_message(session_id, 'user', query)
            await agent.db.add_message(
                session_id,
                'assistant',
                full_response,
                metadata={
                    'route': 'workflow',
                    'workflow_name': workflow.name,
                    'steps': [step.skill_name for step in workflow.steps],
                },
            )

            logger.info(
                '[WorkflowExecutor] complete - %s - duration: %.2fs - workflow=%s',
                session_id,
                duration,
                workflow.name,
            )

            metadata = StreamFormatter.format_metadata(
                session_id=session_id,
                chunk_count=len(step_outputs),
                duration=duration,
                tools_called=workflow_registry.get_allowed_tools(workflow.name),
                skills_called=[step.skill_name for step in workflow.steps],
            )
            yield f'\n<!-- {metadata} -->'

        except Exception as exc:
            logger.error('[WorkflowExecutor] error: %s', exc, exc_info=True)
            from src.core.stream.handler import StreamHandler

            yield StreamHandler.format_stream_error(exc)

    @staticmethod
    def _build_step_input(
        original_query: str,
        workflow_name: str,
        step_description: str,
        step_outputs: List[Dict[str, str]],
    ) -> str:
        previous = []
        for item in step_outputs[-3:]:
            compact = re.sub(r'\s+', ' ', item['reply']).strip()
            if len(compact) > 1200:
                compact = compact[:1197] + '...'
            previous.append(f"- {item['step_name']} ({item['skill_name']}): {compact}")

        previous_block = '\n'.join(previous) if previous else 'None yet.'
        return (
            f'Original user request:\n{original_query}\n\n'
            f'Workflow: {workflow_name}\n'
            f'Current step objective: {step_description}\n\n'
            f'Previous workflow outputs:\n{previous_block}\n\n'
            'Produce the best result for the current step. Reuse earlier workflow outputs when they are relevant.'
        )