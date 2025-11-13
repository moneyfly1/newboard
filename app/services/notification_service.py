"""通知服务"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.order import Order
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.notification import NotificationCreate
from app.services.email import EmailService
from app.services.email_template_enhanced import EmailTemplateEnhanced

logger = logging.getLogger(__name__)


class NotificationCRUDService:
    """通知CRUD服务类"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, notification_id: int) -> Optional[Notification]:
        return self.db.query(Notification).filter(Notification.id == notification_id).first()

    def get_user_notifications(self, user_id: int, skip: int = 0, limit: int = 100, unread_only: bool = False) -> Tuple[List[Notification], int]:
        query = self.db.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            query = query.filter(Notification.is_read == False)
        total = query.count()
        notifications = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()
        return notifications, total

    def get_system_notifications(self, skip: int = 0, limit: int = 100) -> Tuple[List[Notification], int]:
        query = self.db.query(Notification).filter(Notification.user_id.is_(None))
        total = query.count()
        notifications = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()
        return notifications, total

    def create(self, notification_in: NotificationCreate) -> Notification:
        notification = Notification(
            user_id=notification_in.user_id,
            title=notification_in.title,
            content=notification_in.content,
            type=notification_in.type
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def create_system_notification(self, title: str, content: str, notification_type: str = "system") -> Notification:
        return self.create(NotificationCreate(title=title, content=content, type=notification_type))

    def mark_as_read(self, notification_id: int, user_id: int) -> bool:
        notification = self.db.query(Notification).filter(
            and_(Notification.id == notification_id, Notification.user_id == user_id)
        ).first()
        if not notification:
            return False
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        self.db.commit()
        return True

    def mark_all_as_read(self, user_id: int) -> int:
        result = self.db.query(Notification).filter(
            and_(Notification.user_id == user_id, Notification.is_read == False)
        ).update({"is_read": True, "read_at": datetime.utcnow()})
        self.db.commit()
        return result

    def delete(self, notification_id: int) -> bool:
        notification = self.get(notification_id)
        if not notification:
            return False
        self.db.delete(notification)
        self.db.commit()
        return True

    def get_unread_count(self, user_id: int) -> int:
        return self.db.query(Notification).filter(
            and_(Notification.user_id == user_id, Notification.is_read == False)
        ).count()

class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService(db)

    def should_send_notification(self, user: User, notification_type: str) -> bool:
        from app.core.settings_manager import settings_manager
        system_email_notifications = settings_manager.get_setting('email_notifications', True, self.db)
        if not system_email_notifications:
            return False
        notification_key_map = {
            'subscription': 'subscription_expiry_notifications',
            'payment': 'new_order_notifications',
            'system': 'system_notifications',
            'marketing': 'new_user_notifications'
        }
        if notification_type in notification_key_map:
            setting_key = notification_key_map[notification_type]
            type_enabled = settings_manager.get_setting(setting_key, True, self.db)
            if not type_enabled:
                return False
        if user.email_notifications is False:
            return False
        if user.notification_types:
            try:
                allowed_types = json.loads(user.notification_types)
                if isinstance(allowed_types, list) and notification_type not in allowed_types:
                    return False
            except (json.JSONDecodeError, TypeError):
                pass
        return True

    def _send_expiry_notification(self, subscriptions, is_expired: bool) -> int:
        sent_count = 0
        for subscription in subscriptions:
            user = subscription.user
            if not self.should_send_notification(user, 'subscription'):
                continue
            success = self.email_service.send_subscription_expiry_reminder(
                subscription_id=subscription.id,
                is_expired=is_expired,
                request=None
            )
            if success:
                sent_count += 1
                logger.info(f"发送{'过期' if is_expired else '到期'}提醒邮件成功: {user.email}")
            else:
                logger.error(f"发送{'过期' if is_expired else '到期'}提醒邮件失败: {user.email}")
        return sent_count

    def send_subscription_expiry_reminder(self, days_before: int = 7) -> int:
        try:
            now = datetime.now()
            target_date = now + timedelta(days=days_before)
            subscriptions = self.db.query(Subscription).join(User).filter(
                and_(
                    Subscription.status == 'active',
                    Subscription.expire_time.isnot(None),
                    Subscription.expire_time >= target_date - timedelta(hours=1),
                    Subscription.expire_time <= target_date + timedelta(hours=1)
                )
            ).all()
            return self._send_expiry_notification(subscriptions, False)
        except Exception as e:
            logger.error(f"发送订阅到期提醒失败: {e}", exc_info=True)
            return 0

    def send_subscription_expired_notification(self) -> int:
        try:
            now = datetime.now()
            expired_subscriptions = self.db.query(Subscription).join(User).filter(
                and_(
                    Subscription.status == 'active',
                    Subscription.expire_time.isnot(None),
                    Subscription.expire_time < now
                )
            ).all()
            return self._send_expiry_notification(expired_subscriptions, True)
        except Exception as e:
            logger.error(f"发送订阅过期通知失败: {e}", exc_info=True)
            return 0

    def _send_notification_email(self, user: User, notification_type: str, subject: str, html_content: str, email_type: str) -> bool:
        if not self.should_send_notification(user, notification_type):
            return False
        try:
            from app.schemas.email import EmailQueueCreate
            email_data = EmailQueueCreate(
                to_email=user.email,
                subject=subject,
                content=html_content,
                content_type='html',
                email_type=email_type
            )
            return self.email_service.queue_email(email_data)
        except Exception as e:
            logger.error(f"发送通知邮件失败: {e}", exc_info=True)
            return False

    def send_payment_success_notification(self, order: Order) -> bool:
        try:
            from app.core.settings_manager import settings_manager
            new_order_notifications = settings_manager.get_setting('new_order_notifications', True, self.db)
            if not new_order_notifications:
                return False
            user = order.user
            content = EmailTemplateEnhanced.get_payment_success_template(order_id=order.id, request=None, db=self.db)
            if not content or content in ["数据库连接不可用", "订单信息不存在"]:
                logger.error("发送支付成功通知失败: 无法获取订单模板内容")
                return False
            return self._send_notification_email(
                user=user,
                notification_type='payment',
                subject="支付成功通知 - 网络服务",
                html_content=content,
                email_type='payment_success'
            )
        except Exception as e:
            logger.error(f"发送支付成功通知失败: {e}", exc_info=True)
            return False

    def send_new_user_welcome_notification(self, user: User) -> bool:
        try:
            from app.core.settings_manager import settings_manager
            new_user_notifications = settings_manager.get_setting('new_user_notifications', True, self.db)
            if not new_user_notifications:
                return False
            content = EmailTemplateEnhanced.get_welcome_template(user_id=user.id, password=None, request=None, db=self.db)
            return self._send_notification_email(
                user=user,
                notification_type='marketing',
                subject="欢迎注册 - 网络服务",
                html_content=content,
                email_type='welcome'
            )
        except Exception as e:
            logger.error(f"发送新用户欢迎通知失败: {e}", exc_info=True)
            return False

    def send_subscription_created_notification(self, subscription: Subscription) -> bool:
        try:
            user = subscription.user
            content = EmailTemplateEnhanced.get_subscription_created_template(subscription_id=subscription.id, request=None, db=self.db)
            return self._send_notification_email(
                user=user,
                notification_type='subscription',
                subject="订阅创建成功 - 网络服务",
                html_content=content,
                email_type='subscription_created'
            )
        except Exception as e:
            logger.error(f"发送订阅创建通知失败: {e}", exc_info=True)
            return False

    def get_notification_stats(self) -> Dict[str, Any]:
        try:
            total_users = self.db.query(User).count()
            email_enabled_users = self.db.query(User).filter(User.email_notifications == True).count()
            subscription_notifications = 0
            payment_notifications = 0
            system_notifications = 0
            users = self.db.query(User).all()
            for user in users:
                if user.notification_types:
                    try:
                        types = json.loads(user.notification_types)
                        if isinstance(types, list):
                            if 'subscription' in types:
                                subscription_notifications += 1
                            if 'payment' in types:
                                payment_notifications += 1
                            if 'system' in types:
                                system_notifications += 1
                    except:
                        pass
            return {
                "total_users": total_users,
                "email_enabled_users": email_enabled_users,
                "subscription_notifications": subscription_notifications,
                "payment_notifications": payment_notifications,
                "system_notifications": system_notifications
            }
        except Exception as e:
            logger.error(f"获取通知统计失败: {e}", exc_info=True)
            return {}
