"""
产业链图谱 API 路由
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from src.api.middleware.auth import get_current_user
from src.storage.neo4j import get_neo4j
from src.tools.industry_graph import (
    QueryIndustryChainTool,
    ListIndustryChainsTool,
    FindUpstreamTool
)
from src.core.logging_decorator import log_method_call
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/industry", tags=["industry-graph"])


# ═══════════════════════════════════════
# 请求/响应模型
# ═══════════════════════════════════════

class IndustryQueryRequest(BaseModel):
    """产业链查询请求"""
    industry: str = Field(..., description="产业链名称", examples=["氢能", "核能", "新能源"])
    include_codes: bool = Field(default=True, description="是否包含行业分类代码")


class UpstreamQueryRequest(BaseModel):
    """上游依赖查询请求"""
    industry: str = Field(..., description="产业链名称")
    segment: str = Field(..., description="环节名称")
    depth: int = Field(default=3, ge=1, le=5, description="查询深度")


class IndustryResponse(BaseModel):
    """产业链响应"""
    success: bool
    industry: Optional[str] = None
    description: Optional[str] = None
    graph: Optional[Dict[str, Any]] = None
    stats: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    available_chains: Optional[List[str]] = None


class ChainsListResponse(BaseModel):
    """产业链列表响应"""
    success: bool
    chains: List[str]
    count: int
    description: Optional[str] = None


# ═══════════════════════════════════════
# API 路由
# ═══════════════════════════════════════

@router.post("/query", response_model=IndustryResponse, summary="查询产业链图谱")
@log_method_call(prefix="[API-图谱] ")
async def query_industry_chain(request: IndustryQueryRequest, req: Request):
    """查询指定产业链的完整图谱"""
    try:
        # 验证用户（可选）
        try:
            user_id = await get_current_user(req)
        except:
            user_id = "anonymous"
        
        tool = QueryIndustryChainTool()
        result = await tool.execute(
            industry=request.industry,
            user_id=user_id
        )
        
        if result.get("success"):
            logger.info(f"✅ 产业链查询成功: {request.industry}")
            return IndustryResponse(
                success=True,
                industry=result["industry"],
                description=result["description"],
                graph=result["graph"],
                stats=result["stats"]
            )
        else:
            return IndustryResponse(
                success=False,
                industry=request.industry,
                error=result.get("error", "查询失败"),
                available_chains=result.get("available_chains", [])
            )
            
    except Exception as e:
        logger.error(f"查询产业链失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/chains", response_model=ChainsListResponse, summary="列出所有产业链")
@log_method_call(prefix="[API-图谱] ")
async def list_industry_chains(req: Request):
    """列出系统中所有可用的产业链"""
    try:
        tool = ListIndustryChainsTool()
        result = await tool.execute()
        
        if result.get("success"):
            return ChainsListResponse(
                success=True,
                chains=result["chains"],
                count=result["count"],
                description=result.get("description")
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "获取产业链列表失败")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"列出产业链失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.post("/upstream", summary="查询上游依赖")
@log_method_call(prefix="[API-图谱] ")
async def query_upstream(request: UpstreamQueryRequest, req: Request):
    """查询指定环节的上游依赖链"""
    try:
        tool = FindUpstreamTool()
        result = await tool.execute(
            industry=request.industry,
            segment=request.segment,
            depth=request.depth
        )
        
        if result.get("success"):
            logger.info(f"✅ 上游依赖查询成功: {request.industry} -> {request.segment}")
            return {
                "success": True,
                "industry": request.industry,
                "segment": request.segment,
                "graph": result["graph"]
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=result.get("error", "查询失败")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询上游依赖失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/stats", summary="图谱统计")
@log_method_call(prefix="[API-图谱] ")
async def get_stats(req: Request):
    """获取图谱统计信息"""
    try:
        neo4j = get_neo4j()
        if not neo4j:
            raise HTTPException(status_code=503, detail="Neo4j 未连接")
        
        chains = await neo4j.list_all_chains()
        
        stats = {
            "success": True,
            "total_chains": len(chains),
            "chains": chains,
            "database": "neo4j",
            "status": "connected"
        }
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")
