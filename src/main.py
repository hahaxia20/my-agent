"""
My Agent - 生产级 AI Agent 系统
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from src.config import get_settings_safe, print_config_summary, validate_config
from src.api.middleware import setup_cors
from src.api.routes import chat_router
from src.api.routes import auth_router
from src.api.routes import complex_tasks_router
from src.core.logging.config import setup_logging

# ═══════════════════════════════════════
# 应用生命周期
# ═══════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的处理"""
    
    # 初始化日志系统（必须在最前面）
    settings = get_settings_safe()
    setup_logging(
        log_level=getattr(settings, 'LOG_LEVEL', 'INFO'),
        log_to_console=True,
        log_to_file=True,
        log_file_path='logs/agent.log',
        json_format=False,
        enable_emoji=True
    )

    # 启动时
    print("\n" + "=" * 60)
    print("🚀 My Agent 启动中...")
    print("=" * 60)

    # 验证配置
    if not validate_config():
        raise RuntimeError("配置验证失败，请检查 .env 文件")

    # 打印配置摘要
    print_config_summary()

    # 预加载 Agent（可选）
    print("📦 预加载 Agent...")
    from src.core.agent import get_agent
    agent = await get_agent()  # 等待异步函数完成
    print(f"✅ Agent 加载完成: {type(agent).__name__}\n")

    yield

    # 关闭时
    print("\n" + "=" * 60)
    print("👋 My Agent 关闭中...")
    print("=" * 60)


# ═══════════════════════════════════════
# 创建应用
# ═══════════════════════════════════════

def create_app() -> FastAPI:
    """创建 FastAPI 应用"""

    settings = get_settings_safe()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="生产级 AI Agent 系统",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # 配置 CORS
    setup_cors(app)

    # 注册路由
    app.include_router(chat_router)
    app.include_router(auth_router)
    app.include_router(complex_tasks_router)


    # 健康检查
    @app.get("/health", tags=["health"])
    async def health_check():
        """健康检查"""
        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION
        }

    # 根路径
    @app.get("/", tags=["root"])
    async def root():
        """根路径"""
        return {
            "message": "Welcome to My Agent",
            "docs": "/docs",
            "health": "/health"
        }

    # 全局异常处理
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """全局异常处理"""
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal Server Error",
                "detail": str(exc) if settings.DEBUG else None
            }
        )

    return app


# 创建应用实例
app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings_safe()

    uvicorn.run(
        "src.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )