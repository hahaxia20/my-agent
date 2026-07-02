"""Intent router for selecting the appropriate execution path."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Optional

from src.core.router.route_types import RouteDecision, RouteType

logger = logging.getLogger(__name__)


_ROUTE_SYSTEM_PROMPT = """You are a precise agent router. Decide the best execution path from the user query, context summary, loaded skills, and loaded workflows.

Loaded workflows:
{workflows_info}

Loaded skills:
{skills_info}

Routing rules, in priority order:
1. workflow: use when the query asks for a fixed end-to-end business process or staged delivery across multiple specialist steps, such as research -> planning -> copywriting -> creative.
2. skill_direct: use when the query clearly points to a specific skill such as website analysis, image analysis, image generation, PDF analysis, stock-chart analysis, data analysis, or skill creation.
3. graph_only: use when the query is a direct supply-chain or industry-chain structure lookup.
4. simple: use for casual Q&A, definitions, greetings, simple retrieval, or single-step tasks.
5. complex: use for open-ended deep analysis, research, comparison, multi-step reasoning, or report-style tasks where the decomposition is not fixed in advance.

Special rule:
- Poster, key-visual, main-visual, and image-asset requests should prefer image-generation or marketing-creative skills unless the user explicitly asks for frontend code, HTML, CSS, React, Vue, pages, or components.

Return strict JSON only:
{{
  "route": "workflow" | "skill_direct" | "simple" | "complex" | "graph_only",
  "skill_name": "skill-name" or null,
  "workflow_name": "workflow-name" or null,
  "confidence": 0.0-1.0,
  "reason": "short reason",
  "sub_tasks": null,
  "model_override": null
}}"""


_llm = None


def _log_route_prompt(system_prompt: str, user_content: str):
    from src.config import get_settings_safe

    settings = get_settings_safe()
    if not getattr(settings, "ROUTE_DEBUG", False):
        return

    logger.info("=" * 80)
    logger.info("[route prompt] system")
    for line in system_prompt.splitlines():
        logger.info("[route prompt] %s", line)
    logger.info("[route prompt] user")
    for line in user_content.splitlines():
        logger.info("[route prompt] %s", line)
    logger.info("=" * 80)


def _get_llm():
    global _llm
    if _llm is None:
        from langchain_openai import ChatOpenAI
        from pydantic import SecretStr
        from src.config import get_settings_safe

        settings = get_settings_safe()
        _llm = ChatOpenAI(
            model=settings.INTENT_CLASSIFIER_MODEL,
            api_key=SecretStr(settings.INTENT_CLASSIFIER_API_KEY),
            base_url=settings.INTENT_CLASSIFIER_BASE_URL,
            temperature=0,
            max_tokens=300,
            timeout=settings.INTENT_CLASSIFIER_TIMEOUT,
        )
        logger.info(
            "Intent router LLM initialized: %s @ %s",
            settings.INTENT_CLASSIFIER_MODEL,
            settings.INTENT_CLASSIFIER_BASE_URL,
        )
    return _llm


def _normalize_decision(decision: RouteDecision) -> RouteDecision:
    if decision.route != RouteType.SKILL_DIRECT:
        decision.skill_name = None
    if decision.route != RouteType.WORKFLOW:
        decision.workflow_name = None
    return decision


def _direct_route_override(query: str) -> Optional[RouteDecision]:
    text = query.lower().strip()

    frontend_terms = [
        "html",
        "css",
        "react",
        "vue",
        "前端",
        "页面",
        "组件",
        "网页",
        "web page",
        "landing page",
        "代码",
    ]
    if any(term in text for term in frontend_terms):
        return None

    poster_terms = [
        "海报",
        "poster",
        "主视觉",
        "核心主视觉",
        "活动主视觉",
        "kv",
        "key visual",
        "视觉海报",
        "cover image",
    ]
    marketing_terms = [
        "社媒",
        "campaign",
        "宣发",
        "小红书",
        "social",
        "launch",
        "营销",
        "投放",
        "品牌传播",
        "渠道投放",
    ]
    image_generation_terms = [
        "生成",
        "生图",
        "create",
        "generate",
        "输出到",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        "图片",
        "图像",
        "image",
    ]

    has_poster = any(term in text for term in poster_terms)
    has_marketing = any(term in text for term in marketing_terms)
    has_image_intent = any(term in text for term in image_generation_terms)

    if has_poster and has_marketing:
        return RouteDecision(
            route=RouteType.SKILL_DIRECT,
            skill_name="social-creative",
            confidence=0.93,
            reason="direct override: marketing poster/main-visual request",
        )

    if has_poster and (has_image_intent or len(text) <= 24):
        return RouteDecision(
            route=RouteType.SKILL_DIRECT,
            skill_name="imagegen",
            confidence=0.93,
            reason="direct override: poster/main-visual image generation request",
        )

    return None


def _keyword_fallback(
    query: str,
    loaded_skills: Optional[str] = None,
    loaded_workflows: Optional[str] = None,
) -> RouteDecision:
    from src.core.workflows import workflow_registry
    from src.skills.manager import skill_registry

    direct_override = _direct_route_override(query)
    if direct_override:
        logger.info(
            "[keyword fallback] -> %s(%s) | query: %s",
            direct_override.route,
            direct_override.skill_name,
            query[:80],
        )
        return direct_override

    text = query.lower().strip()

    if loaded_workflows:
        matched = workflow_registry.match_query_with_reason(query)
        if matched:
            workflow_name, match_reason = matched
            logger.info("[keyword fallback] -> workflow(%s) | query: %s", workflow_name, query[:80])
            return RouteDecision(
                route=RouteType.WORKFLOW,
                workflow_name=workflow_name,
                confidence=0.84,
                reason=f"workflow match: {match_reason}",
            )

    if loaded_skills:
        for skill in skill_registry.get_active_skills():
            trigger_keywords = [str(keyword).lower() for keyword in getattr(skill, "trigger_keywords", [])]
            if any(keyword and keyword in text for keyword in trigger_keywords):
                logger.info("[keyword fallback] -> skill_direct(%s) | query: %s", skill.name, query[:80])
                return RouteDecision(
                    route=RouteType.SKILL_DIRECT,
                    skill_name=skill.name,
                    confidence=0.78,
                    reason=f"keyword matched skill trigger: {skill.name}",
                )

    graph_patterns = [
        r"(产业链|供应链|价值链).{0,6}(有哪些|是什么|结构|环节|组成)",
        r"(上游|中游|下游).{0,6}(是什么|包括|包含)",
        r"(行业|产业).{0,6}(图谱|结构|链条)",
    ]
    for rule in graph_patterns:
        if re.search(rule, text):
            logger.info("[keyword fallback] -> graph_only | query: %s", query[:80])
            return RouteDecision(
                route=RouteType.GRAPH_ONLY,
                confidence=0.8,
                reason="keyword matched graph query",
            )

    complex_patterns = [
        r"对比.{0,20}(和|与|还是)",
        r"比较.{0,20}(和|与|还是)",
        r"(深度|详细|全面|系统).{0,4}(分析|报告|研究|调研)",
        r"(综合|横向|纵向).{0,4}(分析|对比|比较)",
    ]
    for rule in complex_patterns:
        if re.search(rule, text):
            logger.info("[keyword fallback] -> complex | query: %s", query[:80])
            return RouteDecision(
                route=RouteType.COMPLEX,
                confidence=0.7,
                reason="keyword matched complex task",
            )

    logger.info("[keyword fallback] -> simple | query: %s", query[:80])
    return RouteDecision(
        route=RouteType.SIMPLE,
        confidence=0.6,
        reason="keyword fallback defaulted to simple",
    )


async def route_query(
    query: str,
    context_summary: Optional[str] = None,
    loaded_skills: Optional[str] = None,
    loaded_workflows: Optional[str] = None,
) -> RouteDecision:
    from langchain_core.messages import HumanMessage, SystemMessage
    from src.config import get_settings_safe

    direct_override = _direct_route_override(query)
    if direct_override:
        logger.info(
            "Router -> %s(%s) confidence=%.2f | reason: %s | query: %s",
            direct_override.route,
            direct_override.skill_name,
            direct_override.confidence,
            direct_override.reason,
            query[:80],
        )
        return direct_override

    settings = get_settings_safe()
    if not settings.INTENT_CLASSIFIER_ENABLED:
        logger.info("Intent classifier disabled, using keyword fallback")
        return _keyword_fallback(query, loaded_skills, loaded_workflows)

    skills_info = loaded_skills or "No active skills"
    workflows_info = loaded_workflows or "No active workflows"
    system_prompt = _ROUTE_SYSTEM_PROMPT.format(
        skills_info=skills_info,
        workflows_info=workflows_info,
    )

    user_content = f"Query: {query}"
    if context_summary:
        user_content += f"\nContext summary: {context_summary}"

    raw = ""
    try:
        llm = _get_llm()
        _log_route_prompt(system_prompt, user_content)
        response = await asyncio.wait_for(
            llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_content),
                ]
            ),
            timeout=settings.INTENT_CLASSIFIER_TIMEOUT,
        )

        raw = response.content.strip()
        logger.debug("Intent router raw response: %s", raw[:300])

        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(line for line in lines if not line.strip().startswith("```"))

        decision = RouteDecision(**json.loads(raw))
        decision = _normalize_decision(decision).with_fallback(RouteType.SIMPLE)
        logger.info(
            "Router -> %s%s confidence=%.2f | reason: %s | query: %s",
            decision.route,
            f"({decision.workflow_name or decision.skill_name})" if (decision.workflow_name or decision.skill_name) else "",
            decision.confidence,
            decision.reason,
            query[:80],
        )
        return decision

    except asyncio.TimeoutError:
        logger.warning(
            "Intent router timed out after %ss, using keyword fallback",
            settings.INTENT_CLASSIFIER_TIMEOUT,
        )
        return _keyword_fallback(query, loaded_skills, loaded_workflows)
    except json.JSONDecodeError as exc:
        logger.warning("Intent router JSON parse failed: %s | raw: %s", exc, raw[:120])
        return _keyword_fallback(query, loaded_skills, loaded_workflows)
    except Exception as exc:
        logger.warning("Intent router failed: %s, using keyword fallback", exc)
        return _keyword_fallback(query, loaded_skills, loaded_workflows)
