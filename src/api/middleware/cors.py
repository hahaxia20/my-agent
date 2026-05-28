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

    # 安全检查: 生产环境不应使用 ["*"]
    if settings.CORS_ORIGINS == ["*"] and not settings.DEBUG:
        logger.warning(
            "⚠️ 生产环境使用通配符 CORS 配置 [*]，建议明确指定允许的域名"
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