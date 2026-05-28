"""
工具管理器
"""

from typing import Dict, List, Any,Optional
from src.tools.base import BaseTool


class ToolManager:
    """工具管理器"""

    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """注册工具"""
        self.tools[tool.name] = tool
        print(f"✅ 已注册工具: {tool.name}")

    def get_tools_openai_format(self) -> List[Dict]:
        """获取所有工具的 LangChain 格式（用于 Function Calling）"""
        return [tool.to_langchain_tool() for tool in self.tools.values()]

    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """执行工具"""
        if tool_name not in self.tools:
            raise ValueError(f"工具 {tool_name} 不存在")

        return await self.tools[tool_name].execute(**kwargs)

    def has_tool(self, tool_name: str) -> bool:
        """检查工具是否存在"""
        return tool_name in self.tools

    def get_all(self) -> List[BaseTool]:
        """获取所有注册的工具"""
        return list(self.tools.values())


# 全局实例
tool_manager = ToolManager()

# 注册默认工具
from src.tools.calculator import CalculatorTool
from src.tools.time import TimeTool
from src.tools.web_search import WebSearchTool
from src.tools.web_scraper import WebScraperTool

tool_manager.register(CalculatorTool())
tool_manager.register(TimeTool())
tool_manager.register(WebSearchTool())
tool_manager.register(WebScraperTool())