from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Numeric
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Package(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    duration_days = Column(Integer, nullable=False)
    device_limit = Column(Integer, default=3)
    bandwidth_limit = Column(Integer, nullable=True)  # 流量限制（GB）
    sort_order = Column(Integer, default=1)  # 排序顺序
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    orders = relationship("Order", back_populates="package")
    subscriptions = relationship("Subscription", back_populates="package")
    
    def __repr__(self):
        return f"<Package(id={self.id}, name='{self.name}', price={self.price})>"
