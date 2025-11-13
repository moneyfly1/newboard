"""响应工具函数"""
import logging
from typing import Optional

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)


def sanitize_error_message(message: str, debug: bool = None) -> str:
    """清理错误消息，移除敏感信息"""
    if debug is None:
        debug = settings.DEBUG

    if debug:
        return message

    sensitive_patterns = [
        'password',
        'secret',
        'key',
        'token',
        'api_key',
        'database',
        'db',
        'connection',
        'sql',
        'query',
        'file path',
        'directory',
        'path',
        'traceback',
        'stack trace',
        'exception',
        'error at'
    ]

    message_lower = message.lower()
    for pattern in sensitive_patterns:
        if pattern in message_lower:
            return "操作失败，请稍后重试或联系管理员"

    return message


def create_error_response(
    status_code: int,
    message: str,
    detail: Optional[str] = None,
    debug: bool = None
) -> JSONResponse:
    """创建错误响应"""
    if debug is None:
        debug = settings.DEBUG

    safe_message = sanitize_error_message(message, debug)

    content = {
        "success": False,
        "message": safe_message,
        "data": None
    }

    if debug and detail:
        content["detail"] = detail

    return JSONResponse(
        status_code=status_code,
        content=content
    )


def create_safe_http_exception(
    status_code: int,
    message: str,
    detail: Optional[str] = None,
    debug: bool = None
) -> HTTPException:
    """创建安全的HTTP异常"""
    if debug is None:
        debug = settings.DEBUG

    safe_message = sanitize_error_message(message, debug)

    if debug and detail:
        return HTTPException(
            status_code=status_code,
            detail=f"{safe_message}: {detail}"
        )

    return HTTPException(
        status_code=status_code,
        detail=safe_message
    )
