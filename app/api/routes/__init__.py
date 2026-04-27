from .admin import router as admin_router
from .approval import router as approval_router
from .chat import router as chat_router
from .knowledge import router as knowledge_router

__all__ = ["admin_router", "approval_router", "chat_router", "knowledge_router"]
