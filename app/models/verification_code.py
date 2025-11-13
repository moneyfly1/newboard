from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func
from app.core.database import Base
from datetime import datetime, timezone

class VerificationCode(Base):
    """邮箱验证码表"""
    __tablename__ = "verification_codes"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), nullable=False, index=True)
    code = Column(String(6), nullable=False)  # 6位数字验证码
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Integer, default=0)  # 0=未使用, 1=已使用
    purpose = Column(String(50), default='register')  # register, reset_password, etc.
    
    __table_args__ = (
        Index('idx_email_created', 'email', 'created_at'),
    )
    
    def is_expired(self) -> bool:
        """检查验证码是否过期"""
        now = datetime.now(timezone.utc)
        # 如果 expires_at 没有时区信息，添加 UTC 时区
        if self.expires_at.tzinfo is None:
            expires_at = self.expires_at.replace(tzinfo=timezone.utc)
        else:
            expires_at = self.expires_at
        return now > expires_at
    
    def is_used(self) -> bool:
        """检查验证码是否已使用"""
        return self.used == 1
    
    def mark_as_used(self):
        """标记验证码为已使用"""
        self.used = 1
    
    def __repr__(self):
        return f"<VerificationCode(email='{self.email}', code='{self.code}', expires_at='{self.expires_at}')>"

