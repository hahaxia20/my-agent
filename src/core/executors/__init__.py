"""
Executors 模块

提供基于路由决策的 Executor 工厂函数。
"""

import logging

from src.core.router.route_types import RouteDecision, RouteType
from src.core.executors.base import BaseExecutor, ExecutorContext
from src.core.executors.simple_executor import SimpleExecutor
from src.core.executors.skill_executor import SkillExecutor
from src.core.executors.complex_executor import ComplexExecutor
from src.core.executors.graph_executor import GraphExecutor

logger = logging.getLogger(__name__)


__all__ = [
    "BaseExecutor",
    "ExecutorContext",
    "SimpleExecutor",
    "SkillExecutor",
    "ComplexExecutor",
    "GraphExecutor",
    "get_executor",
]


# ═══════════════════════════════════════════════════════════
# Executor 工厂函数
# ═══════════════════════════════════════════════════════════

# 路由类型 → Executor 映射
_EXECUTOR_MAP: dict = {
    RouteType.SIMPLE: SimpleExecutor,
    RouteType.SKILL_DIRECT: SkillExecutor,
    RouteType.COMPLEX: ComplexExecutor,
    RouteType.GRAPH_ONLY: GraphExecutor,
}


def get_executor(route_decision: RouteDecision) -> BaseExecutor:
    """
    根据路由决策返回对应的 Executor 实例

    Args:
        route_decision: 路由决策结果

    Returns:
        BaseExecutor: 对应的 Executor 实例

    示例:
        decision = await route_query(query, ...)
        executor = get_executor(decision)
        async for chunk in executor.execute(query, ctx):
            yield chunk
    """
    route = route_decision.route

    # 将字符串值转换为枚举（兼容 use_enum_values=True 配置）
    if isinstance(route, str):
        try:
            route = RouteType(route)
        except ValueError:
            logger.warning(
                f"⚠️ [get_executor] 未知路由类型: {route}，回退到 SimpleExecutor"
            )
            return SimpleExecutor()

    executor_class = _EXECUTOR_MAP.get(route)

    if not executor_class:
        logger.warning(
            f"⚠️ [get_executor] 未注册的路由类型: {route}，回退到 SimpleExecutor"
        )
        return SimpleExecutor()

    executor = executor_class()
    logger.info(
        f"🔀 [get_executor] 路由: {route} → {executor.__class__.__name__}"
        f"{'(' + str(route_decision.skill_name) + ')' if route_decision.skill_name else ''}"
    )
    return executor
