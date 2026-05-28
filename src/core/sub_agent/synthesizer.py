"""
结果合成器 (ResultSynthesizer)

将多个 Sub-Agent 的结果合成为最终的结构化报告
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.core.sub_agent.models import (
    SubAgentResult, 
    SubAgentStatus, 
    TaskDecomposition,
    OrchestratorResult
)

logger = logging.getLogger(__name__)


class ResultSynthesizer:
    """
    结果合成器
    
    负责将多个 Sub-Agent 的执行结果合成为统一的最终报告，支持：
    - Markdown 格式合成
    - JSON 格式合成
    - 纯文本合成
    - 智能摘要生成
    """
    
    def __init__(self, llm: ChatOpenAI, output_format: str = "markdown"):
        """
        初始化结果合成器
        
        Args:
            llm: LLM 客户端
            output_format: 输出格式 (markdown/json/text)
        """
        self.llm = llm
        self.output_format = output_format
    
    async def synthesize(
        self,
        original_task: str,
        sub_agent_results: List[SubAgentResult],
        decomposition: Optional[TaskDecomposition] = None
    ) -> str:
        """
        合成多个 Sub-Agent 的结果
        
        Args:
            original_task: 原始任务
            sub_agent_results: Sub-Agent 结果列表
            decomposition: 任务分解信息
        
        Returns:
            str: 合成后的结果
        """
        logger.info(f"🔗 [结果合成] 开始合成 {len(sub_agent_results)} 个子任务结果")
        logger.info(f"   输出格式: {self.output_format}")
        
        # 统计执行情况
        success_count = sum(1 for r in sub_agent_results if r.status == SubAgentStatus.COMPLETED)
        failed_count = sum(1 for r in sub_agent_results if r.status == SubAgentStatus.FAILED)
        
        logger.info(f"   成功: {success_count}, 失败: {failed_count}")
        
        # 根据格式选择合成策略
        if self.output_format == "json":
            return await self._synthesize_json(original_task, sub_agent_results, decomposition)
        elif self.output_format == "text":
            return await self._synthesize_text(original_task, sub_agent_results, decomposition)
        else:  # markdown (默认)
            return await self._synthesize_markdown(original_task, sub_agent_results, decomposition)
    
    async def _synthesize_markdown(
        self,
        original_task: str,
        sub_agent_results: List[SubAgentResult],
        decomposition: Optional[TaskDecomposition]
    ) -> str:
        """合成为 Markdown 格式"""
        
        # 构建合成提示词
        prompt = self._build_markdown_synthesis_prompt(original_task, sub_agent_results, decomposition)
        
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="你是一个专业的报告撰写助手，擅长将多个信息源整合为结构化的报告。"),
                HumanMessage(content=prompt)
            ])
            
            synthesized = response.content
            logger.info(f"✅ [结果合成] 合成完成，结果长度: {len(synthesized)} 字符")
            
            return synthesized
            
        except Exception as e:
            logger.error(f"❌ [结果合成] LLM 合成失败: {e}，使用简单拼接")
            return self._simple_concat_markdown(original_task, sub_agent_results, decomposition)
    
    def _build_markdown_synthesis_prompt(
        self,
        original_task: str,
        sub_agent_results: List[SubAgentResult],
        decomposition: Optional[TaskDecomposition]
    ) -> str:
        """构建 Markdown 合成提示词"""
        
        prompt = f"""
请将以下多个子任务的执行结果整合为一份完整的报告。

**原始任务**:
{original_task}

**子任务执行结果**:
"""
        
        for i, result in enumerate(sub_agent_results, 1):
            prompt += f"\n---\n\n### 子任务 {i}: {result.task_id}\n"
            prompt += f"**状态**: {result.status.value}\n"
            
            if result.status == SubAgentStatus.COMPLETED:
                prompt += f"**结果**:\n{result.result}\n"
            elif result.error:
                prompt += f"**错误**: {result.error}\n"
            
            if result.duration > 0:
                prompt += f"**耗时**: {result.duration:.2f}秒\n"
        
        prompt += """
**合成要求**:
1. 生成一份结构清晰、逻辑连贯的完整报告
2. 使用 Markdown 格式
3. 包含以下部分：
   - 任务概述 (原始任务说明)
   - 执行摘要 (关键发现总结)
   - 详细分析 (整合各子任务结果)
   - 结论与建议
   - 附录 (执行情况统计)
4. 如果某些子任务失败，在报告中说明
5. 确保内容完整、专业、易读

请生成完整的报告。
"""
        
        return prompt
    
    def _simple_concat_markdown(
        self,
        original_task: str,
        sub_agent_results: List[SubAgentResult],
        decomposition: Optional[TaskDecomposition]
    ) -> str:
        """简单拼接 Markdown (后备方案)"""
        
        report = f"# 任务执行报告\n\n"
        report += f"## 原始任务\n{original_task}\n\n"
        report += f"## 执行结果\n\n"
        
        for i, result in enumerate(sub_agent_results, 1):
            report += f"### 子任务 {i}\n"
            report += f"**状态**: {result.status.value}\n\n"
            
            if result.result:
                report += f"{result.result}\n\n"
            elif result.error:
                report += f"**错误**: {result.error}\n\n"
        
        # 添加统计信息
        report += f"## 执行统计\n"
        success_count = sum(1 for r in sub_agent_results if r.status == SubAgentStatus.COMPLETED)
        report += f"- 总任务数: {len(sub_agent_results)}\n"
        report += f"- 成功: {success_count}\n"
        report += f"- 失败: {len(sub_agent_results) - success_count}\n"
        
        total_duration = sum(r.duration for r in sub_agent_results)
        report += f"- 总耗时: {total_duration:.2f}秒\n"
        
        return report
    
    async def _synthesize_json(
        self,
        original_task: str,
        sub_agent_results: List[SubAgentResult],
        decomposition: Optional[TaskDecomposition]
    ) -> str:
        """合成为 JSON 格式"""
        import json
        
        # 构建结构化数据
        synthesis = {
            "original_task": original_task,
            "summary": "",
            "sub_tasks": [],
            "statistics": {
                "total": len(sub_agent_results),
                "success": sum(1 for r in sub_agent_results if r.status == SubAgentStatus.COMPLETED),
                "failed": sum(1 for r in sub_agent_results if r.status == SubAgentStatus.FAILED),
                "total_duration": sum(r.duration for r in sub_agent_results)
            }
        }
        
        for result in sub_agent_results:
            synthesis["sub_tasks"].append({
                "task_id": result.task_id,
                "status": result.status.value,
                "result": result.result,
                "error": result.error,
                "duration": result.duration
            })
        
        # 使用 LLM 生成摘要
        try:
            summary_prompt = f"""
基于以下执行结果，生成一段简洁的摘要 (200字以内):

原始任务: {original_task}
成功: {synthesis['statistics']['success']}
失败: {synthesis['statistics']['failed']}

请只输出摘要内容。
"""
            response = await self.llm.ainvoke([HumanMessage(content=summary_prompt)])
            synthesis["summary"] = response.content
        except:
            synthesis["summary"] = "任务执行完成"
        
        return json.dumps(synthesis, ensure_ascii=False, indent=2)
    
    async def _synthesize_text(
        self,
        original_task: str,
        sub_agent_results: List[SubAgentResult],
        decomposition: Optional[TaskDecomposition]
    ) -> str:
        """合成为纯文本格式"""
        
        report = f"任务执行报告\n"
        report += f"{'='*60}\n\n"
        report += f"原始任务:\n{original_task}\n\n"
        report += f"执行结果:\n{'-'*60}\n\n"
        
        for i, result in enumerate(sub_agent_results, 1):
            report += f"[子任务 {i}] {result.status.value}\n"
            if result.result:
                report += f"{result.result}\n\n"
            elif result.error:
                report += f"错误: {result.error}\n\n"
        
        report += f"{'-'*60}\n"
        report += f"统计: {len(sub_agent_results)} 个子任务, "
        report += f"总耗时 {sum(r.duration for r in sub_agent_results):.2f}秒\n"
        
        return report
