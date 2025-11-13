from pydantic import BaseModel
from typing import Optional, Any, List
from .user import User

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    user: Optional[User] = None

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None

class ResponseBase(BaseModel):
    success: bool = True
    message: str = "Success"
    data: Optional[Any] = None

class PaginationParams(BaseModel):
    page: int = 1
    size: int = 10
    search: Optional[str] = None

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int

class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[Any] = None 