"""
MongoDB 数据管理
"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, List, Dict, Any
import uuid

from datetime import datetime, timezone, timedelta

from src.core.logging_decorator import log_method_call

# 中国时区
CST = timezone(timedelta(hours=8))


class MongoDBManager:
    """MongoDB 管理器"""

    def __init__(self, url: str, db_name: str):
        self.client = AsyncIOMotorClient(url)
        self.db = self.client[db_name]

    async def ping(self) -> bool:
        """测试连接"""
        try:
            await self.client.admin.command('ping')
            return True
        except:
            return False

    # ═══════════════════════════════════════
    # 用户管理
    # ═══════════════════════════════════════

    async def create_user(self, username: str, password_hash: str) -> str:
        """创建用户，返回 user_id"""
        try:
            result = await self.db.users.insert_one({
                "username": username,
                "password_hash": password_hash,
                "created_at": datetime.now(CST)
            })
            return str(result.inserted_id)  # 返回 MongoDB _id
        except:
            return None  # 用户名已存在

    async def find_user(self, username: str) -> dict:
        """查找用户"""
        return await self.db.users.find_one({"username": username})

    async def get_user_id(self, username: str) -> str:
        """获取用户 ID"""
        user = await self.find_user(username)
        return str(user["_id"]) if user else None

    # ═══════════════════════════════════════
    # 会话管理
    # ═══════════════════════════════════════

    @log_method_call(prefix="[DB-会话] ")
    async def create_session(self, user_id: str = "default", title: str = None) -> str:
        """创建会话"""
        session_id = f"session-{uuid.uuid4().hex[:12]}"

        now = datetime.now(CST)

        await self.db.sessions.insert_one({
            "_id": session_id,
            "user_id": user_id,
            "title": title or f"会话 {now.strftime('%H:%M')}",
            "messages": [],
            "metadata": {
                "created_at": now,
                "updated_at": now,
                "message_count": 0
            }
        })

        return session_id

    @log_method_call(prefix="[DB-消息] ")
    async def add_message(self, session_id: str, role: str, content: str, metadata: dict = None):
        """添加消息"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(CST)
        }
        
        # 如果有元数据（如子任务信息），保存到消息中
        if metadata:
            message["metadata"] = metadata

        await self.db.sessions.update_one(
            {"_id": session_id},
            {
                "$push": {"messages": message},
                "$inc": {"metadata.message_count": 1},
                "$set": {"metadata.updated_at": datetime.now(CST)}
            }
        )

    async def get_session(self, session_id: str) -> Optional[dict]:
        """获取会话"""
        session = await self.db.sessions.find_one({"_id": session_id})

        if session:
            session = self._format_session(session)

        return session

    @log_method_call(prefix="[DB-消息] ")
    async def get_messages(self, session_id: str, limit: int = None) -> list:
        """获取消息列表"""
        session = await self.get_session(session_id)
        if not session:
            return []

        messages = session.get("messages", [])

        if limit:
            return messages[-limit:]

        return messages

    async def list_sessions(
        self,
        user_id: str = "default",
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: int = -1
    ) -> List[Dict[str, Any]]:
        """
        列出会话（支持分页）

        Args:
            user_id: 用户ID
            limit: 每页数量
            offset: 跳过数量（用于分页）
            sort_by: 排序字段 (created_at, updated_at, message_count)
            sort_order: 排序方向 (-1降序, 1升序)

        Returns:
            会话列表
        """
        # 构建排序字段
        if sort_by in ["created_at", "updated_at"]:
            sort_field = f"metadata.{sort_by}"
        elif sort_by == "message_count":
            sort_field = "metadata.message_count"
        else:
            sort_field = "metadata.updated_at"  # 默认

        cursor = self.db.sessions.find(
            {"user_id": user_id}
        ).sort(sort_field, sort_order).skip(offset).limit(limit)

        sessions = await cursor.to_list(length=limit)

        # 统一处理时间格式
        return self._format_sessions(sessions)

    async def count_sessions(self, user_id: str = "default") -> int:
        """
        统计用户会话总数（用于分页）

        Args:
            user_id: 用户ID

        Returns:
            会话总数
        """
        return await self.db.sessions.count_documents({"user_id": user_id})

    async def list_sessions_paginated(
        self,
        user_id: str = "default",
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "updated_at",
        sort_order: int = -1
    ) -> Dict[str, Any]:
        """
        分页获取会话（返回完整分页信息）

        Args:
            user_id: 用户ID
            page: 页码（从1开始）
            page_size: 每页数量
            sort_by: 排序字段
            sort_order: 排序方向

        Returns:
            {
                "sessions": [...],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5,
                "has_next": True,
                "has_prev": False,
                "offset": 0
            }
        """
        total = await self.count_sessions(user_id)
        offset = (page - 1) * page_size

        sessions = await self.list_sessions(
            user_id=user_id,
            limit=page_size,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order
        )

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return {
            "sessions": sessions,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
            "offset": offset
        }

    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        result = await self.db.sessions.delete_one({"_id": session_id})
        return result.deleted_count > 0

    async def update_session_title(self, session_id: str, title: str) -> bool:
        """更新会话标题"""
        result = await self.db.sessions.update_one(
            {"_id": session_id},
            {"$set": {"title": title}}
        )
        return result.modified_count > 0

    async def delete_user_sessions(self, user_id: str) -> int:
        """删除用户的所有会话"""
        result = await self.db.sessions.delete_many({"user_id": user_id})
        return result.deleted_count

    # ═══════════════════════════════════════
    # 格式化方法（保持原有时区处理）
    # ═══════════════════════════════════════

    def _format_sessions(self, sessions: List[dict]) -> List[dict]:
        """格式化会话列表的时间"""
        for session in sessions:
            session = self._format_session(session)
        return sessions

    def _format_session(self, session: dict) -> dict:
        """格式化单个会话的时间"""
        # 处理 metadata 中的时间
        if 'metadata' in session:
            # 处理 created_at
            if 'created_at' in session['metadata']:
                created_at = session['metadata']['created_at']
                if created_at and created_at.tzinfo is None:
                    session['metadata']['created_at'] = created_at.replace(tzinfo=CST)

            # 处理 updated_at
            if 'updated_at' in session['metadata']:
                updated_at = session['metadata']['updated_at']
                if updated_at and updated_at.tzinfo is None:
                    session['metadata']['updated_at'] = updated_at.replace(tzinfo=CST)

        # 处理消息中的时间
        if 'messages' in session:
            for msg in session['messages']:
                if 'timestamp' in msg and msg['timestamp']:
                    if msg['timestamp'].tzinfo is None:
                        msg['timestamp'] = msg['timestamp'].replace(tzinfo=CST)

        return session


# 全局实例
_mongodb_manager = None


def get_mongodb(url: str = None, db_name: str = None) -> MongoDBManager:
    """获取 MongoDB 管理器（单例）"""
    global _mongodb_manager
    if _mongodb_manager is None:
        from src.config import get_settings_safe
        settings = get_settings_safe()

        _mongodb_manager = MongoDBManager(
            url=url or settings.MONGODB_URL,
            db_name=db_name or settings.MONGODB_DB
        )

    return _mongodb_manager