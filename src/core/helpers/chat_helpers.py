"""
对话辅助函数 (Chat Helpers)

从 agent.py 中提取的纯工具函数，不依赖任何实例状态。
供 agent.py 和 stream_handler.py 共享使用。
"""

import logging
import time
from typing import Dict, Any, List, Optional

from src.core.security import InputSecurityFilter

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 安全拦截
# ═══════════════════════════════════════════════════════════

def check_input_security(
    user_query: str,
    session_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    检查输入安全性

    Args:
        user_query: 用户输入文本
        session_id: 当前会话 ID（用于拦截响应）

    Returns:
        None 表示安全通过；返回 dict 表示拦截响应
    """
    security_result = InputSecurityFilter.check_input(user_query)
    if not security_result.is_safe:
        logger.warning(f"🚨 [安全拦截] {security_result.reason}")
        return {
            "reply": "抱歉，您的请求包含了不安全的内容，我无法处理。",
            "session_id": session_id,
            "success": False,
            "error": "security_violation",
            "security_reason": security_result.reason
        }
    elif security_result.risk_level == "medium":
        logger.info(f"⚠️ [安全警告] {security_result.reason}")
    return None


# ═══════════════════════════════════════════════════════════
# 错误处理
# ═══════════════════════════════════════════════════════════

def handle_timeout(session_id: str, request_start: float) -> Dict[str, Any]:
    """处理对话超时"""
    elapsed = time.time() - request_start
    logger.error(f"⏰ [对话超时] session={session_id} - 耗时: {elapsed:.2f}s")
    return {
        "reply": "抱歉，请求超时，请稍后重试。",
        "session_id": session_id,
        "success": False,
        "error": "timeout",
        "elapsed_time": elapsed
    }


def handle_chat_error(
    session_id: str,
    error: Exception,
    request_start: float
) -> Dict[str, Any]:
    """处理对话异常"""
    elapsed = time.time() - request_start
    logger.error(
        f"💥 [对话错误] session={session_id} - "
        f"耗时: {elapsed:.2f}s - 错误: {str(error)}",
        exc_info=True
    )
    return {
        "reply": f"抱歉，处理请求时出现错误：{str(error)}",
        "session_id": session_id,
        "success": False,
        "error": str(error),
        "elapsed_time": elapsed
    }


# ═══════════════════════════════════════════════════════════
# 结果格式化
# ═══════════════════════════════════════════════════════════

def format_subtask_results(sub_agent_results) -> List[Dict[str, Any]]:
    """
    格式化子任务结果列表（用于 DB 元数据和 API 响应）

    Args:
        sub_agent_results: SubAgentResult 对象列表

    Returns:
        可序列化的字典列表
    """
    return [
        {
            "task_id": r.task_id,
            "task_name": r.task_id,
            "status": r.status.value,
            "duration": r.duration,
            "result_length": len(r.result) if r.result else 0,
            "result_preview": r.result[:200] if r.result else None
        }
        for r in sub_agent_results
    ]
