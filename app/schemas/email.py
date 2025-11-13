from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

class EmailQueueBase(BaseModel):
    to_email: str
    subject: str
    content: str
    content_type: str = "plain"  # plain, html
    email_type: Optional[str] = None  # verification, reset, subscription, etc.
    attachments: Optional[List[Dict[str, Any]]] = None

class EmailQueueCreate(EmailQueueBase):
    pass

class EmailQueueUpdate(BaseModel):
    to_email: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    content_type: Optional[str] = None
    email_type: Optional[str] = None
    status: Optional[str] = None
    retry_count: Optional[int] = None
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None

class EmailQueueInDB(EmailQueueBase):
    id: int
    status: str
    retry_count: int
    max_retries: int
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class EmailQueue(EmailQueueInDB):
    pass 