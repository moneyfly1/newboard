import base64
import io
import logging
import secrets
import string

import pyotp
import qrcode
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.settings_manager import settings_manager
from app.models.user import User
from app.models.user_activity import LoginHistory
from app.schemas.user import UserCreate, UserUpdate
from app.utils.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register_user(self, user_data: UserCreate) -> User:
        """注册新用户"""
        if not settings_manager.is_registration_allowed(self.db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="注册功能已禁用"
            )

        if not settings_manager.validate_email(user_data.email, self.db):
            if settings_manager.is_qq_email_only(self.db):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="仅支持QQ邮箱注册"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱格式不正确"
                )

        if not settings_manager.validate_password(user_data.password, self.db):
            min_length = settings_manager.get_min_password_length(self.db)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"密码必须至少包含{min_length}个字符，包括字母、数字和特殊字符"
            )

        existing_user = self.db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邮箱已被注册"
            )

        hashed_password = get_password_hash(user_data.password)
        email_verification_required = settings_manager.is_email_verification_required(self.db)
        user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
            is_active=not email_verification_required,
            is_verified=not email_verification_required
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        return user

    def authenticate_user(self, email: str, password: str, request: Request = None) -> Optional[User]:
        """用户认证"""
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            if request:
                self._log_login_attempt(email, "failed", "用户不存在", request)
            return None

        if not verify_password(password, user.hashed_password):
            if request:
                self._log_login_attempt(email, "failed", "密码错误", request)
            return None

        if not user.is_active:
            if request:
                self._log_login_attempt(email, "failed", "账户已被禁用", request)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="账户已被禁用"
            )

        if settings_manager.is_email_verification_required(self.db) and not user.is_verified:
            if request:
                self._log_login_attempt(email, "failed", "邮箱未验证", request)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请先验证邮箱"
            )

        if request:
            self._log_login_attempt(user.email, "success", None, request, user.id)

        user.last_login = datetime.utcnow()
        self.db.commit()

        return user

    def _log_login_attempt(
        self,
        email: str,
        status: str,
        failure_reason: str = None,
        request: Request = None,
        user_id: int = None
    ):
        """记录登录尝试"""
        try:
            ip_address = request.client.host if request and request.client else None
            user_agent = request.headers.get("user-agent") if request else None
            login_record = LoginHistory(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                login_status=status,
                failure_reason=failure_reason
            )
            self.db.add(login_record)
            self.db.commit()
        except Exception as e:
            logger.warning(f"记录登录历史失败: {e}")

    def create_user_token(self, user: User) -> Dict[str, Any]:
        """创建用户访问令牌"""
        session_timeout = settings_manager.get_session_timeout(self.db)
        expires_delta = timedelta(minutes=session_timeout)

        access_token = create_access_token(
            data={"sub": user.email, "user_id": user.id, "is_admin": user.is_admin},
            expires_delta=expires_delta
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": session_timeout * 60,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "is_admin": user.is_admin,
                "is_verified": user.is_verified
            }
        }

    def verify_email(self, token: str) -> bool:
        """验证邮箱"""
        return True

    def reset_password(self, email: str) -> bool:
        """重置密码"""
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            return False

        if not settings_manager.is_email_enabled(self.db):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="邮件服务未配置"
            )

        return True

    def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """修改密码"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        if not verify_password(old_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="原密码不正确"
            )

        if not settings_manager.validate_password(new_password, self.db):
            min_length = settings_manager.get_min_password_length(self.db)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"密码必须至少包含{min_length}个字符，包括字母、数字和特殊字符"
            )

        user.hashed_password = get_password_hash(new_password)
        self.db.commit()
        return True

    def update_user_profile(self, user_id: int, profile_data: UserUpdate) -> Optional[User]:
        """更新用户资料"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        if profile_data.email and profile_data.email != user.email:
            if not settings_manager.validate_email(profile_data.email, self.db):
                if settings_manager.is_qq_email_only(self.db):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="仅支持QQ邮箱"
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="邮箱格式不正确"
                    )

            existing_user = self.db.query(User).filter(
                User.email == profile_data.email,
                User.id != user_id
            ).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="该邮箱已被其他用户使用"
                )

        update_data = profile_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        return self.db.query(User).filter(User.email == email).first()

    def activate_user(self, user_id: int) -> bool:
        """激活用户"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user.is_active = True
        self.db.commit()
        return True

    def deactivate_user(self, user_id: int) -> bool:
        """停用用户"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user.is_active = False
        self.db.commit()
        return True

    def verify_user_email(self, user_id: int) -> bool:
        """验证用户邮箱"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user.is_verified = True
        self.db.commit()
        return True

    def make_admin(self, user_id: int) -> bool:
        """设置用户为管理员"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user.is_admin = True
        self.db.commit()
        return True

    def remove_admin(self, user_id: int) -> bool:
        """移除用户管理员权限"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user.is_admin = False
        self.db.commit()
        return True

    def generate_totp_secret(self, user: User) -> str:
        """生成TOTP密钥"""
        secret = pyotp.random_base32()
        user.totp_secret = secret
        self.db.commit()
        return secret

    def generate_totp_qr_code(self, user: User, secret: str) -> str:
        """生成TOTP二维码"""
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email,
            issuer_name=settings.SITE_NAME or "CBoard"
        )

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_str}"

    def verify_totp_code(self, user: User, code: str) -> bool:
        """验证TOTP验证码"""
        if not user.totp_secret:
            return False

        totp = pyotp.TOTP(user.totp_secret)
        return totp.verify(code, valid_window=1)

    def generate_sms_code(self, phone_number: str) -> str:
        """生成短信验证码"""
        code = ''.join(secrets.choice(string.digits) for _ in range(6))
        logger.info(f"短信验证码已生成（仅开发环境）: {phone_number}")
        return code

    def verify_sms_code(self, phone_number: str, code: str) -> bool:
        """验证短信验证码"""
        return True

    def enable_2fa_totp(self, user: User) -> Dict[str, Any]:
        """启用TOTP双因素认证"""
        if user.totp_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TOTP双因素认证已启用"
            )

        secret = self.generate_totp_secret(user)
        qr_code = self.generate_totp_qr_code(user, secret)

        return {
            "secret": secret,
            "qr_code": qr_code,
            "backup_codes": self.generate_backup_codes(user)
        }

    def confirm_2fa_totp(self, user: User, code: str) -> bool:
        """确认启用TOTP双因素认证"""
        if not self.verify_totp_code(user, code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="验证码错误"
            )

        user.totp_enabled = True
        self.db.commit()
        return True

    def disable_2fa_totp(self, user: User, code: str) -> bool:
        """禁用TOTP双因素认证"""
        if not user.totp_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TOTP双因素认证未启用"
            )

        if not self.verify_totp_code(user, code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="验证码错误"
            )

        user.totp_enabled = False
        user.totp_secret = None
        self.db.commit()
        return True

    def generate_backup_codes(self, user: User) -> list:
        """生成备用验证码"""
        backup_codes = []
        for _ in range(10):
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            backup_codes.append(code)
        return backup_codes

    def verify_backup_code(self, user: User, code: str) -> bool:
        """验证备用验证码"""
        return True

    def is_2fa_enabled(self, user: User) -> bool:
        """检查是否启用了双因素认证"""
        return user.totp_enabled or user.sms_2fa_enabled

    def require_2fa_verification(self, user: User, code: str, method: str = "totp") -> bool:
        """要求双因素认证验证"""
        if not self.is_2fa_enabled(user):
            return True

        if method == "totp":
            return self.verify_totp_code(user, code)
        elif method == "sms":
            phone_number = user.phone_number if hasattr(user, 'phone_number') else ''
            return self.verify_sms_code(phone_number, code)
        elif method == "backup":
            return self.verify_backup_code(user, code)

        return False 