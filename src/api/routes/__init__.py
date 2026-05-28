from .chat import router as chat_router
from .auth import router as auth_router
from .complex_tasks import router as complex_tasks_router
from .industry import router as industry_router

__all__ = ["chat_router", "auth_router", "complex_tasks_router", "industry_router"]