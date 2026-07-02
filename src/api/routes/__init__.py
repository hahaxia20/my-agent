from .chat import router as chat_router
from .auth import router as auth_router
from .complex_tasks import router as complex_tasks_router
from .skills import router as skills_router

__all__ = ["chat_router", "auth_router", "complex_tasks_router", "skills_router", "uploads_router"]
from .uploads import router as uploads_router
