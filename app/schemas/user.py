from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime
import re

# 允许的邮箱后缀
ALLOWED_EMAIL_DOMAINS = [
    'gmail.com',
    'qq.com', 
    '126.com',
    '163.com',
    'hotmail.com',
    'foxmail.com'
]

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str
    username: str  # 必填用户名
    verification_code: Optional[str] = None  # 验证码
    
    @validator('email')
    def validate_email(cls, v):
        """验证邮箱格式和域名"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('请输入正确的邮箱地址')
        
        # 检查邮箱域名是否在允许列表中
        domain = v.split('@')[1].lower()
        if domain not in ALLOWED_EMAIL_DOMAINS:
            raise ValueError(f'只支持以下邮箱类型: {", ".join(ALLOWED_EMAIL_DOMAINS)}')
        
        return v
    
    @validator('username')
    def validate_username(cls, v):
        """验证用户名"""
        if not v or len(v.strip()) < 2:
            raise ValueError('用户名长度不能少于2位')
        if len(v) > 20:
            raise ValueError('用户名长度不能超过20位')
        # 只允许字母、数字、下划线
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v.strip()
    
    @validator('password')
    def validate_password(cls, v):
        """验证密码强度"""
        if len(v) < 8:
            raise ValueError('密码长度不能少于8位')
        if len(v) > 50:
            raise ValueError('密码长度不能超过50位')
        # 至少包含字母和数字
        if not re.search(r'[A-Za-z]', v) or not re.search(r'[0-9]', v):
            raise ValueError('密码必须包含字母和数字')
        return v

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_admin: Optional[bool] = None
    avatar: Optional[str] = None
    theme: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    email_notifications: Optional[bool] = None
    notification_types: Optional[str] = None
    sms_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None

class UserInDB(UserBase):
    id: int
    username: str
    is_active: bool
    is_verified: bool
    is_admin: bool
    avatar: Optional[str] = None
    theme: Optional[str] = 'light'
    language: Optional[str] = 'zh-CN'
    timezone: Optional[str] = 'Asia/Shanghai'
    email_notifications: Optional[bool] = True
    notification_types: Optional[str] = '["subscription", "payment", "system"]'
    sms_notifications: Optional[bool] = False
    push_notifications: Optional[bool] = True
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True
        orm_mode = True  # Pydantic v1 兼容
        populate_by_name = True  # Pydantic v2 兼容

class User(UserInDB):
    pass

class UserLogin(BaseModel):
    username: str  # 可以是用户名或邮箱
    password: str

class UserPasswordChange(BaseModel):
    old_password: str
    new_password: str

class EmailVerificationRequest(BaseModel):
    email: EmailStr

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordReset(BaseModel):
    email: EmailStr
    verification_code: str
    new_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        """验证密码强度"""
        if len(v) < 8:
            raise ValueError('密码长度不能少于8位')
        if len(v) > 50:
            raise ValueError('密码长度不能超过50位')
        # 至少包含字母和数字
        if not re.search(r'[A-Za-z]', v) or not re.search(r'[0-9]', v):
            raise ValueError('密码必须包含字母和数字')
        return v

class ThemeUpdate(BaseModel):
    theme: str
    
    @validator('theme')
    def validate_theme(cls, v):
        """验证主题设置"""
        allowed_themes = ['light', 'dark', 'blue', 'green', 'purple', 'orange', 'red', 'cyan', 'luck', 'aurora', 'auto']
        if v not in allowed_themes:
            raise ValueError(f'主题必须是以下之一: {", ".join(allowed_themes)}')
        return v

class PreferenceSettings(BaseModel):
    language: Optional[str] = 'zh-CN'
    timezone: Optional[str] = 'Asia/Shanghai'

class NotificationSettings(BaseModel):
    email_notifications: bool = True
    notification_types: list = ["subscription", "payment", "system"]
    sms_notifications: bool = False
    push_notifications: bool = True

# 导出允许的邮箱域名列表
__all__ = [
    'UserBase', 'UserCreate', 'UserUpdate', 'UserInDB', 'User',
    'UserLogin', 'UserPasswordChange', 'EmailVerificationRequest',
    'PasswordResetRequest', 'PasswordReset',
    'ThemeUpdate', 'PreferenceSettings', 'NotificationSettings', 'ALLOWED_EMAIL_DOMAINS'
]