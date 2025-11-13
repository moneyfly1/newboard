from typing import Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request as FastAPIRequest
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.domain_config import get_domain_config
from app.schemas.user import User, UserUpdate, UserPasswordChange, ThemeUpdate, PreferenceSettings
from app.schemas.common import ResponseBase
from app.schemas.email import EmailQueueCreate
from app.services.user import UserService
from app.services.subscription import SubscriptionService
from app.services.device_manager import DeviceManager
from app.services.email import EmailService
from app.services.email_template_enhanced import EmailTemplateEnhanced
from app.utils.security import get_current_user, verify_password, get_password_hash
from app.utils.timezone import format_beijing_time, get_beijing_time_str
import logging
import json
import time
import base64
from urllib.parse import quote

logger = logging.getLogger(__name__)
router = APIRouter()

def _get_user_or_404(user_service, user_id):
    user = user_service.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return user

def _generate_subscription_urls(subscription, request, db):
    if not subscription or not subscription.subscription_url:
        return "", "", "", ""
    timestamp = int(time.time())
    domain_config = get_domain_config()
    base_url = domain_config.get_base_url(request, db).rstrip('/')
    mobile_url = f"{base_url}/api/v1/subscriptions/ssr/{subscription.subscription_url}?t={timestamp}"
    clash_url = f"{base_url}/api/v1/subscriptions/clash/{subscription.subscription_url}?t={timestamp}"
    v2ray_url = f"{base_url}/api/v1/subscriptions/ssr/{subscription.subscription_url}?t={timestamp}"
    expiry_display = subscription.expire_time.strftime('%Y-%m-%d %H:%M:%S') if subscription.expire_time and subscription.expire_time != "未设置" else subscription.subscription_url
    encoded_url = base64.b64encode(mobile_url.encode()).decode()
    qrcode_url = f"sub://{encoded_url}#{quote(expiry_display)}"
    return mobile_url, clash_url, v2ray_url, qrcode_url

@router.get("/profile", response_model=User)
def get_user_profile(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    user_service = UserService(db)
    return _get_user_or_404(user_service, current_user.id)

@router.get("/dashboard-info", response_model=ResponseBase)
def get_user_dashboard_info(
    request: FastAPIRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        user_service = UserService(db)
        subscription_service = SubscriptionService(db)
        user = _get_user_or_404(user_service, current_user.id)
        subscription = subscription_service.get_by_user_id(current_user.id)
        remaining_days = 0
        expiry_date = "未设置"
        if subscription and subscription.expire_time:
            expire_date = subscription.expire_time
            if isinstance(expire_date, datetime):
                remaining_days = (expire_date - datetime.now()).days
                expiry_date = expire_date.strftime('%Y-%m-%d %H:%M:%S')
        mobile_url, clash_url, v2ray_url, qrcode_url = _generate_subscription_urls(subscription, request, db)
        subscription_status = "inactive"
        if subscription:
            subscription_status = "active" if remaining_days > 0 else "expired"
        user_balance = f"{float(user.balance):.2f}" if user.balance else "0.00"
        created_at_str = format_beijing_time(user.created_at) if user.created_at else "未知"
        last_login_str = format_beijing_time(user.last_login) if user.last_login else "未知"
        is_verified_value = bool(getattr(user, 'is_verified', False))
        dashboard_info = {
            "username": user.username,
            "email": user.email,
            "is_verified": is_verified_value,
            "email_verified": is_verified_value,
            "verified": is_verified_value,
            "last_login": last_login_str,
            "last_login_time": last_login_str,
            "login_time": last_login_str,
            "created_at": created_at_str,
            "created_time": created_at_str,
            "register_time": created_at_str,
            "status": "active" if user.is_active else "inactive",
            "user_status": "active" if user.is_active else "inactive",
            "account_status": "active" if user.is_active else "inactive",
            "membership": "普通会员",
            "expire_time": subscription.expire_time.isoformat() if subscription and subscription.expire_time else None,
            "expiryDate": expiry_date,
            "remaining_days": remaining_days,
            "online_devices": 0,
            "total_devices": 0,
            "balance": user_balance,
            "speed_limit": "不限速",
            "subscription_url": subscription.subscription_url if subscription else None,
            "subscription_status": subscription_status,
            "clashUrl": clash_url,
            "v2rayUrl": v2ray_url,
            "mobileUrl": mobile_url,
            "qrcodeUrl": qrcode_url
        }
        return ResponseBase(data=dashboard_info)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取仪表盘信息失败: {str(e)}")

@router.get("/devices", response_model=ResponseBase)
def get_user_devices(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        device_manager = DeviceManager(db)
        devices = device_manager.get_user_devices(current_user.id)
        return ResponseBase(data=devices)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取设备列表失败: {str(e)}")

@router.put("/profile", response_model=User)
def update_user_profile(
    user_update: UserUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    user_service = UserService(db)
    user = user_service.update(current_user.id, user_update)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return user

@router.post("/change-password", response_model=ResponseBase)
def change_user_password(
    password_change: UserPasswordChange,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    user_service = UserService(db)
    user = _get_user_or_404(user_service, current_user.id)
    if not verify_password(password_change.old_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")
    user.hashed_password = get_password_hash(password_change.new_password)
    db.commit()
    try:
        email_service = EmailService(db)
        change_time = get_beijing_time_str('%Y-%m-%d %H:%M:%S')
        html_content = EmailTemplateEnhanced.get_password_changed_template(
            username=user.username, change_time=change_time, request=None, db=db
        )
        email_data = EmailQueueCreate(
            to_email=user.email,
            subject="密码修改成功 - 网络服务",
            content=html_content,
            content_type='html',
            email_type='password_changed'
        )
        email_service.queue_email(email_data)
    except Exception:
        pass
    return ResponseBase(message="密码修改成功")

@router.get("/theme", response_model=ResponseBase)
def get_user_theme(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    user_service = UserService(db)
    user = _get_user_or_404(user_service, current_user.id)
    return ResponseBase(data={"theme": user.theme or "light"})

@router.put("/theme", response_model=ResponseBase)
def update_user_theme(
    theme_update: ThemeUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    user_service = UserService(db)
    user = _get_user_or_404(user_service, current_user.id)
    user.theme = theme_update.theme
    db.commit()
    return ResponseBase(message="主题更新成功")

@router.get("/notification-settings", response_model=ResponseBase)
def get_user_notification_settings(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        user_service = UserService(db)
        user = _get_user_or_404(user_service, current_user.id)
        notification_types = []
        if user.notification_types:
            try:
                notification_types = json.loads(user.notification_types)
            except:
                notification_types = ['subscription', 'payment', 'system', 'marketing']
        else:
            notification_types = ['subscription', 'payment', 'system', 'marketing']
        return ResponseBase(data={
            "email_notifications": user.email_notifications if user.email_notifications is not None else True,
            "notification_types": notification_types,
            "sms_notifications": user.sms_notifications if user.sms_notifications is not None else False,
            "push_notifications": user.push_notifications if user.push_notifications is not None else True
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取通知设置失败: {str(e)}")

@router.put("/notification-settings", response_model=ResponseBase)
def update_user_notification_settings(
    settings: dict,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        user_service = UserService(db)
        user = _get_user_or_404(user_service, current_user.id)
        if "email_notifications" in settings:
            user.email_notifications = bool(settings["email_notifications"])
        if "notification_types" in settings:
            user.notification_types = json.dumps(settings["notification_types"])
        if "sms_notifications" in settings:
            user.sms_notifications = bool(settings["sms_notifications"])
        if "push_notifications" in settings:
            user.push_notifications = bool(settings["push_notifications"])
        db.commit()
        db.refresh(user)
        return ResponseBase(message="通知设置更新成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新通知设置失败: {str(e)}")

@router.get("/privacy-settings", response_model=ResponseBase)
def get_user_privacy_settings(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        user_service = UserService(db)
        user = _get_user_or_404(user_service, current_user.id)
        return ResponseBase(data={
            "data_sharing": user.data_sharing if user.data_sharing is not None else True,
            "analytics": user.analytics if user.analytics is not None else True
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取隐私设置失败: {str(e)}")

@router.put("/privacy-settings", response_model=ResponseBase)
def update_user_privacy_settings(
    settings: dict,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        user_service = UserService(db)
        user = _get_user_or_404(user_service, current_user.id)
        if "data_sharing" in settings:
            user.data_sharing = bool(settings["data_sharing"])
        if "analytics" in settings:
            user.analytics = bool(settings["analytics"])
        db.commit()
        db.refresh(user)
        return ResponseBase(message="隐私设置更新成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新隐私设置失败: {str(e)}")

@router.get("/preference-settings", response_model=ResponseBase)
def get_user_preference_settings(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        user_service = UserService(db)
        user = _get_user_or_404(user_service, current_user.id)
        return ResponseBase(data={
            "language": user.language or "zh-CN",
            "timezone": user.timezone or "Asia/Shanghai",
            "theme": user.theme or "light"
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取偏好设置失败: {str(e)}")

@router.put("/preference-settings", response_model=ResponseBase)
def update_user_preference_settings(
    settings: PreferenceSettings,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        user_service = UserService(db)
        user = _get_user_or_404(user_service, current_user.id)
        if settings.language is not None:
            user.language = settings.language
        if settings.timezone is not None:
            user.timezone = settings.timezone
        db.commit()
        db.refresh(user)
        return ResponseBase(message="偏好设置更新成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新偏好设置失败: {str(e)}")

@router.get("/login-history", response_model=ResponseBase)
def get_user_login_history(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        user_service = UserService(db)
        login_history_list = user_service.get_login_history(current_user.id, limit=size * page)
        skip = (page - 1) * size
        paginated_history = login_history_list[skip:skip + size]
        formatted_history = []
        for login in paginated_history:
            country = "未知"
            city = "未知"
            if login.location:
                location_parts = login.location.split(',')
                if len(location_parts) >= 1:
                    country = location_parts[0].strip()
                if len(location_parts) >= 2:
                    city = location_parts[1].strip()
            device_info = "未知设备"
            if login.user_agent:
                user_agent = login.user_agent.lower()
                if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
                    device_info = "移动设备"
                elif 'windows' in user_agent:
                    device_info = "Windows设备"
                elif 'mac' in user_agent:
                    device_info = "Mac设备"
                elif 'linux' in user_agent:
                    device_info = "Linux设备"
                else:
                    device_info = "其他设备"
            formatted_history.append({
                "id": login.id,
                "login_time": login.login_time.isoformat() if login.login_time else None,
                "ip_address": login.ip_address or "未知",
                "country": country,
                "city": city,
                "location": login.location or "未知",
                "user_agent": login.user_agent or "未知",
                "status": login.login_status or "success"
            })
        total = len(login_history_list)
        pages = (total + size - 1) // size if total > 0 else 1
        return ResponseBase(
            success=True,
            data={
                "logins": formatted_history,
                "total": total,
                "page": page,
                "size": size,
                "pages": pages
            }
        )
    except Exception as e:
        logger.error(f"更新用户偏好设置失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"获取登录历史失败: {str(e)}")
