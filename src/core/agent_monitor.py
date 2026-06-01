"""
Agent 监控模块
负责工具调用统计、健康检查等运维相关功能
从 agent.py 中拆分，进一步降低核心模块复杂度
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from langsmith import traceable

logger = logging.getLogger(__name__)


class AgentMonitor:
    """
    Agent 监控器
    
    职责：
    - 工具调用统计（次数、耗时、错误率）
    - 健康检查（LLM / MongoDB / Tools / Checkpointer）
    - 性能指标收集
    """
    
    def __init__(self):
        """初始化监控器"""
        self.tool_call_stats: Dict[str, Dict[str, Any]] = {}
    
    # ═══════════════════════════════════════════════════════
    # 工具调用统计
    # ═══════════════════════════════════════════════════════
    
    def record_tool_call(self, tool_name: str, duration: float, success: bool = True):
        """
        记录工具调用统计信息
        
        Args:
            tool_name: 工具名称
            duration: 调用耗时（秒）
            success: 是否成功
        """
        if tool_name not in self.tool_call_stats:
            self.tool_call_stats[tool_name] = {"count": 0, "total_time": 0.0, "errors": 0}

        self.tool_call_stats[tool_name]["count"] += 1
        self.tool_call_stats[tool_name]["total_time"] += duration
        if not success:
            self.tool_call_stats[tool_name]["errors"] += 1
    
    def get_tool_call_stats(self) -> Dict[str, Any]:
        """获取工具调用统计"""
        return {
            "tools": self.tool_call_stats,
            "total_tool_calls": sum(s["count"] for s in self.tool_call_stats.values()),
            "tool_error_rate": sum(s["errors"] for s in self.tool_call_stats.values()) / max(1, sum(
                s["count"] for s in self.tool_call_stats.values()))
        }
    
    def log_tool_call_stats(self):
        """打印工具调用统计信息"""
        if self.tool_call_stats:
            logger.info(f"📊 [调用统计] 工具: {len(self.tool_call_stats)} 个")
            for tool_name, stats in self.tool_call_stats.items():
                avg_time = stats["total_time"] / stats["count"] if stats["count"] > 0 else 0
                logger.debug(
                    f"   工具 [{tool_name}]: 调用{stats['count']}次, "
                    f"平均{avg_time:.2f}s, 错误{stats['errors']}次"
                )
    
    def reset_stats(self):
        """重置调用统计"""
        self.tool_call_stats.clear()
        logger.info("📊 调用统计已重置")
    
    # ═══════════════════════════════════════════════════════
    # 健康检查
    # ═══════════════════════════════════════════════════════
    
    @traceable(name="agent_health_check", tags=["production", "monitoring"])
    async def health_check(
        self,
        llm=None,
        db=None,
        tools: Optional[List] = None,
        checkpointer=None
    ) -> Dict[str, Any]:
        """
        执行全面健康检查
        
        Args:
            llm: LLM 客户端
            db: MongoDB 数据库实例
            tools: 工具列表
            checkpointer: 检查点实例
        
        Returns:
            健康检查结果
        """
        logger.info("🏥 执行健康检查")

        checks = {
            "llm": False,
            "mongodb": False,
            "tools": False,
            "checkpointer": False
        }

        # 检查 LLM
        if llm:
            try:
                await llm.ainvoke("ping")
                checks["llm"] = True
                logger.debug("✅ LLM 健康检查通过")
            except Exception as e:
                logger.error(f"❌ LLM 健康检查失败: {e}")

        # 检查 MongoDB
        if db:
            try:
                await db.ping()
                checks["mongodb"] = True
                logger.debug("✅ MongoDB 健康检查通过")
            except Exception as e:
                logger.error(f"❌ MongoDB 健康检查失败: {e}")

        # 检查工具
        checks["tools"] = tools is not None and len(tools) > 0
        checks["checkpointer"] = checkpointer is not None

        all_healthy = all(checks.values())
        status = "healthy" if all_healthy else "unhealthy"
        logger.info(f"🏥 健康检查结果: {status}")

        return {
            "status": status,
            "checks": checks,
            "timestamp": datetime.now().isoformat()
        }
