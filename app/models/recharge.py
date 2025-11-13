from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class RechargeRecord(Base):
    """充值记录表"""
    __tablename__ = "recharge_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_no = Column(String(50), unique=True, index=True, nullable=False, comment="充值订单号")
    amount = Column(Numeric(10, 2), nullable=False, comment="充值金额")
    status = Column(String(20), default="pending", comment="状态: pending, paid, cancelled, failed")
    payment_method = Column(String(50), nullable=True, comment="支付方式: alipay, wechat, balance")
    payment_transaction_id = Column(String(100), nullable=True, comment="支付交易号")
    payment_qr_code = Column(Text, nullable=True, comment="支付二维码")
    payment_url = Column(Text, nullable=True, comment="支付链接")
    ip_address = Column(String(45), nullable=True, comment="IP地址")
    user_agent = Column(Text, nullable=True, comment="用户代理")
    paid_at = Column(DateTime(timezone=True), nullable=True, comment="支付时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系（在 __init__.py 中设置）
    
    def __repr__(self):
        return f"<RechargeRecord(id={self.id}, order_no='{self.order_no}', amount={self.amount}, status='{self.status}')>"

