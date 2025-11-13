from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base

class PaymentMethod(Base):
    __tablename__ = "payment_methods"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="支付方式名称")
    type = Column(String(50), nullable=False, comment="支付类型")
    status = Column(String(20), default="active", comment="状态: active, inactive")
    sort_order = Column(Integer, default=0, comment="排序")
    description = Column(Text, comment="描述")
    
    # 配置信息（JSON格式存储）
    config = Column(JSON, comment="支付配置信息")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    class Config:
        from_attributes = True

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, comment="订单ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    payment_method_id = Column(Integer, ForeignKey("payment_methods.id"), nullable=False, comment="支付方式ID")
    
    amount = Column(Integer, nullable=False, comment="支付金额（分）")
    currency = Column(String(10), default="CNY", comment="货币")
    
    transaction_id = Column(String(100), unique=True, comment="交易流水号")
    external_transaction_id = Column(String(100), comment="第三方交易号")
    
    status = Column(String(20), default="pending", comment="状态: pending, success, failed, cancelled")
    
    # 支付详情
    payment_data = Column(JSON, comment="支付相关数据")
    callback_data = Column(JSON, comment="回调数据")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    class Config:
        from_attributes = True

class PaymentCallback(Base):
    __tablename__ = "payment_callbacks"

    id = Column(Integer, primary_key=True, index=True)
    payment_transaction_id = Column(Integer, nullable=False, comment="支付交易ID")
    callback_type = Column(String(50), nullable=False, comment="回调类型: notify, return, webhook")
    callback_data = Column(JSON, nullable=False, comment="回调数据")
    raw_request = Column(Text, comment="原始请求数据")
    processed = Column(Boolean, default=False, comment="是否已处理")
    processing_result = Column(String(50), comment="处理结果: success, failed, pending")
    error_message = Column(Text, comment="错误信息")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    class Config:
        from_attributes = True 