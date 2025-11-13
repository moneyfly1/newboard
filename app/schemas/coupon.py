"""
优惠券相关的 Pydantic 模型
"""
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from app.models.coupon import CouponType, CouponStatus


class CouponBase(BaseModel):
    """优惠券基础模型"""
    name: str = Field(..., min_length=1, max_length=100, description="优惠券名称")
    description: Optional[str] = Field(None, description="优惠券描述")
    type: CouponType = Field(..., description="优惠券类型")
    discount_value: Decimal = Field(..., ge=0, description="优惠值")
    min_amount: Optional[Decimal] = Field(default=0, ge=0, description="最低消费金额")
    max_discount: Optional[Decimal] = Field(None, ge=0, description="最大折扣金额（仅折扣类型）")
    valid_from: datetime = Field(..., description="生效时间")
    valid_until: datetime = Field(..., description="失效时间")
    total_quantity: Optional[int] = Field(None, ge=1, description="总发放数量")
    max_uses_per_user: int = Field(default=1, ge=1, description="每个用户最多使用次数")
    applicable_packages: Optional[List[int]] = Field(None, description="适用套餐ID列表")


class CouponCreate(CouponBase):
    """创建优惠券"""
    code: Optional[str] = Field(None, max_length=50, description="优惠券码（不提供则自动生成）")
    status: CouponStatus = Field(default=CouponStatus.ACTIVE, description="状态")


class CouponUpdate(BaseModel):
    """更新优惠券"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    discount_value: Optional[Decimal] = Field(None, ge=0)
    min_amount: Optional[Decimal] = Field(None, ge=0)
    max_discount: Optional[Decimal] = Field(None, ge=0)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    total_quantity: Optional[int] = Field(None, ge=1)
    max_uses_per_user: Optional[int] = Field(None, ge=1)
    status: Optional[CouponStatus] = None
    applicable_packages: Optional[List[int]] = None


class CouponValidate(BaseModel):
    """验证优惠券"""
    code: str = Field(..., min_length=1, max_length=50, description="优惠券码")
    amount: Decimal = Field(..., ge=0, description="订单金额")
    package_id: Optional[int] = Field(None, description="套餐ID")


class CouponUsageInDB(BaseModel):
    """优惠券使用记录（数据库模型）"""
    id: int
    coupon_id: int
    user_id: int
    order_id: Optional[int] = None
    discount_amount: Decimal
    used_at: datetime
    coupon: Optional[dict] = None
    user: Optional[dict] = None
    
    class Config:
        from_attributes = True


class CouponInDB(BaseModel):
    """优惠券（数据库模型）"""
    id: int
    code: str
    name: str
    description: Optional[str] = None
    type: CouponType
    discount_value: Decimal
    min_amount: Optional[Decimal] = None
    max_discount: Optional[Decimal] = None
    valid_from: datetime
    valid_until: datetime
    total_quantity: Optional[int] = None
    used_quantity: int
    max_uses_per_user: int
    status: CouponStatus
    applicable_packages: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

