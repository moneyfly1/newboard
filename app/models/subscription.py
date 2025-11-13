from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=True)
    subscription_url = Column(String(100), unique=True, index=True, nullable=False)
    device_limit = Column(Integer, default=3)
    current_devices = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    status = Column(String(20), default='active')  # active, expired, cancelled
    expire_time = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    user = relationship("User", back_populates="subscriptions")
    package = relationship("Package", back_populates="subscriptions")
    devices = relationship("Device", back_populates="subscription")
    resets = relationship("SubscriptionReset", back_populates="subscription")
    
    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, url='{self.subscription_url}')>"
class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # 直接关联用户
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    device_fingerprint = Column(String(255), nullable=False)
    device_hash = Column(String(255), nullable=True)  # 设备哈希
    device_ua = Column(String(255), nullable=True)  # 设备UA组合
    device_name = Column(String(100), nullable=True)
    device_type = Column(String(50), nullable=True)  # mobile, desktop, tablet
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    software_name = Column(String(100), nullable=True)  # 软件名称
    software_version = Column(String(50), nullable=True)  # 软件版本
    os_name = Column(String(50), nullable=True)  # 操作系统名称
    os_version = Column(String(50), nullable=True)  # 操作系统版本
    device_model = Column(String(100), nullable=True)  # 设备型号
    device_brand = Column(String(50), nullable=True)  # 设备品牌
    is_active = Column(Boolean, default=True)
    is_allowed = Column(Boolean, default=True)  # 是否允许访问
    first_seen = Column(DateTime(timezone=True), nullable=True)  # 首次出现
    last_access = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), nullable=True)  # 最后出现
    access_count = Column(Integer, default=0)  # 访问次数
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    user = relationship("User", back_populates="devices")
    subscription = relationship("Subscription", back_populates="devices")
    
    def __repr__(self):
        return f"<Device(id={self.id}, subscription_id={self.subscription_id}, fingerprint='{self.device_fingerprint}')>" 
