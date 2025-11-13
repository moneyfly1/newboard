from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# 通知类型枚举
class NotificationType(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"
    success = "success"
    system = "system"

# 通知状态枚举
class NotificationStatus(str, Enum):
    unread = "unread"
    read = "read"
    archived = "archived"

class NotificationBase(BaseModel):
    title: str
    content: str
    type: str = "system"

class NotificationCreate(NotificationBase):
    user_id: Optional[int] = None
    send_email: bool = False

class NotificationUpdate(NotificationBase):
    title: Optional[str] = None
    content: Optional[str] = None
    type: Optional[str] = None
    is_read: Optional[bool] = None
    send_email: bool = False

class Notification(NotificationBase):
    id: int
    user_id: Optional[int]
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# 通知数据库模型别名
NotificationInDB = Notification

# 通知广播
class NotificationBroadcast(BaseModel):
    title: str = Field(..., description="通知标题")
    content: str = Field(..., description="通知内容")
    type: NotificationType = Field(NotificationType.info, description="通知类型")
    user_ids: Optional[List[int]] = Field(None, description="指定用户ID列表，为空则广播给所有用户")
    send_email: bool = Field(False, description="是否同时发送邮件通知")

# 邮件模板数据库模型别名（在类定义后设置）
# EmailTemplateInDB = EmailTemplatePreview

class NotificationList(BaseModel):
    notifications: List[Notification]
    total: int
    page: int
    size: int

# 邮件模板相关Schema
class EmailTemplateBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    subject: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=10)
    variables: Optional[str] = None
    is_active: bool = True

class EmailTemplateCreate(EmailTemplateBase):
    pass

class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    subject: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=10)
    variables: Optional[str] = None
    is_active: Optional[bool] = None

class EmailTemplate(EmailTemplateBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class EmailTemplateList(BaseModel):
    templates: List[EmailTemplate]
    total: int
    page: int
    size: int

class EmailTemplatePreview(BaseModel):
    template_name: str
    variables: Dict[str, Any] = Field(default_factory=dict)
    preview_subject: Optional[str] = None
    preview_content: Optional[str] = None

# 邮件模板数据库模型别名
EmailTemplateInDB = EmailTemplatePreview


class EmailTemplateDuplicate(BaseModel):
    template_id: int
    new_name: str = Field(..., min_length=2, max_length=100) 