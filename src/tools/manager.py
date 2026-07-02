"""Tool registry for built-in runtime tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolManager:
    """Registry for project tools."""

    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self.tools[tool.name] = tool
        logger.info("registered tool: %s", tool.name)

    def get_tools_openai_format(self) -> List[Dict]:
        return [tool.to_langchain_tool() for tool in self.tools.values()]

    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        if tool_name not in self.tools:
            raise ValueError(f"tool {tool_name} does not exist")
        return await self.tools[tool_name].execute(**kwargs)

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self.tools

    def get_all(self) -> List[BaseTool]:
        return list(self.tools.values())


tool_manager = ToolManager()

from src.tools.calculator import CalculatorTool
from src.tools.time import TimeTool
from src.tools.web_scraper import WebScraperTool
from src.tools.pdf_tool import PdfTool
from src.tools.image_tool import ImageTool
from src.tools.imagegen_tool import ImageGenTool

tool_manager.register(CalculatorTool())
tool_manager.register(TimeTool())
tool_manager.register(WebScraperTool())
tool_manager.register(PdfTool())
tool_manager.register(ImageTool())
tool_manager.register(ImageGenTool())

try:
    from src.config import get_settings_safe

    _settings = get_settings_safe()
    if _settings.SEARCH_ENABLED:
        from src.tools.web_search import WebSearchTool

        tool_manager.register(WebSearchTool())
    else:
        logger.info("web_search disabled by SEARCH_ENABLED=False")
except Exception as _e:
    from src.tools.web_search import WebSearchTool

    tool_manager.register(WebSearchTool())
    logger.warning("search tool config load failed, using fallback registration: %s", _e)

