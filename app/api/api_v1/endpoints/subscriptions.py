from datetime import datetime
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
import base64
import time
from urllib.parse import quote
from app.core.config import settings
from app.core.database import get_db
from app.core.domain_config import get_domain_config
from app.utils.timezone import format_beijing_time
from app.schemas.common import ResponseBase
from app.services.subscription import SubscriptionService
from app.services.email import EmailService
from app.services.device_manager import DeviceManager
from app.utils.security import get_current_user, generate_subscription_url
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

def _get_default_subscription_data():
    return {
        "subscription_id": None,
        "status": "expired",
        "remainingDays": 0,
        "expiryDate": "未订阅",
        "is_expiring": False,
        "currentDevices": 0,
        "maxDevices": 0,
        "is_device_limit_reached": False,
        "mobileUrl": "",
        "clashUrl": "",
        "qrcodeUrl": ""
    }

def _generate_subscription_urls(subscription, request, db):
    if not subscription or not subscription.subscription_url:
        return "", "", "", ""
    timestamp = int(time.time())
    domain_config = get_domain_config()
    base_url = domain_config.get_base_url(request, db).rstrip('/')
    ssr_url = f"{base_url}/api/v1/subscriptions/ssr/{subscription.subscription_url}?t={timestamp}"
    clash_base_url = f"{base_url}/api/v1/subscriptions/clash/{subscription.subscription_url}?t={timestamp}"
    if subscription.expire_time:
        expiry_date = subscription.expire_time.strftime('%Y-%m-%d')
        clash_url = f"{clash_base_url}&expiry={expiry_date}"
    else:
        clash_url = clash_base_url
    v2ray_url = f"{base_url}/api/v1/subscriptions/ssr/{subscription.subscription_url}?t={timestamp}"
    expiry_date = subscription.expire_time.strftime('%Y-%m-%d %H:%M:%S') if subscription.expire_time else "未设置"
    qrcode_url = f"sub://{base64.b64encode(ssr_url.encode()).decode()}#{quote(expiry_date)}"
    return ssr_url, clash_url, v2ray_url, qrcode_url

def _check_subscription_validity(subscription, subscription_service):
    if not subscription:
        return False
    if subscription.expire_time and subscription.expire_time < datetime.utcnow():
        return False
    if subscription.user and not subscription.user.is_active:
        return False
    devices = subscription_service.get_devices_by_subscription_id(subscription.id)
    if len(devices) > subscription.device_limit:
        return False
    return True

def _send_reset_email(db, current_user, new_key, subscription_id, reason):
    try:
        if current_user.email:
            email_service = EmailService(db)
            reset_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            email_service.send_subscription_reset_notification(
                user_email=current_user.email,
                username=current_user.username,
                new_subscription_url=new_key,
                reset_time=reset_time,
                reset_reason=reason,
                subscription_id=subscription_id
            )
            logger.info(f"已发送用户重置订阅通知邮件到: {current_user.email}")
    except Exception as e:
        logger.error(f"发送用户重置订阅通知邮件失败: {e}", exc_info=True)

def _record_device_access(subscription, request, db):
    user_agent = request.headers.get("user-agent", "")
    client_ip = request.client.host if request.client else "unknown"
    device_manager = DeviceManager(db)
    access_result = device_manager.check_subscription_access(
        subscription.subscription_url, user_agent, client_ip
    )
    if settings.DEBUG:
        logger.debug(f"设备访问检查结果: {access_result}")

@router.get("/user-subscription", response_model=ResponseBase)
def get_user_subscription(
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.get_by_user_id(current_user.id)
        if not subscription:
            return ResponseBase(data=_get_default_subscription_data())
        now = datetime.utcnow()
        if subscription.expire_time:
            remaining_days = max(0, (subscription.expire_time - now).days)
            is_expiring = remaining_days <= 7
            expiry_date = subscription.expire_time.strftime('%Y-%m-%d %H:%M:%S')
        else:
            remaining_days = 0
            is_expiring = False
            expiry_date = "未设置"
        devices = subscription_service.get_devices_by_subscription_id(subscription.id)
        current_devices = len(devices)
        max_devices = subscription.device_limit
        ssr_url, clash_url, v2ray_url, qrcode_url = _generate_subscription_urls(subscription, request, db)
        return ResponseBase(
            data={
                "subscription_id": subscription.id,
                "status": "active" if remaining_days > 0 else "expired",
                "remainingDays": remaining_days,
                "expiryDate": expiry_date,
                "is_expiring": is_expiring,
                "currentDevices": current_devices,
                "current_devices": current_devices,
                "online_devices": current_devices,
                "maxDevices": max_devices,
                "is_device_limit_reached": current_devices >= max_devices,
                "mobileUrl": ssr_url,
                "clashUrl": clash_url,
                "v2rayUrl": v2ray_url,
                "qrcodeUrl": qrcode_url
            }
        )
    except Exception as e:
        return ResponseBase(data=_get_default_subscription_data())

@router.post("/reset-subscription", response_model=ResponseBase)
def reset_subscription(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    subscription_service = SubscriptionService(db)
    subscription = subscription_service.get_by_user_id(current_user.id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到订阅信息")
    try:
        subscription_service.delete_devices_by_subscription_id(subscription.id)
    except Exception as e:
        logger.error(f"删除设备记录失败: {e}", exc_info=True)
    new_key = generate_subscription_url()
    try:
        subscription_service.update_subscription_key(subscription.id, new_key)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"重置订阅地址失败: {str(e)}")
    _send_reset_email(db, current_user, new_key, subscription.id, "用户重置")
    return ResponseBase(message="订阅地址重置成功")

@router.post("/send-subscription-email", response_model=ResponseBase)
def send_subscription_email_endpoint(
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    subscription_service = SubscriptionService(db)
    subscription = subscription_service.get_by_user_id(current_user.id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到订阅信息")
    try:
        success = subscription_service.send_subscription_email(current_user.id, request=request)
        if success:
            return ResponseBase(message="订阅邮件发送成功")
        else:
            logger.warning("发送订阅邮件失败: 返回 False")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="邮件发送失败，请检查邮箱配置")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"发送订阅邮件异常: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"邮件发送失败: {str(e)}")

@router.get("/devices", response_model=ResponseBase)
def get_user_devices(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.get_by_user_id(current_user.id)
        if not subscription:
            return ResponseBase(data={"devices": []})
        device_query = text("""
            SELECT * FROM devices
            WHERE subscription_id = :subscription_id
            ORDER BY last_access DESC
        """)
        device_rows = db.execute(device_query, {"subscription_id": subscription.id}).fetchall()
        device_list = []
        for device_row in device_rows:
            device_list.append({
                "id": device_row.id,
                "device_name": device_row.device_name or "未知设备",
                "device_type": device_row.device_type or "unknown",
                "ip_address": device_row.ip_address,
                "user_agent": device_row.user_agent,
                "last_access": format_beijing_time(device_row.last_access) if device_row.last_access else None,
                "is_active": device_row.is_active,
                "created_at": format_beijing_time(device_row.created_at) if device_row.created_at else None
            })
        return ResponseBase(data={"devices": device_list})
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"获取用户设备列表失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"获取设备列表失败: {str(e)}", data={"devices": []})

@router.delete("/devices/{device_id}", response_model=ResponseBase)
def remove_device(
    device_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.get_by_user_id(current_user.id)
        if not subscription:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户没有订阅")
        device_query = text("""
            SELECT id FROM devices 
            WHERE id = :device_id AND subscription_id = :subscription_id
        """)
        device = db.execute(device_query, {'device_id': device_id, 'subscription_id': subscription.id}).fetchone()
        if not device:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在或无权限操作")
        result = db.execute(text("DELETE FROM devices WHERE id = :device_id"), {'device_id': device_id})
        if result.rowcount > 0:
            subscription_service.sync_current_devices(subscription.id)
            return ResponseBase(message="设备移除成功")
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"移除设备失败: {str(e)}")

@router.get("/{subscription_id}/ssr")
def get_ssr_subscription(
    subscription_id: int,
    request: Request,
    db: Session = Depends(get_db)
) -> Any:
    subscription_service = SubscriptionService(db)
    subscription = subscription_service.get(subscription_id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订阅不存在")
    if subscription.expire_time and subscription.expire_time < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="订阅已过期")
    _record_device_access(subscription, request, db)
    ssr_content = subscription_service.generate_ssr_subscription(subscription)
    return ResponseBase(data={"content": ssr_content})

@router.get("/{subscription_id}/clash")
def get_clash_subscription(
    subscription_id: int,
    request: Request,
    db: Session = Depends(get_db)
) -> Any:
    subscription_service = SubscriptionService(db)
    subscription = subscription_service.get(subscription_id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订阅不存在")
    is_valid = _check_subscription_validity(subscription, subscription_service)
    _record_device_access(subscription, request, db)
    if is_valid:
        clash_content = subscription_service.generate_clash_subscription(subscription)
    else:
        clash_content = subscription_service.get_invalid_clash_config()
    return ResponseBase(data={"content": clash_content})

@router.get("/{subscription_id}/v2ray")
def get_v2ray_subscription(
    subscription_id: int,
    request: Request,
    db: Session = Depends(get_db)
) -> Any:
    subscription_service = SubscriptionService(db)
    subscription = subscription_service.get(subscription_id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订阅不存在")
    is_valid = _check_subscription_validity(subscription, subscription_service)
    _record_device_access(subscription, request, db)
    if is_valid:
        v2ray_content = subscription_service.generate_v2ray_subscription(subscription)
    else:
        v2ray_content = subscription_service.get_invalid_v2ray_config()
    return ResponseBase(data={"content": v2ray_content})

@router.put("/user-subscription", response_model=ResponseBase)
def update_user_subscription(
    subscription_data: dict,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.get_by_user_id(current_user.id)
        if not subscription:
            raise HTTPException(status_code=404, detail="用户没有订阅")
        if "device_limit" in subscription_data:
            new_limit = subscription_data["device_limit"]
            if new_limit < subscription.current_devices:
                raise HTTPException(status_code=400, detail="设备限制不能小于当前设备数量")
            subscription.device_limit = new_limit
        if "expire_time" in subscription_data:
            try:
                new_expire_time = datetime.fromisoformat(subscription_data["expire_time"])
                subscription.expire_time = new_expire_time
            except ValueError:
                raise HTTPException(status_code=400, detail="日期格式错误")
        subscription_service.db.commit()
        return ResponseBase(message="订阅设置更新成功")
    except HTTPException:
        raise
    except Exception as e:
        return ResponseBase(success=False, message=f"更新订阅设置失败: {str(e)}")

@router.post("/user-subscription/reset-url", response_model=ResponseBase)
def reset_user_subscription_url(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.get_by_user_id(current_user.id)
        if not subscription:
            raise HTTPException(status_code=400, detail="用户没有订阅")
        new_url = generate_subscription_url()
        subscription.subscription_url = new_url
        devices = subscription_service.get_devices_by_subscription_id(subscription.id)
        for device in devices:
            subscription_service.db.delete(device)
        subscription.current_devices = 0
        subscription_service.db.commit()
        _send_reset_email(db, current_user, new_url, subscription.id, "用户重置订阅地址")
        return ResponseBase(message="订阅地址重置成功", data={"new_subscription_url": new_url})
    except Exception as e:
        return ResponseBase(success=False, message=f"重置订阅地址失败: {str(e)}")

@router.post("/devices/clear", response_model=ResponseBase)
def clear_user_devices(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.get_by_user_id(current_user.id)
        if not subscription:
            raise HTTPException(status_code=400, detail="用户没有订阅")
        devices = subscription_service.get_devices_by_subscription_id(subscription.id)
        for device in devices:
            subscription_service.db.delete(device)
        subscription_service.db.commit()
        subscription_service.sync_current_devices(subscription.id)
        return ResponseBase(message="所有设备清理成功")
    except Exception as e:
        return ResponseBase(success=False, message=f"清理设备失败: {str(e)}")

@router.get("/ssr/{subscription_key}")
def get_ssr_subscription_by_key(
    subscription_key: str,
    request: Request,
    device_id: Optional[str] = Query(None, description="设备ID，用于精确识别设备"),
    db: Session = Depends(get_db)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        device_manager = DeviceManager(db)
        user_agent = request.headers.get("user-agent", "")
        client_ip = request.client.host if request.client else "unknown"
        if settings.DEBUG:
            logger.debug(f"订阅访问请求: subscription_key={subscription_key}, device_id={device_id}, UA: {user_agent[:100]}, IP: {client_ip}")
        access_result = device_manager.check_subscription_access(
            subscription_key, user_agent, client_ip, subscription_type='ssr', device_id=device_id
        )
        if not access_result['allowed']:
            logger.warning(f"订阅访问被拒绝: {access_result['message']}")
            invalid_config = subscription_service.get_invalid_v2ray_config()
            return Response(content=invalid_config, media_type="text/plain", status_code=403)
        if settings.DEBUG:
            logger.debug(f"订阅访问允许: {subscription_key}")
        v2ray_config = subscription_service.get_v2ray_config()
        if settings.DEBUG:
            logger.debug("返回V2Ray配置")
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        return Response(content=v2ray_config, media_type="text/plain", headers=headers)
    except Exception as e:
        logger.error(f"获取SSR订阅失败: {e}", exc_info=True)
        subscription_service = SubscriptionService(db)
        invalid_config = subscription_service.get_invalid_v2ray_config()
        return Response(content=invalid_config, media_type="text/plain")

@router.get("/clash/{subscription_key}")
def get_clash_subscription_by_key(
    subscription_key: str,
    request: Request,
    device_id: Optional[str] = Query(None, description="设备ID，用于精确识别设备"),
    db: Session = Depends(get_db)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        device_manager = DeviceManager(db)
        user_agent = request.headers.get("user-agent", "")
        client_ip = request.client.host if request.client else "unknown"
        if settings.DEBUG:
            logger.debug(f"Clash订阅访问请求: subscription_key={subscription_key}, device_id={device_id}, UA: {user_agent[:100]}, IP: {client_ip}")
        access_result = device_manager.check_subscription_access(
            subscription_key, user_agent, client_ip, subscription_type='clash', device_id=device_id
        )
        if not access_result['allowed']:
            logger.warning(f"订阅访问被拒绝: {access_result['message']}")
            invalid_config = subscription_service.get_invalid_clash_config()
            return Response(content=invalid_config, media_type="text/plain", status_code=403)
        logger.debug(f"订阅访问允许: {subscription_key}")
        clash_config = subscription_service.get_clash_config()
        logger.debug("返回Clash配置")
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        return Response(content=clash_config, media_type="text/plain", headers=headers)
    except Exception as e:
        logger.error(f"获取Clash订阅失败: {e}", exc_info=True)
        subscription_service = SubscriptionService(db)
        invalid_config = subscription_service.get_invalid_clash_config()
        return Response(content=invalid_config, media_type="text/plain")
