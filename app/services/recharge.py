"""充值服务"""
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.recharge import RechargeRecord
from app.models.user import User
from app.utils.security import generate_order_no


class RechargeService:
    """充值服务类"""

    def __init__(self, db: Session):
        self.db = db

    def create_recharge(self, user_id: int, amount: Decimal, payment_method: str = "alipay", ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> RechargeRecord:
        order_no = f"R{generate_order_no()}"
        recharge = RechargeRecord(
            user_id=user_id,
            order_no=order_no,
            amount=amount,
            status="pending",
            payment_method=payment_method,
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.db.add(recharge)
        self.db.commit()
        self.db.refresh(recharge)
        return recharge

    def get_by_order_no(self, order_no: str) -> Optional[RechargeRecord]:
        return self.db.query(RechargeRecord).filter(RechargeRecord.order_no == order_no).first()

    def get_by_id(self, recharge_id: int) -> Optional[RechargeRecord]:
        return self.db.query(RechargeRecord).filter(RechargeRecord.id == recharge_id).first()

    def get_user_recharges(self, user_id: int, skip: int = 0, limit: int = 100, status: Optional[str] = None) -> Tuple[List[RechargeRecord], int]:
        query = self.db.query(RechargeRecord).filter(RechargeRecord.user_id == user_id)
        if status:
            query = query.filter(RechargeRecord.status == status)
        total = query.count()
        recharges = query.order_by(RechargeRecord.created_at.desc()).offset(skip).limit(limit).all()
        return recharges, total

    def update_payment_info(self, recharge_id: int, payment_url: Optional[str] = None, payment_qr_code: Optional[str] = None, payment_transaction_id: Optional[str] = None) -> bool:
        recharge = self.get_by_id(recharge_id)
        if not recharge:
            return False
        if payment_url:
            recharge.payment_url = payment_url
        if payment_qr_code:
            recharge.payment_qr_code = payment_qr_code
        if payment_transaction_id:
            recharge.payment_transaction_id = payment_transaction_id
        self.db.commit()
        return True

    def mark_as_paid(self, recharge_id: int, payment_transaction_id: Optional[str] = None) -> bool:
        recharge = self.get_by_id(recharge_id)
        if not recharge or recharge.status != "pending":
            return False
        recharge.status = "paid"
        recharge.paid_at = datetime.now(timezone.utc)
        if payment_transaction_id:
            recharge.payment_transaction_id = payment_transaction_id
        user = self.db.query(User).filter(User.id == recharge.user_id).first()
        if user:
            user.balance = (user.balance or Decimal('0')) + recharge.amount
        self.db.commit()
        return True

    def cancel_recharge(self, recharge_id: int) -> bool:
        recharge = self.get_by_id(recharge_id)
        if not recharge or recharge.status != "pending":
            return False
        recharge.status = "cancelled"
        self.db.commit()
        return True
