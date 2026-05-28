"""
输入安全过滤器 - 防止 Prompt Injection 和恶意输入

提供多层安全防护：
1. 模式匹配检测（快速拦截明显攻击）
2. 语义分析（检测复杂注入尝试）
3. 工具调用限制（防止工具滥用）
"""

import re
import logging
from typing import Tuple, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SecurityCheckResult:
    """安全检查结果"""
    is_safe: bool
    risk_level: str  # "safe", "low", "medium", "high"
    reason: str
    blocked_patterns: List[str]


class InputSecurityFilter:
    """
    输入安全过滤器
    
    检测并拦截以下类型的恶意输入：
    1. Prompt Injection（提示词注入）
    2. 代码执行尝试
    3. 文件操作尝试
    4. SSRF 攻击（内网访问）
    5. 角色扮演绕过
    """
    
    # 高风险模式 - 直接拒绝
    HIGH_RISK_PATTERNS = [
        # 忽略指令类
        (r'(?i)ignore\s+(all\s+)?(previous|above|instructions|rules|prompts)', '尝试忽略系统指令'),
        (r'(?i)(forget|disregard|override)\s+(all\s+)?(previous|above|instructions|rules)', '尝试覆盖系统规则'),
        (r'(?i)you\s+are\s+(now|no\s+longer|acting\s+as)', '角色转换尝试'),
        
        # 代码执行类 - 更精确的模式，避免误报
        (r'(?i)(execute|run)\s+(python|javascript|js|bash|shell|code|script)', '代码执行尝试'),
        (r'(?i)(import|from)\s+(os|subprocess|sys|shutil|pathlib)\s*[;\n]', '导入危险模块'),
        (r'(?i)(?<!\.)\b(eval|exec|compile|__import__|getattr)\s*\(', '调用危险函数'),
        (r'(?i)\bos\.(system|popen|spawn|exec)\s*\(', '系统命令调用'),
        (r'(?i)\bsubprocess\.(run|call|Popen|check_output)\s*\(', '子进程调用'),
        
        # 文件操作类 - 更精确的模式
        (r'(?i)(read|write|delete|remove|create)\s+(file|directory|folder)', '文件操作尝试'),
        (r'(?i)\bdelete\s+(all\s+)?files\b', '删除文件尝试'),
        (r'(?i)open\s*\([^)]+[\'\"](\.\/|\/|\\\\)', '文件打开尝试'),
        (r'(?i)(rm\s+-rf|del\s+\/|rd\s+\/s)', '删除命令'),
        
        # 网络攻击类
        (r'(?i)(port\s+scan|nmap|masscan)', '端口扫描'),
        (r'(?i)(ddos|dos\s+attack|flood)', '拒绝服务攻击'),
        (r'(?i)(sql\s+injection|xss|csrf)', 'Web 攻击'),
    ]
    
    # 中风险模式 - 记录警告
    MEDIUM_RISK_PATTERNS = [
        # 内网地址
        (r'(?i)(127\.0\.0\.1|localhost|0\.0\.0\.0)', '内网地址访问'),
        (r'(?i)(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)', '私有网络地址'),
        
        # 可疑关键词
        (r'(?i)(hack|exploit|vulnerability|backdoor)', '安全相关关键词'),
        (r'(?i)(password|secret|api[_-]?key|token)', '敏感信息关键词'),
        
        # Base64 编码（可能隐藏恶意内容）
        (r'[A-Za-z0-9+/]{40,}={0,2}', '长 Base64 编码字符串'),
    ]
    
    # 允许的安全模式（误报过滤）
    SAFE_CONTEXTS = [
        r'(?i)(explain|teach|learn|study|什么是|解释一下|说明)\s+(python|javascript|programming|os\.system|subprocess)',  # 学习编程
        r'(?i)(what\s+is|how\s+to\s+use|如何使用)\s+(os\.system|subprocess)',  # 询问概念
        r'(?i)(security|safety|protect)\s+(against|from|安全)',  # 安全讨论
    ]
    
    @classmethod
    def check_input(cls, user_input: str) -> SecurityCheckResult:
        """
        检查用户输入是否安全
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            SecurityCheckResult: 安全检查结果
        """
        if not user_input or not user_input.strip():
            return SecurityCheckResult(
                is_safe=True,
                risk_level="safe",
                reason="空输入",
                blocked_patterns=[]
            )
        
        blocked_patterns = []
        max_risk = "safe"
        
        # 1. 检查是否在安全上下文中
        for pattern in cls.SAFE_CONTEXTS:
            if re.search(pattern, user_input):
                logger.debug(f"✅ 输入在安全上下文中: {pattern}")
                return SecurityCheckResult(
                    is_safe=True,
                    risk_level="safe",
                    reason="安全的学习/讨论上下文",
                    blocked_patterns=[]
                )
        
        # 2. 检查高风险模式
        for pattern, description in cls.HIGH_RISK_PATTERNS:
            if re.search(pattern, user_input):
                blocked_patterns.append(f"🔴 {description}")
                max_risk = "high"
                logger.warning(f"🚨 检测到高风险输入: {description}")
        
        # 3. 检查中风险模式
        if max_risk != "high":
            for pattern, description in cls.MEDIUM_RISK_PATTERNS:
                if re.search(pattern, user_input):
                    blocked_patterns.append(f"🟡 {description}")
                    if max_risk == "safe":
                        max_risk = "medium"
                    logger.info(f"⚠️ 检测到中风险输入: {description}")
        
        # 4. 生成结果
        if max_risk == "high":
            return SecurityCheckResult(
                is_safe=False,
                risk_level="high",
                reason=f"检测到恶意输入模式: {'; '.join(blocked_patterns)}",
                blocked_patterns=blocked_patterns
            )
        elif max_risk == "medium":
            return SecurityCheckResult(
                is_safe=True,  # 中风险仅警告，不拦截
                risk_level="medium",
                reason=f"注意到可疑内容，但可能是合法的: {'; '.join(blocked_patterns)}",
                blocked_patterns=blocked_patterns
            )
        else:
            return SecurityCheckResult(
                is_safe=True,
                risk_level="safe",
                reason="输入安全检查通过",
                blocked_patterns=[]
            )
    
    @classmethod
    def check_url(cls, url: str) -> Tuple[bool, str]:
        """
        检查 URL 是否安全（防止 SSRF）
        
        Args:
            url: 待检查的 URL
            
        Returns:
            (is_safe, reason)
        """
        # 禁止内网地址
        internal_patterns = [
            (r'^https?://(127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01]))', '禁止访问内网地址'),
            (r'^https?://localhost', '禁止访问 localhost'),
            (r'^https?://0\.0\.0\.0', '禁止访问 0.0.0.0'),
            (r'^https?://\[::1\]', '禁止访问 IPv6 localhost'),
            (r'^https?://(metadata|169\.254\.169\.254)', '禁止访问云元数据服务'),
        ]
        
        for pattern, reason in internal_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                logger.warning(f"🚨 阻止访问内网地址: {url} - {reason}")
                return False, reason
        
        return True, "URL 安全检查通过"


class OutputSecurityFilter:
    """
    输出安全过滤器
    
    清理 AI 输出中的敏感信息，防止信息泄露
    """
    
    SENSITIVE_PATTERNS = [
        (r'(?i)(api[_\s-]?key|apikey)\s*[:=\s]+["\']?[a-zA-Z0-9_-]{20,}["\']?', '[API_KEY_REDACTED]'),
        (r'(?i)(password|passwd|pwd)\s*[:=\s]+["\']?\S+["\']?', '[PASSWORD_REDACTED]'),
        (r'(?i)(secret|token)\s*[:=\s]+["\']?[a-zA-Z0-9]{20,}["\']?', '[SECRET_REDACTED]'),
        (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----.*?-----END\s+(RSA\s+)?PRIVATE\s+KEY-----', '[PRIVATE_KEY_REDACTED]', re.DOTALL),
        (r'\b\d{16}\b', '[CREDIT_CARD_REDACTED]'),  # 简单信用卡号检测
        (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]'),  # 美国社保号
    ]
    
    @classmethod
    def sanitize_output(cls, output: str) -> str:
        """
        清理输出中的敏感信息
        
        Args:
            output: AI 生成的输出文本
            
        Returns:
            清理后的文本
        """
        cleaned = output
        
        for pattern, replacement, *flags in cls.SENSITIVE_PATTERNS:
            flag = flags[0] if flags else 0
            cleaned = re.sub(pattern, replacement, cleaned, flags=flag)
        
        return cleaned
    
    @classmethod
    def check_for_leaks(cls, output: str) -> List[str]:
        """
        检查输出是否包含敏感信息
        
        Args:
            output: AI 生成的输出文本
            
        Returns:
            检测到的敏感信息类型列表
        """
        detected = []
        
        for pattern, replacement, *flags in cls.SENSITIVE_PATTERNS:
            flag = flags[0] if flags else 0
            if re.search(pattern, output, flags=flag):
                detected.append(replacement)
        
        return detected
