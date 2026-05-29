# src/tools/web_search.py
"""
网络搜索工具 - 多 Provider 可配置架构
支持：tavily（付费）/ duckduckgo（免费）
"""
from typing import Dict, Any, List, Optional
from src.tools.base import BaseTool, ToolExecutionError
import asyncio
import logging
import time

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════
# Provider 抽象层
# ═══════════════════════════════════════════════════

class SearchProvider:
    """搜索引擎 Provider 基类"""

    name: str = "base"

    def search(self, query: str, num_results: int, search_depth: str) -> Dict[str, Any]:
        raise NotImplementedError


class TavilyProvider(SearchProvider):
    """Tavily 搜索（付费，质量高）"""

    name = "tavily"

    def search(self, query: str, num_results: int, search_depth: str) -> Dict[str, Any]:
        from src.config import get_settings_safe
        from tavily import TavilyClient

        settings = get_settings_safe()
        if not settings.TAVILY_API_KEY:
            raise ToolExecutionError(
                "Tavily API key 未配置，请在 .env 中设置 TAVILY_API_KEY，"
                "或将 SEARCH_PROVIDER 改为 duckduckgo（免费）"
            )

        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        response = client.search(
            query=query,
            max_results=min(num_results, 5),
            search_depth=search_depth,
            include_answer=False,
            include_raw_content=False,
        )

        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
                "score": r.get("score", 0),
            }
            for r in response.get("results", [])[:num_results]
        ]
        return {"results": results}


class DuckDuckGoProvider(SearchProvider):
    """DuckDuckGo 搜索（免费，无需 API key）"""

    name = "duckduckgo"

    def search(self, query: str, num_results: int, search_depth: str) -> Dict[str, Any]:
        try:
            from ddgs import DDGS
        except ImportError:
            raise ToolExecutionError(
                "ddgs 未安装，请运行: pip install ddgs"
            )

        # DuckDuckGo 不区分 search_depth，统一用文本搜索
        ddgs = DDGS()
        raw_results = list(ddgs.text(query, max_results=min(num_results, 5)))

        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
                "score": 0,  # DuckDuckGo 不返回评分
            }
            for r in raw_results[:num_results]
        ]
        return {"results": results}


# Provider 注册表
_PROVIDER_REGISTRY: Dict[str, type] = {
    "tavily": TavilyProvider,
    "duckduckgo": DuckDuckGoProvider,
}


def _get_provider() -> SearchProvider:
    """根据配置获取搜索 Provider"""
    from src.config import get_settings_safe
    settings = get_settings_safe()
    provider_name = settings.SEARCH_PROVIDER.lower().strip()
    provider_cls = _PROVIDER_REGISTRY.get(provider_name)
    if provider_cls is None:
        supported = ", ".join(_PROVIDER_REGISTRY.keys())
        raise ToolExecutionError(
            f"不支持的 SEARCH_PROVIDER: '{provider_name}'，可选: {supported}"
        )
    return provider_cls()


# ═══════════════════════════════════════════════════
# WebSearchTool（对外接口不变）
# ═══════════════════════════════════════════════════

class WebSearchTool(BaseTool):
    """网络搜索工具（支持多 Provider 配置）"""

    def __init__(self):
        super().__init__()
        self.name = "web_search"
        self.description = "搜索网络获取最新信息、新闻和事实数据"

        self.parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (be specific for better results)",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 3, max: 5)",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 5,
                },
                "search_depth": {
                    "type": "string",
                    "description": "Search depth: 'basic' for quick results, 'advanced' for detailed",
                    "enum": ["basic", "advanced"],
                    "default": "basic",
                },
            },
            "required": ["query"],
        }

        self.timeout = 15
        self.retry_count = 2

    def _search_sync(
        self, query: str, num_results: int, search_depth: str
    ) -> Dict[str, Any]:
        """同步搜索（在线程池中运行）"""
        start_time = time.time()

        try:
            from src.config import get_settings_safe
            settings = get_settings_safe()

            # 用配置默认值覆盖未传入的参数
            if num_results is None:
                num_results = settings.SEARCH_MAX_RESULTS
            if search_depth is None:
                search_depth = settings.SEARCH_DEPTH

            logger.info(
                f"🔍 [{settings.SEARCH_PROVIDER}] 执行搜索: "
                f"query='{query}', results={num_results}, depth={search_depth}"
            )

            provider = _get_provider()
            data = provider.search(query, num_results, search_depth)
            results = data.get("results", [])

            elapsed = time.time() - start_time
            logger.info(
                f"✅ [{provider.name}] 搜索成功: {len(results)} 条结果, 耗时 {elapsed:.2f}s"
            )

            return {
                "success": True,
                "query": query,
                "provider": provider.name,
                "results": results,
                "count": len(results),
                "execution_time": round(elapsed, 2),
            }

        except Exception as e:
            logger.error(f"❌ 搜索失败: {e}", exc_info=True)
            return {
                "success": False,
                "query": query,
                "error": f"搜索失败: {str(e)}",
                "results": [],
                "count": 0,
            }

    async def execute(
        self,
        query: str,
        num_results: Optional[int] = None,
        search_depth: Optional[str] = None,
    ) -> Dict[str, Any]:
        """异步执行网络搜索"""
        if not query or not query.strip():
            return {"success": False, "error": "搜索查询不能为空", "results": []}

        if num_results is not None:
            num_results = min(max(num_results, 1), 5)

        try:
            result = await asyncio.to_thread(
                self._search_sync,
                query.strip(),
                num_results,
                search_depth,
            )
            return result

        except asyncio.CancelledError:
            logger.warning(f"搜索任务被取消: {query}")
            return {"success": False, "error": "搜索被取消", "results": []}
        except Exception as e:
            logger.error(f"搜索执行异常: {e}", exc_info=True)
            return {"success": False, "error": f"搜索失败: {str(e)}", "results": []}
