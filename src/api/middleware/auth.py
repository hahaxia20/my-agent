"""
认证中间件
"""
from fastapi import Request, HTTPException
import jwt

from src.config import get_settings_safe

settings = get_settings_safe()
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"


async def get_current_user(request: Request) -> str:
    """从 Token 中获取当前用户 ID"""
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    # Bearer xxx.xxx.xxx
    parts = auth_header.split()
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(status_code=401, detail="认证令牌格式错误")

    token = parts[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # 返回 user_id（MongoDB _id）
        return payload["user_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="令牌已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的令牌")