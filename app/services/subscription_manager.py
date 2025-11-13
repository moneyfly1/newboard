"""订阅管理服务"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.package import Package
from app.models.subscription import Subscription
from app.models.user import User

logger = logging.getLogger(__name__)


class SubscriptionManager:
    """订阅管理器类"""

    def __init__(self, db: Session):
        self.db = db

    def _send_notification(self, method_name: str, *args):
        try:
            from app.services.notification_service import NotificationService
            notification_service = NotificationService(self.db)
            getattr(notification_service, method_name)(*args)
        except Exception as e:
            logger.warning(f"发送通知失败 ({method_name}): {e}")

    def _update_subscription_fields(self, subscription: Subscription, device_limit: int = None, expire_time: datetime = None, status: str = None, package_id: int = None):
        if device_limit is not None:
            subscription.device_limit = device_limit
        if expire_time is not None:
            subscription.expire_time = expire_time
        if status is not None:
            subscription.status = status
        if package_id is not None:
            subscription.package_id = package_id
        subscription.updated_at = datetime.now()

    def process_paid_order(self, order: Order) -> bool:
        try:
            user = self.db.query(User).filter(User.id == order.user_id).first()
            package = self.db.query(Package).filter(Package.id == order.package_id).first()
            if not user or not package:
                return False
            current_subscription = self.db.query(Subscription).filter(
                Subscription.user_id == user.id,
                Subscription.status == 'active'
            ).first()
            new_device_limit = package.device_limit
            new_expire_time = self._calculate_expire_time(current_subscription, package, order.created_at)
            if current_subscription and current_subscription.status == 'active':
                if package.device_limit > current_subscription.device_limit:
                    self._handle_device_upgrade(current_subscription, new_device_limit, new_expire_time)
                else:
                    self._handle_subscription_renewal(current_subscription, new_expire_time)
            else:
                if current_subscription:
                    self._reactivate_expired_subscription(current_subscription, package, new_device_limit, new_expire_time)
                else:
                    self._create_new_subscription(user, package, new_device_limit, new_expire_time)
            order.status = 'paid'
            order.payment_time = datetime.now()
            self.db.commit()
            self._send_notification('send_payment_success_notification', order)
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"处理订单支付失败: {e}", exc_info=True)
            return False

    def _calculate_expire_time(self, current_subscription: Optional[Subscription], package: Package, order_time: datetime) -> datetime:
        package_duration = timedelta(days=package.duration_days)
        if current_subscription and current_subscription.status == 'active' and current_subscription.expire_time > order_time:
            return current_subscription.expire_time + package_duration
        return order_time + package_duration

    def _handle_device_upgrade(self, current_subscription: Subscription, new_device_limit: int, new_expire_time: datetime):
        remaining_time = current_subscription.expire_time - datetime.now()
        total_time = current_subscription.expire_time - current_subscription.created_at
        if remaining_time.total_seconds() > 0 and total_time.total_seconds() > 0:
            remaining_ratio = remaining_time.total_seconds() / total_time.total_seconds()
        self._update_subscription_fields(current_subscription, new_device_limit, new_expire_time)

    def _handle_subscription_renewal(self, current_subscription: Subscription, new_expire_time: datetime):
        self._update_subscription_fields(current_subscription, expire_time=new_expire_time)

    def _create_new_subscription(self, user: User, package: Package, device_limit: int, expire_time: datetime):
        subscription = Subscription(
            user_id=user.id,
            package_id=package.id,
            device_limit=device_limit,
            status='active',
            created_at=datetime.now(),
            expire_time=expire_time
        )
        self.db.add(subscription)
        self.db.flush()
        self._send_notification('send_subscription_created_notification', subscription)

    def _reactivate_expired_subscription(self, current_subscription: Subscription, package: Package, device_limit: int, expire_time: datetime):
        self._update_subscription_fields(current_subscription, device_limit, expire_time, 'active', package.id)

    def check_expired_subscriptions(self):
        try:
            now = datetime.now()
            expired_subscriptions = self.db.query(Subscription).filter(
                and_(
                    Subscription.status == 'active',
                    Subscription.expire_time < now
                )
            ).all()
            for subscription in expired_subscriptions:
                self._update_subscription_fields(subscription, 0, status='expired')
            self.db.commit()
            return len(expired_subscriptions)
        except Exception as e:
            self.db.rollback()
            logger.error(f"处理过期订阅失败: {e}", exc_info=True)
            return 0

    def get_user_subscription_info(self, user_id: int) -> dict:
        subscription = self.db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status == 'active'
        ).first()
        if not subscription:
            return {'has_subscription': False, 'device_limit': 0, 'expire_time': None, 'status': 'inactive'}
        return {
            'has_subscription': True,
            'device_limit': subscription.device_limit,
            'expire_time': subscription.expire_time,
            'status': 'active' if subscription.expire_time > datetime.now() else 'expired'
        }
