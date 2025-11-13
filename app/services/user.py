"""用户服务"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_activity import LoginHistory, SubscriptionReset, UserActivity
from app.schemas.user import UserCreate, UserUpdate
from app.utils.security import get_password_hash, verify_password

logger = logging.getLogger(__name__)


class UserService:
    """用户服务类"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_multi(self, skip: int = 0, limit: int = 100) -> List[User]:
        return self.db.query(User).offset(skip).limit(limit).all()

    def _authenticate_user(self, user: Optional[User], password: str, identifier: str) -> Optional[User]:
        if not user:
            return None
        try:
            if not verify_password(password, user.hashed_password):
                return None
            return user
        except Exception as e:
            logger.error(f"密码验证异常 ({identifier}): {e}", exc_info=True)
            return None

    def create(self, user_in: UserCreate) -> User:
        try:
            user = User(
                username=user_in.username,
                email=user_in.email,
                hashed_password=get_password_hash(user_in.password),
                is_active=True,
                is_verified=False,
                is_admin=False
            )
            self.db.add(user)
            self.db.flush()
            try:
                from app.services.subscription import SubscriptionService
                from app.schemas.subscription import SubscriptionCreate
                subscription_service = SubscriptionService(self.db)
                default_subscription = SubscriptionCreate(
                    user_id=user.id,
                    device_limit=0,
                    expire_time=datetime.utcnow() - timedelta(days=1)
                )
                subscription_service.create(default_subscription)
            except Exception as e:
                self.db.rollback()
                logger.error(f"创建默认订阅失败: {e}", exc_info=True)
                raise Exception(f"创建用户失败: 无法创建默认订阅 - {str(e)}")
            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception as e:
            self.db.rollback()
            raise e

    def update(self, user_id: int, user_in: UserUpdate) -> Optional[User]:
        user = self.get(user_id)
        if not user:
            return None
        for field, value in user_in.dict(exclude_unset=True).items():
            setattr(user, field, value)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_password(self, user_id: int, new_password: str) -> bool:
        user = self.get(user_id)
        if not user:
            return False
        user.hashed_password = get_password_hash(new_password)
        self.db.commit()
        return True

    def update_last_login(self, user_id: int) -> bool:
        user = self.get(user_id)
        if not user:
            return False
        user.last_login = datetime.utcnow()
        self.db.commit()
        return True

    def verify_email(self, user_id: int) -> bool:
        user = self.get(user_id)
        if not user:
            return False
        user.is_verified = True
        self.db.commit()
        return True

    def authenticate(self, username: str, password: str) -> Optional[User]:
        try:
            return self._authenticate_user(self.get_by_username(username), password, f"用户: {username}")
        except Exception as e:
            logger.error(f"认证过程异常 (用户: {username}): {e}", exc_info=True)
            return None

    def authenticate_by_email(self, email: str, password: str) -> Optional[User]:
        try:
            return self._authenticate_user(self.get_by_email(email), password, f"邮箱: {email}")
        except Exception as e:
            logger.error(f"认证过程异常 (邮箱: {email}): {e}", exc_info=True)
            return None

    def send_verification_email(self, user_id: int) -> bool:
        return False

    def send_password_reset_email(self, email: str) -> bool:
        from app.services.email import EmailService
        from app.core.domain_config import get_domain_config
        from app.utils.security import generate_password_reset_token
        user = self.get_by_email(email)
        if not user:
            return False
        token = generate_password_reset_token(user.id)
        domain_config = get_domain_config()
        base_url = domain_config.get_email_base_url(None, self.db)
        reset_url = f"{base_url}/reset-password?token={token}"
        email_service = EmailService(self.db)
        return email_service.send_password_reset_email_direct(email, user.username, reset_url)

    def _delete_user_related_data(self, user_id: int, user_email: str):
        from app.models.subscription import Device, Subscription
        from app.models.order import Order
        from app.models.payment import PaymentTransaction
        from app.models.notification import Notification
        from app.models.email import EmailQueue
        devices = self.db.query(Device).filter(Device.user_id == user_id).all()
        for device in devices:
            self.db.delete(device)
        subscriptions = self.db.query(Subscription).filter(Subscription.user_id == user_id).all()
        for subscription in subscriptions:
            subscription_devices = self.db.query(Device).filter(Device.subscription_id == subscription.id).all()
            for device in subscription_devices:
                self.db.delete(device)
            self.db.delete(subscription)
        for model_class in [Order, PaymentTransaction, Notification]:
            items = self.db.query(model_class).filter(model_class.user_id == user_id).all()
            for item in items:
                self.db.delete(item)
        for activity in self.db.query(UserActivity).filter(UserActivity.user_id == user_id).all():
            self.db.delete(activity)
        for login in self.db.query(LoginHistory).filter(LoginHistory.user_id == user_id).all():
            self.db.delete(login)
        for reset in self.db.query(SubscriptionReset).filter(SubscriptionReset.user_id == user_id).all():
            self.db.delete(reset)
        for email in self.db.query(EmailQueue).filter(EmailQueue.to_email == user_email).all():
            self.db.delete(email)

    def delete(self, user_id: int) -> bool:
        user = self.get(user_id)
        if not user:
            return False
        try:
            self._delete_user_related_data(user_id, user.email)
            self.db.delete(user)
            return True
        except Exception as e:
            logger.error(f"删除用户失败: {e}", exc_info=True)
            return False

    def count(self) -> int:
        return self.db.query(User).count()

    def get_active_users(self, days: int = 30) -> List[User]:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self.db.query(User).filter(User.last_login >= cutoff_date).all()

    def get_recent_users(self, days: int = 7) -> List[User]:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self.db.query(User).filter(User.created_at >= cutoff_date).all()

    def count_active_users(self, days: int = 30) -> int:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self.db.query(User).filter(User.last_login >= cutoff_date).count()

    def count_recent_users(self, days: int = 7) -> int:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self.db.query(User).filter(User.created_at >= cutoff_date).count()

    def count_users_since(self, start_date: datetime, end_date: Optional[datetime] = None) -> int:
        query = self.db.query(User).filter(User.created_at >= start_date)
        if end_date:
            query = query.filter(User.created_at < end_date)
        return query.count()

    def get_users_with_pagination(self, skip: int = 0, limit: int = 100, search: Optional[str] = None, status: Optional[str] = None, email: Optional[str] = None, username: Optional[str] = None, date_range: Optional[str] = None) -> Tuple[List[User], int]:
        query = self.db.query(User)
        if search:
            query = query.filter(or_(User.username.contains(search), User.email.contains(search)))
        if email:
            query = query.filter(User.email.contains(email))
        if username:
            query = query.filter(User.username.contains(username))
        if status == "active":
            query = query.filter(User.is_active == True)
        elif status == "inactive":
            query = query.filter(User.is_active == False)
        elif status == "verified":
            query = query.filter(User.is_verified == True)
        elif status == "unverified":
            query = query.filter(User.is_verified == False)
        elif status == "disabled":
            query = query.filter(User.is_active == False)
        if date_range:
            try:
                dates = date_range.split(',')
                if len(dates) == 2:
                    start_date = datetime.fromisoformat(dates[0])
                    end_date = datetime.fromisoformat(dates[1])
                    query = query.filter(User.created_at >= start_date, User.created_at <= end_date)
            except (ValueError, IndexError):
                pass
        total = query.count()
        users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
        return users, total

    def get_user_stats(self) -> dict:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        return {
            "total": self.count(),
            "active": self.count_active_users(30),
            "recent_7_days": self.count_recent_users(7),
            "today": self.count_users_since(today_start),
            "yesterday": self.count_users_since(yesterday_start, today_start)
        }

    def get_user_activities(self, user_id: int, limit: int = 50) -> List[UserActivity]:
        return self.db.query(UserActivity).filter(UserActivity.user_id == user_id).order_by(UserActivity.created_at.desc()).limit(limit).all()

    def get_login_history(self, user_id: int, limit: int = 50) -> List[LoginHistory]:
        return self.db.query(LoginHistory).filter(LoginHistory.user_id == user_id).order_by(LoginHistory.login_time.desc()).limit(limit).all()

    def get_subscription_resets(self, user_id: int, limit: int = 50) -> List[SubscriptionReset]:
        return self.db.query(SubscriptionReset).filter(SubscriptionReset.user_id == user_id).order_by(SubscriptionReset.created_at.desc()).limit(limit).all()

    def log_user_activity(self, user_id: int, activity_type: str, description: str = None, ip_address: str = None, user_agent: str = None, location: str = None, metadata: dict = None) -> UserActivity:
        activity = UserActivity(user_id=user_id, activity_type=activity_type, description=description, ip_address=ip_address, user_agent=user_agent, location=location, metadata=metadata)
        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)
        return activity

    def log_login(self, user_id: int, ip_address: str = None, user_agent: str = None, location: str = None, device_fingerprint: str = None, login_status: str = "success", failure_reason: str = None) -> LoginHistory:
        login_record = LoginHistory(user_id=user_id, ip_address=ip_address, user_agent=user_agent, location=location, device_fingerprint=device_fingerprint, login_status=login_status, failure_reason=failure_reason)
        self.db.add(login_record)
        self.db.commit()
        self.db.refresh(login_record)
        return login_record

    def log_subscription_reset(self, user_id: int, subscription_id: int, reset_type: str, reason: str = None, old_subscription_url: str = None, new_subscription_url: str = None, device_count_before: int = 0, device_count_after: int = 0, reset_by: str = "user") -> SubscriptionReset:
        reset_record = SubscriptionReset(user_id=user_id, subscription_id=subscription_id, reset_type=reset_type, reason=reason, old_subscription_url=old_subscription_url, new_subscription_url=new_subscription_url, device_count_before=device_count_before, device_count_after=device_count_after, reset_by=reset_by)
        self.db.add(reset_record)
        self.db.commit()
        self.db.refresh(reset_record)
        return reset_record
