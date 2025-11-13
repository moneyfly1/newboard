from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(50), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), default="pending")  # pending, paid, cancelled, refunded
    payment_method_id = Column(Integer, nullable=True, comment="支付方式ID")
    payment_method_name = Column(String(100), nullable=True, comment="支付方式名称")
    payment_time = Column(DateTime(timezone=True), nullable=True)
    payment_transaction_id = Column(String(100), nullable=True, comment="支付交易号")
    expire_time = Column(DateTime(timezone=True), nullable=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=True, comment="使用的优惠券ID")
    discount_amount = Column(Numeric(10, 2), nullable=True, default=0, comment="优惠金额")
    final_amount = Column(Numeric(10, 2), nullable=True, comment="最终支付金额")
    created_at = Column(DateTime(timezone=True), server_default=func.now('localtime'))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now('localtime'))
    
    # 关系
    user = relationship("User", back_populates="orders")
    package = relationship("Package", back_populates="orders")
    coupon = relationship("Coupon", foreign_keys=[coupon_id], backref="orders")
    
    def __repr__(self):
        return f"<Order(id={self.id}, order_no='{self.order_no}', status='{self.status}')>" 