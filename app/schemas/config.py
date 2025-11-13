from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class ConfigCategory(str, Enum):
    GENERAL = "general"
    REGISTRATION = "registration"
    EMAIL = "email"
    NOTIFICATION = "notification"
    THEME = "theme"
    PAYMENT = "payment"
    ANNOUNCEMENT = "announcement"
    SECURITY = "security"
    PERFORMANCE = "performance"

class ConfigValue(BaseModel):
    key: str
    value: Any
    description: Optional[str] = None
    type: str = "string"
    required: bool = False
    options: Optional[List[Any]] = None

class SystemConfigBase(BaseModel):
    category: ConfigCategory
    config_data: Dict[str, Any] = {}

class SystemConfigCreate(SystemConfigBase):
    pass

class SystemConfigUpdate(SystemConfigBase):
    pass

class SystemConfig(SystemConfigBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SystemConfigInDB(SystemConfig):
    pass

class GeneralConfig(BaseModel):
    site_name: str = "CBoard Modern"
    site_description: str = "现代化订阅管理系统"
    site_logo: Optional[str] = None
    maintenance_mode: bool = False
    maintenance_message: str = "系统维护中，请稍后再试"
    registration_enabled: bool = True
    email_verification_required: bool = True
    min_password_length: int = 6
    max_login_attempts: int = 5
    session_timeout: int = 30

class RegistrationConfig(BaseModel):
    enabled: bool = True
    require_email_verification: bool = True
    allow_qq_email_only: bool = True
    auto_approve: bool = False
    welcome_message: str = "欢迎加入CBoard！"
    terms_of_service: str = ""
    privacy_policy: str = ""

class EmailConfig(BaseModel):
    smtp_host: str = "smtp.qq.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    sender_name: str = "CBoard"
    sender_email: str = ""
    use_tls: bool = True
    use_ssl: bool = False
    max_retries: int = 3
    retry_delay: int = 60

class NotificationConfig(BaseModel):
    email_notifications: bool = True
    push_notifications: bool = False
    subscription_expiry_reminder: bool = True
    reminder_days: List[int] = [7, 3, 1]
    new_user_notification: bool = True
    payment_notification: bool = True
    system_notification: bool = True

class ThemeConfig(BaseModel):
    default_theme: str = "default"
    available_themes: List[str] = ["default", "dark", "light"]
    custom_css: Optional[str] = None
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_color: str = "#1677ff"
    secondary_color: str = "#52c41a"

class PaymentConfig(BaseModel):
    enabled: bool = True
    currency: str = "CNY"
    alipay_enabled: bool = True
    alipay_app_id: str = ""
    alipay_private_key: str = ""
    alipay_public_key: str = ""
    wechat_enabled: bool = False
    wechat_app_id: str = ""
    wechat_mch_id: str = ""
    wechat_key: str = ""
    paypal_enabled: bool = False
    paypal_client_id: str = ""
    paypal_client_secret: str = ""

class AnnouncementConfig(BaseModel):
    enabled: bool = True
    max_announcements: int = 10
    auto_publish: bool = False
    require_approval: bool = True
    allow_html: bool = False
    max_length: int = 1000

class SecurityConfig(BaseModel):
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_min_length: int = 6
    password_require_special: bool = False
    password_require_number: bool = True
    password_require_uppercase: bool = False
    max_login_attempts: int = 5
    lockout_duration: int = 30
    session_timeout: int = 30
    enable_captcha: bool = False
    enable_2fa: bool = False

class PerformanceConfig(BaseModel):
    cache_enabled: bool = True
    cache_type: str = "memory"
    cache_timeout: int = 300
    max_connections: int = 1000
    workers: int = 4
    enable_compression: bool = True
    enable_gzip: bool = True
    static_file_cache: int = 3600

class ConfigUpdateRequest(BaseModel):
    category: ConfigCategory
    config: Dict[str, Any]

class ConfigTestRequest(BaseModel):
    category: ConfigCategory
    test_data: Dict[str, Any]

class ConfigTestResponse(BaseModel):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None

# Announcement schemas
class AnnouncementBase(BaseModel):
    title: str
    content: str
    is_active: bool = True
    priority: int = 0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    target_audience: str = "all"  # all, users, admins
    category: str = "general"

class AnnouncementCreate(AnnouncementBase):
    pass

class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    target_audience: Optional[str] = None
    category: Optional[str] = None

class AnnouncementInDB(AnnouncementBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None

    class Config:
        from_attributes = True

class Announcement(AnnouncementInDB):
    pass

# Theme schemas
class ThemeConfigBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True
    config_data: Dict[str, Any] = {}

class ThemeConfigCreate(ThemeConfigBase):
    pass

class ThemeConfigUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    config_data: Optional[Dict[str, Any]] = None

class ThemeConfigInDB(ThemeConfigBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ThemeConfig(ThemeConfigInDB):
    pass

# 系统设置专用的主题配置schema
class SystemThemeConfig(BaseModel):
    default_theme: str = "default"
    available_themes: List[str] = ["default", "dark", "light"]
    custom_css: Optional[str] = None
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_color: str = "#1677ff"
    secondary_color: str = "#52c41a"

# System Settings
class SystemSettings(BaseModel):
    general: GeneralConfig
    registration: RegistrationConfig
    email: EmailConfig
    notification: NotificationConfig
    theme: SystemThemeConfig  # 使用SystemThemeConfig
    payment: PaymentConfig
    announcement: AnnouncementConfig
    security: SecurityConfig
    performance: PerformanceConfig 