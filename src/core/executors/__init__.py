"""Executor factory and exports."""

from __future__ import annotations

import logging

from src.core.executors.base import BaseExecutor, ExecutorContext
from src.core.executors.complex_executor import ComplexExecutor
from src.core.executors.graph_executor import GraphExecutor
from src.core.executors.simple_executor import SimpleExecutor
from src.core.executors.skill_executor import SkillExecutor
from src.core.executors.workflow_executor import WorkflowExecutor
from src.core.router.route_types import RouteDecision, RouteType

logger = logging.getLogger(__name__)

__all__ = [
    'BaseExecutor',
    'ExecutorContext',
    'SimpleExecutor',
    'SkillExecutor',
    'ComplexExecutor',
    'GraphExecutor',
    'WorkflowExecutor',
    'get_executor',
]


_EXECUTOR_MAP: dict = {
    RouteType.WORKFLOW: WorkflowExecutor,
    RouteType.SIMPLE: SimpleExecutor,
    RouteType.SKILL_DIRECT: SkillExecutor,
    RouteType.COMPLEX: ComplexExecutor,
    RouteType.GRAPH_ONLY: GraphExecutor,
}


def get_executor(route_decision: RouteDecision) -> BaseExecutor:
    route = route_decision.route
    if isinstance(route, str):
        try:
            route = RouteType(route)
        except ValueError:
            logger.warning('[get_executor] unknown route type: %s, fallback to SimpleExecutor', route)
            return SimpleExecutor()

    executor_class = _EXECUTOR_MAP.get(route)
    if not executor_class:
        logger.warning('[get_executor] unregistered route type: %s, fallback to SimpleExecutor', route)
        return SimpleExecutor()

    executor = executor_class()
    target = route_decision.workflow_name or route_decision.skill_name
    logger.info('[get_executor] route=%s target=%s -> %s', route, target or '-', executor.__class__.__name__)
    return executor