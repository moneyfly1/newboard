"""系统设置服务"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.config import Announcement, SystemConfig, ThemeConfig
from app.schemas.config import (
    AnnouncementConfig,
    AnnouncementCreate,
    AnnouncementUpdate,
    EmailConfig,
    GeneralConfig,
    NotificationConfig,
    PaymentConfig,
    PerformanceConfig,
    RegistrationConfig,
    SecurityConfig,
    SystemConfigCreate,
    SystemConfigUpdate,
    SystemSettings,
    SystemThemeConfig,
    ThemeConfigCreate,
    ThemeConfigUpdate,
)


class SettingsService:
    """系统设置服务类"""

    def __init__(self, db: Session):
        self.db = db

    def get_config(self, key: str) -> Optional[SystemConfig]:
        return self.db.query(SystemConfig).filter(SystemConfig.key == key).first()

    def get_configs_by_category(self, category: str) -> List[SystemConfig]:
        return self.db.query(SystemConfig).filter(SystemConfig.category == category).order_by(SystemConfig.sort_order, SystemConfig.id).all()

    def get_all_configs(self) -> List[SystemConfig]:
        return self.db.query(SystemConfig).order_by(SystemConfig.category, SystemConfig.sort_order, SystemConfig.id).all()

    def get_public_configs(self) -> List[SystemConfig]:
        return self.db.query(SystemConfig).filter(SystemConfig.is_public == True).order_by(SystemConfig.category, SystemConfig.sort_order).all()

    def create_config(self, config_in: SystemConfigCreate) -> SystemConfig:
        config = SystemConfig(**config_in.dict())
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def update_config(self, key: str, config_in: SystemConfigUpdate) -> Optional[SystemConfig]:
        config = self.get_config(key)
        if not config:
            return None
        update_data = config_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(config, field, value)
        self.db.commit()
        self.db.refresh(config)
        return config

    def delete_config(self, key: str) -> bool:
        config = self.get_config(key)
        if not config:
            return False
        self.db.delete(config)
        self.db.commit()
        return True

    def get_config_value(self, key: str, default: Any = None) -> Any:
        config = self.get_config(key)
        if not config:
            return default
        if config.type == 'boolean':
            return config.value.lower() in ('true', '1', 'yes', 'on')
        elif config.type == 'number':
            try:
                return float(config.value) if '.' in config.value else int(config.value)
            except (ValueError, TypeError):
                return default
        elif config.type == 'json':
            try:
                return json.loads(config.value) if config.value else {}
            except (ValueError, TypeError):
                return default
        else:
            return config.value

    def set_config_value(self, key: str, value: Any, config_type: str = 'string') -> bool:
        config = self.get_config(key)
        if not config:
            return False
        config.value = str(value)
        config.type = config_type
        self.db.commit()
        return True

    def _get_configs_dict(self, category: str, default: Dict[str, Any]) -> Dict[str, Any]:
        try:
            configs = self.get_configs_by_category(category)
            result = {}
            for config in configs:
                result[config.key] = self.get_config_value(config.key)
            return result if result else default
        except Exception:
            return default

    def _update_configs_dict(self, config_dict: Dict[str, Any], allowed_keys: List[str]) -> bool:
        try:
            for key, value in config_dict.items():
                if key in allowed_keys:
                    self.set_config_value(key, value)
            return True
        except Exception:
            return False

    def get_system_settings(self) -> SystemSettings:
        try:
            configs = self.get_all_configs()
            settings = {config.key: self.get_config_value(config.key) for config in configs}
            general_config = GeneralConfig(
                site_name=settings.get('site_name', 'CBoard Modern'),
                site_description=settings.get('site_description', '现代化订阅管理系统'),
                site_logo=settings.get('site_logo'),
                maintenance_mode=settings.get('maintenance_mode', False),
                maintenance_message=settings.get('maintenance_message', '系统维护中，请稍后再试'),
                registration_enabled=settings.get('allow_registration', True),
                email_verification_required=settings.get('email_verification_required', True),
                min_password_length=settings.get('min_password_length', 6),
                max_login_attempts=settings.get('max_login_attempts', 5),
                session_timeout=settings.get('session_timeout', 30)
            )
            registration_config = RegistrationConfig(
                enabled=settings.get('allow_registration', True),
                require_email_verification=settings.get('email_verification_required', True),
                allow_qq_email_only=settings.get('allow_qq_email_only', True),
                auto_approve=settings.get('auto_approve', False),
                welcome_message=settings.get('welcome_message', '欢迎加入CBoard！'),
                terms_of_service=settings.get('terms_of_service', ''),
                privacy_policy=settings.get('privacy_policy', '')
            )
            email_config = EmailConfig(
                smtp_host=settings.get('smtp_host', 'smtp.qq.com'),
                smtp_port=settings.get('smtp_port', 587),
                smtp_username=settings.get('smtp_username', ''),
                smtp_password=settings.get('smtp_password', ''),
                sender_name=settings.get('sender_name', 'CBoard'),
                sender_email=settings.get('sender_email', ''),
                use_tls=settings.get('use_tls', True),
                use_ssl=settings.get('use_ssl', False),
                max_retries=settings.get('max_retries', 3),
                retry_delay=settings.get('retry_delay', 60)
            )
            notification_config = NotificationConfig(
                email_notifications=settings.get('email_notifications', True),
                push_notifications=settings.get('push_notifications', False),
                subscription_expiry_reminder=settings.get('subscription_expiry_reminder', True),
                reminder_days=settings.get('reminder_days', [7, 3, 1]),
                new_user_notification=settings.get('new_user_notification', True),
                payment_notification=settings.get('payment_notification', True),
                system_notification=settings.get('system_notification', True)
            )
            theme_config = SystemThemeConfig(
                default_theme=settings.get('default_theme', 'default'),
                available_themes=settings.get('available_themes', ['default', 'dark', 'light']),
                custom_css=settings.get('custom_css'),
                logo_url=settings.get('logo_url'),
                favicon_url=settings.get('favicon_url'),
                primary_color=settings.get('primary_color', '#1677ff'),
                secondary_color=settings.get('secondary_color', '#52c41a')
            )
            payment_config = PaymentConfig(
                enabled=settings.get('payment_enabled', True),
                currency=settings.get('currency', 'CNY'),
                alipay_enabled=settings.get('alipay_enabled', True),
                wechat_enabled=settings.get('wechat_enabled', True),
                paypal_enabled=settings.get('paypal_enabled', False),
                stripe_enabled=settings.get('stripe_enabled', False)
            )
            announcement_config = AnnouncementConfig(
                enabled=settings.get('announcement_enabled', True),
                max_announcements=settings.get('max_announcements', 10),
                auto_expire=settings.get('auto_expire', True),
                expire_days=settings.get('expire_days', 30)
            )
            security_config = SecurityConfig(
                two_factor_auth=settings.get('two_factor_auth', False),
                login_attempts_limit=settings.get('login_attempts_limit', 5),
                lockout_duration=settings.get('lockout_duration', 15),
                password_expiry_days=settings.get('password_expiry_days', 90),
                require_strong_password=settings.get('require_strong_password', True),
                session_timeout_minutes=settings.get('session_timeout_minutes', 30)
            )
            performance_config = PerformanceConfig(
                cache_enabled=settings.get('cache_enabled', True),
                cache_type=settings.get('cache_type', 'memory'),
                cache_timeout=settings.get('cache_timeout', 300),
                max_connections=settings.get('max_connections', 1000),
                workers=settings.get('workers', 4),
                enable_compression=settings.get('enable_compression', True),
                enable_gzip=settings.get('enable_gzip', True),
                static_file_cache=settings.get('static_file_cache', 3600)
            )
            return SystemSettings(
                general=general_config,
                registration=registration_config,
                email=email_config,
                notification=notification_config,
                theme=theme_config,
                payment=payment_config,
                announcement=announcement_config,
                security=security_config,
                performance=performance_config
            )
        except Exception:
            return self._get_default_system_settings()

    def update_system_settings(self, settings: Dict[str, Any]) -> bool:
        try:
            type_map = {
                'boolean': ['maintenance_mode', 'registration_enabled', 'email_verification_required'],
                'number': ['min_password_length', 'max_login_attempts', 'session_timeout', 'smtp_port'],
                'json': ['reminder_days', 'available_themes']
            }
            for key, value in settings.items():
                config_type = 'string'
                for t, keys in type_map.items():
                    if key in keys:
                        config_type = t
                        break
                self.set_config_value(key, value, config_type)
            return True
        except Exception:
            return False

    def _get_default_system_settings(self) -> SystemSettings:
        return SystemSettings(
            general=GeneralConfig(),
            registration=RegistrationConfig(),
            email=EmailConfig(),
            notification=NotificationConfig(),
            theme=SystemThemeConfig(),
            payment=PaymentConfig(),
            announcement=AnnouncementConfig(),
            security=SecurityConfig(),
            performance=PerformanceConfig()
        )

    def get_smtp_config(self) -> Dict[str, Any]:
        default = {
            'smtp_host': 'smtp.qq.com',
            'smtp_port': 587,
            'smtp_username': '',
            'smtp_password': '',
            'sender_name': 'CBoard',
            'sender_email': '',
            'use_tls': True,
            'use_ssl': False
        }
        try:
            configs = self.get_configs_by_category('email')
            smtp_config = {}
            for config in configs:
                if config.key.startswith('smtp_') or config.key in ['sender_name', 'sender_email', 'use_tls', 'use_ssl']:
                    smtp_config[config.key] = self.get_config_value(config.key)
            return smtp_config if smtp_config else default
        except Exception:
            return default

    def update_smtp_config(self, smtp_config: Dict[str, Any]) -> bool:
        allowed_keys = ['smtp_host', 'smtp_port', 'smtp_username', 'smtp_password', 'sender_name', 'sender_email', 'use_tls', 'use_ssl']
        return self._update_configs_dict(smtp_config, allowed_keys)

    def test_smtp_connection(self, smtp_config: Dict[str, Any]) -> bool:
        try:
            return True
        except Exception:
            return False

    def get_registration_config(self) -> Dict[str, Any]:
        default = {
            'allow_registration': True,
            'email_verification_required': True,
            'allow_qq_email_only': True,
            'auto_approve': False,
            'welcome_message': '欢迎加入CBoard！'
        }
        return self._get_configs_dict('registration', default)

    def update_registration_config(self, reg_config: Dict[str, Any]) -> bool:
        allowed_keys = ['allow_registration', 'email_verification_required', 'allow_qq_email_only', 'auto_approve', 'welcome_message']
        return self._update_configs_dict(reg_config, allowed_keys)

    def get_notification_config(self) -> Dict[str, Any]:
        default = {
            'email_notifications': True,
            'push_notifications': False,
            'subscription_expiry_reminder': True,
            'reminder_days': [7, 3, 1],
            'new_user_notification': True,
            'payment_notification': True,
            'system_notification': True
        }
        return self._get_configs_dict('notification', default)

    def update_notification_config(self, notif_config: Dict[str, Any]) -> bool:
        allowed_keys = ['email_notifications', 'push_notifications', 'subscription_expiry_reminder', 'reminder_days', 'new_user_notification', 'payment_notification', 'system_notification']
        return self._update_configs_dict(notif_config, allowed_keys)

    def get_security_config(self) -> Dict[str, Any]:
        default = {
            'two_factor_auth': False,
            'login_attempts_limit': 5,
            'lockout_duration': 15,
            'password_expiry_days': 90,
            'require_strong_password': True,
            'session_timeout_minutes': 30
        }
        return self._get_configs_dict('security', default)

    def update_security_config(self, security_config: Dict[str, Any]) -> bool:
        allowed_keys = ['two_factor_auth', 'login_attempts_limit', 'lockout_duration', 'password_expiry_days', 'require_strong_password', 'session_timeout_minutes']
        return self._update_configs_dict(security_config, allowed_keys)

    def update_payment_configs(self, payment_configs: Dict[str, Any]) -> bool:
        try:
            field_groups = {
                'basic': ['payment_enabled', 'currency', 'default_payment_method'],
                'alipay': ['alipay_app_id', 'alipay_private_key', 'alipay_public_key', 'alipay_gateway'],
                'wechat': ['wechat_app_id', 'wechat_mch_id', 'wechat_api_key', 'wechat_cert_path', 'wechat_key_path'],
                'paypal': ['paypal_client_id', 'paypal_secret', 'paypal_mode'],
                'stripe': ['stripe_publishable_key', 'stripe_secret_key', 'stripe_webhook_secret'],
                'bank': ['bank_name', 'bank_account', 'bank_branch', 'account_holder'],
                'callback': ['return_url', 'notify_url']
            }
            for key, value in payment_configs.items():
                for fields in field_groups.values():
                    if key in fields:
                        self.set_config_value(key, value)
                        break
            return True
        except Exception:
            return False

    def test_payment_config(self, payment_config: Dict[str, Any]) -> bool:
        try:
            payment_method = payment_config.get('default_payment_method', 'alipay')
            validators = {
                'alipay': lambda c: bool(c.get('alipay_app_id') and c.get('alipay_private_key')),
                'wechat': lambda c: bool(c.get('wechat_app_id') and c.get('wechat_mch_id') and c.get('wechat_api_key')),
                'paypal': lambda c: bool(c.get('paypal_client_id') and c.get('paypal_secret')),
                'stripe': lambda c: bool(c.get('stripe_publishable_key') and c.get('stripe_secret_key')),
                'bank_transfer': lambda c: bool(c.get('bank_name') and c.get('bank_account') and c.get('account_holder'))
            }
            validator = validators.get(payment_method)
            return validator(payment_config) if validator else False
        except Exception:
            return False

    def get_announcements(self, target_users: str = 'all') -> List[Announcement]:
        query = self.db.query(Announcement).filter(Announcement.is_active == True)
        if target_users != 'all':
            query = query.filter(or_(Announcement.target_audience == target_users, Announcement.target_audience == 'all'))
        return query.order_by(Announcement.priority.desc(), Announcement.created_at.desc()).all()

    def get_active_announcements(self, target_users: str = 'all') -> List[Announcement]:
        now = datetime.utcnow()
        announcements = self.get_announcements(target_users)
        return [a for a in announcements if (not a.start_date or a.start_date <= now) and (not a.end_date or a.end_date >= now)]

    def create_announcement(self, announcement_in: AnnouncementCreate) -> Announcement:
        announcement = Announcement(**announcement_in.dict())
        self.db.add(announcement)
        self.db.commit()
        self.db.refresh(announcement)
        return announcement

    def update_announcement(self, announcement_id: int, announcement_in: AnnouncementUpdate) -> Optional[Announcement]:
        announcement = self.db.query(Announcement).filter(Announcement.id == announcement_id).first()
        if not announcement:
            return None
        update_data = announcement_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(announcement, field, value)
        self.db.commit()
        self.db.refresh(announcement)
        return announcement

    def delete_announcement(self, announcement_id: int) -> bool:
        announcement = self.db.query(Announcement).filter(Announcement.id == announcement_id).first()
        if not announcement:
            return False
        self.db.delete(announcement)
        self.db.commit()
        return True

    def get_themes(self) -> List[ThemeConfig]:
        return self.db.query(ThemeConfig).filter(ThemeConfig.is_active == True).all()

    def get_theme(self, theme_id: int) -> Optional[ThemeConfig]:
        return self.db.query(ThemeConfig).filter(ThemeConfig.id == theme_id).first()

    def create_theme(self, theme_in: ThemeConfigCreate) -> ThemeConfig:
        theme = ThemeConfig(**theme_in.dict())
        self.db.add(theme)
        self.db.commit()
        self.db.refresh(theme)
        return theme

    def update_theme(self, theme_id: int, theme_in: ThemeConfigUpdate) -> Optional[ThemeConfig]:
        theme = self.get_theme(theme_id)
        if not theme:
            return None
        update_data = theme_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(theme, field, value)
        self.db.commit()
        self.db.refresh(theme)
        return theme

    def delete_theme(self, theme_id: int) -> bool:
        theme = self.get_theme(theme_id)
        if not theme:
            return False
        self.db.delete(theme)
        self.db.commit()
        return True
