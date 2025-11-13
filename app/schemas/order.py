from pydantic import BaseModel
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal

if TYPE_CHECKING:
    from app.schemas.package import Package

class OrderBase(BaseModel):
    package_id: int
    amount: Decimal

class OrderCreate(OrderBase):
    payment_method: str = "alipay"
    coupon_code: Optional[str] = None  # 优惠券码
    use_balance: Optional[bool] = False  # 是否使用余额
    balance_amount: Optional[float] = None  # 使用余额的金额（如果为None，则使用全部余额）

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    payment_method_id: Optional[int] = None
    payment_method_name: Optional[str] = None
    payment_time: Optional[datetime] = None
    payment_transaction_id: Optional[str] = None
    expire_time: Optional[datetime] = None

class OrderInDB(OrderBase):
    id: int
    order_no: str
    status: str
    payment_method_id: Optional[int] = None
    payment_method_name: Optional[str] = None
    payment_time: Optional[datetime] = None
    payment_transaction_id: Optional[str] = None
    expire_time: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Order(OrderInDB):
    pass

class OrderWithPackage(Order):
    package: "Package"  # 使用字符串引用避免循环导入 