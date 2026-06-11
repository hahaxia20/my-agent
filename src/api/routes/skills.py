"""
Skill 管理 API - 列出、启禁用、热重载
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from src.api.middleware.auth import get_current_user
from src.skills.manager import skill_registry

router = APIRouter(prefix="/api/skills", tags=["skills"])


# ==================== 响应模型 ====================

class SkillItem(BaseModel):
    name: str
    description: str
    enabled: bool
    version: Optional[str] = None
    resolved_tools: List[str] = []


class SkillDetail(SkillItem):
    scripts: List[str] = []
    references: List[str] = []
    assets: List[str] = []
    allowed_tools: Optional[List[str]] = None


class SkillStatusUpdate(BaseModel):
    enabled: bool


class ReloadResponse(BaseModel):
    added: List[str]
    removed: List[str]
    reloaded_count: int
    failed: List[Dict[str, str]]
    summary: str


# ==================== 路由 ====================

@router.get("", response_model=List[SkillItem], summary="列出所有 Skill")
async def list_skills(user_id: str = Depends(get_current_user)):
    """返回所有已加载的 Skill（含已禁用），含启用状态"""
    return [
        SkillItem(
            name=s.name,
            description=s.description,
            enabled=getattr(s, "enabled", True),
            version=(
                s.config.metadata.version
                if hasattr(s, "config") and s.config.metadata
                else None
            ),
            resolved_tools=getattr(s, "resolved_tools", []),
        )
        for s in skill_registry.get_all()
    ]


@router.get("/{skill_name}", response_model=SkillDetail, summary="获取 Skill 详情")
async def get_skill(skill_name: str, user_id: str = Depends(get_current_user)):
    """获取单个 Skill 的完整信息"""
    skill = skill_registry.get_skill(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")

    config = getattr(skill, "config", None)
    meta = config.metadata if config else None

    return SkillDetail(
        name=skill.name,
        description=skill.description,
        enabled=getattr(skill, "enabled", True),
        version=meta.version if meta else None,
        resolved_tools=getattr(skill, "resolved_tools", []),
        scripts=getattr(skill, "scripts", []),
        references=getattr(skill, "references", []),
        assets=getattr(skill, "assets", []),
        allowed_tools=meta.allowed_tools if meta else None,
    )


@router.patch("/{skill_name}", summary="修改 Skill 启用状态")
async def update_skill_status(
    skill_name: str,
    body: SkillStatusUpdate,
    user_id: str = Depends(get_current_user),
):
    """启用或禁用指定 Skill"""
    skill = skill_registry.get_skill(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")

    if body.enabled:
        skill_registry.enable(skill_name)
    else:
        skill_registry.disable(skill_name)

    return {"name": skill_name, "enabled": body.enabled}


@router.post("/reload", response_model=ReloadResponse, summary="热重载所有 Skill")
async def reload_skills(user_id: str = Depends(get_current_user)):
    """重新扫描 Skills 目录，刷新所有 Skill 配置"""
    report = skill_registry.reload()
    return ReloadResponse(
        added=report.added,
        removed=report.removed,
        reloaded_count=len(report.reloaded),
        failed=report.failed,
        summary=report.summary(),
    )
