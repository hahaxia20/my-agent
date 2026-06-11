"""
CORS 中间件配置
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import get_settings_safe
import logging

logger = logging.getLogger(__name__)


def setup_cors(app: FastAPI):
    """配置 CORS"""

    settings = get_settings_safe()

    # 生产环境安全保护：禁止使用通配符
    if settings.CORS_ORIGINS == ["*"] and not settings.DEBUG:
        logger.error(
            "❌ 生产环境禁止使用通配符 CORS [*]，请在 .env1 中配置 CORS_ORIGINS"
        )
        raise ValueError(
            "生产环境 CORS_ORIGINS 不能为 ['*']，请在 .env1 中明确指定允许的域名，"
            "例如：CORS_ORIGINS=['https://yourdomain.com']"
        )

    # 记录 CORS 配置
    if settings.DEBUG:
        logger.info(f"🔓 CORS 配置: {settings.CORS_ORIGINS}")
    else:
        logger.info(f"🔒 CORS 配置: {'生产环境安全模式' if settings.CORS_ORIGINS != ['*'] else '⚠️ 通配符模式'}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )