"""
网页抓取工具 - 使用 requests + BeautifulSoup
轻量级网页抓取，支持提取文本、链接、图片等
"""

from typing import Dict, Any, List, Optional
from src.tools.base import BaseTool, ToolExecutionError
from src.core.security import InputSecurityFilter
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
import time
from urllib.parse import urljoin, urlparse
import re

logger = logging.getLogger(__name__)


class WebScraperTool(BaseTool):
    """基于 Scrapy 的网页抓取工具"""
    
    def __init__(self):
        super().__init__()
        self.name = "web_scraper"
        self.description = "抓取网页原始内容（简单抓取用这个，深度分析用 web-content-analyzer 技能）"
        
        self.parameters = {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The complete URL to scrape (must include http:// or https://)"
                },
                "extract_links": {
                    "type": "boolean",
                    "description": "Whether to extract all links from the page (default: False)",
                    "default": False
                },
                "extract_images": {
                    "type": "boolean",
                    "description": "Whether to extract image URLs (default: False)",
                    "default": False
                },
                "max_content_length": {
                    "type": "integer",
                    "description": "Maximum content length to return (default: 5000, max: 10000)",
                    "default": 5000,
                    "minimum": 1000,
                    "maximum": 10000
                }
            },
            "required": ["url"]
        }
        
        self.timeout = 30  # 30秒超时
        self._executor = ThreadPoolExecutor(max_workers=3)
    
    def _validate_url(self, url: str) -> bool:
        """验证 URL 格式"""
        try:
            result = urlparse(url)
            return all([result.scheme in ['http', 'https'], result.netloc])
        except:
            return False
    
    def _check_url_security(self, url: str) -> tuple[bool, str]:
        """
        安全检查 URL（防止 SSRF 攻击）
        
        Returns:
            (is_safe, reason)
        """
        # 使用安全过滤器检查
        is_safe, reason = InputSecurityFilter.check_url(url)
        
        if not is_safe:
            logger.warning(f"🚨 [SSRF 防护] 阻止访问: {url} - {reason}")
        
        return is_safe, reason
    
    def _scrape_sync(self, url: str, extract_links: bool = False, 
                   extract_images: bool = False, max_content_length: int = 5000) -> Dict[str, Any]:
        """同步抓取实现（在线程池中运行）"""
        start_time = time.time()
        
        try:
            import requests
            from bs4 import BeautifulSoup
            
            logger.info(f"🌐 开始抓取网页: {url}")
            
            # 设置请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            # 发送请求
            response = requests.get(
                url,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            # 检查响应状态
            response.raise_for_status()
            
            # 解析 HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 提取标题
            title = soup.title.string if soup.title else "No title"
            
            # 提取 meta description
            meta_tag = soup.find('meta', attrs={'name': 'description'})
            meta_description = meta_tag.get('content', '') if meta_tag else ''
            
            # 移除不需要的元素
            for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()
            
            # 提取正文内容（智能提取算法）
            body_content = None
            
            # 获取页面标题（用于验证）
            page_title = soup.title.string.strip() if soup.title else ""
            
            # 策略 1: 查找 article 标签（最准确）
            body_content = soup.find('article')
            
            # 策略 2: 查找 main 标签
            if not body_content:
                body_content = soup.find('main')
            
            # 策略 3: 查找包含 article/post/content 的 div（按权重排序 + 标题验证）
            if not body_content:
                # 定义可能的选择器及其权重
                candidates = []
                
                for div in soup.find_all('div'):
                    div_id = div.get('id', '').lower()
                    div_class = ' '.join(div.get('class', [])).lower()
                    combined = f"{div_id} {div_class}"
                    
                    # 计算权重
                    weight = 0
                    
                    # ID 权重更高
                    if 'article' in div_id:
                        weight += 10
                    if 'content' in div_id:
                        weight += 8
                    if 'main' in div_id:
                        weight += 7
                    if 'post' in div_id:
                        weight += 6
                    
                    # Class 权重
                    if 'article' in div_class:
                        weight += 5
                    if 'content' in div_class:
                        weight += 4
                    if 'post-content' in div_class or 'article-content' in div_class:
                        weight += 8
                    if 'main-content' in div_class:
                        weight += 7
                    
                    # 检查文本长度（正文通常较长）
                    text_len = len(div.get_text(strip=True))
                    if text_len > 500:  # 至少 500 字符
                        weight += 3
                    
                    # ⭐ 关键：验证是否包含正确的 h1 标题
                    h1_tag = div.find('h1')
                    if h1_tag:
                        h1_text = h1_tag.get_text(strip=True)
                        # 如果 h1 与页面标题匹配，大幅提升权重
                        if h1_text and (h1_text in page_title or page_title in h1_text):
                            weight += 50  # 大幅加分
                        else:
                            weight -= 20  # 不匹配则减分
                    
                    if weight > 0:
                        candidates.append((weight, div))
                
                # 选择权重最高的
                if candidates:
                    candidates.sort(key=lambda x: x[0], reverse=True)
                    body_content = candidates[0][1]
            
            # 策略 4: 如果都没找到，使用 body，但移除干扰元素
            if not body_content:
                body_content = soup.body if soup.body else soup
                # 移除导航、侧边栏、页脚等
                for selector in ['nav', 'aside', 'footer', 'header', 'sidebar', 
                               '.sidebar', '.nav', '.menu', '.header', '.footer']:
                    for elem in body_content.select(selector):
                        elem.decompose()
            
            # 提取文本
            text_content = body_content.get_text(separator='\n', strip=True)
            
            # 清理多余空行
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            cleaned_text = '\n'.join(lines)
            
            # 限制内容长度
            if len(cleaned_text) > max_content_length:
                cleaned_text = cleaned_text[:max_content_length] + "\n\n... [内容已截断]"
            
            # 提取链接（可选）
            links = []
            if extract_links:
                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href']
                    # 转换为绝对 URL
                    absolute_url = urljoin(url, href)
                    link_text = a_tag.get_text(strip=True)
                    if link_text and absolute_url.startswith('http'):
                        links.append({
                            'url': absolute_url,
                            'text': link_text[:100]
                        })
                
                # 限制链接数量
                links = links[:50]
            
            # 提取图片（可选）
            images = []
            if extract_images:
                for img_tag in soup.find_all('img', src=True):
                    src = img_tag['src']
                    alt = img_tag.get('alt', '')
                    # 转换为绝对 URL
                    absolute_url = urljoin(url, src)
                    if absolute_url.startswith('http'):
                        images.append({
                            'url': absolute_url,
                            'alt': alt[:100]
                        })
                
                # 限制图片数量
                images = images[:20]
            
            execution_time = time.time() - start_time
            
            result = {
                "success": True,
                "url": url,
                "title": title,
                "meta_description": meta_description,
                "content": cleaned_text,
                "content_length": len(cleaned_text),
                "links": links if extract_links else [],
                "links_count": len(links) if extract_links else 0,
                "images": images if extract_images else [],
                "images_count": len(images) if extract_images else 0,
                "execution_time": round(execution_time, 2)
            }
            
            logger.info(f"✅ 抓取成功: {title}, 内容长度 {len(cleaned_text)} 字符, 耗时 {execution_time:.2f}s")
            return result
            
        except ImportError as e:
            logger.error(f"❌ 缺少依赖库: {e}")
            return {
                "success": False,
                "url": url,
                "error": f"缺少依赖库，请安装: pip install requests beautifulsoup4",
                "content": ""
            }
        except Exception as e:
            logger.error(f"❌ 抓取失败: {url} - {e}", exc_info=True)
            return {
                "success": False,
                "url": url,
                "error": f"抓取失败: {str(e)}",
                "content": ""
            }
    
    async def execute(self, url: str, extract_links: bool = False, 
                     extract_images: bool = False, max_content_length: int = 5000) -> Dict[str, Any]:
        """异步执行网页抓取"""
        # URL 验证
        if not url or not url.strip():
            return {
                "success": False,
                "error": "URL 不能为空",
                "content": ""
            }
        
        # 自动添加 https://
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # 验证 URL 格式
        if not self._validate_url(url):
            return {
                "success": False,
                "error": "URL 格式不正确，请使用完整 URL（如 https://example.com）",
                "content": ""
            }
        
        # 🔒 安全检查：防止 SSRF 攻击
        is_safe, security_reason = self._check_url_security(url)
        if not is_safe:
            return {
                "success": False,
                "error": f"安全限制：{security_reason}",
                "content": ""
            }
        
        # 限制参数范围
        max_content_length = min(max(max_content_length, 1000), 10000)
        
        try:
            # 在线程池中运行同步抓取
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._scrape_sync,
                url,
                extract_links,
                extract_images,
                max_content_length
            )
            return result
            
        except asyncio.CancelledError:
            logger.warning(f"抓取任务被取消: {url}")
            return {
                "success": False,
                "error": "抓取被取消",
                "content": ""
            }
        except Exception as e:
            logger.error(f"抓取执行异常: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"抓取失败: {str(e)}",
                "content": ""
            }
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
