from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.services.settings import SettingsService
from app.core.database import get_db
import json
import re

class SettingsManager:
    _instance = None
    _settings_cache = {}
    _cache_ttl = 300
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
        return cls._instance
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._settings_service = None
    def get_settings_service(self, db: Session) -> SettingsService:
        if self._settings_service is None:
            self._settings_service = SettingsService(db)
        return self._settings_service
    def _get_db(self, db: Session = None) -> Session:
        return db if db is not None else next(get_db())
    def get_setting(self, key: str, default: Any = None, db: Session = None) -> Any:
        db = self._get_db(db)
        settings_service = self.get_settings_service(db)
        return settings_service.get_config_value(key, default)
    def set_setting(self, key: str, value: Any, config_type: str = 'string', db: Session = None) -> bool:
        db = self._get_db(db)
        settings_service = self.get_settings_service(db)
        success = settings_service.set_config_value(key, value, config_type)
        if success:
            self._settings_cache.clear()
        return success
    def get_all_settings(self, db: Session = None) -> Dict[str, Any]:
        db = self._get_db(db)
        settings_service = self.get_settings_service(db)
        return settings_service.get_system_settings().dict()
    def get_site_name(self, db: Session = None) -> str:
        return self.get_setting('site_name', 'CBoard', db)
    def get_site_description(self, db: Session = None) -> str:
        return self.get_setting('site_description', '高性能面板系统', db)
    def get_site_keywords(self, db: Session = None) -> str:
        return self.get_setting('site_keywords', '面板,管理,系统', db)
    def get_site_logo(self, db: Session = None) -> str:
        return self.get_setting('site_logo', '', db)
    def get_site_favicon(self, db: Session = None) -> str:
        return self.get_setting('site_favicon', '', db)
    def is_registration_allowed(self, db: Session = None) -> bool:
        registration_enabled = self.get_setting('registration_enabled', None, db)
        return registration_enabled if registration_enabled is not None else self.get_setting('allow_registration', True, db)
    def is_email_verification_required(self, db: Session = None) -> bool:
        return self.get_setting('require_email_verification', True, db)
    def is_qq_email_only(self, db: Session = None) -> bool:
        return self.get_setting('allow_qq_email_only', True, db)
    def get_min_password_length(self, db: Session = None) -> int:
        return self.get_setting('min_password_length', 8, db)
    def get_smtp_config(self, db: Session = None) -> Dict[str, Any]:
        return {
            'host': self.get_setting('smtp_host', '', db),
            'port': self.get_setting('smtp_port', 587, db),
            'username': self.get_setting('email_username', self.get_setting('smtp_username', '', db), db),
            'password': self.get_setting('email_password', self.get_setting('smtp_password', '', db), db),
            'encryption': self.get_setting('smtp_encryption', 'tls', db),
            'from_email': self.get_setting('from_email', '', db),
            'from_name': self.get_setting('sender_name', self.get_setting('from_name', 'CBoard', db), db)
        }
    def is_email_enabled(self, db: Session = None) -> bool:
        smtp_config = self.get_smtp_config(db)
        return bool(smtp_config['host'] and smtp_config['username'] and smtp_config['password'])
    def is_email_notification_enabled(self, db: Session = None) -> bool:
        return self.get_setting('enable_email_notification', True, db)
    def is_sms_notification_enabled(self, db: Session = None) -> bool:
        return self.get_setting('enable_sms_notification', False, db)
    def is_webhook_notification_enabled(self, db: Session = None) -> bool:
        return self.get_setting('enable_webhook_notification', False, db)
    def get_webhook_url(self, db: Session = None) -> str:
        return self.get_setting('webhook_url', '', db)
    def get_default_theme(self, db: Session = None) -> str:
        return self.get_setting('default_theme', 'default', db)
    def is_user_theme_allowed(self, db: Session = None) -> bool:
        return self.get_setting('allow_user_theme', True, db)
    def get_available_themes(self, db: Session = None) -> list:
        themes = self.get_setting('available_themes', ['default', 'dark', 'blue', 'green'], db)
        if isinstance(themes, str):
            try:
                return json.loads(themes)
            except:
                return ['default', 'dark', 'blue', 'green']
        return themes
    def is_payment_enabled(self, db: Session = None) -> bool:
        return self.get_setting('enable_payment', True, db)
    def get_default_payment_method(self, db: Session = None) -> str:
        return self.get_setting('default_payment_method', '', db)
    def get_payment_currency(self, db: Session = None) -> str:
        return self.get_setting('payment_currency', 'CNY', db)
    def is_announcement_enabled(self, db: Session = None) -> bool:
        return self.get_setting('enable_announcement', True, db)
    def get_announcement_position(self, db: Session = None) -> str:
        return self.get_setting('announcement_position', 'top', db)
    def get_max_announcements(self, db: Session = None) -> int:
        return self.get_setting('max_announcements', 5, db)
    def is_captcha_enabled(self, db: Session = None) -> bool:
        return self.get_setting('enable_captcha', False, db)
    def get_max_login_attempts(self, db: Session = None) -> int:
        return self.get_setting('max_login_attempts', 5, db)
    def get_lockout_duration(self, db: Session = None) -> int:
        return self.get_setting('lockout_duration', 30, db)
    def get_session_timeout(self, db: Session = None) -> int:
        return self.get_setting('session_timeout', 1440, db)
    def is_cache_enabled(self, db: Session = None) -> bool:
        return self.get_setting('enable_cache', True, db)
    def get_cache_duration(self, db: Session = None) -> int:
        return self.get_setting('cache_duration', 3600, db)
    def is_compression_enabled(self, db: Session = None) -> bool:
        return self.get_setting('enable_compression', True, db)
    def get_max_upload_size(self, db: Session = None) -> int:
        return self.get_setting('max_upload_size', 10, db)
    def validate_email(self, email: str, db: Session = None) -> bool:
        if not email:
            return False
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return False
        if self.is_qq_email_only(db):
            return email.endswith('@qq.com')
        return True
    def validate_password(self, password: str, db: Session = None) -> bool:
        if not password:
            return False
        min_length = self.get_min_password_length(db)
        if len(password) < min_length:
            return False
        has_letter = any(c.isalpha() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
        return has_letter and has_digit and has_special
    def get_public_settings(self, db: Session = None) -> Dict[str, Any]:
        return {
            'site_name': self.get_site_name(db),
            'site_description': self.get_site_description(db),
            'site_keywords': self.get_site_keywords(db),
            'site_logo': self.get_site_logo(db),
            'site_favicon': self.get_site_favicon(db),
            'allow_registration': self.is_registration_allowed(db),
            'require_email_verification': self.is_email_verification_required(db),
            'allow_qq_email_only': self.is_qq_email_only(db),
            'min_password_length': self.get_min_password_length(db),
            'default_theme': self.get_default_theme(db),
            'allow_user_theme': self.is_user_theme_allowed(db),
            'available_themes': self.get_available_themes(db),
            'enable_payment': self.is_payment_enabled(db),
            'payment_currency': self.get_payment_currency(db),
            'enable_announcement': self.is_announcement_enabled(db),
            'announcement_position': self.get_announcement_position(db),
            'max_announcements': self.get_max_announcements(db)
        }

settings_manager = SettingsManager()
