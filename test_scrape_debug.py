"""测试网页抓取 - 调试正文提取"""
import sys
sys.path.insert(0, 'd:/projects/self_python/my-deerflow')

from src.tools.web_scraper import WebScraperTool

url = 'https://thinktank.cnfin.com/szjj-lb/detail/20260525/4416943_1.html'

print(f"测试URL: {url}\n")

tool = WebScraperTool()
result = tool._scrape_sync(url, max_content_length=1000)

print("=" * 80)
print(f"标题: {result.get('title')}")
print("=" * 80)
print(f"\n内容预览 (前500字):")
print(result.get('content', '')[:500])
print("\n" + "=" * 80)
print(f"完整内容长度: {len(result.get('content', ''))}")
print(f"状态: {result.get('status')}")
print(f"用时: {result.get('elapsed_time', 0):.2f}秒")
