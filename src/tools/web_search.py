# src/tools/web_search.py
"""
网络搜索工具 - 生产级实现
"""
from typing import Dict, Any, List, Optional
from src.tools.base import BaseTool, ToolExecutionError
from tavily import TavilyClient
import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """生产级网络搜索工具"""
    
    def __init__(self):
        super().__init__()
        self.name = "web_search"
        self.description = "搜索网络获取最新信息、新闻和事实数据"
        
        self.parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (be specific for better results)"
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 3, max: 5)",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 5
                },
                "search_depth": {
                    "type": "string",
                    "description": "Search depth: 'basic' for quick results, 'advanced' for detailed",
                    "enum": ["basic", "advanced"],
                    "default": "basic"
                }
            },
            "required": ["query"]
        }
        
        self.timeout = 15  # 15秒超时
        self.retry_count = 2
    
    def _search_sync(self, query: str, num_results: int = 3, search_depth: str = "basic") -> Dict[str, Any]:
        """同步搜索实现（在线程池中运行）"""
        start_time = time.time()
        
        try:
            from src.config import get_settings_safe
            settings = get_settings_safe()
            
            # 验证 API key
            if not settings.TAVILY_API_KEY:
                raise ToolExecutionError("Tavily API key not configured")
            
            logger.info(f"🔍 执行搜索: query='{query}', results={num_results}, depth={search_depth}")
            
            # 初始化客户端
            client = TavilyClient(api_key=settings.TAVILY_API_KEY)
            
            # 执行搜索
            response = client.search(
                query=query,
                max_results=min(num_results, 5),  # 限制最大5条
                search_depth=search_depth,
                include_answer=False,
                include_raw_content=False
            )
            
            # 格式化结果
            formatted_results = []
            for result in response.get('results', [])[:num_results]:
                formatted_results.append({
                    "title": result.get('title', 'No title'),
                    "url": result.get('url', ''),
                    "snippet": result.get('content', 'No content'),
                    "score": result.get('score', 0)
                })
            
            execution_time = time.time() - start_time
            
            result = {
                "success": True,
                "query": query,
                "results": formatted_results,
                "count": len(formatted_results),
                "execution_time": round(execution_time, 2)
            }
            
            logger.info(f"✅ 搜索成功: {len(formatted_results)} 条结果, 耗时 {execution_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"❌ 搜索失败: {e}", exc_info=True)
            return {
                "success": False,
                "query": query,
                "error": f"搜索失败: {str(e)}",
                "results": [],
                "count": 0
            }
    
    async def execute(self, query: str, num_results: int = 3, search_depth: str = "basic") -> Dict[str, Any]:
        """异步执行网络搜索"""
        # 参数验证
        if not query or not query.strip():
            return {
                "success": False,
                "error": "搜索查询不能为空",
                "results": []
            }
        
        # 限制参数范围
        num_results = min(max(num_results, 1), 5)
        
        try:
            # 使用 asyncio.to_thread 运行同步搜索（Python 3.9+）
            result = await asyncio.to_thread(
                self._search_sync,
                query.strip(),
                num_results,
                search_depth
            )
            return result
            
        except asyncio.CancelledError:
            logger.warning(f"搜索任务被取消: {query}")
            return {
                "success": False,
                "error": "搜索被取消",
                "results": []
            }
        except Exception as e:
            logger.error(f"搜索执行异常: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"搜索失败: {str(e)}",
                "results": []
            }