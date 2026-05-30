# src/core/stream_manager.py - 添加工具追踪功能

import asyncio
import time
import re
from typing import AsyncIterator, Optional, Dict, Any, List
from datetime import datetime
from collections import deque
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class StreamEventType(Enum):
    """流式事件类型"""
    TEXT = "text"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    SKILL_START = "skill_start"
    SKILL_END = "skill_end"
    THOUGHT = "thought"
    ERROR = "error"
    METADATA = "metadata"
    DONE = "done"


@dataclass
class StreamChunk:
    """流式数据块"""
    type: StreamEventType
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """是否为空块"""
        return not self.content or not self.content.strip()

    @property
    def size(self) -> int:
        """内容大小"""
        return len(self.content) if self.content else 0


class StreamBuffer:
    """流式缓冲区 - 用于批量处理和优化"""

    def __init__(self, max_size: int = 10, flush_interval: float = 0.05):
        self.max_size = max_size
        self.flush_interval = flush_interval
        self.buffer: deque = deque()
        self.last_flush = time.time()
        self.total_chunks = 0
        self.filtered_chunks = 0

    def add(self, chunk: StreamChunk) -> Optional[str]:
        """添加块，返回需要立即刷新的内容"""
        self.total_chunks += 1

        # 过滤空块
        if chunk.is_empty:
            self.filtered_chunks += 1
            return None

        self.buffer.append(chunk)

        # 缓冲区满或超时，触发刷新
        if len(self.buffer) >= self.max_size or (time.time() - self.last_flush) >= self.flush_interval:
            return self.flush()

        return None

    def flush(self) -> Optional[str]:
        """刷新缓冲区，返回合并后的内容"""
        if not self.buffer:
            return None

        # 合并缓冲区内容
        merged_content = "".join([chunk.content for chunk in self.buffer])
        self.buffer.clear()
        self.last_flush = time.time()

        return merged_content

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_chunks": self.total_chunks,
            "filtered_chunks": self.filtered_chunks,
            "filter_rate": self.filtered_chunks / self.total_chunks if self.total_chunks > 0 else 0,
            "buffer_size": len(self.buffer)
        }


class StreamFormatter:
    """流式格式化器"""

    @staticmethod
    def format_sse(data: str, event: Optional[str] = None) -> str:
        """格式化为 SSE 格式"""
        if not data:
            return ""

        lines = []
        if event:
            lines.append(f"event: {event}")

        # 处理多行数据
        for line in data.split('\n'):
            lines.append(f"data: {line}")

        lines.append("")  # 空行分隔
        return "\n".join(lines)

    @staticmethod
    def format_metadata(session_id: str, chunk_count: int, duration: float,
                        tools_called: List[str] = None, skills_called: List[str] = None) -> str:
        """格式化元数据"""
        import json
        return json.dumps({
            "session_id": session_id,
            "chunk_count": chunk_count,
            "duration": round(duration, 2),
            "tools_called": tools_called or [],
            "skills_called": skills_called or [],
            "timestamp": datetime.now().isoformat()
        })

    @staticmethod
    def should_output(content: str, min_length: int = 1) -> bool:
        """判断是否应该输出"""
        return content and len(content.strip()) >= min_length


class StreamMetrics:
    """流式性能监控"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.start_time = None
        self.end_time = None
        self.chunk_count = 0
        self.total_chars = 0
        self.tool_calls = []
        self.skill_calls = []
        self.errors = 0
        self.empty_chunks = 0

    def start(self):
        self.reset()
        self.start_time = time.time()

    def record_chunk(self, content: str, is_empty: bool = False):
        self.chunk_count += 1
        if is_empty:
            self.empty_chunks += 1
        else:
            self.total_chars += len(content)

    def record_tool_call(self, tool_name: str):
        """记录工具调用"""
        self.tool_calls.append({
            "name": tool_name,
            "timestamp": time.time()
        })

    def record_skill_call(self, skill_name: str):
        """记录技能调用"""
        self.skill_calls.append({
            "name": skill_name,
            "timestamp": time.time()
        })

    def record_error(self):
        self.errors += 1

    def finish(self):
        self.end_time = time.time()

    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0

    @property
    def chars_per_second(self) -> float:
        if self.duration > 0:
            return self.total_chars / self.duration
        return 0

    def get_tool_names(self) -> List[str]:
        """获取调用的工具名称列表"""
        return list(set([call["name"] for call in self.tool_calls]))

    def get_skill_names(self) -> List[str]:
        """获取调用的技能名称列表"""
        return list(set([call["name"] for call in self.skill_calls]))

    def get_stats(self) -> Dict[str, Any]:
        return {
            "duration": round(self.duration, 2),
            "chunk_count": self.chunk_count,
            "empty_chunks": self.empty_chunks,
            "total_chars": self.total_chars,
            "chars_per_second": round(self.chars_per_second, 2),
            "tools_called": self.get_tool_names(),
            "skills_called": self.get_skill_names(),
            "total_tool_calls": len(self.tool_calls),
            "total_skill_calls": len(self.skill_calls),
            "errors": self.errors
        }


class StreamCypherFilter:
    """流式输出 Cypher 过滤器 —— 防止 Neo4j Cypher 查询语句泄漏到用户界面

    设计原则：宁可漏放，不可误杀。
    使用 Neo4j 结构性模式检测（而非关键词），避免误判自然语言。
    """

    # 高置信度 Cypher 结构性模式（在自然语言中几乎不可能出现）
    _CYPHER_STRUCTURES = (
        "(:",      # 节点标签  MATCH (n:Entity)
        "-[",      # 关系语法  -[r:RELATIONSHIP]->
        "]->",     # 关系箭头  ]->(target)
        "<-[",     # 反向关系  <-[r:RELATIONSHIP]-
        "}.CONTAINS", # 属性+函数 (少见但确定性强)
    )
    # Cypher 特有函数/子句（在自然语言中极少见）
    _CYPHER_FUNCTIONS = (
        "CONTAINS ", "STARTS WITH ", "ENDS WITH ",
        "OPTIONAL MATCH", "ORDER BY ", "COLLECT(",
    )
    # RETURN 是强信号，但单独 "return" 可能出现在编程讨论中
    # 所以我们要求 RETURN 后面跟着类似 Cypher 的标识符
    _RETURN_PATTERN = "RETURN "

    def __init__(self):
        self._buffer = ""
        self._suppressing = False
        self._seen_return = False

    def _is_cypher(self, text: str) -> bool:
        """使用结构模式检测判断是否为 Cypher（高置信度，低误报率）"""
        upper = text.upper()
        # 1. 结构性模式（最高置信度）
        if any(p in text for p in self._CYPHER_STRUCTURES):
            return True
        # 2. 节点标签模式 (e:Entity), (n:Label), (chain:Entity) 等
        if re.search(r'\(\w+:\w+', text):
            return True
        # 3. Cypher 特有函数
        if any(f in upper for f in self._CYPHER_FUNCTIONS):
            return True
        # 4. RETURN 后跟 Cypher 风格标识符（如 e.title, r.weight）
        if "RETURN " in upper and any(c in text for c in "._"):
            return True
        return False

    def _has_cjk(self, text: str) -> bool:
        return any('\u4e00' <= c <= '\u9fff' for c in text)

    def _chunk_still_cypher(self, chunk: str) -> bool:
        """检查 chunk 是否仍然包含 Cypher 结构（防止字符串内的中文触发提前退出）"""
        if self._is_cypher(chunk):
            return True
        if re.search(r'\bLIMIT\s+\d+\s*$', self._buffer, re.IGNORECASE):
            return True
        return False

    def _extract_answer_from_chunk(self, chunk: str) -> str:
        """从混合 chunk（Cypher尾部 + 答案开头）中提取纯答案部分"""
        # 场景: chunk = "LIMIT 20氢能的上游是制氢" → 提取 "氢能的上游是制氢"
        m = re.search(r'\bLIMIT\s+\d+\s*', chunk, re.IGNORECASE)
        if m:
            after = chunk[m.end():]
            if self._has_cjk(after):
                return after
        return ""

    def process(self, chunk: str) -> str:
        """处理一个流式 chunk，返回过滤后的文本"""
        if not chunk:
            return ""

        self._buffer += chunk

        if self._suppressing:
            upper = self._buffer.upper()
            if not self._seen_return and "RETURN " in upper:
                self._seen_return = True

            # RETURN 之后的中文才是真正的自然语言答案
            # 但必须确保 chunk 不是 Cypher 的一部分（如字符串内的中文 '上游'）
            if self._seen_return and self._has_cjk(chunk):
                if not self._chunk_still_cypher(chunk):
                    result = chunk
                    self._buffer = ""
                    self._suppressing = False
                    self._seen_return = False
                    return result
                # chunk 仍含 Cypher，尝试提取答案部分
                extracted = self._extract_answer_from_chunk(chunk)
                if extracted:
                    self._buffer = ""
                    self._suppressing = False
                    self._seen_return = False
                    return extracted
            return ""

        # 只在高置信度时进入抑制模式
        if self._is_cypher(self._buffer):
            self._suppressing = True
            self._seen_return = False
            return ""

        # 安全输出（保留最后几个字符作为前缀缓冲区，防止关键词被拆分）
        if len(self._buffer) > 10:
            result = self._buffer[:-6]
            self._buffer = self._buffer[-6:]
            return result

        return ""

    def flush(self) -> str:
        """流结束时，输出缓冲区剩余内容（过滤后）"""
        if not self._buffer:
            return ""
        remaining = self._buffer.strip()
        self._buffer = ""
        self._suppressing = False
        self._seen_return = False
        if self._is_cypher(remaining):
            return ""
        return remaining