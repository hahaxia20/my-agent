"""
路由类型定义

定义 Agent 路由决策的枚举和数据模型，
供 intent_router.py 和各 Executor 共享。
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
# 路由类型枚举
# ═══════════════════════════════════════════════════════════

class RouteType(str, Enum):
    """Agent 路由类型"""

    SKILL_DIRECT = "skill_direct"   # 直达某个 Skill（如网站分析、PDF 处理）
    SIMPLE = "simple"               # 简单问答、闲聊、定义解释 → ReAct Agent
    COMPLEX = "complex"             # 多步推理、对比分析、深度研究 → Sub-Agent 编排
    GRAPH_ONLY = "graph_only"       # 产业链图谱单次查询 → 直接调用图谱工具

    def __str__(self) -> str:
        return self.value


# ═══════════════════════════════════════════════════════════
# 置信度阈值
# ═══════════════════════════════════════════════════════════

CONFIDENCE_THRESHOLD: float = 0.75
"""低于此阈值时，路由回退到保守路径（SIMPLE）"""


# ═══════════════════════════════════════════════════════════
# 路由决策模型
# ═══════════════════════════════════════════════════════════

class RouteDecision(BaseModel):
    """
    路由决策结果

    由 intent_router.route_query() 返回，
    供 Executor 层根据 route + skill_name 选择执行路径。
    """

    route: RouteType = Field(
        ...,
        description="路由类型"
    )

    skill_name: Optional[str] = Field(
        None,
        description="当 route=SKILL_DIRECT 时，指定目标 Skill 名称"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="路由置信度 (0-1)，低于 CONFIDENCE_THRESHOLD 则回退"
    )

    reason: str = Field(
        ...,
        description="路由决策原因（供日志记录）"
    )

    sub_tasks: Optional[List[str]] = Field(
        None,
        description="当 route=COMPLEX 时，可选的预分解子任务列表"
    )

    model_override: Optional[str] = Field(
        None,
        description="强制使用指定强模型（覆盖默认配置）"
    )

    class Config:
        use_enum_values = True

    @property
    def is_low_confidence(self) -> bool:
        """置信度是否低于阈值"""
        return self.confidence < CONFIDENCE_THRESHOLD

    def with_fallback(self, fallback_route: RouteType = RouteType.SIMPLE) -> "RouteDecision":
        """
        如果置信度过低，返回保守路径的决策副本

        Args:
            fallback_route: 回退路由类型，默认 SIMPLE

        Returns:
            置信度过低时返回回退路由决策，否则返回自身
        """
        if self.is_low_confidence:
            return RouteDecision(
                route=fallback_route,
                confidence=self.confidence,
                reason=f"置信度 {self.confidence:.2f} 低于阈值，回退到 {fallback_route}（原始: {self.reason}）",
                model_override=self.model_override
            )
        return self

    @staticmethod
    def fallback(reason: str = "路由失败，回退到 simple") -> "RouteDecision":
        """构建默认回退决策"""
        return RouteDecision(
            route=RouteType.SIMPLE,
            confidence=0.6,
            reason=reason
        )
