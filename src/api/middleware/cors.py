"""CORS middleware configuration."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from src.config import get_settings_safe

logger = logging.getLogger(__name__)


PRODUCTION_ENVS = {"production", "prod"}


def setup_cors(app: FastAPI):
    """Configure CORS for the FastAPI app."""
    settings = get_settings_safe()
    app_env = str(getattr(settings, "APP_ENV", "development") or "development").strip().lower()
    is_production = app_env in PRODUCTION_ENVS

    if settings.CORS_ORIGINS == ["*"] and is_production:
        logger.error(
            "production environment cannot use wildcard CORS origins; set explicit CORS_ORIGINS in .env"
        )
        raise ValueError(
            "Production CORS_ORIGINS cannot be ['*']; set explicit allowed origins in .env, "
            "for example CORS_ORIGINS=['https://yourdomain.com']"
        )

    if is_production:
        logger.info("CORS configured for production origins: %s", settings.CORS_ORIGINS)
    else:
        logger.info("CORS configured for development origins: %s", settings.CORS_ORIGINS)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
