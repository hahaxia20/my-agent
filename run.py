"""
启动脚本
"""

import uvicorn
from src.config import get_settings_safe


def main():
    """启动应用"""
    settings = get_settings_safe()

    print(f"\n🚀 启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"📍 地址: http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"📖 API文档: http://localhost:{settings.API_PORT}/docs\n")

    uvicorn.run(
        "src.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info"
    )


if __name__ == "__main__":
    main()