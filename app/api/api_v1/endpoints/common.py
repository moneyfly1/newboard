from typing import Any, Callable, Optional
from functools import wraps
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.schemas.common import ResponseBase
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def _get_error_message(error: Exception, operation: str, debug: bool = None) -> str:
    if debug is None:
        debug = settings.DEBUG
    return f"{operation}失败: {str(error)}" if debug else f"{operation}失败，请稍后重试或联系管理员"

def _handle_exception(e: Exception, operation: str, db: Optional[Session] = None) -> ResponseBase:
    if db:
        try:
            db.rollback()
        except Exception:
            pass
    error_msg = f"{operation}失败: {str(e)}"
    logger.error(f"❌ {error_msg}", exc_info=True)
    user_message = _get_error_message(e, operation)
    return ResponseBase(success=False, message=user_message)

def handle_api_error(operation: str = "操作"):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                return _handle_exception(e, operation)
        return wrapper
    return decorator

def safe_db_operation(operation: str = "数据库操作", db: Optional[Session] = None):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                return _handle_exception(e, operation, db)
        return wrapper
    return decorator

def validate_required_fields(data: dict, required_fields: list) -> None:
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"缺少必需字段: {', '.join(missing_fields)}"
        )

def format_error_response(error: Exception, operation: str = "操作", db: Optional[Session] = None) -> ResponseBase:
    return _handle_exception(error, operation, db)
