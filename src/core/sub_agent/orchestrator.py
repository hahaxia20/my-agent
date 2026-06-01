"""
Sub-Agent 编排器 (SubAgentOrchestrator)

核心编排逻辑，协调任务分解、并行执行和结果合成
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.tools import StructuredTool
from langsmith import traceable

from src.core.sub_agent.models import (
    SubAgentConfig,
    SubAgentStatus,
    TaskDecomposition,
    SubAgentResult,
    OrchestratorResult
)
from src.core.sub_agent.decomposer import TaskDecomposer
from src.core.sub_agent.worker import SubAgentWorker
from src.core.sub_agent.synthesizer import ResultSynthesizer

logger = logging.getLogger(__name__)


class SubAgentOrchestrator:
    """
    Sub-Agent 编排器
    
    负责整个 Sub-Agent 系统的协调工作：
    1. 接收复杂任务
    2. 使用 TaskDecomposer 分解任务
    3. 使用 SubAgentWorker 并行/串行执行子任务
    4. 使用 ResultSynthesizer 合成最终结果
    
    类似 DeerFlow 的 Lead Agent 角色
    """
    
    def __init__(
        self,
        llm: ChatOpenAI,
        tools: List[StructuredTool],
        config: Optional[SubAgentConfig] = None
    ):
        """
        初始化编排器
        
        Args:
            llm: LLM 客户端
            tools: 可用工具列表
            config: 编排器配置
        """
        self.llm = llm
        self.tools = tools
        self.config = config or SubAgentConfig()
        
        # 初始化子组件
        self.decomposer = TaskDecomposer(
            llm=self.llm,
            max_sub_tasks=self.config.max_sub_tasks
        )
        
        self.worker = SubAgentWorker(
            llm=self.llm,
            tools=self.tools,
            timeout=self.config.sub_agent_timeout,
            max_retries=self.config.max_retries
        )
        
        self.synthesizer = ResultSynthesizer(
            llm=self.llm,
            output_format=self.config.synthesis_format
        )
        
        logger.info(f"🎭 [编排器] 初始化完成 - 最大并发: {self.config.max_concurrent_agents}")
    
    @traceable(name="sub_agent_orchestrator", tags=["production", "orchestration"])
    async def execute(
        self,
        task: str,
        session_id: Optional[str] = None,
        user_id: str = "anonymous",
        decomposition_strategy: str = "auto",
        progress_callback=None,
        context: Optional[str] = None
    ) -> OrchestratorResult:
        """
        执行复杂任务 (完整流程)
        
        Args:
            task: 复杂任务描述（纯任务，不含历史）
            session_id: 会话 ID
            user_id: 用户 ID
            decomposition_strategy: 分解策略
            progress_callback: 进度回调函数 async callback(event_type, data)
            context: 对话历史背景（仅供 Decomposer 理解意图，不作为子任务执行）
        
        Returns:
            OrchestratorResult: 最终编排结果
        """
        logger.info(f"🎭 [编排器] 开始执行复杂任务: {task[:100]}...")
        
        start_time = time.time()
        
        # 初始化结果
        orchestrator_result = OrchestratorResult(
            success=False,
            original_task=task
        )
        
        try:
            # ═══════════════════════════════════════════════════════
            # 步骤 1: 任务分解
            # ═══════════════════════════════════════════════════════
            logger.info("")
            logger.info("━" * 80)
            logger.info("📋 步骤 1/4: 任务分解")
            logger.info("━" * 80)
            
            if progress_callback:
                await progress_callback("decompose_start", {"task": task})
            
            decomposition = await self._decompose_task(task, decomposition_strategy, context=context)
            orchestrator_result.decomposition = decomposition
            
            if progress_callback:
                await progress_callback("decompose_complete", {
                    "sub_tasks_count": len(decomposition.sub_tasks),
                    "sub_tasks": [
                        {"id": st.task_id, "title": st.title, "description": st.description}
                        for st in decomposition.sub_tasks
                    ]
                })
            
            if not decomposition.sub_tasks:
                raise ValueError("任务分解失败：未生成子任务")
            
            # 打印分解结果
            logger.info(f"✅ 任务分解完成，生成 {len(decomposition.sub_tasks)} 个子任务:")
            for i, st in enumerate(decomposition.sub_tasks, 1):
                logger.info(f"   {i}. {st.title} (顺序: {st.execution_order})")
            logger.info("")
            
            # ═══════════════════════════════════════════════════════
            # 步骤 2: 执行子任务
            # ═══════════════════════════════════════════════════════
            logger.info("━" * 80)
            logger.info("🚀 步骤 2/4: 执行子任务")
            logger.info("━" * 80)
            
            if progress_callback:
                await progress_callback("execution_start", {
                    "total_tasks": len(decomposition.sub_tasks)
                })
            
            sub_agent_results = await self._execute_sub_tasks(
                decomposition, session_id, user_id, progress_callback
            )
            orchestrator_result.sub_agent_results = sub_agent_results
            
            # 检查是否有成功执行的任务
            success_count = sum(
                1 for r in sub_agent_results 
                if r.status == SubAgentStatus.COMPLETED
            )
            
            if progress_callback:
                await progress_callback("execution_complete", {
                    "success_count": success_count,
                    "total_count": len(sub_agent_results)
                })
            
            # 打印执行结果
            logger.info("")
            logger.info(f"✅ 子任务执行完成: {success_count}/{len(sub_agent_results)} 成功")
            for i, r in enumerate(sub_agent_results, 1):
                status_icon = "✅" if r.status == SubAgentStatus.COMPLETED else "❌"
                logger.info(f"   {status_icon} 子任务 {i}: {r.task_id} - {r.status.value} ({r.duration:.1f}s)")
            logger.info("")
            
            if success_count == 0:
                raise RuntimeError("所有子任务执行失败")
            
            # ═══════════════════════════════════════════════════════
            # 步骤 3: 结果合成
            # ═══════════════════════════════════════════════════════
            logger.info("━" * 80)
            logger.info("🔗 步骤 3/4: 结果合成")
            logger.info("━" * 80)
            
            if self.config.enable_synthesis:
                if progress_callback:
                    await progress_callback("synthesis_start", {"format": self.config.synthesis_format})
                
                synthesized_result = await self.synthesizer.synthesize(
                    original_task=task,
                    sub_agent_results=sub_agent_results,
                    decomposition=decomposition
                )
                orchestrator_result.synthesized_result = synthesized_result
                
                if progress_callback:
                    await progress_callback("synthesis_complete", {
                        "result_length": len(synthesized_result)
                    })
                
                logger.info(f"✅ 结果合成完成: {len(synthesized_result)} 字符")
                logger.info("")
            else:
                # 简单拼接
                orchestrator_result.synthesized_result = self._concat_results(sub_agent_results)
                logger.info("✅ 结果已拼接 (未启用智能合成)")
                logger.info("")
            
            # ═══════════════════════════════════════════════════════
            # 步骤 4: 计算统计信息
            # ═══════════════════════════════════════════════════════
            logger.info("━" * 80)
            logger.info("📊 步骤 4/4: 生成统计报告")
            logger.info("━" * 80)
            
            orchestrator_result.success = True
            orchestrator_result.total_duration = time.time() - start_time
            orchestrator_result.parallel_efficiency = self._calculate_parallel_efficiency(
                sub_agent_results, orchestrator_result.total_duration
            )
            
            logger.info(f"✅ 任务执行完成!")
            logger.info(f"   ⏱️ 总耗时: {orchestrator_result.total_duration:.2f}s")
            logger.info(f"   ⚡ 并行效率: {orchestrator_result.parallel_efficiency:.2%}")
            logger.info(f"   📝 结果长度: {len(orchestrator_result.synthesized_result)} 字符")
            logger.info("━" * 80)
            logger.info("")
            
            return orchestrator_result
            
        except Exception as e:
            logger.error(f"❌ [编排器] 任务执行失败: {e}", exc_info=True)
            orchestrator_result.success = False
            orchestrator_result.error = str(e)
            orchestrator_result.total_duration = time.time() - start_time
            return orchestrator_result
    
    async def _decompose_task(
        self, 
        task: str, 
        strategy: str,
        context: Optional[str] = None
    ) -> TaskDecomposition:
        """步骤 1: 分解任务
        
        Args:
            task: 纯任务描述
            strategy: 分解策略
            context: 对话历史背景（传给 Decomposer，帮助理解意图）
        """
        if not self.config.enable_decomposition:
            # 不分解，直接创建单任务
            from src.core.sub_agent.models import SubTask
            import uuid
            
            return TaskDecomposition(
                original_task=task,
                sub_tasks=[
                    SubTask(
                        task_id=f"task_{uuid.uuid4().hex[:8]}",
                        title="执行任务",
                        description=task,
                        execution_order=1
                    )
                ],
                decomposition_strategy="sequential"
            )
        
        return await self.decomposer.decompose(
            task,
            strategy,
            context={"conversation_history": context} if context else None
        )
    
    async def _execute_sub_tasks(
        self,
        decomposition: TaskDecomposition,
        session_id: Optional[str],
        user_id: str,
        progress_callback=None  # 新增进度回调
    ) -> List[SubAgentResult]:
        """步骤 2: 执行子任务 (支持并行/串行)"""
        
        # 按执行顺序分组
        task_groups = self._group_tasks_by_order(decomposition.sub_tasks)
        
        all_results = []
        
        for order, tasks in task_groups.items():
            execution_type = "并行" if order == 1 else "串行"
            logger.info(f"▶️ 执行组 {order} ({execution_type}): {len(tasks)} 个任务")
            
            if order == 1:
                # 并行执行
                results = await self._execute_parallel(tasks, session_id, user_id, progress_callback)
            else:
                # 串行执行
                results = await self._execute_sequential(tasks, session_id, user_id, progress_callback)
            
            all_results.extend(results)
            
            # 打印该组结果
            success_in_group = sum(1 for r in results if r.status == SubAgentStatus.COMPLETED)
            logger.info(f"   ✅ 组 {order} 完成: {success_in_group}/{len(results)} 成功")
            logger.info("")
            
            # 检查是否有必要继续
            failed_count = sum(1 for r in results if r.status == SubAgentStatus.FAILED)
            if failed_count == len(results):
                logger.warning(f"⚠️ [编排器] 顺序 {order} 所有任务失败，停止执行")
                break
        
        return all_results
    
    async def _execute_parallel(
        self,
        tasks,
        session_id: Optional[str],
        user_id: str,
        progress_callback=None
    ) -> List[SubAgentResult]:
        """并行执行任务组"""
        
        # 使用 Semaphore 控制并发数
        semaphore = asyncio.Semaphore(self.config.max_concurrent_agents)
        
        async def run_with_semaphore(task):
            # 通知任务开始
            if progress_callback:
                await progress_callback("subtask_start", {
                    "task_id": task.task_id,
                    "task_name": task.title,
                    "description": task.description
                })
            
            async with semaphore:
                result = await self.worker.execute(task, session_id)
                
                # 通知任务完成
                if progress_callback:
                    await progress_callback("subtask_complete", {
                        "task_id": result.task_id,
                        "task_name": task.title,
                        "status": result.status.value,
                        "duration": result.duration,
                        "result_length": len(result.result) if result.result else 0,
                        "result_preview": result.result[:200] if result.result else None
                    })
                
                return result
        
        # 并发执行
        results = await asyncio.gather(
            *[run_with_semaphore(task) for task in tasks],
            return_exceptions=True
        )
        
        # 处理异常
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ 并行任务 {tasks[i].task_id} 异常: {result}")
                
                # 通知任务失败
                if progress_callback:
                    await progress_callback("subtask_failed", {
                        "task_id": tasks[i].task_id,
                        "task_name": tasks[i].title,
                        "error": str(result)
                    })
                
                final_results.append(SubAgentResult(
                    task_id=tasks[i].task_id,
                    status=SubAgentStatus.FAILED,
                    error=str(result)
                ))
            else:
                final_results.append(result)
        
        return final_results
    
    async def _execute_sequential(
        self,
        tasks,
        session_id: Optional[str],
        user_id: str,
        progress_callback=None
    ) -> List[SubAgentResult]:
        """串行执行任务组"""
        results = []
        
        for task in tasks:
            # 通知任务开始
            if progress_callback:
                await progress_callback("subtask_start", {
                    "task_id": task.task_id,
                    "task_name": task.title,
                    "description": task.description
                })
            
            result = await self.worker.execute(task, session_id)
            
            # 通知任务完成/失败
            if progress_callback:
                if result.status == SubAgentStatus.COMPLETED:
                    await progress_callback("subtask_complete", {
                        "task_id": result.task_id,
                        "task_name": task.title,
                        "status": result.status.value,
                        "duration": result.duration,
                        "result_length": len(result.result) if result.result else 0,
                        "result_preview": result.result[:200] if result.result else None
                    })
                else:
                    await progress_callback("subtask_failed", {
                        "task_id": result.task_id,
                        "task_name": task.title,
                        "error": result.error
                    })
            
            results.append(result)
            
            # 如果失败，可以选择是否继续
            if result.status == SubAgentStatus.FAILED:
                logger.warning(f"⚠️ 串行任务 {task.task_id} 失败")
        
        return results
    
    def _group_tasks_by_order(self, tasks):
        """按执行顺序分组任务"""
        groups = {}
        for task in tasks:
            order = task.execution_order
            if order not in groups:
                groups[order] = []
            groups[order].append(task)
        
        return dict(sorted(groups.items()))
    
    def _calculate_parallel_efficiency(
        self,
        results: List[SubAgentResult],
        total_duration: float
    ) -> float:
        """
        计算并行效率
        
        效率 = 串行总时间 / (并行时间 * 任务数)
        范围: 0-1, 越接近 1 表示并行效果越好
        """
        if not results or total_duration == 0:
            return 0.0
        
        sequential_time = sum(r.duration for r in results)
        parallel_time = total_duration
        
        # 理想情况下 parallel_time = sequential_time / n
        # 效率 = sequential_time / (parallel_time * n)
        efficiency = sequential_time / (parallel_time * len(results))
        
        return min(1.0, efficiency)  # 限制在 0-1 之间
    
    def _concat_results(self, results: List[SubAgentResult]) -> str:
        """简单拼接结果 (不启用合成时)"""
        parts = []
        for i, result in enumerate(results, 1):
            parts.append(f"## 子任务 {i}\n\n{result.result or result.error or '无结果'}\n")
        
        return "\n".join(parts)
