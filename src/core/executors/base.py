"""
Executor 基类

所有 Executor 实现均继承此抽象类，
通过 execute() 方法以 AsyncIterator 形式产出流式 chunks。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, AsyncIterator, Optional, Any

from langchain_core.runnables import RunnableConfig

from src.core.router.route_types import RouteDecision

if TYPE_CHECKING:
    from src.core.agent import MyAgent

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# Executor 上下文（封装公共依赖）
# ═══════════════════════════════════════════════════════════

@dataclass
class ExecutorContext:
    """
    Executor 执行上下文，封装所有公共依赖

    由各 Executor.execute() 接收，避免重复传参。
    """

    agent: "MyAgent"                        # MyAgent 单例
    session_id: str                         # 会话 ID
    user_id: str = "anonymous"              # 用户 ID
    config: Optional[RunnableConfig] = None # LangChain Runnable 配置
    route_decision: Optional[RouteDecision] = None  # 路由决策结果
    enable_metrics: bool = True             # 启用流式监控
    buffer_size: int = 5                    # 流式缓冲区大小
    flush_interval: float = 0.05            # 流式刷新间隔

    def build_runnable_config(self) -> RunnableConfig:
        """如果未提供 config，则构建默认配置"""
        if self.config:
            return self.config
        return RunnableConfig(
            configurable={"thread_id": self.session_id},
            metadata={"user_id": self.user_id},
            tags=["production", "stream"],
            recursion_limit=self.agent.config.recursion_limit
        )


# ═══════════════════════════════════════════════════════════
# Executor 抽象基类
# ═══════════════════════════════════════════════════════════

class BaseExecutor(ABC):
    """
    Executor 抽象基类

    子类实现 execute() 方法，以 AsyncIterator[str] 形式
    逐 chunk 产出响应内容（与 StreamHandler.stream() 的 yield 格式保持一致）。
    """

    @abstractmethod
    async def execute(
        self,
        query: str,
        ctx: ExecutorContext,
    ) -> AsyncIterator[str]:
        """
        执行查询并流式返回响应

        Args:
            query: 用户查询
            ctx: 执行上下文（包含 agent、session_id 等）

        Yields:
            str: 流式响应 chunk
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"
