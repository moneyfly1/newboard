"""
登录尝试记录模型
用于跟踪登录失败次数，实现账户锁定机制
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index
from sqlalchemy.sql import func
from app.core.database import Base
from datetime import datetime, timezone


class LoginAttempt(Base):
    """登录尝试记录表"""
    __tablename__ = "login_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, index=True)  # 用户名或邮箱
    ip_address = Column(String(45), index=True)  # IP地址
    success = Column(Boolean, default=False)  # 是否成功
    user_agent = Column(String(500))  # 用户代理
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('idx_username_created', 'username', 'created_at'),
        Index('idx_ip_created', 'ip_address', 'created_at'),
    )
    
    def __repr__(self):
        return f"<LoginAttempt(username='{self.username}', success={self.success}, ip='{self.ip_address}')>"

