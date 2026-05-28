"""
对话历史上下文管理器

负责：
1. 从数据库加载历史消息
2. 转换为 LangChain Message 格式
3. 上下文裁剪（基于 token 数量或消息数量）
4. 上下文压缩（对旧消息生成摘要）
"""

from typing import List, Optional, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
import logging

from src.core.logging_decorator import log_method_call

logger = logging.getLogger(__name__)


class ConversationContextManager:
    """对话历史上下文管理器
    
    生产级实现：
    - 智能加载历史消息
    - Token 级别的上下文控制
    - 支持上下文压缩策略
    """
    
    def __init__(
        self,
        db_manager=None,
        max_messages: int = 50,
        max_tokens: int = 8000,
        enable_compression: bool = False,
        keep_recent_messages: int = 20,
        enable_ai_summary: bool = True,
        summary_max_length: int = 200,
        chinese_token_ratio: float = 1.5,
        english_token_ratio: float = 0.75
    ):
        """
        初始化对话上下文管理器
        
        Args:
            db_manager: 数据库管理器实例
            max_messages: 最大消息数量限制
            max_tokens: 最大 token 数量限制
            enable_compression: 是否启用上下文压缩
            keep_recent_messages: 保留最近的消息数量
            enable_ai_summary: 是否启用 AI 智能摘要
            summary_max_length: 摘要最大长度
            chinese_token_ratio: 中文字符 token 比例
            english_token_ratio: 英文字符 token 比例
        """
        self.db = db_manager
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.enable_compression = enable_compression
        self.keep_recent_messages = keep_recent_messages
        self.enable_ai_summary = enable_ai_summary
        self.summary_max_length = summary_max_length
        self.chinese_token_ratio = chinese_token_ratio
        self.english_token_ratio = english_token_ratio
    
    @log_method_call(prefix="[上下文] ", log_duration=True)
    async def load_context(
        self,
        session_id: str,
        current_message: str,
        llm=None
    ) -> List[BaseMessage]:
        """
        加载对话上下文
        
        Args:
            session_id: 会话 ID
            current_message: 当前用户消息
            llm: LLM 实例（用于智能摘要）
            
        Returns:
            包含历史消息和当前消息的列表
        """
        if not self.db:
            logger.warning("数据库管理器未设置，返回空上下文")
            return [HumanMessage(content=current_message)]
        
        # 1. 从数据库加载历史消息
        messages_history = await self.db.get_messages(session_id)
        
        if not messages_history:
            logger.debug(f"会话 {session_id} 无历史消息")
            return [HumanMessage(content=current_message)]
        
        logger.info(f"📚 加载历史消息: {len(messages_history)} 条")
        
        # 2. 转换为 LangChain Message 格式
        history_messages = self._convert_to_langchain_messages(messages_history)
        
        # 3. 应用上下文限制策略
        if self.enable_compression:
            context_messages = await self._apply_compression(history_messages, llm=llm)
        else:
            context_messages = self._apply_token_limit(history_messages)
        
        # 4. 添加当前消息
        context_messages.append(HumanMessage(content=current_message))
        
        logger.info(f"✅ 最终上下文字数: {len(context_messages)} 条消息")
        
        return context_messages
    
    def _convert_to_langchain_messages(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[BaseMessage]:
        """
        将数据库消息格式转换为 LangChain Message 格式
        
        Args:
            messages: 数据库消息列表
            
        Returns:
            LangChain Message 列表
        """
        langchain_messages = []
        
        for msg in messages:
            role = msg.get('role')
            content = msg.get('content', '')
            
            if role == 'user':
                langchain_messages.append(HumanMessage(content=content))
            elif role == 'assistant':
                langchain_messages.append(AIMessage(content=content))
            else:
                logger.warning(f"未知的消息角色: {role}")
        
        return langchain_messages
    
    def _apply_token_limit(
        self,
        messages: List[BaseMessage]
    ) -> List[BaseMessage]:
        """
        基于 token 数量限制上下文
        
        策略：从最新的消息开始保留，直到达到 token 限制
        
        Args:
            messages: 所有历史消息
            
        Returns:
            裁剪后的消息列表
        """
        if not messages:
            return []
        
        # 如果消息数量超过限制，先按数量裁剪
        if len(messages) > self.max_messages:
            logger.info(f"消息数量超限 ({len(messages)} > {self.max_messages})，裁剪到最近 {self.max_messages} 条")
            messages = messages[-self.max_messages:]
        
        # 从后往前计算 token（保留最新的消息）
        selected_messages = []
        total_tokens = 0
        
        for msg in reversed(messages):
            msg_tokens = self._estimate_tokens(msg.content)
            
            if total_tokens + msg_tokens > self.max_tokens:
                logger.info(f"Token 数量达到限制 ({total_tokens}/{self.max_tokens})，停止加载")
                break
            
            selected_messages.insert(0, msg)
            total_tokens += msg_tokens
        
        logger.info(f"Token 限制后保留: {len(selected_messages)} 条消息, 约 {total_tokens} tokens")
        
        return selected_messages
    
    @log_method_call(prefix="[上下文] ")
    async def _apply_compression(
        self,
        messages: List[BaseMessage],
        llm=None
    ) -> List[BaseMessage]:
        """
        应用上下文压缩策略
        
        策略：
        1. 保留最近 N 条消息（完整）
        2. 对更早的消息生成摘要
        
        Args:
            messages: 所有历史消息
            llm: LLM 实例（可选）
            
        Returns:
            压缩后的消息列表
        """
        if not messages:
            return []
        
        # 保留最近的消息（从配置读取）
        keep_recent = min(self.keep_recent_messages, len(messages))
        recent_messages = messages[-keep_recent:]
        
        # 如果有更早的消息，生成摘要
        old_messages = messages[:-keep_recent] if len(messages) > keep_recent else []
        
        if old_messages:
            logger.info(f"对 {len(old_messages)} 条旧消息进行压缩")
            summary = await self._generate_summary(old_messages, llm=llm)
            
            # 将摘要作为系统消息插入
            summary_message = HumanMessage(
                content=f"[历史对话摘要]\n{summary}\n[以上是之前对话的摘要，详细内容已压缩]\n"
            )
            
            return [summary_message] + recent_messages
        
        return recent_messages
    
    @log_method_call(prefix="[上下文] ", log_duration=True)
    async def _generate_summary(self, messages: List[BaseMessage], llm=None) -> str:
        """
        生成对话摘要
        
        使用 LLM 智能生成对话摘要，提取关键信息
        
        Args:
            messages: 需要摘要的消息列表
            llm: LLM 实例（可选，如果不提供则使用简化版本）
            
        Returns:
            摘要文本
        """
        # 如果提供了 LLM，使用 AI 生成摘要
        if llm:
            return await self._generate_ai_summary(messages, llm)
        
        # 否则使用简化版本
        return self._generate_simple_summary(messages)
    
    async def _generate_ai_summary(self, messages: List[BaseMessage], llm) -> str:
        """
        使用 LLM 生成智能摘要
        
        Args:
            messages: 消息列表
            llm: LLM 实例
            
        Returns:
            智能摘要文本
        """
        # 构建对话内容
        conversation_text = "\n".join([
            f"{'用户' if isinstance(m, HumanMessage) else '助手'}: {m.content[:200]}"
            for m in messages
        ])
        
        # 构建提示词
        prompt = f"""请对以下对话生成简洁的摘要，提取关键信息：

{conversation_text}

要求：
1. 总结对话的主要话题和关键信息
2. 提取用户的意图和需求
3. 保留重要的上下文信息
4. 用简洁的中文描述，不超过 {self.summary_max_length} 字
5. 格式：
   - 主要话题：xxx
   - 关键信息：xxx
   - 用户意图：xxx

摘要："""
        
        try:
            # 调用 LLM 生成摘要
            response = await llm.ainvoke(prompt)
            summary = response.content if hasattr(response, 'content') else str(response)
            
            logger.info(f" AI 生成摘要成功，长度: {len(summary)} 字符")
            return summary
            
        except Exception as e:
            logger.error(f" AI 生成摘要失败: {e}，使用简化版本")
            # 降级到简化版本
            return self._generate_simple_summary(messages)
    
    def _generate_simple_summary(self, messages: List[BaseMessage]) -> str:
        """
        简化版摘要生成（不依赖 LLM）
        
        Args:
            messages: 消息列表
            
        Returns:
            简化摘要文本
        """
        summary_parts = []
        
        # 统计用户和 AI 的消息数量
        user_count = sum(1 for m in messages if isinstance(m, HumanMessage))
        ai_count = sum(1 for m in messages if isinstance(m, AIMessage))
        
        summary_parts.append(f"共进行了 {user_count} 轮对话")
        
        # 提取第一条和最后一条消息的主题
        if messages:
            first_msg = messages[0]
            last_msg = messages[-1]
            
            first_preview = first_msg.content[:50] if hasattr(first_msg, 'content') else ""
            last_preview = last_msg.content[:50] if hasattr(last_msg, 'content') else ""
            
            summary_parts.append(f"开始话题: {first_preview}...")
            summary_parts.append(f"最近话题: {last_preview}...")
        
        summary = "\n".join(summary_parts)
        
        logger.debug(f"生成简化摘要: {summary}")
        
        return summary
    
    def _estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数量
        
        使用配置的 token 比例进行估算
        生产环境建议使用 tiktoken 库
        
        Args:
            text: 要估算的文本
            
        Returns:
            估算的 token 数量
        """
        if not text:
            return 0
        
        # 使用配置的 token 比例
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        
        # 使用实例的配置参数
        estimated_tokens = int(
            chinese_chars * self.chinese_token_ratio + 
            other_chars * self.english_token_ratio
        )
        
        return estimated_tokens
    
    def get_context_stats(self, messages: List[BaseMessage]) -> Dict[str, Any]:
        """
        获取上下文统计信息
        
        Args:
            messages: 消息列表
            
        Returns:
            统计信息字典
        """
        total_tokens = sum(self._estimate_tokens(msg.content) for msg in messages)
        
        return {
            "message_count": len(messages),
            "estimated_tokens": total_tokens,
            "max_messages": self.max_messages,
            "max_tokens": self.max_tokens,
            "compression_enabled": self.enable_compression
        }
