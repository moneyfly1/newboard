"""
工单相关的 Pydantic 模型
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.ticket import TicketStatus, TicketType, TicketPriority


class TicketBase(BaseModel):
    """工单基础模型"""
    title: str = Field(..., min_length=1, max_length=200, description="工单标题")
    content: str = Field(..., min_length=1, description="工单内容")
    type: TicketType = Field(default=TicketType.OTHER, description="工单类型")
    priority: TicketPriority = Field(default=TicketPriority.NORMAL, description="优先级")


class TicketCreate(TicketBase):
    """创建工单"""
    pass


class TicketUpdate(BaseModel):
    """更新工单"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    assigned_to: Optional[int] = None
    admin_notes: Optional[str] = None


class TicketReplyCreate(BaseModel):
    """创建工单回复"""
    content: str = Field(..., min_length=1, description="回复内容")


class TicketRating(BaseModel):
    """工单评价"""
    rating: int = Field(..., ge=1, le=5, description="评分（1-5星）")
    rating_comment: Optional[str] = Field(None, description="评价内容")


class TicketAttachmentCreate(BaseModel):
    """创建工单附件"""
    file_name: str
    file_path: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None


class TicketReplyInDB(BaseModel):
    """工单回复（数据库模型）"""
    id: int
    ticket_id: int
    user_id: int
    content: str
    is_admin: str
    created_at: datetime
    user: Optional[dict] = None
    
    class Config:
        from_attributes = True


class TicketAttachmentInDB(BaseModel):
    """工单附件（数据库模型）"""
    id: int
    ticket_id: int
    reply_id: Optional[int] = None
    file_name: str
    file_path: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class TicketInDB(BaseModel):
    """工单（数据库模型）"""
    id: int
    ticket_no: str
    user_id: int
    title: str
    content: str
    type: TicketType
    status: TicketStatus
    priority: TicketPriority
    assigned_to: Optional[int] = None
    admin_notes: Optional[str] = None
    rating: Optional[int] = None
    rating_comment: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    user: Optional[dict] = None
    assignee: Optional[dict] = None
    replies: Optional[List[TicketReplyInDB]] = []
    attachments: Optional[List[TicketAttachmentInDB]] = []
    
    class Config:
        from_attributes = True

