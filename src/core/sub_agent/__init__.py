"""
Sub-Agent 编排系统

实现多 Agent 协作能力，支持：
- 复杂任务分解
- 并行 Sub-Agent 执行
- 结果合成与汇总
"""

from src.core.sub_agent.orchestrator import SubAgentOrchestrator
from src.core.sub_agent.models import SubAgentConfig, TaskDecomposition, SubAgentResult

__all__ = [
    'SubAgentOrchestrator',
    'SubAgentConfig',
    'TaskDecomposition',
    'SubAgentResult'
]
