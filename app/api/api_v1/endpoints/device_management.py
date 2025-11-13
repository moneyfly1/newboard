from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.utils.security import get_current_admin_user
from app.utils.timezone import format_beijing_time
from app.schemas.common import ResponseBase
from app.services.device_manager import DeviceManager
from app.services.subscription import SubscriptionService
from app.api.api_v1.endpoints.common import handle_api_error
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

def _serialize_device(row):
    return {
        'id': row.id,
        'user_id': row.user_id,
        'subscription_id': row.subscription_id,
        'subscription_url': getattr(row, 'subscription_url', None),
        'username': getattr(row, 'username', None),
        'email': getattr(row, 'email', None),
        'device_ua': row.device_ua,
        'device_hash': row.device_hash,
        'ip_address': row.ip_address,
        'user_agent': row.user_agent,
        'software_name': row.software_name,
        'software_version': row.software_version,
        'os_name': row.os_name,
        'os_version': row.os_version,
        'device_model': row.device_model,
        'device_brand': row.device_brand,
        'is_allowed': bool(row.is_allowed),
        'first_seen': format_beijing_time(row.first_seen) if row.first_seen else None,
        'last_seen': format_beijing_time(row.last_seen) if row.last_seen else None,
        'access_count': row.access_count,
        'created_at': format_beijing_time(row.created_at) if row.created_at else None,
        'updated_at': format_beijing_time(row.updated_at) if row.updated_at else None
    }

def _build_where_clause(conditions):
    return " AND ".join(conditions) if conditions else "1=1"

@router.get("/devices", response_model=ResponseBase)
@handle_api_error("获取设备列表")
def get_all_devices(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), user_id: Optional[int] = Query(None), subscription_id: Optional[int] = Query(None), software_name: Optional[str] = Query(None), is_allowed: Optional[bool] = Query(None), db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    conditions = []
    params = {}
    if user_id:
        conditions.append("d.user_id = :user_id")
        params['user_id'] = user_id
    if subscription_id:
        conditions.append("d.subscription_id = :subscription_id")
        params['subscription_id'] = subscription_id
    if software_name:
        conditions.append("d.software_name LIKE :software_name")
        params['software_name'] = f"%{software_name}%"
    if is_allowed is not None:
        conditions.append("d.is_allowed = :is_allowed")
        params['is_allowed'] = is_allowed
    where_clause = _build_where_clause(conditions)
    count_sql = f"SELECT COUNT(*) FROM devices d JOIN subscriptions s ON d.subscription_id = s.id JOIN users u ON d.user_id = u.id WHERE {where_clause}"
    total = db.execute(text(count_sql), params).scalar()
    offset = (page - 1) * size
    data_sql = f"SELECT d.*, s.subscription_url, u.username, u.email FROM devices d JOIN subscriptions s ON d.subscription_id = s.id JOIN users u ON d.user_id = u.id WHERE {where_clause} ORDER BY d.last_seen DESC LIMIT :size OFFSET :offset"
    params.update({'size': size, 'offset': offset})
    result = db.execute(text(data_sql), params).fetchall()
    devices = [_serialize_device(row) for row in result]
    return ResponseBase(data={'devices': devices, 'total': total, 'page': page, 'size': size, 'pages': (total + size - 1) // size})

@router.get("/devices/{device_id}", response_model=ResponseBase)
@handle_api_error("获取设备详情")
def get_device_detail(device_id: int, db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    result = db.execute(text("SELECT d.*, s.subscription_url, u.username, u.email FROM devices d JOIN subscriptions s ON d.subscription_id = s.id JOIN users u ON d.user_id = u.id WHERE d.id = :device_id"), {'device_id': device_id}).fetchone()
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    return ResponseBase(data=_serialize_device(result))

@router.put("/devices/{device_id}", response_model=ResponseBase)
@handle_api_error("更新设备状态")
def update_device(device_id: int, device_data: dict, db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    device_manager = DeviceManager(db)
    device = db.execute(text("SELECT id, user_id, subscription_id FROM devices WHERE id = :device_id"), {'device_id': device_id}).fetchone()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    success = device_manager.update_device_status(device_id, device_data)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="设备状态更新失败")
    return ResponseBase(message="设备状态更新成功")

@router.delete("/devices/{device_id}", response_model=ResponseBase)
@handle_api_error("删除设备")
def delete_device(device_id: int, db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    device_query = text("SELECT id, user_id, subscription_id, is_allowed FROM devices WHERE id = :device_id")
    device = db.execute(device_query, {'device_id': device_id}).fetchone()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    subscription_id = device.subscription_id
    was_allowed = bool(device.is_allowed)
    result = db.execute(text("DELETE FROM devices WHERE id = :device_id"), {'device_id': device_id})
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    subscription_service = SubscriptionService(db)
    subscription_service.sync_current_devices(subscription_id)
    logger.info(f"管理员删除设备: device_id={device_id}, subscription_id={subscription_id}, was_allowed={was_allowed}")
    db.commit()
    return ResponseBase(message="设备删除成功")

@router.get("/users/{user_id}/devices", response_model=ResponseBase)
@handle_api_error("获取用户设备列表")
def get_user_devices(user_id: int, subscription_id: Optional[int] = Query(None), db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    device_manager = DeviceManager(db)
    devices = device_manager.get_user_devices(user_id, subscription_id)
    return ResponseBase(data={'devices': devices})

@router.get("/user/{user_id}", response_model=ResponseBase)
@handle_api_error("获取用户设备列表")
def get_user_devices_alt(user_id: int, subscription_id: Optional[int] = Query(None), db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    device_manager = DeviceManager(db)
    devices = device_manager.get_user_devices(user_id, subscription_id)
    return ResponseBase(data=devices)

@router.post("/user/{user_id}/clear", response_model=ResponseBase)
@handle_api_error("清理用户设备")
def clear_user_devices(user_id: int, db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    device_manager = DeviceManager(db)
    subscriptions = db.execute(text("SELECT id FROM subscriptions WHERE user_id = :user_id"), {'user_id': user_id}).fetchall()
    cleared_count = sum(device_manager.clear_user_devices(sub.id) for sub in subscriptions)
    return ResponseBase(message=f"成功清理 {cleared_count} 个设备", data={'cleared_count': cleared_count})

@router.get("/subscriptions/{subscription_id}/devices", response_model=ResponseBase)
@handle_api_error("获取订阅设备列表")
def get_subscription_devices(subscription_id: int, db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    device_manager = DeviceManager(db)
    subscription = db.execute(text("SELECT id, user_id FROM subscriptions WHERE id = :subscription_id"), {'subscription_id': subscription_id}).fetchone()
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订阅不存在")
    devices = device_manager.get_user_devices(subscription.user_id, subscription_id)
    stats = device_manager.get_subscription_device_stats(subscription_id)
    return ResponseBase(data={'devices': devices, 'stats': stats})

@router.get("/software-rules", response_model=ResponseBase)
@handle_api_error("获取软件识别规则")
def get_software_rules(db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    device_manager = DeviceManager(db)
    rules = device_manager.get_software_rules()
    return ResponseBase(data={'rules': rules})

@router.get("/access-logs", response_model=ResponseBase)
@handle_api_error("获取访问日志")
def get_access_logs(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), subscription_id: Optional[int] = Query(None), access_type: Optional[str] = Query(None), db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    conditions = []
    params = {}
    if subscription_id:
        conditions.append("l.subscription_id = :subscription_id")
        params['subscription_id'] = subscription_id
    if access_type:
        conditions.append("l.access_type = :access_type")
        params['access_type'] = access_type
    where_clause = _build_where_clause(conditions)
    count_sql = f"SELECT COUNT(*) FROM subscription_access_logs l JOIN subscriptions s ON l.subscription_id = s.id JOIN users u ON s.user_id = u.id WHERE {where_clause}"
    total = db.execute(text(count_sql), params).scalar()
    offset = (page - 1) * size
    data_sql = f"SELECT l.*, s.subscription_url, u.username, u.email FROM subscription_access_logs l JOIN subscriptions s ON l.subscription_id = s.id JOIN users u ON s.user_id = u.id WHERE {where_clause} ORDER BY l.access_time DESC LIMIT :size OFFSET :offset"
    params.update({'size': size, 'offset': offset})
    result = db.execute(text(data_sql), params).fetchall()
    logs = [{'id': row.id, 'subscription_id': row.subscription_id, 'subscription_url': row.subscription_url, 'username': row.username, 'email': row.email, 'device_id': row.device_id, 'ip_address': row.ip_address, 'user_agent': row.user_agent, 'access_type': row.access_type, 'response_status': row.response_status, 'response_message': row.response_message, 'access_time': row.access_time} for row in result]
    return ResponseBase(data={'logs': logs, 'total': total, 'page': page, 'size': size, 'pages': (total + size - 1) // size})

@router.post("/devices/{device_id}/allow", response_model=ResponseBase)
@handle_api_error("允许设备")
def allow_device(device_id: int, db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    device_manager = DeviceManager(db)
    device = db.execute(text("SELECT d.*, s.device_limit FROM devices d JOIN subscriptions s ON d.subscription_id = s.id WHERE d.id = :device_id"), {'device_id': device_id}).fetchone()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    allowed_count = db.execute(text("SELECT COUNT(*) FROM devices WHERE subscription_id = :subscription_id AND is_allowed = 1"), {'subscription_id': device.subscription_id}).scalar()
    if allowed_count >= device.device_limit:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"订阅设备数量已达上限（{device.device_limit}个）")
    success = device_manager.update_device_status(device_id, {'is_allowed': True})
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="允许设备失败")
    return ResponseBase(message="设备已允许访问", data={'device_id': device_id})

@router.post("/devices/{device_id}/block", response_model=ResponseBase)
@handle_api_error("禁止设备")
def block_device(device_id: int, db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    device_manager = DeviceManager(db)
    success = device_manager.update_device_status(device_id, {'is_allowed': False})
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="禁止设备失败")
    return ResponseBase(message="设备已禁止访问", data={'device_id': device_id})
