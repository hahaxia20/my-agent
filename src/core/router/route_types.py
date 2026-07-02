from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RouteType(str, Enum):
    """Top-level execution routes supported by the runtime."""

    WORKFLOW = "workflow"
    SKILL_DIRECT = "skill_direct"
    SIMPLE = "simple"
    COMPLEX = "complex"
    GRAPH_ONLY = "graph_only"

    def __str__(self) -> str:
        return self.value


CONFIDENCE_THRESHOLD: float = 0.75


class RouteDecision(BaseModel):
    """Structured routing result returned by the intent router."""

    model_config = ConfigDict(use_enum_values=True)

    route: RouteType = Field(..., description='Top-level execution route')
    skill_name: Optional[str] = Field(None, description='Target skill when route=skill_direct')
    workflow_name: Optional[str] = Field(None, description='Target workflow when route=workflow')
    confidence: float = Field(..., ge=0.0, le=1.0, description='Router confidence score')
    reason: str = Field(..., description='Short route explanation for logs/debugging')
    sub_tasks: Optional[List[str]] = Field(None, description='Optional precomputed subtasks for complex routes')
    model_override: Optional[str] = Field(None, description='Optional forced model name')

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence < CONFIDENCE_THRESHOLD

    @property
    def target_name(self) -> Optional[str]:
        if self.route == RouteType.WORKFLOW:
            return self.workflow_name
        if self.route == RouteType.SKILL_DIRECT:
            return self.skill_name
        return None

    def with_fallback(self, fallback_route: RouteType = RouteType.SIMPLE) -> 'RouteDecision':
        if not self.is_low_confidence:
            return self
        return RouteDecision(
            route=fallback_route,
            confidence=self.confidence,
            reason=(
                f'confidence {self.confidence:.2f} below threshold; '
                f'fallback to {fallback_route} (original: {self.reason})'
            ),
            model_override=self.model_override,
        )

    @staticmethod
    def fallback(reason: str = 'router failed, fallback to simple') -> 'RouteDecision':
        return RouteDecision(
            route=RouteType.SIMPLE,
            confidence=0.6,
            reason=reason,
        )