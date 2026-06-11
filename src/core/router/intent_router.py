"""
意图路由器 (IntentRouter)

使用本地小模型（Qwen2.5-7B via Ollama）进行结构化路由决策，
返回 RouteDecision，包含路由类型、目标 Skill、置信度等信息。

复用现有 INTENT_CLASSIFIER_* 配置，无需新增环境变量。
"""

import asyncio
import json
import logging
from typing import Optional

from src.core.router.route_types import RouteDecision, RouteType, CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 路由 System Prompt
# ═══════════════════════════════════════════════════════════

_ROUTE_SYSTEM_PROMPT = """你是一个精准的 Agent 路由器。根据用户查询、对话上下文和已加载 Skills，决定最佳执行路径。

已加载 Skills:
{skills_info}

路由规则（严格按优先级）:
1. **skill_direct**：如果查询明确指向某个 Skill（如"分析这个网站"→web-content-analyzer，"分析数据"→data-analysis），优先 skill_direct 并指定 skill_name。
2. **graph_only**：如果查询是产业链/行业图谱的单次事实查询（如"新能源汽车产业链有哪些环节"、"半导体上游是什么"），走 graph_only。
3. **simple**：日常问答、闲聊、定义解释、打招呼、简单计算、单步事实检索。
4. **complex**：需要多维度分析、跨主题对比、深度报告、系统性调研、多步骤推理。

输出严格 JSON，不要解释，格式如下：
{{
  "route": "skill_direct" | "simple" | "complex" | "graph_only",
  "skill_name": "skill-name（仅 skill_direct 时填写，其他填 null）",
  "confidence": 0.0-1.0,
  "reason": "简短决策原因",
  "sub_tasks": null,
  "model_override": null
}}"""


# ═══════════════════════════════════════════════════════════
# 懒加载 LLM 客户端（与 intent_classifier.py 保持一致）
# ═══════════════════════════════════════════════════════════

_llm = None


def _get_llm():
    """懒加载本地小模型 LLM 客户端，复用 INTENT_CLASSIFIER_* 配置"""
    global _llm
    if _llm is None:
        from src.config import get_settings_safe
        from langchain_openai import ChatOpenAI
        from pydantic import SecretStr

        settings = get_settings_safe()
        _llm = ChatOpenAI(
            model=settings.INTENT_CLASSIFIER_MODEL,
            api_key=SecretStr(settings.INTENT_CLASSIFIER_API_KEY),
            base_url=settings.INTENT_CLASSIFIER_BASE_URL,
            temperature=0,
            max_tokens=300,   # 路由 JSON 不需要太多 token
            timeout=settings.INTENT_CLASSIFIER_TIMEOUT,
        )
        logger.info(
            f"🎯 [路由器] LLM 初始化: {settings.INTENT_CLASSIFIER_MODEL} "
            f"@ {settings.INTENT_CLASSIFIER_BASE_URL}"
        )
    return _llm


# ═══════════════════════════════════════════════════════════
# 关键词兜底（LLM 不可用时）
# ═══════════════════════════════════════════════════════════

def _keyword_fallback(query: str, loaded_skills: Optional[str] = None) -> RouteDecision:
    """
    纯关键词兜底路由，保证 LLM 宕机时系统仍可用

    优先级：skill_direct → graph_only → complex → simple
    """
    import re
    text = query.lower().strip()

    # 1. 尝试匹配 Skill
    #    根据实际 Skill 关键词判断（web-content-analyzer、data-analysis 等）
    skill_keywords = {
        "web-content-analyzer": [
            r"分析.{0,6}(网站|网页|url|链接|文章)",
            r"(网站|网页|url|链接).{0,6}(分析|解读|总结|评估)",
            r"帮我.{0,4}(分析|看|读).{0,6}(网站|网页|链接)",
        ],
        "data-analysis": [
            r"(数据分析|数据处理|统计分析|可视化)",
            r"分析.{0,6}(数据|表格|csv|excel)",
        ],
    }
    if loaded_skills:
        for skill_name, patterns in skill_keywords.items():
            for p in patterns:
                if re.search(p, text):
                    logger.info(
                        f"⚠️ [关键词兜底路由] → skill_direct({skill_name}) | query: {query[:60]}"
                    )
                    return RouteDecision(
                        route=RouteType.SKILL_DIRECT,
                        skill_name=skill_name,
                        confidence=0.75,
                        reason=f"关键词匹配到 Skill: {skill_name}"
                    )

    # 2. 图谱查询
    graph_patterns = [
        r"(产业链|供应链|价值链).{0,6}(有哪些|是什么|结构|环节|组成)",
        r"(上游|中游|下游).{0,6}(是|有|包含)",
        r"(行业|产业).{0,6}(图谱|结构|链条)",
    ]
    for p in graph_patterns:
        if re.search(p, text):
            logger.info(f"⚠️ [关键词兜底路由] → graph_only | query: {query[:60]}")
            return RouteDecision(
                route=RouteType.GRAPH_ONLY,
                confidence=0.8,
                reason="关键词匹配到图谱查询"
            )

    # 3. 复杂任务
    complex_patterns = [
        r"对比.{0,20}(和|与|还是)", r"比较.{0,20}(和|与|还是)",
        r"(深度|详细|全面|系统).{0,4}(分析|报告|研究|调研)",
        r"(综合|横向|纵向).{0,4}(分析|对比|比较)",
        r"(产业链|行业).{0,4}(对比|比较|分析)",
    ]
    for p in complex_patterns:
        if re.search(p, text):
            logger.info(f"⚠️ [关键词兜底路由] → complex | query: {query[:60]}")
            return RouteDecision(
                route=RouteType.COMPLEX,
                confidence=0.7,
                reason="关键词匹配到复杂任务"
            )

    # 4. 默认简单
    logger.info(f"⚠️ [关键词兜底路由] → simple | query: {query[:60]}")
    return RouteDecision(
        route=RouteType.SIMPLE,
        confidence=0.6,
        reason="关键词兜底，默认 simple"
    )


# ═══════════════════════════════════════════════════════════
# 对外接口
# ═══════════════════════════════════════════════════════════

async def route_query(
    query: str,
    context_summary: Optional[str] = None,
    loaded_skills: Optional[str] = None,
) -> RouteDecision:
    """
    异步路由决策（主路径）

    使用本地小模型做结构化路由判断，返回 RouteDecision。
    超时或异常时退回关键词兜底，保证系统可用性。

    Args:
        query: 用户查询
        context_summary: 对话历史摘要（可选）
        loaded_skills: 已加载 Skills 描述字符串（由 skill_registry.get_skills_metadata_list() 生成）

    Returns:
        RouteDecision: 路由决策结果
    """
    from src.config import get_settings_safe
    from langchain_core.messages import SystemMessage, HumanMessage

    settings = get_settings_safe()

    # 功能关闭时直接走关键词兜底
    if not settings.INTENT_CLASSIFIER_ENABLED:
        logger.info("🎯 [路由器] INTENT_CLASSIFIER_ENABLED=False，使用关键词兜底")
        return _keyword_fallback(query, loaded_skills)

    skills_info = loaded_skills or "暂无可用 Skills"
    system_prompt = _ROUTE_SYSTEM_PROMPT.format(skills_info=skills_info)

    user_content = f"查询: {query}"
    if context_summary:
        user_content += f"\n上下文摘要: {context_summary}"

    try:
        llm = _get_llm()

        response = await asyncio.wait_for(
            llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_content),
            ]),
            timeout=settings.INTENT_CLASSIFIER_TIMEOUT
        )

        raw = response.content.strip()
        logger.debug(f"🎯 [路由器] 原始响应: {raw[:300]}")

        # 提取 JSON（兼容 markdown 代码块包裹）
        if raw.startswith("```"):
            # 去掉 ```json 和 ```
            lines = raw.split("\n")
            raw = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            )

        data = json.loads(raw)
        decision = RouteDecision(**data)

        # 置信度校验：低于阈值则回退到 SIMPLE
        decision = decision.with_fallback(RouteType.SIMPLE)

        logger.info(
            f"🎯 [路由器] → {decision.route}"
            f"{'(' + decision.skill_name + ')' if decision.skill_name else ''} "
            f"confidence={decision.confidence:.2f} "
            f"| reason: {decision.reason} "
            f"| query: {query[:60]}"
        )
        return decision

    except asyncio.TimeoutError:
        logger.warning(f"⚠️ [路由器] LLM 超时（{settings.INTENT_CLASSIFIER_TIMEOUT}s），使用关键词兜底")
        return _keyword_fallback(query, loaded_skills)

    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ [路由器] JSON 解析失败: {e}，使用关键词兜底 | raw: {raw[:100]}")
        return _keyword_fallback(query, loaded_skills)

    except Exception as e:
        logger.warning(f"⚠️ [路由器] 调用失败: {e}，使用关键词兜底")
        return _keyword_fallback(query, loaded_skills)
