"""
优惠券模型
"""
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, Boolean, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum
import secrets
import string


class CouponType(str, enum.Enum):
    """优惠券类型"""
    DISCOUNT = "discount"  # 折扣（百分比）
    FIXED = "fixed"  # 固定金额减免
    FREE_DAYS = "free_days"  # 赠送天数


class CouponStatus(str, enum.Enum):
    """优惠券状态"""
    ACTIVE = "active"  # 有效
    INACTIVE = "inactive"  # 无效
    EXPIRED = "expired"  # 已过期


class Coupon(Base):
    """优惠券模型"""
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False, comment="优惠券码")
    name = Column(String(100), nullable=False, comment="优惠券名称")
    description = Column(Text, nullable=True, comment="优惠券描述")
    type = Column(SQLEnum(CouponType), nullable=False, comment="优惠券类型")
    
    # 优惠金额/比例
    discount_value = Column(Numeric(10, 2), nullable=False, comment="优惠值（折扣百分比或固定金额或天数）")
    
    # 使用限制
    min_amount = Column(Numeric(10, 2), nullable=True, default=0, comment="最低消费金额")
    max_discount = Column(Numeric(10, 2), nullable=True, comment="最大折扣金额（仅折扣类型）")
    
    # 有效期
    valid_from = Column(DateTime(timezone=True), nullable=False, comment="生效时间")
    valid_until = Column(DateTime(timezone=True), nullable=False, comment="失效时间")
    
    # 使用限制
    total_quantity = Column(Integer, nullable=True, comment="总发放数量（None表示无限制）")
    used_quantity = Column(Integer, default=0, comment="已使用数量")
    max_uses_per_user = Column(Integer, default=1, comment="每个用户最多使用次数")
    
    # 状态
    status = Column(SQLEnum(CouponStatus), default=CouponStatus.ACTIVE, comment="状态")
    
    # 适用套餐（None表示所有套餐）
    applicable_packages = Column(Text, nullable=True, comment="适用套餐ID列表（JSON格式）")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID")
    
    # 关系
    creator = relationship("User", foreign_keys=[created_by], backref="created_coupons")
    usages = relationship("CouponUsage", back_populates="coupon", cascade="all, delete-orphan")
    
    @staticmethod
    def generate_code(length: int = 8) -> str:
        """生成优惠券码"""
        characters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(characters) for _ in range(length))
    
    def __repr__(self):
        return f"<Coupon(id={self.id}, code='{self.code}', type='{self.type}')>"


class CouponUsage(Base):
    """优惠券使用记录"""
    __tablename__ = "coupon_usages"

    id = Column(Integer, primary_key=True, index=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=False, comment="优惠券ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, comment="订单ID")
    discount_amount = Column(Numeric(10, 2), nullable=False, comment="实际折扣金额")
    used_at = Column(DateTime(timezone=True), server_default=func.now(), comment="使用时间")
    
    # 关系
    coupon = relationship("Coupon", back_populates="usages")
    user = relationship("User", backref="coupon_usages")
    order = relationship("Order", backref="coupon_usages")
    
    def __repr__(self):
        return f"<CouponUsage(id={self.id}, coupon_id={self.coupon_id}, user_id={self.user_id})>"

