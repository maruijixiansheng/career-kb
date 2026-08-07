"""JWT 认证工具 — token 生成、验证、密码哈希"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt, JWTError

from ..config import settings

# JWT 密钥（生产环境必须通过环境变量配置）
_SECRET_KEY = settings.SECRET_KEY or uuid.uuid4().hex
_ALGORITHM = "HS256"


def create_access_token(user_id: str) -> str:
    """生成 JWT access token"""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)


def verify_token(token: str) -> dict | None:
    """验证 JWT token，返回 payload 或 None"""
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        return payload
    except JWTError:
        return None


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
