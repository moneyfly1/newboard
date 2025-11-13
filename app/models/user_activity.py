from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class UserActivity(Base):
    """用户操作历史记录"""
    __tablename__ = "user_activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    activity_type = Column(String(50), nullable=False)  # login, logout, password_change, profile_update, etc.
    description = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    location = Column(String(100), nullable=True)
    activity_metadata = Column(JSON, nullable=True)  # 存储额外的操作数据
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user = relationship("User", back_populates="activities")
    
    def __repr__(self):
        return f"<UserActivity(id={self.id}, user_id={self.user_id}, type='{self.activity_type}')>"

class SubscriptionReset(Base):
    """订阅重置记录"""
    __tablename__ = "subscription_resets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    reset_type = Column(String(50), nullable=False)  # manual, automatic, admin
    reason = Column(Text, nullable=True)
    old_subscription_url = Column(String(255), nullable=True)
    new_subscription_url = Column(String(255), nullable=True)
    device_count_before = Column(Integer, default=0)
    device_count_after = Column(Integer, default=0)
    reset_by = Column(String(50), nullable=True)  # user, admin, system
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user = relationship("User", back_populates="subscription_resets")
    subscription = relationship("Subscription", back_populates="resets")
    
    def __repr__(self):
        return f"<SubscriptionReset(id={self.id}, user_id={self.user_id}, type='{self.reset_type}')>"

class LoginHistory(Base):
    """登录历史记录"""
    __tablename__ = "login_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    login_time = Column(DateTime(timezone=True), server_default=func.now())
    logout_time = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    location = Column(String(100), nullable=True)
    device_fingerprint = Column(String(255), nullable=True)
    login_status = Column(String(20), default="success")  # success, failed, blocked
    failure_reason = Column(Text, nullable=True)
    session_duration = Column(Integer, nullable=True)  # 会话持续时间（秒）
    
    # 关系
    user = relationship("User", back_populates="login_history")
    
    def __repr__(self):
        return f"<LoginHistory(id={self.id}, user_id={self.user_id}, status='{self.login_status}')>"
