"""My Agent application entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.api.middleware import setup_cors
from src.api.routes import auth_router, chat_router, complex_tasks_router, skills_router, uploads_router
from src.config import PROJECT_ROOT, get_settings_safe, print_config_summary, validate_config
from src.core.logging.config import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    settings = get_settings_safe()
    setup_logging(
        log_level=getattr(settings, 'LOG_LEVEL', 'INFO'),
        log_to_console=True,
        log_to_file=True,
        log_file_path='logs/agent.log',
        json_format=False,
        enable_emoji=True,
    )

    print('\n' + '=' * 60)
    print('My Agent starting...')
    print('=' * 60)

    if not validate_config():
        raise RuntimeError('Configuration validation failed. Please check the environment settings.')

    print_config_summary()

    import os

    tracing_enabled = bool(settings.LANGSMITH_ENABLED and settings.LANGCHAIN_API_KEY)
    if tracing_enabled:
        os.environ['LANGSMITH_TRACING'] = 'true'
        os.environ['LANGCHAIN_TRACING_V2'] = 'true'
        os.environ['LANGCHAIN_PROJECT'] = settings.LANGSMITH_PROJECT
        os.environ['LANGCHAIN_API_KEY'] = settings.LANGCHAIN_API_KEY
        if settings.LANGSMITH_ENDPOINT:
            os.environ['LANGSMITH_ENDPOINT'] = settings.LANGSMITH_ENDPOINT
        print(f'LangSmith tracing enabled: {settings.LANGSMITH_PROJECT}')
    else:
        for env_name in (
            'LANGSMITH_TRACING',
            'LANGCHAIN_TRACING_V2',
            'LANGCHAIN_PROJECT',
            'LANGCHAIN_API_KEY',
            'LANGSMITH_ENDPOINT',
        ):
            os.environ.pop(env_name, None)
        disabled_reason = 'LANGSMITH_ENABLED=False' if not settings.LANGSMITH_ENABLED else 'missing LANGCHAIN_API_KEY'
        print(f'LangSmith tracing disabled: {disabled_reason}')

    print('Preloading agent...')
    from src.core.agent import get_agent

    agent = await get_agent()
    print(f'Agent ready: {type(agent).__name__}\n')

    yield

    print('\n' + '=' * 60)
    print('My Agent shutting down...')
    print('=' * 60)


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    settings = get_settings_safe()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description='Production-grade AI agent service',
        lifespan=lifespan,
        docs_url='/docs',
        redoc_url='/redoc',
    )

    setup_cors(app)

    app.include_router(chat_router)
    app.include_router(auth_router)
    app.include_router(complex_tasks_router)
    app.include_router(skills_router)
    app.include_router(uploads_router)

    base_dir = Path(__file__).resolve().parent.parent
    app.mount('/static', StaticFiles(directory=base_dir / 'static'), name='static')
    app.mount('/uploads', StaticFiles(directory=PROJECT_ROOT / 'data' / 'uploads'), name='uploads')

    @app.get('/health', tags=['health'])
    async def health_check():
        """Basic health check."""
        return {
            'status': 'ok',
            'app': settings.APP_NAME,
            'version': settings.APP_VERSION,
        }

    @app.get('/login', tags=['pages'])
    async def login_page():
        """Serve the login page."""
        return FileResponse(base_dir / 'login.html')

    @app.get('/login.html', tags=['pages'], include_in_schema=False)
    async def login_html_redirect():
        return RedirectResponse(url='/login')

    @app.get('/', tags=['pages'])
    async def index_page():
        """Serve the main chat page."""
        return FileResponse(base_dir / 'index.html')

    @app.get('/index.html', tags=['pages'], include_in_schema=False)
    async def index_html_redirect():
        return RedirectResponse(url='/')

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """Global exception handler."""
        return JSONResponse(
            status_code=500,
            content={
                'success': False,
                'error': 'Internal Server Error',
                'detail': str(exc) if settings.DEBUG else None,
            },
        )

    return app


app = create_app()

if __name__ == '__main__':
    import uvicorn

    settings = get_settings_safe()

    uvicorn.run(
        'src.main:app',
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
