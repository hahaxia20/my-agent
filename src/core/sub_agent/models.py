"""
Sub-Agent 数据模型

定义 Sub-Agent 系统使用的核心数据结构
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class SubAgentStatus(str, Enum):
    """Sub-Agent 执行状态"""
    PENDING = "pending"          # 等待执行
    RUNNING = "running"          # 执行中
    COMPLETED = "completed"      # 成功完成
    FAILED = "failed"            # 执行失败
    CANCELLED = "cancelled"      # 已取消


class SubAgentConfig(BaseModel):
    """Sub-Agent 配置"""
    
    # 基础配置
    max_concurrent_agents: int = Field(
        default=5, 
        description="最大并行 Sub-Agent 数量"
    )
    sub_agent_timeout: int = Field(
        default=300, 
        description="单个 Sub-Agent 超时时间 (秒)"
    )
    max_retries: int = Field(
        default=2, 
        description="失败重试次数"
    )
    
    # 任务分解配置
    enable_decomposition: bool = Field(
        default=True, 
        description="启用任务自动分解"
    )
    max_sub_tasks: int = Field(
        default=10, 
        description="最大子任务数量"
    )
    
    # 结果合成配置
    enable_synthesis: bool = Field(
        default=True, 
        description="启用结果自动合成"
    )
    synthesis_format: str = Field(
        default="markdown", 
        description="合成结果格式 (markdown/json/text)"
    )
    
    # 调试配置
    debug: bool = Field(
        default=False, 
        description="调试模式"
    )
    enable_logging: bool = Field(
        default=True, 
        description="启用详细日志"
    )


class SubTask(BaseModel):
    """子任务定义"""
    
    task_id: str = Field(..., description="任务唯一 ID")
    title: str = Field(..., description="任务标题")
    description: str = Field(..., description="任务详细描述")
    execution_order: int = Field(
        default=1, 
        description="执行顺序 (1=并行, >1=串行)"
    )
    required_tools: List[str] = Field(
        default_factory=list, 
        description="需要的工具列表"
    )
    expected_output: str = Field(
        default="", 
        description="期望的输出格式"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="额外元数据"
    )


class TaskDecomposition(BaseModel):
    """任务分解结果"""
    
    original_task: str = Field(..., description="原始任务")
    sub_tasks: List[SubTask] = Field(..., description="子任务列表")
    decomposition_strategy: str = Field(
        default="parallel", 
        description="分解策略 (parallel/sequential/hybrid)"
    )
    estimated_time: int = Field(
        default=0, 
        description="预估执行时间 (秒)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="额外元数据"
    )


class SubAgentResult(BaseModel):
    """Sub-Agent 执行结果"""
    
    task_id: str = Field(..., description="任务 ID")
    status: SubAgentStatus = Field(..., description="执行状态")
    result: str = Field(default="", description="执行结果内容")
    error: Optional[str] = Field(default=None, description="错误信息")
    
    # 性能指标
    start_time: Optional[datetime] = Field(default=None, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    duration: float = Field(default=0.0, description="执行耗时 (秒)")
    
    # 资源使用
    tools_used: List[str] = Field(default_factory=list, description="使用的工具")
    token_usage: Dict[str, int] = Field(
        default_factory=lambda: {"prompt": 0, "completion": 0, "total": 0},
        description="Token 使用情况"
    )
    
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class OrchestratorResult(BaseModel):
    """编排器最终结果"""
    
    success: bool = Field(..., description="是否成功")
    original_task: str = Field(..., description="原始任务")
    
    # 分解信息
    decomposition: Optional[TaskDecomposition] = Field(
        default=None, 
        description="任务分解结果"
    )
    
    # Sub-Agent 结果
    sub_agent_results: List[SubAgentResult] = Field(
        default_factory=list, 
        description="所有 Sub-Agent 结果"
    )
    
    # 合成结果
    synthesized_result: str = Field(default="", description="合成后的最终结果")
    
    # 性能统计
    total_duration: float = Field(default=0.0, description="总执行时间 (秒)")
    parallel_efficiency: float = Field(
        default=0.0, 
        description="并行效率 (0-1, 越高越好)"
    )
    
    # 错误信息
    error: Optional[str] = Field(default=None, description="错误信息")
    
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")
