"""
任务分解器 (TaskDecomposer)

负责将复杂任务分解为多个可并行/串行执行的子任务
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from src.core.sub_agent.models import TaskDecomposition, SubTask

logger = logging.getLogger(__name__)


class TaskDecomposer:
    """
    任务分解器
    
    使用 LLM 将复杂任务智能分解为多个子任务，支持：
    - 并行任务分解
    - 串行任务分解
    - 混合策略分解
    """
    
    def __init__(self, llm: ChatOpenAI, max_sub_tasks: int = 10):
        """
        初始化任务分解器
        
        Args:
            llm: LLM 客户端
            max_sub_tasks: 最大子任务数量
        """
        self.llm = llm
        self.max_sub_tasks = max_sub_tasks
    
    async def decompose(
        self, 
        task: str,
        strategy: str = "auto",
        context: Optional[Dict[str, Any]] = None
    ) -> TaskDecomposition:
        """
        分解任务为子任务
        
        Args:
            task: 原始任务描述
            strategy: 分解策略 (parallel/sequential/hybrid/auto)
            context: 额外上下文信息
        
        Returns:
            TaskDecomposition: 任务分解结果
        """
        logger.info(f"🔪 [任务分解] 开始分解任务: {task[:100]}...")
        logger.info(f"   策略: {strategy}, 最大子任务数: {self.max_sub_tasks}")
        
        # 自动选择策略
        if strategy == "auto":
            strategy = await self._select_strategy(task)
            logger.info(f"   自动选择策略: {strategy}")
        
        # 构建分解提示词
        prompt = self._build_decomposition_prompt(task, strategy, context)
        
        # 调用 LLM 进行分解
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="你是一个专业的任务规划师，擅长将复杂任务分解为可执行的子任务。"),
                HumanMessage(content=prompt)
            ])
            
            # 解析 LLM 响应
            decomposition = self._parse_decomposition_response(
                response.content, task, strategy
            )
            
            logger.info(f"✅ [任务分解] 成功分解为 {len(decomposition.sub_tasks)} 个子任务")
            for i, sub_task in enumerate(decomposition.sub_tasks, 1):
                logger.info(f"   {i}. {sub_task.title} (顺序: {sub_task.execution_order})")
            
            return decomposition
            
        except Exception as e:
            logger.error(f"❌ [任务分解] 分解失败: {e}", exc_info=True)
            # 返回默认分解 (单个任务)
            return self._create_fallback_decomposition(task)
    
    async def _select_strategy(self, task: str) -> str:
        """自动选择分解策略"""
        # 简单启发式规则
        task_lower = task.lower()
        
        # 包含多个独立主题 -> 并行
        if any(keyword in task_lower for keyword in ["对比", "比较", "分析", "多个", "分别"]):
            return "parallel"
        
        # 包含步骤、流程 -> 串行
        if any(keyword in task_lower for keyword in ["步骤", "流程", "依次", "然后", "接着"]):
            return "sequential"
        
        # 默认混合策略
        return "hybrid"
    
    def _build_decomposition_prompt(
        self, 
        task: str, 
        strategy: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建任务分解提示词"""
        
        strategy_descriptions = {
            "parallel": "将任务分解为可以并行执行的独立子任务",
            "sequential": "将任务分解为需要按顺序执行的依赖子任务",
            "hybrid": "将任务分解为部分并行、部分串行的混合子任务"
        }
        
        prompt = f"""
请将以下任务分解为多个可执行的子任务：

**原始任务**:
{task}

**分解策略**: {strategy}
**策略说明**: {strategy_descriptions.get(strategy, "")}

**要求**:
1. 子任务数量不超过 {self.max_sub_tasks} 个
2. 每个子任务应该有明确的目标和输出
3. 子任务之间应该尽量独立 (如果是并行策略)
4. 为每个子任务指定需要的工具 (如果有特殊需求)

**输出格式** (JSON):
```json
{{
  "sub_tasks": [
    {{
      "title": "子任务标题",
      "description": "子任务详细描述，包括执行步骤和期望输出",
      "execution_order": 1,
      "required_tools": ["tool1", "tool2"],
      "expected_output": "期望的输出格式描述"
    }}
  ],
  "estimated_time": 60,
  "notes": "分解说明或注意事项"
}}
```

请只输出 JSON，不要其他内容。
"""
        
        if context:
            prompt += f"\n**额外上下文**:\n{context}\n"
        
        return prompt
    
    def _parse_decomposition_response(
        self, 
        response: str, 
        original_task: str,
        strategy: str
    ) -> TaskDecomposition:
        """解析 LLM 的分解响应"""
        import json
        import re
        
        try:
            # 提取 JSON
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response
            
            data = json.loads(json_str)
            
            # 构建子任务列表
            sub_tasks = []
            for i, task_data in enumerate(data.get("sub_tasks", []), 1):
                sub_task = SubTask(
                    task_id=f"task_{uuid.uuid4().hex[:8]}",
                    title=task_data.get("title", f"子任务 {i}"),
                    description=task_data.get("description", ""),
                    execution_order=task_data.get("execution_order", 1),
                    required_tools=task_data.get("required_tools", []),
                    expected_output=task_data.get("expected_output", ""),
                    metadata={"index": i}
                )
                sub_tasks.append(sub_task)
            
            # 如果没有解析出子任务，创建默认任务
            if not sub_tasks:
                return self._create_fallback_decomposition(original_task)
            
            return TaskDecomposition(
                original_task=original_task,
                sub_tasks=sub_tasks,
                decomposition_strategy=strategy,
                estimated_time=data.get("estimated_time", 0),
                metadata={"notes": data.get("notes", "")}
            )
            
        except Exception as e:
            logger.warning(f"⚠️ 解析分解响应失败: {e}，使用默认分解")
            return self._create_fallback_decomposition(original_task)
    
    def _create_fallback_decomposition(self, task: str) -> TaskDecomposition:
        """创建默认的后备分解 (单任务)"""
        return TaskDecomposition(
            original_task=task,
            sub_tasks=[
                SubTask(
                    task_id=f"task_{uuid.uuid4().hex[:8]}",
                    title="执行任务",
                    description=task,
                    execution_order=1,
                    required_tools=[],
                    expected_output=""
                )
            ],
            decomposition_strategy="sequential",
            estimated_time=0,
            metadata={"fallback": True}
        )
