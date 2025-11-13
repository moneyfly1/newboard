from datetime import timedelta, timezone, datetime
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import re
from pydantic import BaseModel
from app.core.config import settings
from app.core.database import get_db
from app.schemas.user import UserLogin, UserCreate, EmailVerificationRequest, PasswordResetRequest, PasswordReset
from app.models.user import User
from app.models.login_attempt import LoginAttempt
from app.models.verification_attempt import VerificationAttempt
from app.schemas.common import ResponseBase, Token
from app.services.user import UserService
from app.services.email import EmailService
from app.utils.security import create_access_token, create_refresh_token
from app.utils.response import create_safe_http_exception, sanitize_error_message
import secrets
import string
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

def validate_email(email: str) -> bool:
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))

def extract_username(email: str) -> str:
    return email.split('@')[0]

def _serialize_user(user):
    from app.schemas.user import User as UserSchema
    try:
        if hasattr(UserSchema, 'model_validate'):
            return UserSchema.model_validate(user)
        elif hasattr(UserSchema, 'from_orm'):
            return UserSchema.from_orm(user)
        else:
            return UserSchema(
                id=user.id, username=user.username, email=user.email, is_active=user.is_active,
                is_verified=user.is_verified, is_admin=user.is_admin, avatar=getattr(user, 'avatar', None),
                theme=getattr(user, 'theme', 'light'), language=getattr(user, 'language', 'zh-CN'),
                timezone=getattr(user, 'timezone', 'Asia/Shanghai'),
                email_notifications=getattr(user, 'email_notifications', True),
                notification_types=getattr(user, 'notification_types', '["subscription", "payment", "system"]'),
                sms_notifications=getattr(user, 'sms_notifications', False),
                push_notifications=getattr(user, 'push_notifications', True),
                created_at=user.created_at, updated_at=getattr(user, 'updated_at', None),
                last_login=getattr(user, 'last_login', None)
            )
    except Exception as e:
        logger.warning(f"用户对象转换失败，使用字典方式: {e}", exc_info=True)
        return UserSchema(
            id=user.id, username=user.username, email=user.email, is_active=user.is_active,
            is_verified=user.is_verified, is_admin=user.is_admin, avatar=getattr(user, 'avatar', None),
            theme=getattr(user, 'theme', 'light'), language=getattr(user, 'language', 'zh-CN'),
            timezone=getattr(user, 'timezone', 'Asia/Shanghai'),
            email_notifications=getattr(user, 'email_notifications', True),
            notification_types=getattr(user, 'notification_types', '["subscription", "payment", "system"]'),
            sms_notifications=getattr(user, 'sms_notifications', False),
            push_notifications=getattr(user, 'push_notifications', True),
            created_at=user.created_at, updated_at=getattr(user, 'updated_at', None),
            last_login=getattr(user, 'last_login', None)
        )

def _serialize_user_dict(user):
    from app.schemas.user import User as UserSchema
    try:
        if hasattr(UserSchema, 'model_validate'):
            return UserSchema.model_validate(user).model_dump()
        elif hasattr(UserSchema, 'from_orm'):
            return UserSchema.from_orm(user).dict()
        else:
            return {"id": user.id, "username": user.username, "email": user.email, "is_admin": user.is_admin,
                    "is_verified": user.is_verified, "is_active": user.is_active, "avatar": user.avatar}
    except Exception as e:
        logger.warning(f"用户数据序列化失败，使用回退方法: {e}", exc_info=True)
        return {"id": user.id, "username": user.username, "email": user.email, "is_admin": user.is_admin,
                "is_verified": user.is_verified, "is_active": user.is_active, "avatar": user.avatar}

def _check_verification_attempts(db, email, purpose='register'):
    MAX_VERIFICATION_ATTEMPTS = 10
    ATTEMPT_WINDOW = 3600
    recent_attempts = db.query(VerificationAttempt).filter(
        VerificationAttempt.email == email,
        VerificationAttempt.success == False,
        VerificationAttempt.purpose == purpose,
        VerificationAttempt.created_at >= datetime.now(timezone.utc) - timedelta(seconds=ATTEMPT_WINDOW)
    ).count()
    if recent_attempts >= MAX_VERIFICATION_ATTEMPTS:
        logger.warning(f"验证码尝试次数过多: email={email}, attempts={recent_attempts}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"验证码尝试次数过多，请1小时后再试（已尝试{recent_attempts}次）"
        )

def _record_verification_attempt(db, email, ip_address, success, purpose):
    attempt = VerificationAttempt(email=email, ip_address=ip_address, success=success, purpose=purpose)
    db.add(attempt)
    db.commit()

def _validate_verification_code(db, email, code, purpose, client_ip):
    from app.models.verification_code import VerificationCode
    _check_verification_attempts(db, email, purpose)
    verification_code_obj = db.query(VerificationCode).filter(
        VerificationCode.email == email,
        VerificationCode.code == code,
        VerificationCode.purpose == purpose,
        VerificationCode.used == 0
    ).order_by(VerificationCode.created_at.desc()).first()
    if not verification_code_obj:
        _record_verification_attempt(db, email, client_ip, False, purpose)
        if settings.DEBUG:
            logger.debug(f"验证码验证失败: 未找到验证码 - email={email}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误或已过期")
    try:
        if verification_code_obj.is_expired():
            _record_verification_attempt(db, email, client_ip, False, purpose)
            if settings.DEBUG:
                logger.debug(f"验证码已过期: email={email}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码已过期，请重新获取")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"检查验证码过期时出错: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码验证失败，请重新获取")
    if verification_code_obj.is_used():
        _record_verification_attempt(db, email, client_ip, False, purpose)
        if settings.DEBUG:
            logger.debug(f"验证码已使用: email={email}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码已使用，请重新获取")
    _record_verification_attempt(db, email, client_ip, True, purpose)
    if settings.DEBUG:
        logger.debug(f"验证码验证成功: email={email}")
    return verification_code_obj

def _send_verification_code_email(db, email, code, purpose='register'):
    from app.models.verification_code import VerificationCode
    from datetime import datetime, timezone, timedelta
    recent_code = db.query(VerificationCode).filter(
        VerificationCode.email == email,
        VerificationCode.purpose == purpose,
        VerificationCode.used == 0,
        VerificationCode.created_at >= datetime.now(timezone.utc) - timedelta(minutes=1)
    ).first()
    if recent_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码发送过于频繁，请稍后再试")
    code_str = ''.join(secrets.choice(string.digits) for _ in range(6))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    verification_code = VerificationCode(email=email, code=code_str, expires_at=expires_at, purpose=purpose)
    db.add(verification_code)
    db.commit()
    try:
        email_service = EmailService(db)
        if purpose == 'register':
            username = extract_username(email)
            email_service.send_verification_code_email(user_email=email, verification_code=code_str, username=username)
        else:
            user_service = UserService(db)
            user = user_service.get_by_email(email)
            if user:
                email_service.send_password_reset_verification_code_email(
                    user_email=email, verification_code=code_str, username=user.username)
    except Exception as e:
        logger.error(f"发送验证码邮件失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="验证码发送失败，请稍后重试")
    return code_str

def _check_login_lockout(db, login_identifier):
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION = 1800
    try:
        recent_failures = db.query(LoginAttempt).filter(
            LoginAttempt.username == login_identifier,
            LoginAttempt.success == False,
            LoginAttempt.created_at >= datetime.now(timezone.utc) - timedelta(seconds=LOCKOUT_DURATION)
        ).count()
        if recent_failures >= MAX_FAILED_ATTEMPTS:
            logger.warning(f"账户已被锁定: username={login_identifier}, failures={recent_failures}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"账户已被锁定，请30分钟后再试（连续失败{recent_failures}次）"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"账户锁定检查失败（表可能不存在）: {e}")

def _handle_login_success(user_service, user, request):
    if request:
        user_service.log_login(user_id=user.id, ip_address=request.client.host if request.client else None,
                                user_agent=request.headers.get("user-agent"), login_status="success")
        user_service.log_user_activity(user_id=user.id, activity_type="login_success", description="用户登录成功",
                                        ip_address=request.client.host if request.client else None,
                                        user_agent=request.headers.get("user-agent"))
    user_service.update_last_login(user.id)

def _handle_login_failure(user_service, user, request, reason):
    if request and user:
        user_service.log_user_activity(user_id=user.id, activity_type="login_failed", description=f"登录失败: {reason}",
                                        ip_address=request.client.host if request.client else None,
                                        user_agent=request.headers.get("user-agent"))

@router.post("/send-verification-code", response_model=ResponseBase)
def send_verification_code(email_request: EmailVerificationRequest, db: Session = Depends(get_db)) -> Any:
    from app.core.settings_manager import settings_manager
    registration_enabled = settings_manager.get_setting('registration_enabled', True, db)
    if not registration_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="注册功能已禁用，请联系管理员")
    if not validate_email(email_request.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱格式不正确")
    user_service = UserService(db)
    if user_service.get_by_email(email_request.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该邮箱已被注册")
    _send_verification_code_email(db, email_request.email, None, 'register')
    return ResponseBase(success=True, message="验证码已发送，请查收邮箱")

@router.post("/register", response_model=Token)
def register(user_in: UserCreate, request: Request, response: Response, db: Session = Depends(get_db)) -> Any:
    from app.core.auth import validate_password_strength
    from app.models.verification_code import VerificationCode
    from app.core.settings_manager import settings_manager
    client_ip = request.client.host if request.client else None
    registration_enabled = settings_manager.get_setting('registration_enabled', True, db)
    if not registration_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="注册功能已禁用，请联系管理员")
    if not user_in.verification_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入验证码")
    verification_code_obj = _validate_verification_code(db, user_in.email, user_in.verification_code, 'register', client_ip)
    is_valid, message = validate_password_strength(user_in.password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"密码不符合安全要求: {message}")
    user_service = UserService(db)
    if user_service.get_by_username(user_in.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该用户名已被注册")
    if user_service.get_by_email(user_in.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该邮箱已被注册")
    user = user_service.create(user_in)
    user.is_verified = True
    user.is_active = True
    db.commit()
    verification_code_obj.mark_as_used()
    db.commit()
    user_service.log_user_activity(user_id=user.id, activity_type="user_registered", description="用户注册成功")
    try:
        email_service = EmailService(db)
        email_service.send_welcome_email(user_email=user.email, username=user.username, user_id=user.id, password=user_in.password)
        logger.info(f"欢迎邮件已发送: {user.email}")
    except Exception as e:
        logger.warning(f"发送欢迎邮件失败: {e}", exc_info=True)
    access_token = create_access_token(data={"sub": str(user.id), "user_id": user.id})
    refresh_token = create_refresh_token(data={"sub": str(user.id), "user_id": user.id})
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    user_schema = _serialize_user(user)
    
    is_secure = request.url.scheme == "https" or settings.DEBUG
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/v1/auth"
    )
    
    return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer",
                 expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, user=user_schema)

@router.post("/login", response_model=Token)
def login(request: Request, response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Any:
    user_service = UserService(db)
    login_identifier = form_data.username
    user = user_service.authenticate_by_email(login_identifier, form_data.password) if '@' in login_identifier else user_service.authenticate(login_identifier, form_data.password)
    if not user:
        raise create_safe_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"}
        )
    if not user.is_active:
        _handle_login_failure(user_service, user, request, "账户已被禁用")
        raise create_safe_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="账户已被禁用"
        )
    _handle_login_success(user_service, user, request)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": str(user.id), "user_id": user.id}, expires_delta=access_token_expires)
    refresh_token = create_refresh_token(data={"sub": str(user.id), "user_id": user.id})
    user_dict = _serialize_user_dict(user)
    
    is_secure = request.url.scheme == "https" or settings.DEBUG
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/v1/auth"
    )
    
    return Token(access_token=access_token, token_type="bearer", expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, refresh_token=refresh_token, user=user_dict)

@router.post("/login-json", response_model=Token)
def login_json(login_data: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> Any:
    try:
        user_service = UserService(db)
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")
        login_identifier = login_data.username
        
        # 检查登录锁定
        try:
            _check_login_lockout(db, login_identifier)
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"检查登录锁定失败: {e}")
        
        # 验证用户
        try:
            user = user_service.authenticate_by_email(login_identifier, login_data.password) if '@' in login_identifier else user_service.authenticate(login_identifier, login_data.password)
        except Exception as e:
            logger.error(f"用户认证失败: {e}", exc_info=True)
            raise create_safe_http_exception(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="登录验证失败，请稍后重试"
            )
        
        if not user:
            try:
                login_attempt = LoginAttempt(username=login_identifier, ip_address=client_ip, success=False, user_agent=user_agent)
                db.add(login_attempt)
                db.commit()
            except Exception as e:
                logger.warning(f"记录登录尝试失败（表可能不存在）: {e}")
                try:
                    db.rollback()
                except:
                    pass
            raise create_safe_http_exception(
                status_code=status.HTTP_401_UNAUTHORIZED,
                message="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        if not user.is_active:
            try:
                _handle_login_failure(user_service, user, request, "账户已被禁用")
            except Exception as e:
                logger.warning(f"记录登录失败信息失败: {e}")
            raise create_safe_http_exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="账户已被禁用"
            )
        
        try:
            _handle_login_success(user_service, user, request)
        except Exception as e:
            logger.warning(f"记录登录成功信息失败: {e}")
        
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data={"sub": str(user.id), "user_id": user.id}, expires_delta=access_token_expires)
        refresh_token = create_refresh_token(data={"sub": str(user.id), "user_id": user.id})
        user_dict = _serialize_user_dict(user)
        
        is_secure = request.url.scheme == "https" or settings.DEBUG
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=is_secure,
            samesite="lax",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/api/v1/auth"
        )
        
        return Token(access_token=access_token, token_type="bearer", expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, refresh_token=refresh_token, user=user_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录处理失败: {e}", exc_info=True)
        raise create_safe_http_exception(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="登录失败，请稍后重试"
        )

@router.post("/refresh", response_model=Token)
def refresh_token(
    request: Request,
    refresh_token: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Any:
    from app.utils.security import verify_token
    
    token = refresh_token
    if not token:
        token = request.cookies.get("refresh_token")
    
    if not token:
        raise create_safe_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="刷新令牌缺失，请重新登录"
        )
    
    # 简化验证逻辑，只验证token是否有效
    payload = verify_token(token)
    if not payload:
        raise create_safe_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="无效的刷新令牌，请重新登录"
        )
    
    # 检查token类型（可选，不强制）
    if payload.get("type") and payload.get("type") != "refresh":
        raise create_safe_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="无效的刷新令牌，请重新登录"
        )
    
    user_id = payload.get("user_id") or payload.get("sub")
    if not user_id:
        raise create_safe_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="无效的令牌数据，请重新登录"
        )
    
    # 简化用户查询，移除重试逻辑
    user_service = UserService(db)
    try:
        user_id_int = int(user_id) if isinstance(user_id, str) and user_id.isdigit() else None
        if user_id_int:
            user = user_service.get(user_id_int)
        else:
            user = user_service.get_by_username(str(user_id))
    except (ValueError, TypeError):
        user = None
    except Exception as e:
        # 数据库错误，返回503而不是401
        raise create_safe_http_exception(
            status_code=503,
            message="数据库连接失败，请稍后重试"
        )
    
    if not user or not user.is_active:
        raise create_safe_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="用户不存在或已被禁用，请重新登录"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": str(user.id), "user_id": user.id}, expires_delta=access_token_expires)
    
    new_refresh_token = create_refresh_token(data={"sub": str(user.id), "user_id": user.id})
    
    response = JSONResponse(content={
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    })
    
    is_secure = request.url.scheme == "https" or settings.DEBUG
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/v1/auth"
    )
    
    return response

@router.post("/forgot-password", response_model=ResponseBase)
def forgot_password(email: str, db: Session = Depends(get_db)) -> Any:
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="此接口已废弃，请使用 /forgot-password-new 接口")

@router.post("/reset-password", response_model=ResponseBase)
def reset_password(token: str, new_password: str, db: Session = Depends(get_db)) -> Any:
    from app.utils.security import verify_token
    payload = verify_token(token)
    if not payload or payload.get("type") != "password_reset":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的重置令牌")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的令牌数据")
    user_service = UserService(db)
    user = user_service.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    user_service.update_password(user_id, new_password)
    return ResponseBase(message="密码重置成功")

@router.post("/forgot-password-new", response_model=ResponseBase)
def forgot_password_new(request_data: PasswordResetRequest, db: Session = Depends(get_db)) -> Any:
    if not validate_email(request_data.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱格式不正确")
    user_service = UserService(db)
    user = user_service.get_by_email(request_data.email)
    if not user:
        return ResponseBase(message="如果该邮箱已注册，验证码已发送到您的邮箱", data={})
    _send_verification_code_email(db, request_data.email, None, 'reset_password')
    return ResponseBase(message="如果该邮箱已注册，验证码已发送到您的邮箱", data={})

@router.post("/reset-password-new", response_model=ResponseBase)
def reset_password_new(reset_data: PasswordReset, request: Request, db: Session = Depends(get_db)) -> Any:
    from app.core.auth import validate_password_strength
    from app.utils.security import get_password_hash
    client_ip = request.client.host if request.client else None
    if not reset_data.verification_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入验证码")
    verification_code_obj = _validate_verification_code(db, reset_data.email, reset_data.verification_code, 'reset_password', client_ip)
    is_valid, message = validate_password_strength(reset_data.new_password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"密码不符合安全要求: {message}")
    user_service = UserService(db)
    user = user_service.get_by_email(reset_data.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    user.hashed_password = get_password_hash(reset_data.new_password)
    user.reset_token = None
    user.reset_expires = None
    verification_code_obj.mark_as_used()
    db.commit()
    return ResponseBase(message="密码重置成功，请使用新密码登录", data={"user_id": user.id, "username": user.username})
