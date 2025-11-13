from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Numeric
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    avatar = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # 邮箱验证相关字段
    verification_token = Column(String(255), nullable=True)
    verification_expires = Column(DateTime(timezone=True), nullable=True)
    
    # 密码重置相关字段
    reset_token = Column(String(255), nullable=True)
    reset_expires = Column(DateTime(timezone=True), nullable=True)
    
    # 双因素认证相关字段
    totp_enabled = Column(Boolean, default=False)
    totp_secret = Column(String(255), nullable=True)
    sms_2fa_enabled = Column(Boolean, default=False)
    phone_number = Column(String(20), nullable=True)
    backup_codes = Column(Text, nullable=True)  # JSON格式存储备用验证码
    
    # 用户偏好设置
    theme = Column(String(20), default='light')  # 主题设置: light, dark, auto
    language = Column(String(10), default='zh-CN')  # 语言设置
    timezone = Column(String(50), default='Asia/Shanghai')  # 时区设置
    
    # 通知设置
    email_notifications = Column(Boolean, default=True)  # 是否启用邮件通知
    notification_types = Column(Text, nullable=True)  # 通知类型设置，JSON格式存储，默认包含所有类型
    sms_notifications = Column(Boolean, default=False)  # 是否启用短信通知
    push_notifications = Column(Boolean, default=True)  # 是否启用推送通知
    
    # 隐私设置
    data_sharing = Column(Boolean, default=True)  # 是否允许数据共享，默认开启
    analytics = Column(Boolean, default=True)  # 是否启用使用统计，默认开启
    
    # 余额
    balance = Column(Numeric(10, 2), default=0, nullable=False, comment="账户余额")
    
    # 关系将在 __init__.py 中定义
    # subscriptions, orders, payments, notifications, activities, subscription_resets, login_history, recharge_records
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>" 