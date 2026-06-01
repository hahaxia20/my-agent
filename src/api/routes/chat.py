"""
对话 API 路由
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import logging

from src.core.agent import get_agent
from src.api.middleware.auth import get_current_user
from src.core.logging.decorator import log_method_call

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


# ═══════════════════════════════════════
# 请求/响应模型
# ═══════════════════════════════════════

class ChatRequest(BaseModel):
    """对话请求"""
    message: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="用户消息",
        examples=["你好，我叫haha"]
    )
    session_id: Optional[str] = Field(
        None,
        description="会话ID（可选，不传则创建新会话）",
        examples=["session-abc123"]
    )


class ChatResponse(BaseModel):
    """对话响应"""
    success: bool = True
    session_id: str
    reply: str
    timestamp: datetime = Field(default_factory=datetime.now)


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    title: str
    message_count: int
    updated_at: datetime


class SessionDetail(BaseModel):
    """会话详情"""
    success: bool = True
    session_id: str
    title: str
    messages: List[dict]
    message_count: int


class Message(BaseModel):
    """单条消息"""
    role: str
    content: str
    timestamp: Optional[datetime] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: str
    detail: Optional[str] = None


# ═══════════════════════════════════════
# API 路由
# ═══════════════════════════════════════


@router.get("/sessions", response_model=List[SessionInfo], summary="获取会话列表")
@log_method_call(prefix="[API-会话] ")
async def list_sessions(req: Request, limit: int = 20, offset: int = 0):
    """获取会话列表"""
    try:
        # 从 Token 获取用户
        user_id = await get_current_user(req)

        agent = await get_agent()
        sessions = await agent.list_sessions(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        return [
            SessionInfo(
                session_id=s["session_id"],
                title=s["title"],
                message_count=s["message_count"],
                updated_at=s["updated_at"]
            )
            for s in sessions
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取会话列表失败: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=SessionDetail, summary="获取会话详情")
@log_method_call(prefix="[API-会话] ")
async def get_session(session_id: str, req: Request):
    """获取会话详情"""
    try:
        # 从 Token 获取用户
        user_id = await get_current_user(req)

        agent = await get_agent()
        history = await agent.get_session_history(session_id, user_id=user_id)

        if not history.get("success"):
            raise HTTPException(
                status_code=404,
                detail=history.get("error", "会话不存在")
            )

        return SessionDetail(
            success=True,
            session_id=history["session_id"],
            title=history["title"],
            messages=history["messages"],
            message_count=history["message_count"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话详情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取会话详情失败: {str(e)}"
        )


@router.delete("/sessions/{session_id}", summary="删除会话")
@log_method_call(prefix="[API-会话] ")
async def delete_session(session_id: str, req: Request):
    """删除会话"""
    try:
        user_id = await get_current_user(req)
        agent = await get_agent()

        # 直接调用 SessionManager，避免重复查询
        deleted = await agent.delete_session(session_id, user_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="会话不存在或无权删除"
            )

        logger.info(f"✅ 会话已删除: {session_id}, user: {user_id}")

        return {
            "success": True,
            "message": "会话已删除"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"删除会话失败: {str(e)}"
        )


@router.post("/chat/stream")
@log_method_call(prefix="[API-流式] ", log_duration=True)
async def chat_stream(request: ChatRequest, req: Request):
    """生产级流式对话接口"""

    async def generate():
        try:
            user_id = await get_current_user(req)

            agent = await get_agent()

            # 配置流式参数
            stream_kwargs = {
                "user_query": request.message,
                "session_id": request.session_id,
                "user_id": user_id,
                "enable_metrics": True,  # 启用监控
                "buffer_size": 5,  # 缓冲区大小
                "flush_interval": 0.05  # 刷新间隔
            }

            async for chunk in agent.stream(**stream_kwargs):
                # 检查客户端是否断开（兼容不同 Starlette 版本）
                is_disc = req.is_disconnected()
                if hasattr(is_disc, '__await__'):
                    is_disc = await is_disc
                if is_disc:
                    logger.info("客户端断开连接")
                    break

                # 格式化 SSE 输出
                if chunk and chunk.strip():
                    yield f"data: {chunk}\n\n"

            # 发送结束标记
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"流式生成错误: {e}", exc_info=True)
            yield f"data: 错误: {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "*",
        }
    )