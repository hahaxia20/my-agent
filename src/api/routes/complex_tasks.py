"""
复杂任务 API 路由

提供 Sub-Agent 编排系统的 HTTP 接口
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import logging
import json
from fastapi.responses import StreamingResponse

from src.core.agent import get_agent
from src.api.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["complex-tasks"])


# ═══════════════════════════════════════════════════════════
# 请求/响应模型
# ═══════════════════════════════════════════════════════════

class ComplexTaskRequest(BaseModel):
    """复杂任务请求"""
    task: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="复杂任务描述",
        examples=["对比分析 2024 年主流的 5 个 AI Agent 框架的优缺点"]
    )
    session_id: Optional[str] = Field(
        None,
        description="会话 ID (可选)"
    )
    decomposition_strategy: str = Field(
        default="auto",
        description="分解策略 (parallel/sequential/hybrid/auto)",
        pattern="^(parallel|sequential|hybrid|auto)$"
    )


class SubTaskInfo(BaseModel):
    """子任务信息"""
    task_id: str
    status: str
    duration: float
    result_preview: Optional[str] = None


class ComplexTaskResponse(BaseModel):
    """复杂任务响应"""
    success: bool = True
    session_id: str
    reply: str
    elapsed_time: float
    sub_tasks: List[SubTaskInfo] = []
    metadata: dict = {}
    timestamp: datetime = Field(default_factory=datetime.now)


# ═══════════════════════════════════════════════════════════
# API 路由
# ═══════════════════════════════════════════════════════════

@router.post("/complex-chat", response_model=ComplexTaskResponse, summary="执行复杂任务")
async def complex_chat(request: ComplexTaskRequest, req: Request):
    """
    执行复杂任务 (使用 Sub-Agent 编排)
    
    适用于：
    - 深度研究与分析
    - 多主题对比
    - 综合报告生成
    - 数据处理流水线
    """
    try:
        # 获取用户
        user_id = await get_current_user(req)
        
        # 获取 Agent
        agent = await get_agent()
        
        # 执行复杂任务
        result = await agent.complex_chat(
            user_query=request.task,
            session_id=request.session_id,
            user_id=user_id,
            decomposition_strategy=request.decomposition_strategy
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "复杂任务执行失败")
            )
        
        # 构建响应
        return ComplexTaskResponse(
            success=True,
            session_id=result["session_id"],
            reply=result["reply"],
            elapsed_time=result["elapsed_time"],
            sub_tasks=[
                SubTaskInfo(
                    task_id=st["task_id"],
                    status=st["status"],
                    duration=st["duration"],
                    result_preview=st.get("result_preview")
                )
                for st in result.get("sub_tasks", [])
            ],
            metadata=result.get("metadata", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"复杂任务执行失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"复杂任务执行失败: {str(e)}"
        )


@router.post("/complex-chat/stream")
async def complex_chat_stream(request: ComplexTaskRequest, req: Request):
    """
    执行复杂任务 (流式输出进度)
    
    使用 Server-Sent Events (SSE) 推送执行进度
    """
    from fastapi.responses import StreamingResponse
    import asyncio
    
    async def generate():
        try:
            user_id = await get_current_user(req)
            agent = await get_agent()
            
            # 创建事件队列
            queue = asyncio.Queue()
            
            # 创建进度回调函数
            async def progress_callback(event_type: str, data: dict):
                event_data = {
                    "type": event_type,
                    "data": data
                }
                await queue.put(f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n")
            
            # 启动后台任务执行复杂任务
            async def execute_task():
                try:
                    result = await agent.complex_chat(
                        user_query=request.task,
                        session_id=request.session_id,
                        user_id=user_id,
                        decomposition_strategy=request.decomposition_strategy,
                        progress_callback=progress_callback
                    )
                    
                    # 返回最终结果
                    final_data = {
                        "type": "final_result",
                        "data": {
                            "success": result.get("success", False),
                            "session_id": result.get("session_id"),
                            "reply": result.get("reply", ""),
                            "duration": result.get("elapsed_time", 0),
                            "sub_tasks": [
                                {
                                    "task_id": st.get("task_id"),
                                    "task_name": st.get("task_name", st.get("task_id")),
                                    "status": st.get("status"),
                                    "duration": st.get("duration", 0),
                                    "result_length": st.get("result_length", 0),
                                    "result_preview": st.get("result_preview")
                                }
                                for st in result.get("sub_tasks", [])
                            ],
                            "parallel_efficiency": result.get("metadata", {}).get("parallel_efficiency", 0)
                        }
                    }
                    await queue.put(f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n")
                    await queue.put("data: [DONE]\n\n")
                except Exception as e:
                    logger.error(f"流式复杂任务失败: {e}", exc_info=True)
                    error_data = {
                        "type": "error",
                        "data": {"error": str(e)}
                    }
                    await queue.put(f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n")
                    await queue.put("data: [DONE]\n\n")
            
            # 启动后台任务
            task = asyncio.create_task(execute_task())
            
            # 从队列中读取并推送事件
            while True:
                event = await queue.get()
                yield event
                
                if "[DONE]" in event:
                    break
            
            # 等待后台任务完成
            await task
            
        except Exception as e:
            logger.error(f"流式复杂任务失败: {e}", exc_info=True)
            error_data = {
                "type": "error",
                "data": {"error": str(e)}
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
