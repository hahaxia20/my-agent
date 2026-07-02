"""
配置管理模块
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
from pydantic import BaseModel, Field, field_validator

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

class StreamConfig(BaseModel):
    """流式配置"""
    buffer_size: int = Field(default=5, description="缓冲区大小")
    flush_interval: float = Field(default=0.05, description="刷新间隔(秒)")
    enable_metrics: bool = Field(default=True, description="启用性能监控")
    enable_debug_info: bool = Field(default=False, description="启用调试信息")
    max_chunk_size: int = Field(default=4096, description="最大块大小")
    client_timeout: int = Field(default=300, description="客户端超时(秒)")


class Settings(BaseSettings):
    """应用配置"""

    # ═══════════════════════════════════════
    # 应用基础配置
    # ═══════════════════════════════════════
    APP_ENV: str = "development"
    APP_NAME: str = "My Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    PROMPT_DEBUG: bool = False
    ROUTE_DEBUG: bool = False
    TOOL_DEBUG: bool = False

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _normalize_debug(cls, value):
        """Allow legacy string values like release/dev in env configuration."""
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            truthy = {"1", "true", "yes", "y", "on", "debug", "dev", "development"}
            falsy = {"0", "false", "no", "n", "off", "release", "prod", "production"}
            if normalized in truthy:
                return True
            if normalized in falsy:
                return False
        return value

    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8001
    API_PREFIX: str = "/api/v1"

    # ═══════════════════════════════════════
    # LLM 配置
    # ═══════════════════════════════════════
    OPENAI_API_KEY: str
    API_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MODEL_NAME: str = "qwen-plus"
    IMAGE_MODEL: str = "qwen-vl-max"
    IMAGEGEN_MODEL: str = "wanx2.1-t2i-plus"
    IMAGEGEN_OUTPUT_DIR: str = "data/uploads/images"
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.7

    # ═══════════════════════════════════════
    # 意图分类器配置（Router + Executor 架构的 LLM 路由）
    # ═══════════════════════════════════════
    # Ollama 兼容 OpenAI 接口，默认地址 http://localhost:11434/v1
    INTENT_CLASSIFIER_BASE_URL: str = "http://localhost:11434/v1"
    INTENT_CLASSIFIER_API_KEY: str = "ollama"  # Ollama 不校验 key，填任意值即可
    INTENT_CLASSIFIER_MODEL: str = "qwen3:8b-q4_K_M"
    INTENT_CLASSIFIER_TIMEOUT: int = 10  # 分类超时（秒）
    INTENT_CLASSIFIER_ENABLED: bool = True  # False 则退回纯关键词规则

    # ═══════════════════════════════════════
    # 路由器配置（Router + Executor 架构）
    # ═══════════════════════════════════════
    ROUTER_CONFIDENCE_THRESHOLD: float = 0.75   # 路由置信度阈值，低于此值回退到 ROUTER_FALLBACK_ROUTE
    ROUTER_FALLBACK_ROUTE: str = "simple"       # 低置信度回退路径（simple/complex）

    # ═══════════════════════════════════════
    # MongoDB 配置
    # ═══════════════════════════════════════
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "deerflow"

    # ═══════════════════════════════════════
    # Neo4j 图数据库配置 (产业链图谱)
    # ═══════════════════════════════════════
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    NEO4J_DATABASE: str = "neo4j"

    # ═══════════════════════════════════════
    # 上下文管理配置（混合策略）
    # ═══════════════════════════════════════
    CONTEXT_MAX_TOKENS: int = 4096
    CONTEXT_MIN_RECENT: int = 5
    CONTEXT_MAX_RECENT: int = 20
    CONTEXT_ENABLE_IMPORTANCE: bool = True
    CONTEXT_ENABLE_RELEVANCE: bool = True
    CONTEXT_RELEVANCE_THRESHOLD: float = 0.3

    # ═══════════════════════════════════════
    # CORS 配置
    # ═══════════════════════════════════════
    # 开发环境: ["*"] 允许所有来源
    # 生产环境: ["https://yourdomain.com"] 明确指定允许的域名
    CORS_ORIGINS: list[str] = ["*"]

    # ═══════════════════════════════════════
    # 搜索工具配置
    # ═══════════════════════════════════════
    # 搜索引擎提供商：tavily（付费）/ duckduckgo（免费，无需 API key）
    SEARCH_PROVIDER: str = "tavily"
    # 是否启用网络搜索工具
    SEARCH_ENABLED: bool = True
    # Tavily API Key（SEARCH_PROVIDER=tavily 时必填）
    TAVILY_API_KEY: str = ""
    # SerpAPI Key（预留）
    SERPAPI_API_KEY: str = ""
    # 默认返回结果条数
    SEARCH_MAX_RESULTS: int = 3
    # 默认搜索深度：basic（快速）/ advanced（详细）
    SEARCH_DEPTH: str = "basic"

    # ═══════════════════════════════════════
    # JWT密钥配置
    # ═══════════════════════════════════════
    JWT_SECRET_KEY: str = ""

    # ══════════════════════════════════════
    # 系统提示词配置
    # ═══════════════════════════════════════
    SYSTEM_PROMPT_VERSION: str = "1.0"  # 提示词版本号，对应文件名 system_prompts_v{version}.json

    # ══════════════════════════════════════
    # LangSmith 监控配置
    # ═══════════════════════════════════════
    # 是否启用 LangSmith 追踪（需配置 LANGCHAIN_API_KEY 环境变量）
    LANGSMITH_ENABLED: bool = False
    # LangSmith 项目名（在 LangSmith UI 中分组查看）
    LANGSMITH_PROJECT: str = "my-agent"
    # LangSmith API Key（从 https://smith.langchain.com 获取）
    LANGCHAIN_API_KEY: str = ""
    # LangSmith 追踪开关（通常由 LANGSMITH_ENABLED 自动控制，无需手动设置）
    LANGSMITH_TRACING: str = ""
    # LangSmith API 端点（默认 https://api.smith.langchain.com，自托管时可修改）
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"

    # ═══════════════════════════════════════
    # 对话上下文管理配置（扁平化，支持环境变量）
    # ═══════════════════════════════════════
    # 基础限制
    CONV_CTX_MAX_MESSAGES: int = 50
    CONV_CTX_MAX_TOKENS: int = 8000
    
    # 摘要压缩配置
    CONV_CTX_ENABLE_COMPRESSION: bool = False
    CONV_CTX_KEEP_RECENT_MESSAGES: int = 20
    
    # AI 摘要配置
    CONV_CTX_ENABLE_AI_SUMMARY: bool = True
    CONV_CTX_SUMMARY_MAX_LENGTH: int = 200
    
    # Token 估算配置
    CONV_CTX_CHINESE_TOKEN_RATIO: float = 1.5
    CONV_CTX_ENGLISH_TOKEN_RATIO: float = 0.75

    stream: StreamConfig = Field(default_factory=StreamConfig)

    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True

    # model_config = {
    #     "env_file": str(PROJECT_ROOT / ".env1"),
    #     "env_file_encoding": "utf-8",
    #     "extra": "ignore"
    # }


@lru_cache()
def get_settings() -> Settings:
    """获取配置（缓存）"""
    return Settings()


_settings = None

def get_settings_safe() -> Settings:
    """安全地获取配置"""
    global _settings
    if _settings is None:
        _settings = get_settings()
    return _settings


def validate_config() -> bool:
    """验证配置"""
    try:
        s = get_settings_safe()
        if not s.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY 未设置")
        return True
    except Exception as e:
        print(f"❌ 配置验证失败: {e}")
        return False


def print_config_summary():
    """打印配置摘要"""
    s = get_settings_safe()
    print("\n" + "="*50)
    print("📋 配置摘要")
    print("="*50)
    print(f"  环境: {'生产' if not s.DEBUG else '开发'}")
    print(f"  模型: {s.MODEL_NAME}")
    print(f"  API: {s.API_BASE_URL}")
    print(f"  API Key: {s.OPENAI_API_KEY[:10]}...{s.OPENAI_API_KEY[-4:]}")
    print(f"  MongoDB: {s.MONGODB_URL}")
    print(f"  Neo4j: {s.NEO4J_URI}")
    print(f"  上下文: {s.CONTEXT_MAX_TOKENS} tokens")
    print(f"  提示词版本: v{s.SYSTEM_PROMPT_VERSION}")
    print(f"  对话上下文:")
    print(f"    - 最大消息数: {s.CONV_CTX_MAX_MESSAGES}")
    print(f"    - 最大 Token: {s.CONV_CTX_MAX_TOKENS}")
    print(f"    - 启用压缩: {s.CONV_CTX_ENABLE_COMPRESSION}")
    print(f"    - AI 摘要: {s.CONV_CTX_ENABLE_AI_SUMMARY}")
    print("="*50 + "\n")
