"""订单服务"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.package import Package
from app.models.payment_config import PaymentConfig
from app.models.user import User
from app.schemas.order import OrderCreate, OrderUpdate
from app.utils.security import generate_order_no

logger = logging.getLogger(__name__)


class OrderService:
    """订单服务类"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, order_id: int) -> Optional[Order]:
        return self.db.query(Order).filter(Order.id == order_id).first()

    def get_by_order_no(self, order_no: str) -> Optional[Order]:
        return self.db.query(Order).filter(Order.order_no == order_no).first()

    def create_order(self, user_id: int, package_id: int, payment_method: str = "alipay", payment_config_id: Optional[int] = None, amount: float = None, coupon_id: Optional[int] = None, discount_amount: float = 0) -> Order:
        order_no = generate_order_no()
        package = self.db.query(Package).filter(Package.id == package_id).first()
        if not package:
            raise ValueError("套餐不存在")
        if amount is None:
            amount = float(package.price)
        order = Order(
            order_no=order_no,
            user_id=user_id,
            package_id=package_id,
            amount=Decimal(str(package.price)),
            status="pending",
            payment_method_id=payment_config_id,
            payment_method_name=payment_method,
            coupon_id=coupon_id,
            discount_amount=Decimal(str(discount_amount)) if discount_amount else Decimal('0'),
            final_amount=Decimal(str(amount)),
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(order)
        try:
            self.db.commit()
            self.db.refresh(order)
            logger.info(f"订单已保存: order_no={order.order_no}, user_id={user_id}, order_id={order.id}")
            return order
        except Exception as e:
            self.db.rollback()
            logger.error(f"订单保存失败: {str(e)}", exc_info=True)
            raise

    def get_user_orders(self, user_id: int, skip: int = 0, limit: int = 100, status: Optional[str] = None, payment_method: Optional[str] = None) -> Tuple[List[Order], int]:
        query = self.db.query(Order).filter(Order.user_id == user_id)
        if status:
            query = query.filter(Order.status == status)
        if payment_method:
            query = query.filter(Order.payment_method_name == payment_method)
        total = query.count()
        orders = query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
        return orders, total

    def _apply_date_filter(self, query, date_filter: str):
        now = datetime.utcnow()
        filters = {
            "today": lambda: (now.replace(hour=0, minute=0, second=0, microsecond=0), now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)),
            "yesterday": lambda: ((now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0), (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)),
            "week": lambda: (now - timedelta(days=7), None),
            "month": lambda: (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), None)
        }
        if date_filter in filters:
            start_date, end_date = filters[date_filter]()
            query = query.filter(Order.created_at >= start_date)
            if end_date:
                query = query.filter(Order.created_at < end_date)
        return query

    def get_orders_with_pagination(self, skip: int = 0, limit: int = 100, status: Optional[str] = None, date_filter: Optional[str] = None, search: Optional[str] = None) -> Tuple[List[Order], int]:
        self.db.expire_all()
        query = self.db.query(Order)
        if status:
            query = query.filter(Order.status == status)
        if date_filter:
            query = self._apply_date_filter(query, date_filter)
        if search:
            query = query.join(User).filter(
                or_(User.username.contains(search), User.email.contains(search), Order.order_no.contains(search))
            )
        total = query.count()
        orders = query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
        return orders, total

    def update(self, order_id: int, order_update: OrderUpdate) -> Optional[Order]:
        order = self.get(order_id)
        if not order:
            return None
        update_data = order_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(order, field, value)
        self.db.commit()
        self.db.refresh(order)
        return order

    def cancel_order(self, order_no: str) -> bool:
        order = self.get_by_order_no(order_no)
        if not order or order.status != "pending":
            return False
        order.status = "cancelled"
        self.db.commit()
        return True

    def complete_payment(self, order_no: str, payment_time: datetime = None, transaction_id: str = None) -> bool:
        order = self.get_by_order_no(order_no)
        if not order:
            logger.warning(f"未找到订单: {order_no}")
            return False
        if order.status != "pending":
            logger.info(f"订单 {order_no} 状态不是pending，当前状态: {order.status}")
            if order.status == "paid":
                return True
            return False
        if payment_time is None:
            payment_time = datetime.now(timezone.utc)
        elif payment_time.tzinfo is None:
            payment_time = payment_time.replace(tzinfo=timezone.utc)
        if transaction_id:
            order.payment_transaction_id = transaction_id
        order.status = "paid"
        order.payment_time = payment_time
        self.db.commit()
        self.db.refresh(order)
        logger.info(f"订单 {order_no} 状态已更新为paid，支付时间: {payment_time}")
        from app.services.subscription import SubscriptionService
        subscription_service = SubscriptionService(self.db)
        try:
            success = subscription_service.process_paid_order(order)
            if success:
                logger.info(f"订单 {order_no} 支付处理成功，订阅已更新")
            else:
                logger.warning(f"订单 {order_no} 订阅更新失败，但订单状态已更新为paid")
                success = True
        except Exception as e:
            logger.error(f"订单 {order_no} 订阅更新异常: {str(e)}", exc_info=True)
            success = True
        return success

    def generate_payment_url(self, order: Order) -> str:
        try:
            from app.services.payment import PaymentService
            from app.schemas.payment import PaymentCreate
            from app.core.domain_config import get_domain_config
            domain_config = get_domain_config()
            base_url = domain_config.get_base_url(None, self.db).strip()
            payment_service = PaymentService(self.db)
            payment_request = PaymentCreate(
                order_no=order.order_no,
                amount=float(order.amount),
                currency="CNY",
                payment_method=order.payment_method_name or "alipay",
                subject=f"CBoard套餐购买-{order.order_no}",
                body=f"订单号：{order.order_no}",
                notify_url=f"{base_url}/api/v1/payment/notify/{order.payment_method_name}".strip(),
                return_url=f"{base_url}/payment/success".strip()
            )
            payment_response = payment_service.create_payment(payment_request)
            if payment_response.status == "failed" or not payment_response.payment_url:
                logger.error(f"支付创建失败: {payment_response}")
                raise Exception("支付创建失败，请检查支付配置")
            return payment_response.payment_url
        except Exception as e:
            logger.error(f"生成支付URL失败: {str(e)}", exc_info=True)
            raise Exception(f"生成支付链接失败: {str(e)}")

    def count(self) -> int:
        return self.db.query(Order).count()

    def count_by_status(self, status: str) -> int:
        return self.db.query(Order).filter(Order.status == status).count()

    def count_orders_since(self, start_date: datetime, end_date: Optional[datetime] = None) -> int:
        query = self.db.query(Order).filter(Order.created_at >= start_date)
        if end_date:
            query = query.filter(Order.created_at < end_date)
        return query.count()

    def get_revenue_since(self, start_date: datetime, end_date: Optional[datetime] = None) -> float:
        query = self.db.query(func.sum(Order.amount)).filter(
            and_(Order.status == "paid", Order.created_at >= start_date)
        )
        if end_date:
            query = query.filter(Order.created_at < end_date)
        result = query.scalar()
        return float(result) if result else 0.0

    def get_total_revenue(self) -> float:
        result = self.db.query(func.sum(Order.amount)).filter(Order.status == "paid").scalar()
        return float(result) if result else 0.0

    def get_recent_orders(self, days: int = 7, limit: int = 100) -> List[Order]:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self.db.query(Order).filter(Order.created_at >= cutoff_date).order_by(Order.created_at.desc()).limit(limit).all()

    def get_order_stats(self) -> dict:
        total_orders = self.count()
        pending_orders = self.count_by_status("pending")
        paid_orders = self.count_by_status("paid")
        cancelled_orders = self.count_by_status("cancelled")
        total_revenue = self.get_total_revenue()
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_orders = self.count_orders_since(today_start)
        today_revenue = self.get_revenue_since(today_start)
        return {
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "paid_orders": paid_orders,
            "cancelled_orders": cancelled_orders,
            "total_revenue": total_revenue,
            "today_orders": today_orders,
            "today_revenue": today_revenue
        }
