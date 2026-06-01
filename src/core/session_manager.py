"""
会话管理模块
负责会话的 CRUD 操作，从 agent.py 中拆分出来以降低耦合
"""

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class SessionManager:
    """
    会话管理器
    
    职责：
    - 会话的创建、查询、删除
    - 会话列表管理
    - 与 MongoDB 和 Checkpointer 交互
    """
    
    def __init__(self, db, checkpointer=None):
        """
        初始化会话管理器
        
        Args:
            db: MongoDB 数据库实例
            checkpointer: LangGraph 检查点实例（可选）
        """
        self.db = db
        self.checkpointer = checkpointer
    
    async def ensure_session(self, session_id: Optional[str], user_id: str, title: str) -> str:
        """确保会话存在，不存在则创建"""
        if not session_id:
            session_id = await self.db.create_session(user_id=user_id, title=title)
            logger.info(f"📝 创建新会话: {session_id}")
        return session_id
    
    async def get_session_history(
        self,
        session_id: str,
        user_id: str = "anonymous"
    ) -> Dict[str, Any]:
        """获取会话历史（业务数据库）"""
        session = await self.db.get_session(session_id)
        if not session or session.get("user_id") != user_id:
            logger.warning(f"无权访问会话: {session_id}, user={user_id}")
            return {"success": False, "error": "无权访问"}

        logger.info(f"获取会话历史: {session_id}, 消息数: {session['metadata']['message_count']}")

        return {
            "success": True,
            "session_id": str(session["_id"]),
            "title": session["title"],
            "messages": session["messages"],
            "message_count": session["metadata"]["message_count"],
            "created_at": session["metadata"]["created_at"],
            "updated_at": session["metadata"]["updated_at"]
        }

    async def list_sessions(
        self,
        user_id: str = "anonymous",
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """列出用户的所有会话"""
        sessions = await self.db.list_sessions(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        logger.info(f"列出用户会话: {user_id}, 数量: {len(sessions)}")

        return [{
            "session_id": str(s["_id"]),
            "title": s["title"],
            "message_count": s["metadata"]["message_count"],
            "updated_at": s["metadata"]["updated_at"]
        } for s in sessions]

    async def delete_session(self, session_id: str, user_id: str = "anonymous") -> bool:
        """删除会话"""
        session = await self.db.get_session(session_id)
        if not session or session.get("user_id") != user_id:
            logger.warning(f"无权删除会话: {session_id}, user={user_id}")
            return False

        await self.db.delete_session(session_id)

        if self.checkpointer:
            try:
                await self.checkpointer.adelete_thread(session_id)
                logger.info(f"✅ 删除会话检查点: {session_id}")
            except Exception as e:
                logger.warning(f"删除检查点失败: {e}")

        logger.info(f"✅ 删除会话: {session_id}")
        return True
    
    async def add_message(self, session_id: str, role: str, content: str, metadata: dict = None):
        """添加消息到会话"""
        await self.db.add_message(session_id, role, content, metadata)
