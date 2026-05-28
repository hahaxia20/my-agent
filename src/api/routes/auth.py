"""
认证 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.storage.mongodb import get_mongodb
import bcrypt
import jwt
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# JWT 配置
from src.config import get_settings_safe

settings = get_settings_safe()
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    success: bool
    token: str
    username: str


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """用户注册"""
    db = get_mongodb()

    # 检查用户名是否已存在
    if await db.find_user(request.username):
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 密码加密
    password_hash = bcrypt.hashpw(
        request.password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

    # 创建用户，获取 user_id
    user_id = await db.create_user(request.username, password_hash)
    
    if not user_id:
        raise HTTPException(status_code=500, detail="注册失败")

    # 生成 Token（存储 user_id 和 username）
    token = jwt.encode(
        {
            "user_id": user_id,
            "username": request.username,
            "exp": datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return TokenResponse(
        success=True,
        token=token,
        username=request.username
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """用户登录"""
    db = get_mongodb()

    # 查找用户
    user = await db.find_user(request.username)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 验证密码
    if not bcrypt.checkpw(
            request.password.encode('utf-8'),
            user["password_hash"].encode('utf-8')
    ):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 生成 Token（存储 user_id 和 username）
    token = jwt.encode(
        {
            "user_id": str(user["_id"]),
            "username": user["username"],
            "exp": datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return TokenResponse(
        success=True,
        token=token,
        username=user["username"]
    )