"""
JWT Token 验证模块 — 用于 iframe 嵌入场景下的 token 认证

支持两种方式传递 token：
1. Authorization: Bearer <token> 请求头（常规 API 调用）
2. ?token=<token> URL 查询参数（文件预览/下载等无法设置 header 的场景）
"""
import logging

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def _decode_token(token: str) -> dict:
    """解码并验证 JWT token，成功返回 payload，失败抛出 HTTPException。"""
    if not settings.JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT 认证未配置，请在 .env 中设置 JWT_SECRET",
        )
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        logger.info("JWT token 验证成功，payload: %s", payload)
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    query_token: str = Query(default="", alias="token", include_in_schema=False),
) -> dict:
    """
    验证 JWT token。

    优先从 Authorization header 读取，若不存在则从 URL ?token= 参数读取。
    验证成功返回 payload dict，失败抛出 401。
    """
    token: str | None = None

    if credentials is not None:
        token = credentials.credentials
    elif query_token:
        token = query_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _decode_token(token)


async def get_current_user_info(
    payload: dict = Depends(verify_token),
) -> dict:
    """验证 token 并返回用户信息，用于 /auth/me 接口。"""
    return payload
