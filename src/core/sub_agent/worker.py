"""
Sub-Agent 工作器 (SubAgentWorker)

负责执行单个子任务，封装独立的 Agent 执行环境
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain.agents import create_agent

from src.core.sub_agent.models import SubTask, SubAgentResult, SubAgentStatus

logger = logging.getLogger(__name__)


class SubAgentWorker:
    """
    Sub-Agent 工作器
    
    为每个子任务创建独立的执行环境，支持：
    - 隔离的上下文
    - 定制的工具集
    - 超时控制
    - 重试机制
    """
    
    def __init__(
        self, 
        llm: ChatOpenAI,
        tools: List[StructuredTool],
        timeout: int = 300,
        max_retries: int = 2
    ):
        """
        初始化 Sub-Agent 工作器
        
        Args:
            llm: LLM 客户端
            tools: 可用工具列表
            timeout: 超时时间 (秒)
            max_retries: 最大重试次数
        """
        self.llm = llm
        self.available_tools = tools
        self.timeout = timeout
        self.max_retries = max_retries
    
    async def execute(
        self, 
        sub_task: SubTask,
        session_id: Optional[str] = None,
        custom_prompt: Optional[str] = None
    ) -> SubAgentResult:
        """
        执行子任务
        
        Args:
            sub_task: 子任务定义
            session_id: 会话 ID (用于追踪)
            custom_prompt: 自定义系统提示词
        
        Returns:
            SubAgentResult: 执行结果
        """
        logger.info(f"🤖 [Sub-Agent] 开始执行: {sub_task.title}")
        logger.info(f"   任务 ID: {sub_task.task_id}")
        logger.info(f"   描述: {sub_task.description[:100]}...")
        logger.info(f"   需要工具: {sub_task.required_tools}")
        
        # 初始化结果
        result = SubAgentResult(
            task_id=sub_task.task_id,
            status=SubAgentStatus.PENDING,
            start_time=datetime.now()
        )
        
        # 选择适合的工具
        task_tools = self._select_tools_for_task(sub_task)
        logger.info(f"   分配工具: {[t.name for t in task_tools]}")
        logger.info("")
        
        # 创建专用 Agent
        agent = self._create_sub_agent(task_tools, custom_prompt)
        
        # 执行任务 (带重试)
        for attempt in range(1, self.max_retries + 1):
            try:
                result.status = SubAgentStatus.RUNNING
                logger.info(f"   尝试 {attempt}/{self.max_retries}")
                
                # 构建配置
                config = self._build_config(session_id, sub_task)
                
                # 执行
                response = await agent.ainvoke(
                    {"messages": [HumanMessage(content=sub_task.description)]},
                    config=config
                )
                
                # 提取结果
                last_message = response["messages"][-1]
                result.result = last_message.content if hasattr(last_message, 'content') else str(last_message)
                result.status = SubAgentStatus.COMPLETED
                
                # 记录性能
                result.end_time = datetime.now()
                result.duration = (result.end_time - result.start_time).total_seconds()
                
                # 提取 token 使用
                if "total_usage" in response:
                    result.token_usage = response["total_usage"]
                
                logger.info(
                    f"✅ [Sub-Agent] 任务完成: {sub_task.title}"
                )
                logger.info(f"   耗时: {result.duration:.2f}s")
                logger.info(f"   结果长度: {len(result.result)} 字符")
                logger.info(f"   Token 使用: {result.token_usage}")
                logger.info("")
                
                return result
                
            except Exception as e:
                logger.error(
                    f"❌ [Sub-Agent] 执行失败 (尝试 {attempt}/{self.max_retries}): "
                    f"{sub_task.title} - {str(e)}",
                    exc_info=True
                )
                
                if attempt < self.max_retries:
                    logger.info(f"   等待重试...")
                    continue
                else:
                    result.status = SubAgentStatus.FAILED
                    result.error = str(e)
                    result.end_time = datetime.now()
                    result.duration = (result.end_time - result.start_time).total_seconds()
                    
                    logger.error(f"💥 [Sub-Agent] 任务失败: {sub_task.title}")
                    return result
        
        return result
    
    def _select_tools_for_task(self, sub_task: SubTask) -> List[StructuredTool]:
        """为任务选择合适的工具"""
        if not sub_task.required_tools:
            # 如果没有指定，返回所有工具
            return self.available_tools
        
        # 根据名称匹配工具
        selected = []
        for tool in self.available_tools:
            if tool.name in sub_task.required_tools:
                selected.append(tool)
        
        # 如果没找到指定的工具，返回所有工具
        return selected if selected else self.available_tools
    
    def _create_sub_agent(
        self, 
        tools: List[StructuredTool],
        custom_prompt: Optional[str] = None
    ):
        """创建专用的 Sub-Agent"""
        
        # 构建系统提示词
        system_prompt = custom_prompt or self._build_system_prompt()
        
        logger.debug(f"📝 [Sub-Agent] 系统提示词: {system_prompt[:200]}...")
        
        return create_agent(
            model=self.llm,
            tools=tools,
            system_prompt=system_prompt,
            name="sub_agent"
        )
    
    def _build_system_prompt(self) -> str:
        """构建 Sub-Agent 系统提示词"""
        return """你是一个专业的任务执行助手。

你的职责：
1. 专注完成分配给你的具体任务
2. 使用提供的工具收集信息和执行操作
3. 输出清晰、结构化、完整的结果
4. 如果遇到问题，说明原因并给出建议

要求：
- 结果应该详细且准确
- 使用 Markdown 格式组织内容
- 如果使用了工具，简要说明使用过程
- 确保结果可以直接被整合到最终报告中"""
    
    def _build_config(
        self, 
        session_id: Optional[str],
        sub_task: SubTask
    ) -> RunnableConfig:
        """构建执行配置"""
        import uuid
        
        thread_id = session_id or f"sub_{uuid.uuid4().hex[:12]}"
        
        return RunnableConfig(
            configurable={"thread_id": thread_id},
            metadata={
                "task_id": sub_task.task_id,
                "task_title": sub_task.title,
                "agent_type": "sub_agent"
            },
            tags=["sub_agent"],
            recursion_limit=30  # Sub-Agent 递归限制较低
        )
