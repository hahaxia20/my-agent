"""
意图分类器 (IntentClassifier)

基于关键词评分规则，将用户输入分为 simple / complex 两类，
供主 Agent 决定走简单对话还是复杂任务编排路径。

纯规则逻辑，不依赖 LLM 或任何外部服务。
"""

import re
import logging

logger = logging.getLogger(__name__)


def classify_intent(query: str) -> str:
    """
    基于关键词评分的用户意图分类

    评分规则：
    - 明确复杂模式：+3（对比分析、深度报告等）
    - 中等复杂信号：+1（上下游、报告、风险分析等）
    - 结构性复杂信号：额外 +1（上下游、对比）
    - 明确简单模式：-5（问候、简单定义等）
    - 长文本（>100字）：+1

    Args:
        query: 用户输入文本

    Returns:
        "simple" 或 "complex"
    """
    score = 0
    text = query.lower().strip()

    # ── 明确复杂意图的模式（高权重，每条 +3）──
    complex_patterns = [
        r"对比.{0,20}(和|与|还是)",
        r"比较.{0,20}(和|与|还是)",
        r"分析.{0,20}(产业链|行业|市场|趋势|格局)",
        r"(深度|详细|全面|系统).{0,4}(分析|报告|研究|调研)",
        r"(综合|横向|纵向).{0,4}(分析|对比|比较)",
        r"分别.{0,6}(介绍|分析|说明|阐述)",
        r"多个.{0,6}(产业链|行业|领域|公司|企业)",
        r"(产业链|行业).{0,4}(对比|比较|分析)",
        r"哪些.{0,6}(企业|公司|上市公司|龙头)",
    ]
    for p in complex_patterns:
        if re.search(p, text):
            score += 3

    # ── 中等复杂信号（每条 +1）──
    medium_patterns = [
        r"(上下游|供应链|竞争格局|卡脖子)",
        r"(报告|调研)",
        r"(风险|机会|威胁|优势|劣势)",
        r"(现状|前景|发展方向)",
        r"对比",
        r"怎么.{0,4}(看|评价|理解)",
        r"分析",  # "分析" 本身是复杂信号
    ]
    for p in medium_patterns:
        if re.search(p, text):
            score += 1

    # ── 结构性复杂信号（需要多维度分析，额外 +1）──
    structural_patterns = [
        r"上下游",  # 涉及产业链上下游关系
        r"对比",   # 涉及横向对比
    ]
    for p in structural_patterns:
        if re.search(p, text):
            score += 1

    # ── 明确简单意图的模式（负分）──
    simple_patterns = [
        r"^(你好|hi|hello|嗨|hey|嘿)[\s!！.。]*$",
        r"^(谢谢|感谢|thanks|thank you|再见|拜拜)[\s!！.。]*$",
        r"^(好的|ok|没问题|明白了|知道了)[\s!！.。]*$",
        r".{2,8}(是什么|什么意思|怎么读|怎么念)",
        r"^帮我(查|找|搜|看).{2,10}$",
    ]
    for p in simple_patterns:
        if re.search(p, text):
            score -= 5

    # ── 长度因子 ──
    if len(query) > 100:
        score += 1

    intent = "complex" if score >= 3 else "simple"
    logger.info(f"🎯 [意图分类] score={score} → {intent} | query: {query[:60]}")
    return intent
