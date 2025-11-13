"""
验证码尝试记录模型
用于跟踪验证码验证失败次数，防止暴力破解
"""
from sqlalchemy import Column, Integer, String, DateTime, Index, Boolean
from sqlalchemy.sql import func
from app.core.database import Base
from datetime import datetime, timezone


class VerificationAttempt(Base):
    """验证码尝试记录表"""
    __tablename__ = "verification_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), nullable=False, index=True)  # 邮箱
    ip_address = Column(String(45), index=True)  # IP地址
    success = Column(Boolean, default=False)  # 是否成功
    purpose = Column(String(50), default='register')  # 用途：register, reset_password
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('idx_email_created', 'email', 'created_at'),
        Index('idx_ip_created', 'ip_address', 'created_at'),
    )
    
    def __repr__(self):
        return f"<VerificationAttempt(email='{self.email}', success={self.success}, purpose='{self.purpose}')>"

