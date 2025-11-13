from typing import Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, BackgroundTasks, Request
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text, func, and_, or_
from datetime import datetime, timedelta, timezone
from app.utils.timezone import format_beijing_time
from pathlib import Path
from urllib.parse import quote
import logging
import csv
import io
import json
import time
import base64
import secrets
from app.core.database import get_db, SessionLocal
from app.core.config import settings
from app.core.auth import validate_password_strength
from app.core.domain_config import get_domain_config
from app.schemas.common import ResponseBase
from app.schemas.subscription import SubscriptionCreate
from app.models.user import User
from app.models.user_activity import UserActivity, SubscriptionReset
from app.models.subscription import Subscription
from app.models.order import Order
from app.models.config import SystemConfig
from app.models.payment_config import PaymentConfig
from app.services.user import UserService
from app.services.subscription import SubscriptionService
from app.services.order import OrderService
from app.services.settings import SettingsService
from app.services.payment_config import PaymentConfigService
from app.services.email_template_enhanced import EmailTemplateEnhanced as EmailTemplateService
from app.services.node_service import NodeService
from app.services.recharge import RechargeService
from app.services.email import EmailService
from app.services.package import PackageService
from app.services.email_queue_processor import EmailQueueProcessor, get_email_queue_processor
from app.services.logging import log_manager
from app.services.config_update_service import ConfigUpdateService
from app.utils.security import get_current_admin_user, get_password_hash, verify_password, generate_subscription_url, create_access_token
logger = logging.getLogger(__name__)
router = APIRouter()
device_query = text("""
    SELECT d.*, COUNT(*) OVER() as total_count
    FROM devices d
    WHERE d.subscription_id = :subscription_id
""")
device_query_by_id = text("SELECT * FROM devices WHERE id = :device_id")
device_query_by_user = text("""
    SELECT d.* FROM devices d
    JOIN subscriptions s ON d.subscription_id = s.id
    WHERE d.id = :device_id AND s.user_id = :user_id
""")
subscription_count_query = text("""
    SELECT
        (
            SELECT COUNT(*)
            FROM subscription_access_logs l
            WHERE l.subscription_id = :subscription_id
            AND l.access_type LIKE 'clash_%'
            AND l.access_type NOT LIKE '%browser%'
        ) as clash_count,
        (
            SELECT COUNT(*)
            FROM subscription_access_logs l
            WHERE l.subscription_id = :subscription_id
            AND (l.access_type LIKE 'ssr_%' OR l.access_type = 'allowed')
            AND l.access_type NOT LIKE '%browser%'
        ) as v2ray_count
""")
insert_query = text("""
    INSERT INTO system_configs (key, value, type, category, display_name, description, sort_order, created_at, updated_at)
    VALUES (:key, :value, :type, :category, :display_name, :description, :sort_order, :created_at, :updated_at)
""")
update_query = text("""
    UPDATE system_configs
    SET value = :value, updated_at = :updated_at
    WHERE key = :key AND type = :type
""")
user_insert_query = text("""
    INSERT INTO users (username, email, hashed_password, is_active, is_admin, is_verified, created_at)
    VALUES (:username, :email, :hashed_password, :is_active, :is_admin, :is_verified, :created_at)
""")
v2ray_insert_query = text("""
    INSERT INTO subscriptions (user_id, subscription_url, device_limit, current_devices, is_active, expire_time, created_at, updated_at)
    VALUES (:user_id, :subscription_url, :device_limit, :current_devices, :is_active, :expire_time, :created_at, :updated_at)
""")
clash_insert_query = text("""
    INSERT INTO subscriptions (user_id, subscription_url, device_limit, current_devices, is_active, expire_time, created_at, updated_at)
    VALUES (:user_id, :subscription_url, :device_limit, :current_devices, :is_active, :expire_time, :created_at, :updated_at)
""")
apple_query = text("""
    SELECT
        COUNT(*) as total_count,
        COUNT(CASE WHEN d.software_name = 'v2ray' THEN 1 END) as apple_count
    FROM devices d
""")
online_query = text("""
    SELECT
        COUNT(*) as total_count,
        COUNT(CASE WHEN d.last_seen > datetime('now', '-5 minutes') THEN 1 END) as online_count
    FROM devices d
""")
delete_device_query = text("DELETE FROM devices WHERE id = :device_id")
def _get_config_from_db(db: Session, config_key: str, config_type: str, default_value: str = "") -> str:
    query = text('SELECT value FROM system_configs WHERE key = :key AND type = :type')
    result = db.execute(query, {"key": config_key, "type": config_type}).first()
    return result.value if result else default_value
def _save_config_to_db(
    db: Session,
    config_key: str,
    config_type: str,
    config_value: str,
    category: str = "system",
    display_name: str = "",
    description: str = "",
    sort_order: int = 0
) -> bool:
    current_time = datetime.now()
    check_query = text('SELECT id FROM system_configs WHERE key = :key AND type = :type')
    existing = db.execute(check_query, {"key": config_key, "type": config_type}).first()
    if existing:
        db.execute(update_query, {
            "value": config_value,
            "updated_at": current_time,
            "key": config_key,
            "type": config_type
        })
    else:
        db.execute(insert_query, {
            "key": config_key,
            "value": config_value,
            "type": config_type,
            "category": category,
            "display_name": display_name or config_key.replace('_', ' ').title(),
            "description": description or f"Configuration for {config_key}",
            "sort_order": sort_order,
            "created_at": current_time,
            "updated_at": current_time
        })
    db.commit()
    return True
def _format_date(date_value):
    if date_value is None:
        return None
    if isinstance(date_value, str):
        try:
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f']:
                try:
                    dt = datetime.strptime(date_value, fmt)
                    return format_beijing_time(dt)
                except ValueError:
                    continue
            return date_value
        except:
            return date_value
    elif hasattr(date_value, 'isoformat'):
        return format_beijing_time(date_value)
    else:
        return str(date_value)
def _parse_datetime(dt_str):
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except:
        return None
def _calculate_subscription_status(subscription):
    if not subscription or not subscription.expire_time:
        return "inactive", None, False
    now = datetime.now(timezone.utc)
    expire_time = _parse_datetime(subscription.expire_time) if isinstance(subscription.expire_time, str) else subscription.expire_time
    if expire_time and expire_time.tzinfo is None:
        expire_time = expire_time.replace(tzinfo=timezone.utc)
    if expire_time and expire_time > now:
        status = "active" if subscription.is_active else "inactive"
        days = (expire_time - now).days
        return status, days, False
    return "expired", 0, True
def _get_device_stats(db, subscription_id):
    try:
        device_result = db.execute(device_query, {'subscription_id': subscription_id}).fetchone()
        count_result = db.execute(subscription_count_query, {'subscription_id': subscription_id}).fetchone()
        device_count = device_result.total_count or 0 if device_result else 0
        clash_count = count_result.clash_count or 0 if count_result else 0
        v2ray_count = count_result.v2ray_count or 0 if count_result else 0
        return device_count, clash_count, v2ray_count, v2ray_count
    except Exception as e:
        logger.error(f"获取设备统计失败: {e}", exc_info=True)
        return 0, 0, 0, 0
def _handle_error(e: Exception, operation: str, db: Session = None) -> ResponseBase:
    if db:
        db.rollback()
    return ResponseBase(success=False, message=f"{operation}失败: {str(e)}")
def _save_configs_batch(db: Session, config_data: dict, config_type: str = None, category: str = "system", value_processor=None) -> None:
    current_time = datetime.now()
    for key, value in config_data.items():
        if value_processor:
            value = value_processor(key, value)
        else:
            value = str(value)
        if config_type:
            check_query = text('SELECT id FROM system_configs WHERE key = :key AND type = :type')
            existing = db.execute(check_query, {"key": key, "type": config_type}).first()
            update_params = {"value": value, "updated_at": current_time, "key": key, "type": config_type}
        else:
            check_query = text('SELECT id FROM system_configs WHERE key = :key AND category = :category')
            existing = db.execute(check_query, {"key": key, "category": category}).first()
            update_params = {"value": value, "updated_at": current_time, "key": key}
        if existing:
            if config_type:
                db.execute(update_query, update_params)
            else:
                update_query_cat = text('UPDATE system_configs SET value = :value, updated_at = :updated_at WHERE key = :key AND category = :category')
                db.execute(update_query_cat, {**update_params, "category": category})
        else:
            db.execute(insert_query, {
                "key": key, "value": value, "type": config_type or "system", "category": category,
                "display_name": key.replace('_', ' ').title(),
                "description": f"{category.title()} setting for {key}",
                "sort_order": 0, "created_at": current_time, "updated_at": current_time
            })
@router.get("/users", response_model=ResponseBase)
def get_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword: str = Query("", description="关键词搜索（邮箱或用户名）"),
    status: str = Query("", description="状态筛选"),
    date_range: str = Query("", description="注册时间范围"),
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        user_service = UserService(db)
        subscription_service = SubscriptionService(db)
        search_params = {}
        if keyword:
            search_params['search'] = keyword
        if status:
            search_params['status'] = status
        skip = (page - 1) * size
        users, total = user_service.get_users_with_pagination(
            skip=skip,
            limit=size,
            **search_params
        )
        user_list = []
        for user in users:
            subscription = subscription_service.get_by_user_id(user.id)
            subscribed_devices = 0
            if subscription:
                try:
                    # 使用与订阅列表相同的逻辑获取在线设备数量
                    device_result = db.execute(device_query, {
                        'subscription_id': subscription.id
                    }).fetchone()
                    if device_result:
                        # device_query 返回 total_count，与订阅列表API保持一致
                        subscribed_devices = device_result.total_count or 0
                    else:
                        subscribed_devices = 0
                except Exception as e:
                    logger.error(f"获取用户设备信息失败: {e}", exc_info=True)
                    subscribed_devices = 0
            subscription_status, days_until_expire, is_expired = _calculate_subscription_status(subscription)
            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_active": user.is_active,
                "is_admin": user.is_admin,
                "is_verified": user.is_verified,
                "status": "active" if user.is_active else "disabled",
                "balance": float(user.balance) if user.balance else 0.0,
                "created_at": format_beijing_time(user.created_at) if user.created_at else None,
                "last_login": format_beijing_time(user.last_login) if user.last_login else None,
                "subscription_count": 1 if subscription else 0,
                "device_count": subscribed_devices,
                "online_devices": subscribed_devices,
                "subscription": {
                    "id": subscription.id if subscription else None,
                    "status": subscription_status,
                    "expire_time": format_beijing_time(subscription.expire_time) if subscription and subscription.expire_time else None,
                    "device_limit": subscription.device_limit if subscription else 0,
                    "current_devices": subscribed_devices,
                    "online_devices": subscribed_devices,
                    "days_until_expire": days_until_expire,
                    "is_expired": is_expired
                } if subscription else None
            }
            user_list.append(user_data)
        response_data = {
            "users": user_list,
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size
        }
        return ResponseBase(data=response_data)
    except Exception as e:
        logger.error(f"获取用户列表失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"获取用户列表失败: {str(e)}")
@router.get("/users/statistics", response_model=ResponseBase)
def get_user_statistics(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        user_service = UserService(db)
        subscription_service = SubscriptionService(db)
        user_stats = user_service.get_user_stats()
        total_subscriptions = subscription_service.count()
        active_subscriptions = subscription_service.count_active()
        subscription_rate = 0
        if user_stats["total"] > 0:
            subscription_rate = round((total_subscriptions / user_stats["total"]) * 100, 2)
        stats = {
            "totalUsers": user_stats["total"],
            "activeUsers": user_stats["active"],
            "newUsersToday": user_stats["today"],
            "newUsersYesterday": user_stats["yesterday"],
            "recentUsers7Days": user_stats["recent_7_days"],
            "totalSubscriptions": total_subscriptions,
            "activeSubscriptions": active_subscriptions,
            "subscriptionRate": subscription_rate
        }
        return ResponseBase(data=stats)
    except Exception as e:
        return _handle_error(e, "获取用户统计", db)
@router.post("/users", response_model=ResponseBase)
def create_user(
    user_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        check_username = text("SELECT id FROM users WHERE username = :username")
        existing_user = db.execute(check_username, {"username": user_data.get("username")}).first()
        if existing_user:
            return ResponseBase(success=False, message="用户名已存在")
        check_email = text("SELECT id FROM users WHERE email = :email")
        existing_email = db.execute(check_email, {"email": user_data.get("email")}).first()
        if existing_email:
            return ResponseBase(success=False, message="邮箱已存在")
        current_time = datetime.now()
        result = db.execute(user_insert_query, {
            "username": user_data["username"],
            "email": user_data["email"],
            "hashed_password": get_password_hash(user_data["password"]),
            "is_active": user_data.get("is_active", True),
            "is_admin": user_data.get("is_admin", False),
            "is_verified": user_data.get("is_verified", False),
            "created_at": current_time
        })
        db.commit()
        user_id = result.lastrowid
        try:
            subscription_service = SubscriptionService(db)
            device_limit = user_data.get("device_limit", 5)
            expire_time = None
            if user_data.get("expire_time"):
                expire_time_str = user_data.get("expire_time")
                if isinstance(expire_time_str, str):
                    try:
                        expire_time = datetime.fromisoformat(expire_time_str.replace('Z', '+00:00'))
                        if expire_time.tzinfo is None:
                            expire_time = expire_time.replace(tzinfo=timezone.utc)
                        expire_time = expire_time.replace(tzinfo=None)
                    except Exception as e:
                        logger.warning(f"解析到期时间失败: {e}，使用默认值（一年后）")
                        expire_time = datetime.utcnow() + timedelta(days=365)
                else:
                    expire_time = datetime.utcnow() + timedelta(days=365)
            else:
                expire_time = datetime.utcnow() + timedelta(days=365)
            default_subscription = SubscriptionCreate(
                user_id=user_id,
                device_limit=device_limit,
                expire_time=expire_time
            )
            subscription_service.create(default_subscription)
        except Exception as e:
            logger.error(f"创建默认订阅失败: {e}", exc_info=True)
        return ResponseBase(message="用户创建成功", data={"user_id": user_id})
    except Exception as e:
        db.rollback()
        return ResponseBase(success=False, message=f"创建用户失败: {str(e)}")
@router.post("/users/batch-delete", response_model=ResponseBase)
def batch_delete_users(
    user_ids: dict = Body(...),
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        user_service = UserService(db)
        deleted_count = 0
        failed_count = 0
        user_id_list = user_ids.get("user_ids", [])
        try:
            for user_id in user_id_list:
                user = user_service.get(user_id)
                if user and not user.is_admin:
                    success = user_service.delete(user_id)
                    if success:
                        deleted_count += 1
                    else:
                        failed_count += 1
                else:
                    failed_count += 1
            if failed_count == 0:
                db.commit()
        except Exception as e:
            db.rollback()
            raise e
        message = f"成功删除 {deleted_count} 个用户及其所有相关数据"
        if failed_count > 0:
            message += f"，{failed_count} 个用户删除失败"
        return ResponseBase(message=message)
    except Exception as e:
        return ResponseBase(success=False, message=f"批量删除用户失败: {str(e)}")
@router.get("/nodes/stats", response_model=ResponseBase)
def get_nodes_stats(
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        db = SessionLocal()
        try:
            node_service = NodeService(db)
            stats = node_service.get_node_statistics()
            return ResponseBase(
                data=stats,
                message="获取节点统计成功"
            )
        finally:
            node_service.close()
    except Exception as e:
        return ResponseBase(success=False, message=f"获取节点统计失败: {str(e)}")
@router.post("/users/batch-enable", response_model=ResponseBase)
def batch_enable_users(
    user_ids: dict = Body(...),
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        user_service = UserService(db)
        updated_count = 0
        user_id_list = user_ids.get("user_ids", [])
        for user_id in user_id_list:
            user = user_service.get(user_id)
            if user:
                user.is_active = True
                updated_count += 1
        db.commit()
        return ResponseBase(message=f"成功启用 {updated_count} 个用户")
    except Exception as e:
        return ResponseBase(success=False, message=f"批量启用用户失败: {str(e)}")
@router.post("/users/batch-disable", response_model=ResponseBase)
def batch_disable_users(
    user_ids: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        user_service = UserService(db)
        updated_count = 0
        user_id_list = user_ids.get("user_ids", [])
        for user_id in user_id_list:
            user = user_service.get(user_id)
            if user and not user.is_admin:
                user.is_active = False
                updated_count += 1
        db.commit()
        return ResponseBase(message=f"成功禁用 {updated_count} 个用户")
    except Exception as e:
        return ResponseBase(success=False, message=f"批量禁用用户失败: {str(e)}")
@router.get("/users/detail/{user_id}", response_model=ResponseBase)
def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        user_service = UserService(db)
        subscription_service = SubscriptionService(db)
        user = user_service.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        subscription = subscription_service.get_by_user_id(user.id)
        devices = subscription_service.get_devices_by_subscription_id(subscription.id) if subscription else []
        online_devices = 0
        clash_count = 0
        v2ray_count = 0
        apple_count = 0
        if subscription:
            device_count, clash_count, v2ray_count, apple_count = _get_device_stats(db, subscription.id)
            online_devices = device_count
        user_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "is_verified": user.is_verified,
            "created_at": format_beijing_time(user.created_at) if user.created_at else None,
            "last_login": format_beijing_time(user.last_login) if user.last_login else None,
            "subscription": {
                "id": subscription.id if subscription else None,
                "status": "active" if subscription and subscription.is_active else "inactive",
                "expire_time": format_beijing_time(subscription.expire_time) if subscription and subscription.expire_time else None,
                "device_limit": subscription.device_limit if subscription else 0,
                "current_devices": subscription.current_devices if subscription else 0,
                "subscription_url": subscription.subscription_url if subscription else None,
                "online_devices": online_devices,
                "v2ray_count": v2ray_count,
                "clash_count": clash_count,
                "apple_count": apple_count
            } if subscription else None,
            "devices": [
                {
                    "id": device.id,
                    "name": device.device_name,
                    "type": device.device_type,
                    "ip": device.ip_address,
                    "last_access": format_beijing_time(device.last_seen) if device.last_seen else None
                } for device in devices
            ]
        }
        return ResponseBase(data=user_data)
    except HTTPException:
        raise
    except Exception as e:
        return ResponseBase(success=False, message=f"获取用户详情失败: {str(e)}")
@router.put("/users/{user_id}", response_model=ResponseBase)
def update_user(
    user_id: int,
    user_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        user_service = UserService(db)
        subscription_service = SubscriptionService(db)
        user = user_service.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if "email" in user_data:
            user.email = user_data["email"]
        if "username" in user_data:
            user.username = user_data["username"]
        if "is_active" in user_data:
            user.is_active = user_data["is_active"]
        if "is_verified" in user_data:
            user.is_verified = user_data["is_verified"]
        if "is_admin" in user_data:
            user.is_admin = user_data["is_admin"]
        if "password" in user_data and user_data["password"]:
            user.hashed_password = get_password_hash(user_data["password"])
        user_service.db.commit()
        if "subscription" in user_data:
            subscription = subscription_service.get_by_user_id(user.id)
            if subscription:
                if "device_limit" in user_data["subscription"]:
                    subscription.device_limit = user_data["subscription"]["device_limit"]
                if "expire_time" in user_data["subscription"]:
                    subscription.expire_time = datetime.fromisoformat(user_data["subscription"]["expire_time"])
                if "is_active" in user_data["subscription"]:
                    subscription.is_active = user_data["subscription"]["is_active"]
                subscription_service.db.commit()
        try:
            user_service.log_user_activity(
                user_id=user.id,
                activity_type="admin_update",
                description=f"管理员 {current_admin.username} 更新了用户信息",
                metadata={"updated_fields": list(user_data.keys())}
            )
        except:
            pass
        return ResponseBase(message="用户信息更新成功")
    except HTTPException:
        raise
    except Exception as e:
        return ResponseBase(success=False, message=f"更新用户信息失败: {str(e)}")
@router.put("/users/{user_id}/toggle-status", response_model=ResponseBase)
def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        user_service = UserService(db)
        user = user_service.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user.is_admin:
            raise HTTPException(status_code=400, detail="不能修改管理员用户状态")
        user.is_active = not user.is_active
        db.commit()
        status_text = "启用" if user.is_active else "禁用"
        return ResponseBase(message=f"用户状态已{status_text}")
    except HTTPException:
        raise
    except Exception as e:
        return ResponseBase(success=False, message=f"切换用户状态失败: {str(e)}")
@router.delete("/users/{user_id}", response_model=ResponseBase)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        user_service = UserService(db)
        user = user_service.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user.is_admin:
            raise HTTPException(status_code=400, detail="不能删除管理员用户")
        success = user_service.delete(user_id)
        if success:
            db.commit()
            return ResponseBase(message="用户及其所有相关数据删除成功")
        else:
            db.rollback()
            return ResponseBase(success=False, message="删除用户失败")
    except HTTPException:
        raise
    except Exception as e:
        return ResponseBase(success=False, message=f"删除用户失败: {str(e)}")
@router.get("/users/{user_id}/devices", response_model=ResponseBase)
def get_user_devices_admin(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.get_by_user_id(user_id)
        if not subscription:
            return ResponseBase(data={"devices": []})
        device_rows = db.execute(device_query, {"subscription_id": subscription.id}).fetchall()
        device_list = []
        for device_row in device_rows:
            device_data = {
                "id": device_row.id,
                "device_name": device_row.device_name or "未知设备",
                "device_type": device_row.device_type or "unknown",
                "ip_address": device_row.ip_address,
                "user_agent": device_row.user_agent,
                "last_access": format_beijing_time(device_row.last_access) if device_row.last_access else None,
                "last_seen": format_beijing_time(device_row.last_seen) if device_row.last_seen else (format_beijing_time(device_row.last_access) if device_row.last_access else None),
                "os_name": device_row.os_name,
                "access_count": device_row.access_count or 0,
                "is_active": device_row.is_active,
                "created_at": format_beijing_time(device_row.created_at) if device_row.created_at else None
            }
            device_list.append(device_data)
        return ResponseBase(data={"devices": device_list})
    except Exception as e:
        logger.error(f"获取用户设备列表失败: {e}", exc_info=True)
        return ResponseBase(data={"devices": []})
@router.delete("/devices/{device_id}", response_model=ResponseBase)
def delete_device_admin(
    device_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        device = db.execute(device_query_by_id, {'device_id': device_id}).fetchone()
        if not device:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
        result = db.execute(delete_device_query, {'device_id': device_id})
        if result.rowcount > 0:
            subscription_service = SubscriptionService(db)
            subscription_service.sync_current_devices(device.subscription_id)
            db.commit()
            return ResponseBase(message="设备删除成功")
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"删除设备失败: {str(e)}")
@router.delete("/users/{user_id}/devices/{device_id}", response_model=ResponseBase)
def delete_user_device_admin(
    user_id: int,
    device_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        user_query = text("SELECT id FROM users WHERE id = :user_id")
        user = db.execute(user_query, {'user_id': user_id}).fetchone()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
        device = db.execute(device_query_by_user, {'device_id': device_id, 'user_id': user_id}).fetchone()
        if not device:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在或不属于该用户")
        result = db.execute(delete_device_query, {'device_id': device_id})
        if result.rowcount > 0:
            subscription_service = SubscriptionService(db)
            subscription_service.sync_current_devices(device.subscription_id)
            db.commit()
            return ResponseBase(message="设备删除成功")
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"删除设备失败: {str(e)}")
@router.post("/users/{user_id}/clear-devices", response_model=ResponseBase)
def clear_user_devices_admin(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.get_by_user_id(user_id)
        if not subscription:
            raise HTTPException(status_code=404, detail="用户没有订阅")
        delete_query = text("DELETE FROM devices WHERE subscription_id = :subscription_id")
        result = db.execute(delete_query, {"subscription_id": subscription.id})
        subscription_service.sync_current_devices(subscription.id)
        db.commit()
        return ResponseBase(message=f"已清理 {result.rowcount} 个设备")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理设备失败: {str(e)}"
        )
@router.post("/users/{user_id}/reset-subscription", response_model=ResponseBase)
def reset_user_subscription(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.get_by_user_id(user_id)
        if not subscription:
            raise HTTPException(status_code=404, detail="用户没有订阅")
        new_url = generate_subscription_url()
        subscription.subscription_url = new_url
        devices = subscription_service.get_devices_by_subscription_id(subscription.id)
        for device in devices:
            subscription_service.db.delete(device)
        subscription.current_devices = 0
        subscription_service.db.commit()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.email:
                email_service = EmailService(db)
                reset_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                email_service.send_subscription_reset_notification(
                    user_email=user.email,
                    username=user.username,
                    new_subscription_url=new_url,
                    reset_time=reset_time,
                    reset_reason="管理员重置",
                    subscription_id=subscription.id,
                    request=request
                )
                logger.info(f"已发送管理员重置订阅通知邮件到: {user.email}")
        except Exception as e:
            logger.error(f"发送管理员重置订阅通知邮件失败: {e}", exc_info=True)
        return ResponseBase(message="订阅重置成功", data={"new_subscription_url": new_url})
    except HTTPException:
        raise
    except Exception as e:
        return ResponseBase(success=False, message=f"重置订阅失败: {str(e)}")
@router.post("/users/{user_id}/reset-password", response_model=ResponseBase)
def reset_user_password(
    user_id: int,
    password_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        user_service = UserService(db)
        user = user_service.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        new_password = password_data.get("password")
        if not new_password:
            raise HTTPException(status_code=400, detail="新密码不能为空")
        if len(new_password) < 6:
            raise HTTPException(status_code=400, detail="密码长度不能少于6位")
        user.hashed_password = get_password_hash(new_password)
        user_service.db.commit()
        try:
            user_service.log_user_activity(
                user_id=user.id,
                activity_type="admin_password_reset",
                description=f"管理员 {current_admin.username} 重置了用户密码"
            )
        except:
            pass
        return ResponseBase(message="密码重置成功")
    except HTTPException:
        raise
    except Exception as e:
        return ResponseBase(success=False, message=f"密码重置失败: {str(e)}")
@router.put("/users/{user_id}/status", response_model=ResponseBase)
def update_user_status(
    user_id: int,
    status_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        user_service = UserService(db)
        user = user_service.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        new_status = status_data.get("status")
        if new_status not in ["active", "disabled", "inactive"]:
            raise HTTPException(status_code=400, detail="无效的状态值")
        user.is_active = (new_status == "active")
        user_service.db.commit()
        activity = UserActivity(
            user_id=user_id,
            activity_type="status_changed",
            description=f"管理员 {current_admin.username} 将用户状态更改为 {new_status}",
            ip_address="127.0.0.1",
            user_agent="Admin Panel"
        )
        user_service.db.add(activity)
        user_service.db.commit()
        return ResponseBase(success=True, message="用户状态更新成功")
    except Exception as e:
        return ResponseBase(success=False, message=f"状态更新失败: {str(e)}")
@router.post("/users/{user_id}/login-as", response_model=ResponseBase)
def login_as_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        if not current_admin.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        user_service = UserService(db)
        user = user_service.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user.is_admin:
            raise HTTPException(status_code=400, detail="不能以管理员身份登录")
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        token = create_access_token(data={"sub": str(user.id), "user_id": user.id, "login_as": True, "admin_id": current_admin.id}, expires_delta=access_token_expires)
        log_manager.log_admin_action(
            current_admin.id,
            "login_as_user",
            f"管理员 {current_admin.username} 以用户 {user.username} 身份登录",
            db
        )
        return ResponseBase(message="登录成功", data={"token": token, "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin
        }})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"登录失败: {str(e)}")
@router.get("/dashboard", response_model=ResponseBase)
def get_admin_dashboard(
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        user_service = UserService(db)
        subscription_service = SubscriptionService(db)
        order_service = OrderService(db)
        total_users = user_service.count()
        active_users = user_service.count_active_users(30)
        total_subscriptions = subscription_service.count()
        active_subscriptions = subscription_service.count_active()
        total_orders = order_service.count()
        total_revenue = order_service.get_total_revenue()
        return ResponseBase(data={
            "users": total_users,
            "subscriptions": total_subscriptions,
            "revenue": total_revenue
        })
    except Exception as e:
        return ResponseBase(success=False, message=f"获取统计数据失败: {str(e)}")
@router.get("/stats", response_model=ResponseBase)
def get_admin_stats(
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        user_service = UserService(db)
        subscription_service = SubscriptionService(db)
        order_service = OrderService(db)
        total_users = user_service.count()
        active_users = user_service.count_active_users()
        new_today = user_service.count_recent_users(1)
        total_subscriptions = subscription_service.count()
        active_subscriptions = subscription_service.count_active()
        expiring_soon = subscription_service.count_expiring_soon()
        order_stats = order_service.get_order_stats()
        return ResponseBase(data={
            "totalUsers": total_users,
            "activeUsers": active_users,
            "newToday": new_today,
            "totalSubscriptions": total_subscriptions,
            "activeSubscriptions": active_subscriptions,
            "expiringSoon": expiring_soon,
            "totalOrders": order_stats["total_orders"],
            "pendingOrders": order_stats["pending_orders"],
            "paidOrders": order_stats["paid_orders"],
            "totalRevenue": order_stats["total_revenue"],
            "todayOrders": order_stats["today_orders"],
            "todayRevenue": order_stats["today_revenue"]
        })
    except Exception as e:
        return _handle_error(e, "获取统计信息", db)
@router.get("/statistics", response_model=ResponseBase)
def get_statistics(
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        user_service = UserService(db)
        subscription_service = SubscriptionService(db)
        order_service = OrderService(db)
        total_users = user_service.count()
        active_subscriptions = subscription_service.count_active()
        total_orders = order_service.count()
        total_revenue = order_service.get_total_revenue()
        user_stats = [
            {"name": "总用户数", "value": total_users, "percentage": 100},
            {"name": "活跃用户", "value": user_service.count_active_users(30), "percentage": round((user_service.count_active_users(30) / total_users * 100) if total_users > 0 else 0, 1)},
            {"name": "今日新增", "value": user_service.count_recent_users(1), "percentage": round((user_service.count_recent_users(1) / total_users * 100) if total_users > 0 else 0, 1)},
            {"name": "本周新增", "value": user_service.count_recent_users(7), "percentage": round((user_service.count_recent_users(7) / total_users * 100) if total_users > 0 else 0, 1)}
        ]
        total_subscriptions = subscription_service.count()
        subscription_stats = [
            {"name": "总订阅数", "value": total_subscriptions, "percentage": 100},
            {"name": "活跃订阅", "value": active_subscriptions, "percentage": round((active_subscriptions / total_subscriptions * 100) if total_subscriptions > 0 else 0, 1)},
            {"name": "即将过期", "value": subscription_service.count_expiring_soon(), "percentage": round((subscription_service.count_expiring_soon() / total_subscriptions * 100) if total_subscriptions > 0 else 0, 1)},
            {"name": "已过期", "value": total_subscriptions - active_subscriptions, "percentage": round(((total_subscriptions - active_subscriptions) / total_subscriptions * 100) if total_subscriptions > 0 else 0, 1)}
        ]
        recent_orders = order_service.get_recent_orders(7)
        recent_activities = []
        for order in recent_orders[:10]:
            recent_activities.append({
                "id": order.id,
                "type": "订单",
                "description": f"用户 {order.user_id} 创建了订单",
                "amount": order.amount,
                "status": order.status,
                "time": format_beijing_time(order.created_at)
            })
        return ResponseBase(data={
            "overview": {
                "totalUsers": total_users,
                "activeSubscriptions": active_subscriptions,
                "totalOrders": total_orders,
                "totalRevenue": total_revenue
            },
            "userStats": user_stats,
            "subscriptionStats": subscription_stats,
            "recentActivities": recent_activities
        })
    except Exception as e:
        return _handle_error(e, "获取统计数据", db)
@router.get("/users/recent", response_model=ResponseBase)
def get_recent_users(
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        user_service = UserService(db)
        recent_users = user_service.get_recent_users(7)
        users_data = []
        for user in recent_users:
            users_data.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None,
                "status": "active" if user.is_active else "inactive"
            })
        return ResponseBase(data=users_data)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取最近用户失败: {str(e)}")
@router.get("/orders/recent", response_model=ResponseBase)
def get_recent_orders(
    days: int = 7,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        order_service = OrderService(db)
        recent_orders = order_service.get_recent_orders(days=days)
        if limit > 0:
            recent_orders = recent_orders[:limit]
        orders_data = []
        for order in recent_orders:
            order_dict = {
                'id': order.id,
                'order_no': order.order_no,
                'user_id': order.user_id,
                'package_id': order.package_id,
                'amount': float(order.amount),
                'status': order.status,
                'payment_method': order.payment_method_name or '未知',
                'payment_method_name': order.payment_method_name,
                'payment_time': format_beijing_time(order.payment_time) if order.payment_time else None,
                'created_at': format_beijing_time(order.created_at) if order.created_at else None,
                'package_name': order.package.name if order.package else '未知套餐',
                'user': {
                    'id': order.user.id,
                    'username': order.user.username,
                    'email': order.user.email
                } if order.user else None,
                'package': {
                    'id': order.package.id,
                    'name': order.package.name,
                    'price': float(order.package.price)
                } if order.package else None
            }
            orders_data.append(order_dict)
        return ResponseBase(data=orders_data)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取最近订单失败: {str(e)}")
@router.get("/users/abnormal", response_model=ResponseBase)
def get_abnormal_users(
    start_date: str = None,
    end_date: str = None,
    subscription_count: int = None,
    reset_count: int = None,
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
            except ValueError:
                return ResponseBase(success=False, message="日期格式错误，请使用 YYYY-MM-DD 格式")
        else:
            end_dt = datetime.utcnow()
            start_dt = end_dt - timedelta(days=30)
        reset_threshold = reset_count if reset_count else 5
        subscription_threshold = subscription_count if subscription_count else 3
        reset_query = db.query(
            SubscriptionReset.user_id,
            func.count(SubscriptionReset.id).label('reset_count'),
            func.max(SubscriptionReset.created_at).label('last_reset')
        ).filter(
            SubscriptionReset.created_at >= start_dt,
            SubscriptionReset.created_at <= end_dt
        ).group_by(SubscriptionReset.user_id)
        if reset_threshold > 0:
            reset_query = reset_query.having(func.count(SubscriptionReset.id) >= reset_threshold)
        frequent_reset_users = reset_query.all()
        subscription_query = db.query(
            Subscription.user_id,
            func.count(Subscription.id).label('subscription_count'),
            func.max(Subscription.created_at).label('last_subscription')
        ).filter(
            Subscription.created_at >= start_dt,
            Subscription.created_at <= end_dt
        ).group_by(Subscription.user_id)
        if subscription_threshold > 0:
            subscription_query = subscription_query.having(func.count(Subscription.id) >= subscription_threshold)
        frequent_subscription_users = subscription_query.all()
        user_service = UserService(db)
        abnormal_users = []
        for user_id, reset_count, last_reset in frequent_reset_users:
            user = user_service.get(user_id)
            if user:
                abnormal_users.append({
                    "user_id": user_id,
                    "username": user.username,
                    "email": user.email,
                    "abnormal_type": "frequent_reset",
                    "abnormal_count": reset_count,
                    "reset_count": reset_count,
                    "last_activity": last_reset.strftime('%Y-%m-%d %H:%M:%S') if last_reset else None,
                    "description": f"时间段内重置订阅{reset_count}次"
                })
        for user_id, subscription_count, last_subscription in frequent_subscription_users:
            user = user_service.get(user_id)
            if user:
                existing = next((u for u in abnormal_users if u["user_id"] == user_id), None)
                if existing:
                    existing["abnormal_type"] = "multiple_abnormal"
                    existing["subscription_count"] = subscription_count
                    existing["description"] += f"，创建{subscription_count}个订阅"
                else:
                    abnormal_users.append({
                        "user_id": user_id,
                        "username": user.username,
                        "email": user.email,
                        "abnormal_type": "frequent_subscription",
                        "abnormal_count": subscription_count,
                        "subscription_count": subscription_count,
                        "last_activity": last_subscription.strftime('%Y-%m-%d %H:%M:%S') if last_subscription else None,
                        "description": f"时间段内创建{subscription_count}个订阅"
                    })
        abnormal_users.sort(key=lambda x: x["last_activity"], reverse=True)
        return ResponseBase(data=abnormal_users)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取异常用户失败: {str(e)}")
@router.get("/users/{user_id}/details", response_model=ResponseBase)
def get_user_details(
    user_id: int,
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        user_service = UserService(db)
        subscription_service = SubscriptionService(db)
        order_service = OrderService(db)
        user = user_service.get(user_id)
        if not user:
            return ResponseBase(success=False, message="用户不存在")
        subscriptions = subscription_service.get_all_by_user_id(user_id)
        orders, total_orders = order_service.get_user_orders(user_id, skip=0, limit=100)
        recharge_service = RechargeService(db)
        recharges, total_recharges = recharge_service.get_user_recharges(user_id, skip=0, limit=100)
        activities = user_service.get_user_activities(user_id, limit=50)
        login_history = user_service.get_login_history(user_id, limit=20)
        subscription_resets = user_service.get_subscription_resets(user_id, limit=50)
        ua_query = text("""
            SELECT id, user_agent, device_type, device_name, ip_address, os_name, software_name, first_seen, last_access, access_count
            FROM devices
            WHERE user_id = :user_id
            ORDER BY last_access DESC
            LIMIT 20
        """)
        ua_records = db.execute(ua_query, {"user_id": user_id}).fetchall()
        total_resets = len(subscription_resets)
        recent_resets = len([r for r in subscription_resets if r.created_at >= datetime.utcnow() - timedelta(days=30)])
        subscription_list = []
        for sub in subscriptions:
            online_devices = 0
            clash_count = 0
            v2ray_count = 0
            apple_count = 0
            try:
                device_result = db.execute(device_query, {
                    'subscription_id': sub.id
                }).fetchone()
                subscription_count_result = db.execute(subscription_count_query, {
                    'subscription_id': sub.id
                }).fetchone()
                if device_result:
                    # device_query 返回 total_count，表示已订阅设备总数
                    # 已订阅设备数量 = 在线设备数量（都是订阅了该订阅的设备总数）
                    online_devices = device_result.total_count or 0
                else:
                    online_devices = 0
                if subscription_count_result:
                    clash_count = subscription_count_result.clash_count or 0
                    v2ray_count = subscription_count_result.v2ray_count or 0
                    apple_count = v2ray_count
                else:
                    clash_count = 0
                    v2ray_count = 0
                    apple_count = 0
            except Exception as e:
                logger.error(f"获取订阅设备统计失败: {e}", exc_info=True)
            subscription_list.append({
                "id": sub.id,
                "subscription_url": sub.subscription_url,
                "device_limit": sub.device_limit,
                "current_devices": sub.current_devices,
                "is_active": sub.is_active,
                "expire_time": sub.expire_time.strftime('%Y-%m-%d %H:%M:%S') if sub.expire_time and hasattr(sub.expire_time, 'strftime') else (str(sub.expire_time) if sub.expire_time else None),
                "created_at": sub.created_at.strftime('%Y-%m-%d %H:%M:%S') if sub.created_at and hasattr(sub.created_at, 'strftime') else (str(sub.created_at) if sub.created_at else None),
                "online_devices": online_devices,
                "v2ray_count": v2ray_count,
                "clash_count": clash_count,
                "apple_count": apple_count
            })
        user_details = {
            "user_info": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "is_admin": user.is_admin,
                "created_at": user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at and hasattr(user.created_at, 'strftime') else (str(user.created_at) if user.created_at else None),
                "last_login": user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login and hasattr(user.last_login, 'strftime') else (str(user.last_login) if user.last_login else None)
            },
            "subscriptions": subscription_list,
            "orders": [
                {
                    "id": order.id,
                    "order_no": order.order_no,
                    "amount": float(order.amount),
                    "status": order.status,
                    "payment_method": order.payment_method_name,
                    "created_at": order.created_at.strftime('%Y-%m-%d %H:%M:%S') if order.created_at and hasattr(order.created_at, 'strftime') else (str(order.created_at) if order.created_at else None),
                    "paid_at": order.payment_time.strftime('%Y-%m-%d %H:%M:%S') if order.payment_time and hasattr(order.payment_time, 'strftime') else (str(order.payment_time) if order.payment_time else None)
                } for order in orders
            ],
            "recharge_records": [
                {
                    "id": recharge.id,
                    "order_no": recharge.order_no,
                    "amount": float(recharge.amount),
                    "status": recharge.status,
                    "payment_method": recharge.payment_method,
                    "ip_address": recharge.ip_address,
                    "created_at": recharge.created_at.strftime('%Y-%m-%d %H:%M:%S') if recharge.created_at and hasattr(recharge.created_at, 'strftime') else (str(recharge.created_at) if recharge.created_at else None),
                    "paid_at": recharge.paid_at.strftime('%Y-%m-%d %H:%M:%S') if recharge.paid_at and hasattr(recharge.paid_at, 'strftime') else (str(recharge.paid_at) if recharge.paid_at else None)
                } for recharge in recharges
            ],
            "statistics": {
                "total_subscriptions": len(subscriptions),
                "total_orders": total_orders,
                "total_resets": total_resets,
                "recent_resets_30d": recent_resets,
                "total_spent": sum(float(order.amount) for order in orders if order.status == "paid")
            },
            "recent_activities": [
                {
                    "id": activity.id,
                    "activity_type": activity.activity_type,
                    "description": activity.description,
                    "ip_address": activity.ip_address,
                    "created_at": activity.created_at.strftime('%Y-%m-%d %H:%M:%S') if activity.created_at and hasattr(activity.created_at, 'strftime') else (str(activity.created_at) if activity.created_at else None)
                } for activity in activities[:10]
            ],
            "login_history": [
                {
                    "id": login.id,
                    "ip_address": login.ip_address,
                    "location": login.location,
                    "login_status": login.login_status,
                    "login_time": login.login_time.strftime('%Y-%m-%d %H:%M:%S') if login.login_time and hasattr(login.login_time, 'strftime') else (str(login.login_time) if login.login_time else None)
                } for login in login_history[:10]
            ],
            "ua_records": [
                {
                    "id": row.id,
                    "user_agent": row.user_agent,
                    "device_type": row.device_type,
                    "device_name": row.device_name,
                    "ip_address": row.ip_address,
                    "os_name": row.os_name,
                    "software_name": row.software_name,
                    "first_seen": row.first_seen.strftime('%Y-%m-%d %H:%M:%S') if row.first_seen and hasattr(row.first_seen, 'strftime') else (str(row.first_seen) if row.first_seen else None),
                    "last_access": row.last_access.strftime('%Y-%m-%d %H:%M:%S') if row.last_access and hasattr(row.last_access, 'strftime') else (str(row.last_access) if row.last_access else None),
                    "access_count": row.access_count or 0
                } for row in ua_records[:10]
            ],
            "subscription_resets": [
                {
                    "id": reset.id,
                    "reset_type": reset.reset_type,
                    "reason": reset.reason,
                    "device_count_before": reset.device_count_before,
                    "device_count_after": reset.device_count_after,
                    "reset_by": reset.reset_by,
                    "created_at": reset.created_at.strftime('%Y-%m-%d %H:%M:%S') if reset.created_at and hasattr(reset.created_at, 'strftime') else (str(reset.created_at) if reset.created_at else None)
                } for reset in subscription_resets[:10]
            ]
        }
        return ResponseBase(data=user_details)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取用户详情失败: {str(e)}")
@router.get("/orders", response_model=ResponseBase)
def get_orders(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    search: Optional[str] = None,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        order_service = OrderService(db)
        query_params = {
            'skip': skip,
            'limit': limit
        }
        if status:
            query_params['status'] = status
        if search:
            query_params['search'] = search
        orders, total = order_service.get_orders_with_pagination(**query_params)
        orders_data = []
        for order in orders:
            order_dict = {
                'id': order.id,
                'order_no': order.order_no,
                'user_id': order.user_id,
                'package_id': order.package_id,
                'amount': float(order.amount),
                'status': order.status,
                'payment_method': order.payment_method_name or '未知',
                'payment_method_name': order.payment_method_name,
                'payment_time': format_beijing_time(order.payment_time) if order.payment_time else None,
                'created_at': format_beijing_time(order.created_at) if order.created_at else None,
                'updated_at': format_beijing_time(order.updated_at) if order.updated_at else None,
                'package_name': order.package.name if order.package else '未知套餐',
                'user': {
                    'id': order.user.id,
                    'username': order.user.username,
                    'email': order.user.email
                } if order.user else None,
                'package': {
                    'id': order.package.id,
                    'name': order.package.name,
                    'price': float(order.package.price)
                } if order.package else None
            }
            orders_data.append(order_dict)
        return ResponseBase(data={
            "orders": orders_data,
            "total": total,
            "skip": skip,
            "limit": limit
        })
    except Exception as e:
        return ResponseBase(success=False, message=f"获取订单列表失败: {str(e)}")
@router.get("/orders/statistics", response_model=ResponseBase)
def get_orders_statistics(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        order_service = OrderService(db)
        total_orders = order_service.count()
        pending_orders = order_service.count_by_status('pending')
        paid_orders = order_service.count_by_status('paid')
        cancelled_orders = order_service.count_by_status('cancelled')
        total_revenue = order_service.get_total_revenue()
        return ResponseBase(data={
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "paid_orders": paid_orders,
            "cancelled_orders": cancelled_orders,
            "total_revenue": total_revenue
        })
    except Exception as e:
        return ResponseBase(success=False, message=f"获取订单统计失败: {str(e)}")
@router.get("/orders/export")
def export_orders(
    request: Request,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        query = db.query(Order).options(
            joinedload(Order.user),
            joinedload(Order.package)
        )
        if status:
            query = query.filter(Order.status == status)
        if search:
            query = query.filter(
                or_(
                    Order.order_no.like(f"%{search}%"),
                    Order.user.has(User.username.like(f"%{search}%")),
                    Order.user.has(User.email.like(f"%{search}%"))
                )
            )
        orders = query.order_by(Order.created_at.desc()).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            '订单ID', '订单号', '用户ID', '用户名', '用户邮箱',
            '套餐ID', '套餐名称', '套餐价格',
            '订单金额', '支付方式', '订单状态',
            '创建时间', '支付时间', '更新时间'
        ])
        for order in orders:
            username = order.user.username if order.user else "未知"
            email = order.user.email if order.user else "未知"
            package_name = order.package.name if order.package else "未知套餐"
            package_price = float(order.package.price) if order.package and order.package.price else 0.0
            payment_method = order.payment_method_name or "未知"
            status_map = {
                'pending': '待支付',
                'paid': '已支付',
                'cancelled': '已取消',
                'refunded': '已退款',
                'expired': '已过期'
            }
            status_text = status_map.get(order.status, order.status)
            created_at = order.created_at.strftime('%Y-%m-%d %H:%M:%S') if order.created_at else "无"
            payment_time = order.payment_time.strftime('%Y-%m-%d %H:%M:%S') if order.payment_time else "无"
            updated_at = order.updated_at.strftime('%Y-%m-%d %H:%M:%S') if order.updated_at else "无"
            writer.writerow([
                order.id,
                order.order_no,
                order.user_id,
                username,
                email,
                order.package_id if order.package_id else "无",
                package_name,
                package_price,
                float(order.amount),
                payment_method,
                status_text,
                created_at,
                payment_time,
                updated_at
            ])
        csv_content = output.getvalue()
        output.close()
        csv_bytes = ('\ufeff' + csv_content).encode('utf-8-sig')
        filename = f"orders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return FastAPIResponse(
            content=csv_bytes,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        logger.error(f"导出订单数据失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"导出订单数据失败: {str(e)}")
@router.post("/subscriptions/check-expired", response_model=ResponseBase)
def check_expired_subscriptions(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        expired_count = subscription_service.check_expired_subscriptions()
        return ResponseBase(
            message=f"检查完成，处理了 {expired_count} 个过期订阅",
            data={"expired_count": expired_count}
        )
    except Exception as e:
        return ResponseBase(success=False, message=f"检查过期订阅失败: {str(e)}")
@router.get("/users/{user_id}/subscription", response_model=ResponseBase)
def get_user_subscription(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.get_by_user_id(user_id)
        if subscription:
            subscription_info = {
                'id': subscription.id,
                'user_id': subscription.user_id,
                'subscription_url': subscription.subscription_url,
                'device_limit': subscription.device_limit,
                'current_devices': subscription.current_devices,
                'is_active': subscription.is_active,
                'expire_time': format_beijing_time(subscription.expire_time) if subscription.expire_time else None,
                'created_at': format_beijing_time(subscription.created_at) if subscription.created_at else None,
                'updated_at': format_beijing_time(subscription.updated_at) if subscription.updated_at else None
            }
        else:
            subscription_info = None
        return ResponseBase(data=subscription_info)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取用户订阅信息失败: {str(e)}")
@router.put("/orders/{order_id}", response_model=ResponseBase)
def update_order(
    order_id: int,
    order_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        if settings.DEBUG:
            logger.debug(f"更新订单 {order_id}，请求数据: {order_data}")
        
        # 使用ORM方式更新订单，确保数据正确保存到数据库
        order_service = OrderService(db)
        order = order_service.get(order_id)
        if not order:
            logger.warning(f"订单 {order_id} 不存在")
            return ResponseBase(success=False, message="订单不存在")
        
        if settings.DEBUG:
            logger.debug(f"订单 {order_id} 当前状态: {order.status}")
        
        updated = False
        
        if "status" in order_data:
            order.status = order_data["status"]
            updated = True
            logger.info(f"更新订单 {order_id} 的状态为: {order_data['status']}")
            
            if order_data["status"] == "paid":
                order.payment_time = datetime.now(timezone.utc)
                logger.info(f"设置订单 {order_id} 的支付时间: {order.payment_time}")
        
        if "payment_status" in order_data:
            # 注意：Order模型可能没有payment_status字段，需要检查
            if hasattr(order, 'payment_status'):
                order.payment_status = order_data["payment_status"]
                updated = True
        
        if "admin_notes" in order_data:
            if hasattr(order, 'admin_notes'):
                order.admin_notes = order_data["admin_notes"]
                updated = True
        
        if updated:
            order.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(order)
            logger.info(f"订单 {order_id} 更新成功，已提交到数据库")
            
            # 如果订单状态更新为已支付，处理订阅
            if "status" in order_data and order_data["status"] == "paid":
                db.expire_all()
                order = order_service.get(order_id)  # 重新获取订单以确保数据最新
                if order:
                    try:
                        subscription_service = SubscriptionService(db)
                        success = subscription_service.process_paid_order(order)
                        if not success:
                            logger.warning(f"订单 {order_id} 状态已更新为已支付，但处理订阅时出错")
                    except Exception as e:
                        logger.warning(f"处理订阅时发生异常: {e}", exc_info=True)
            
            return ResponseBase(message="订单更新成功")
        else:
            return ResponseBase(message="没有需要更新的字段")
    except Exception as e:
        db.rollback()
        logger.error(f"更新订单 {order_id} 失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"更新订单失败: {str(e)}")
@router.delete("/orders/{order_id}", response_model=ResponseBase)
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        order_service = OrderService(db)
        order = order_service.get(order_id)
        if not order:
            return ResponseBase(success=False, message="订单不存在")
        delete_query = text("DELETE FROM orders WHERE id = :order_id")
        db.execute(delete_query, {"order_id": order_id})
        db.commit()
        return ResponseBase(message="订单删除成功")
    except Exception as e:
        db.rollback()
        return ResponseBase(success=False, message=f"删除订单失败: {str(e)}")
@router.post("/orders/batch-delete", response_model=ResponseBase)
def batch_delete_orders(
    order_ids: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        order_id_list = order_ids.get("order_ids", [])
        if not order_id_list:
            return ResponseBase(success=False, message="请选择要删除的订单")
        delete_query = text("DELETE FROM orders WHERE id = ANY(:order_ids)")
        if hasattr(db.bind.url, 'drivername') and 'sqlite' in db.bind.url.drivername:
            placeholders = ','.join([':id' + str(i) for i in range(len(order_id_list))])
            delete_query = text(f"DELETE FROM orders WHERE id IN ({placeholders})")
            params = {f'id{i}': order_id for i, order_id in enumerate(order_id_list)}
        else:
            params = {"order_ids": order_id_list}
        result = db.execute(delete_query, params)
        db.commit()
        deleted_count = result.rowcount
        return ResponseBase(message=f"成功删除 {deleted_count} 个订单")
    except Exception as e:
        db.rollback()
        return ResponseBase(success=False, message=f"批量删除订单失败: {str(e)}")
@router.get("/notifications", response_model=ResponseBase)
def get_notifications(current_admin = Depends(get_current_admin_user)) -> Any:
    return ResponseBase(data={"notifications": [], "total": 0})
@router.get("/system-config", response_model=ResponseBase)
def get_system_config(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        query = text('SELECT key, value FROM system_configs WHERE type = \'system\'')
        result = db.execute(query)
        system_config = {
            "site_name": "CBoard Modern",
            "site_description": "现代化的代理服务管理平台",
            "logo_url": "",
            "maintenance_mode": False,
            "maintenance_message": "系统维护中，请稍后再试"
        }
        for row in result:
            if row.key in system_config:
                if row.key in ['maintenance_mode']:
                    system_config[row.key] = row.value.lower() == 'true'
                else:
                    system_config[row.key] = row.value
        return ResponseBase(data=system_config)
    except Exception as e:
        logger.error(f"获取系统配置失败: {e}", exc_info=True)
        return ResponseBase(success=False, message=f"获取系统配置失败: {str(e)}")
@router.post("/system-config", response_model=ResponseBase)
def save_system_config(
    config_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        _save_configs_batch(db, config_data, "system", "system")
        db.commit()
        return ResponseBase(message="系统配置保存成功")
    except Exception as e:
        return _handle_error(e, "保存系统配置", db)
@router.get("/email-config", response_model=ResponseBase)
def get_email_config(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        query = text("SELECT key, value FROM system_configs WHERE type = 'email'")
        result = db.execute(query)
        email_config = {
            "smtp_host": "smtp.qq.com",
            "smtp_port": 587,
            "email_username": "",
            "email_password": "",
            "sender_name": "CBoard System",
            "smtp_encryption": "tls",
            "from_email": ""
        }
        for row in result:
            if row.key in email_config:
                if row.key in ['smtp_port']:
                    email_config[row.key] = int(row.value) if row.value.isdigit() else email_config[row.key]
                else:
                    email_config[row.key] = row.value
        return ResponseBase(data=email_config)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取邮件配置失败: {str(e)}")
@router.post("/email-config", response_model=ResponseBase)
def save_email_config(
    config_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        _save_configs_batch(db, config_data, "email", "email")
        db.commit()
        return ResponseBase(message="邮件配置保存成功")
    except Exception as e:
        return _handle_error(e, "保存邮件配置", db)
@router.get("/clash-config", response_model=ResponseBase)
def get_clash_config(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        default_config = ""
        config_content = _get_config_from_db(db, 'clash_config', 'clash', default_config)
        return ResponseBase(data=config_content)
    except Exception as e:
        return _handle_error(e, "获取Clash配置", db)
@router.post("/clash-config", response_model=ResponseBase)
def save_clash_config(
    config_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        config_content = config_data.get("content", "")
        if not config_content:
            return ResponseBase(success=False, message="配置内容不能为空")
        _save_config_to_db(
            db, 'clash_config', 'clash', config_content,
            category='proxy', display_name='Clash配置',
            description='Clash代理配置文件', sort_order=1
        )
        return ResponseBase(message="Clash配置保存成功")
    except Exception as e:
        return _handle_error(e, "保存Clash配置", db)
@router.post("/clash-config-invalid", response_model=ResponseBase)
def save_clash_config_invalid(
    config_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        config_content = config_data.get("content", "")
        if not config_content:
            return ResponseBase(success=False, message="配置内容不能为空")
        _save_config_to_db(
            db, 'clash_config_invalid', 'clash_invalid', config_content,
            category='proxy', display_name='Clash失效配置',
            description='Clash失效代理配置文件', sort_order=3
        )
        return ResponseBase(message="Clash失效配置保存成功")
    except Exception as e:
        return _handle_error(e, "保存Clash失效配置", db)
@router.get("/clash-config-invalid", response_model=ResponseBase)
def get_clash_config_invalid(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        default_config = ""
        config_content = _get_config_from_db(db, 'clash_config_invalid', 'clash_invalid', default_config)
        return ResponseBase(data=config_content)
    except Exception as e:
        return _handle_error(e, "获取Clash失效配置", db)
@router.get("/v2ray-config", response_model=ResponseBase)
def get_v2ray_config(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        default_config = ""
        config_content = _get_config_from_db(db, 'v2ray_config', 'v2ray', default_config)
        return ResponseBase(data=config_content)
    except Exception as e:
        return _handle_error(e, "获取V2Ray配置", db)
@router.post("/v2ray-config", response_model=ResponseBase)
def save_v2ray_config(
    config_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        config_content = config_data.get("content", "")
        if not config_content:
            return ResponseBase(success=False, message="配置内容不能为空")
        _save_config_to_db(
            db, 'v2ray_config', 'v2ray', config_content,
            category='proxy', display_name='V2Ray配置',
            description='V2Ray代理配置文件', sort_order=2
        )
        return ResponseBase(message="V2Ray配置保存成功")
    except Exception as e:
        return _handle_error(e, "保存V2Ray配置", db)
@router.post("/v2ray-config-invalid", response_model=ResponseBase)
def save_v2ray_config_invalid(
    config_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        config_content = config_data.get("content", "")
        if not config_content:
            return ResponseBase(success=False, message="配置内容不能为空")
        _save_config_to_db(
            db, 'v2ray_config_invalid', 'v2ray_invalid', config_content,
            category='proxy', display_name='V2Ray失效配置',
            description='V2Ray失效代理配置文件', sort_order=4
        )
        return ResponseBase(message="V2Ray失效配置保存成功")
    except Exception as e:
        return _handle_error(e, "保存V2Ray失效配置", db)
@router.get("/v2ray-config-invalid", response_model=ResponseBase)
def get_v2ray_config_invalid(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        default_config = ""
        config_content = _get_config_from_db(db, 'v2ray_config_invalid', 'v2ray_invalid', default_config)
        return ResponseBase(data=config_content)
    except Exception as e:
        return _handle_error(e, "获取V2Ray失效配置", db)
@router.get("/export-config", response_model=ResponseBase)
def export_config(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        system_configs = db.query(SystemConfig).all()
        system_config_data = {}
        for config in system_configs:
            system_config_data[config.key] = config.value
        payment_configs = db.query(PaymentConfig).all()
        payment_config_data = {}
        for config in payment_configs:
            payment_config_data[config.pay_type] = {
                "app_id": config.app_id,
                "merchant_private_key": config.merchant_private_key,
                "alipay_public_key": config.alipay_public_key,
                "notify_url": config.notify_url,
                "return_url": config.return_url,
                "debug": config.debug,
                "status": config.status
            }
        software_query = text("SELECT key, value FROM system_configs WHERE type = 'software'")
        software_configs = db.execute(software_query).fetchall()
        software_config_data = {}
        for row in software_configs:
            software_config_data[row.key] = row.value
        email_config_data = {}
        email_keys = ['smtp_host', 'smtp_port', 'email_username', 'email_password',
                     'sender_name', 'smtp_encryption', 'from_email']
        for key in email_keys:
            config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            if config:
                email_config_data[key] = config.value
        clash_config_data = {}
        v2ray_config_data = {}
        clash_config_invalid_data = {}
        v2ray_config_invalid_data = {}
        config_dir = Path("uploads/config")
        clash_config_path = config_dir / "clash.yaml"
        v2ray_config_path = config_dir / "v2ray.json"
        if clash_config_path.exists():
            clash_config_data["content"] = clash_config_path.read_text(encoding='utf-8')
        if v2ray_config_path.exists():
            v2ray_config_data["content"] = v2ray_config_path.read_text(encoding='utf-8')
        default_clash_invalid = ""
        clash_invalid_content = _get_config_from_db(db, 'clash_config_invalid', 'clash_invalid', default_clash_invalid)
        if clash_invalid_content:
            clash_config_invalid_data["content"] = clash_invalid_content
        default_v2ray_invalid = '{"log": {"loglevel": "warning"}, "inbounds": [], "outbounds": [{"protocol": "freedom", "settings": {}}]}'
        v2ray_invalid_content = _get_config_from_db(db, 'v2ray_config_invalid', 'v2ray_invalid', default_v2ray_invalid)
        if v2ray_invalid_content:
            v2ray_config_invalid_data["content"] = v2ray_invalid_content
        config_data = {
            "export_info": {
                "export_time": datetime.now().isoformat(),
                "exported_by": current_admin.username,
                "version": "1.0.0"
            },
            "system_config": system_config_data,
            "email_config": email_config_data,
            "payment_config": payment_config_data,
            "software_config": software_config_data,
            "clash_config": clash_config_data,
            "v2ray_config": v2ray_config_data,
            "clash_config_invalid": clash_config_invalid_data,
            "v2ray_config_invalid": v2ray_config_invalid_data
        }
        return ResponseBase(data=config_data)
    except Exception as e:
        return ResponseBase(success=False, message=f"导出配置失败: {str(e)}")
@router.post("/import-config", response_model=ResponseBase)
def import_config(
    config_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        if not isinstance(config_data, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="配置数据格式错误"
            )
        if "system_config" in config_data:
            system_config_data = config_data["system_config"]
            for key, value in system_config_data.items():
                existing_config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
                if existing_config:
                    existing_config.value = str(value)
                else:
                    new_config = SystemConfig(key=key, value=str(value))
                    db.add(new_config)
        if "email_config" in config_data:
            email_config_data = config_data["email_config"]
            for key, value in email_config_data.items():
                existing_config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
                if existing_config:
                    existing_config.value = str(value)
                else:
                    new_config = SystemConfig(key=key, value=str(value))
                    db.add(new_config)
        if "payment_config" in config_data:
            payment_config_data = config_data["payment_config"]
            for pay_type, config in payment_config_data.items():
                existing_config = db.query(PaymentConfig).filter(PaymentConfig.pay_type == pay_type).first()
                if existing_config:
                    existing_config.app_id = config.get("app_id", "")
                    existing_config.merchant_private_key = config.get("merchant_private_key", "")
                    existing_config.alipay_public_key = config.get("alipay_public_key", "")
                    existing_config.notify_url = config.get("notify_url", "")
                    existing_config.return_url = config.get("return_url", "")
                    existing_config.debug = config.get("debug", False)
                    existing_config.status = config.get("status", 1)
                else:
                    new_config = PaymentConfig(
                        pay_type=pay_type,
                        app_id=config.get("app_id", ""),
                        merchant_private_key=config.get("merchant_private_key", ""),
                        alipay_public_key=config.get("alipay_public_key", ""),
                        notify_url=config.get("notify_url", ""),
                        return_url=config.get("return_url", ""),
                        debug=config.get("debug", False),
                        status=config.get("status", 1)
                    )
                    db.add(new_config)
        if "software_config" in config_data:
            software_config_data = config_data["software_config"]
            current_time = datetime.now()
            for key, value in software_config_data.items():
                check_query = text('SELECT id FROM system_configs WHERE key = :key AND type = \'software\'')
                existing = db.execute(check_query, {"key": key}).first()
                if existing:
                    db.execute(update_query, {
                        "value": str(value),
                        "updated_at": current_time,
                        "key": key
                    })
                else:
                    db.execute(insert_query, {
                        "key": key,
                        "value": str(value),
                        "display_name": key.replace('_', ' ').title(),
                        "description": f"Software configuration for {key}",
                        "created_at": current_time,
                        "updated_at": current_time
                    })
        if "clash_config" in config_data and "content" in config_data["clash_config"]:
            config_dir = Path("uploads/config")
            config_dir.mkdir(parents=True, exist_ok=True)
            clash_config_path = config_dir / "clash.yaml"
            clash_config_path.write_text(config_data["clash_config"]["content"], encoding='utf-8')
        if "v2ray_config" in config_data and "content" in config_data["v2ray_config"]:
            config_dir = Path("uploads/config")
            config_dir.mkdir(parents=True, exist_ok=True)
            v2ray_config_path = config_dir / "v2ray.json"
            v2ray_config_path.write_text(config_data["v2ray_config"]["content"], encoding='utf-8')
        if "clash_config_invalid" in config_data and "content" in config_data["clash_config_invalid"]:
            config_content = config_data["clash_config_invalid"]["content"]
            _save_config_to_db(
                db, 'clash_config_invalid', 'clash_invalid', config_content,
                category='proxy', display_name='Clash失效配置',
                description='Clash失效代理配置文件', sort_order=3
            )
        if "v2ray_config_invalid" in config_data and "content" in config_data["v2ray_config_invalid"]:
            config_content = config_data["v2ray_config_invalid"]["content"]
            _save_config_to_db(
                db, 'v2ray_config_invalid', 'v2ray_invalid', config_content,
                category='proxy', display_name='V2Ray失效配置',
                description='V2Ray失效代理配置文件', sort_order=4
            )
        db.commit()
        return ResponseBase(message="配置导入成功")
    except Exception as e:
        db.rollback()
        return ResponseBase(success=False, message=f"导入配置失败: {str(e)}")
@router.get("/settings", response_model=ResponseBase)
def get_all_settings(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        default_settings = {
            "general": {
                "site_name": "CBoard Modern",
                "site_description": "现代化的代理服务管理平台",
                "site_logo": "",
                "logo_url": "",
                "default_theme": "default"
            },
            "registration": {
                "registration_enabled": True,
                "email_verification_required": True,
                "min_password_length": 8,
                "invite_code_required": False
            },
            "notification": {
                "system_notifications": True,
                "email_notifications": True,
                "subscription_expiry_notifications": True,
                "new_user_notifications": True,
                "new_order_notifications": True
            },
            "security": {
                "login_fail_limit": 5,
                "login_lock_time": 30,
                "session_timeout": 120,
                "device_fingerprint_enabled": True,
                "ip_whitelist_enabled": False,
                "ip_whitelist": ""
            },
            "theme": {
                "default_theme": "light",
                "allow_user_theme": True,
                "available_themes": ["light", "dark", "blue", "green", "purple", "orange", "red", "cyan", "luck", "aurora", "auto"]
            }
        }
        query = text('SELECT key, value, category FROM system_configs')
        result = db.execute(query).fetchall()
        for row in result:
            category = row.category
            key = row.key
            value = row.value
            if value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)
            elif value.startswith('[') and value.endswith(']'):
                try:
                    value = json.loads(value)
                except:
                    value = [v.strip() for v in value.strip('[]').split(',') if v.strip()]
            elif value.startswith('{') and value.endswith('}'):
                try:
                    value = json.loads(value)
                except:
                    pass
            if category == 'system' and key in ['site_name', 'site_description', 'logo_url']:
                if key == 'logo_url':
                    default_settings['general']['site_logo'] = value
                    if 'logo_url' not in default_settings['general']:
                        default_settings['general']['logo_url'] = value
                elif key in default_settings['general']:
                    default_settings['general'][key] = value
            elif category in default_settings:
                if key == 'logo_url' and 'site_logo' in default_settings[category]:
                    default_settings[category]['site_logo'] = value
                    if 'logo_url' not in default_settings[category]:
                        default_settings[category]['logo_url'] = value
                elif key in default_settings[category]:
                    default_settings[category][key] = value
        return ResponseBase(data=default_settings)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取系统设置失败: {str(e)}")
@router.put("/settings/general", response_model=ResponseBase)
def update_general_settings(
    settings: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        current_time = datetime.now()
        for key, value in settings.items():
            db_key = key
            if key == 'site_logo':
                db_key = 'logo_url'
            check_query = text("SELECT id FROM system_configs WHERE key = :key AND (category = 'general' OR category = 'system')")
            existing = db.execute(check_query, {"key": db_key}).first()
            if existing:
                db.execute(update_query, {
                    "value": str(value),
                    "updated_at": current_time,
                    "key": db_key
                })
            else:
                display_name = db_key.replace('_', ' ').title()
                description = f"General setting for {db_key}"
                db.execute(insert_query, {
                    "key": db_key,
                    "value": str(value),
                    "display_name": display_name,
                    "description": description,
                    "created_at": current_time,
                    "updated_at": current_time
                })
        db.commit()
        return ResponseBase(message="基本设置保存成功")
    except Exception as e:
        db.rollback()
        return ResponseBase(success=False, message=f"保存基本设置失败: {str(e)}")
@router.put("/settings/registration", response_model=ResponseBase)
def update_registration_settings(
    settings: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        _save_configs_batch(db, settings, category="registration")
        db.commit()
        return ResponseBase(message="注册设置保存成功")
    except Exception as e:
        db.rollback()
        return ResponseBase(success=False, message=f"保存注册设置失败: {str(e)}")
@router.put("/settings/notification", response_model=ResponseBase)
def update_notification_settings(
    settings: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        _save_configs_batch(db, settings, category="notification")
        db.commit()
        return ResponseBase(message="通知设置保存成功")
    except Exception as e:
        db.rollback()
        return ResponseBase(success=False, message=f"保存通知设置失败: {str(e)}")
@router.put("/settings/security", response_model=ResponseBase)
def update_security_settings(
    settings: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        def process_value(key, value):
            if isinstance(value, list):
                return json.dumps(value)
            elif isinstance(value, str) and key == 'ip_whitelist':
                return value
            return str(value)
        _save_configs_batch(db, settings, category="security", value_processor=process_value)
        db.commit()
        return ResponseBase(message="安全设置保存成功")
    except Exception as e:
        db.rollback()
        return ResponseBase(success=False, message=f"保存安全设置失败: {str(e)}")
@router.put("/settings/theme", response_model=ResponseBase)
def update_theme_settings(
    settings: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        def process_value(key, value):
            return json.dumps(value) if isinstance(value, list) else str(value)
        _save_configs_batch(db, settings, category="theme", value_processor=process_value)
        db.commit()
        return ResponseBase(message="主题设置保存成功")
    except Exception as e:
        db.rollback()
        return ResponseBase(success=False, message=f"保存主题设置失败: {str(e)}")
@router.get("/statistics/user-trend", response_model=ResponseBase)
def get_user_trend_statistics(current_admin = Depends(get_current_admin_user)) -> Any:
    return ResponseBase(data={"labels": ["1月", "2月"], "datasets": [{"label": "新用户", "data": [0, 0]}]})
@router.get("/statistics/revenue-trend", response_model=ResponseBase)
def get_revenue_trend_statistics(current_admin = Depends(get_current_admin_user)) -> Any:
    return ResponseBase(data={"labels": ["1月", "2月"], "datasets": [{"label": "收入", "data": [0, 0]}]})
@router.get("/subscriptions", response_model=ResponseBase)
def get_subscriptions(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str = Query("", description="搜索关键词（QQ、邮箱、订阅地址）"),
    status: str = Query("", description="状态筛选"),
    subscription_type: str = Query("", description="订阅类型筛选"),
    sort: str = Query("add_time_desc", description="排序方式"),
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        user_service = UserService(db)
        skip = (page - 1) * size
        query_params = {}
        if search:
            query_params['search'] = search
        if status:
            query_params['status'] = status
        subscriptions, total = subscription_service.get_subscriptions_with_pagination(
            skip=skip,
            limit=size,
            **query_params
        )
        subscription_list = []
        for subscription in subscriptions:
            device_count = 0
            online_devices = 0
            apple_count = 0
            clash_count = 0
            v2ray_count = 0
            try:
                device_result = db.execute(device_query, {
                    'subscription_id': subscription.id
                }).fetchone()
                subscription_count_result = db.execute(subscription_count_query, {
                    'subscription_id': subscription.id
                }).fetchone()
                if device_result:
                    device_count = device_result.total_count or 0
                    online_devices = device_count
                else:
                    device_count = subscription.current_devices if subscription else 0
                    online_devices = device_count
                if subscription_count_result:
                    clash_count = subscription_count_result.clash_count or 0
                    v2ray_count = subscription_count_result.v2ray_count or 0
                    apple_count = v2ray_count
                else:
                    clash_count = 0
                    v2ray_count = 0
                    apple_count = 0
            except Exception as e:
                logger.error(f"获取订阅设备信息失败: {e}", exc_info=True)
                device_count = subscription.current_devices if subscription else 0
                online_devices = 0
            subscription_status, days_until_expire, is_expired = _calculate_subscription_status(subscription)
            domain_config = get_domain_config()
            base_url = domain_config.get_base_url(request, db)
            timestamp = int(time.time())
            v2ray_url = f"{base_url}/api/v1/subscriptions/ssr/{subscription.subscription_url}?t={timestamp}" if subscription.subscription_url else None
            clash_url = None
            if subscription.subscription_url:
                clash_base_url = f"{base_url}/api/v1/subscriptions/clash/{subscription.subscription_url}?t={timestamp}"
                if subscription.expire_time:
                    expire_time = subscription.expire_time
                    expire_time = _parse_datetime(expire_time) if isinstance(expire_time, str) else expire_time
                    if expire_time and expire_time.tzinfo is None:
                        expire_time = expire_time.replace(tzinfo=timezone.utc)
                    expiry_date = expire_time.strftime('%Y-%m-%d')
                    clash_url = f"{clash_base_url}&expiry={expiry_date}"
                else:
                    clash_url = clash_base_url
            qrcode_url = ""
            if subscription and subscription.subscription_url:
                mobile_url = f"{base_url}/api/v1/subscriptions/ssr/{subscription.subscription_url}?t={timestamp}"
                expire_time = None
                if subscription.expire_time:
                    expire_time = subscription.expire_time
                    expire_time = _parse_datetime(expire_time) if isinstance(expire_time, str) else expire_time
                    if expire_time and expire_time.tzinfo is None:
                        expire_time = expire_time.replace(tzinfo=timezone.utc)
                if expire_time:
                    year = expire_time.year
                    month = str(expire_time.month).zfill(2)
                    day = str(expire_time.day).zfill(2)
                    expiry_display = f"到期时间{year}-{month}-{day}"
                else:
                    expiry_display = subscription.subscription_url
                encoded_url = base64.b64encode(mobile_url.encode()).decode()
                qrcode_url = f"sub://{encoded_url}#{quote(expiry_display)}"
            user_info = None
            if subscription.user:
                user_info = {
                    "id": subscription.user.id,
                    "username": subscription.user.username,
                    "email": subscription.user.email,
                    "created_at": format_beijing_time(subscription.user.created_at) if subscription.user.created_at else None,
                    "last_login": format_beijing_time(subscription.user.last_login) if subscription.user.last_login else None,
                    "is_active": subscription.user.is_active,
                    "is_verified": subscription.user.is_verified,
                    "is_admin": subscription.user.is_admin
                }
            else:
                user = db.query(User).filter(User.id == subscription.user_id).first()
                if user:
                    user_info = {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "created_at": format_beijing_time(user.created_at) if user.created_at else None,
                        "last_login": format_beijing_time(user.last_login) if user.last_login else None,
                        "is_active": user.is_active,
                        "is_verified": user.is_verified,
                        "is_admin": user.is_admin
                    }
                else:
                    user_info = {
                        "id": subscription.user_id,
                        "username": "未知用户",
                        "email": "未知邮箱",
                        "created_at": None,
                        "last_login": None,
                        "is_active": False,
                        "is_verified": False,
                        "is_admin": False
                    }
            subscription_data = {
                "id": subscription.id,
                "user": user_info,
                "subscription_url": subscription.subscription_url,
                "v2ray_url": v2ray_url,
                "clash_url": clash_url,
                "qrcodeUrl": qrcode_url,
                "status": subscription_status,
                "is_active": subscription.is_active,
                "expire_time": format_beijing_time(subscription.expire_time) if subscription.expire_time else None,
                "created_at": format_beijing_time(subscription.created_at) if subscription.created_at else None,
                "device_limit": subscription.device_limit,
                "current_devices": device_count,
                "device_count": device_count,
                "online_devices": online_devices,
                "apple_count": apple_count,
                "clash_count": clash_count,
                "v2ray_count": v2ray_count,
                "days_until_expire": days_until_expire,
                "is_expired": is_expired
            }
            subscription_list.append(subscription_data)
        if sort:
            if sort == "add_time_desc":
                subscription_list.sort(key=lambda x: x["created_at"] or "", reverse=True)
            elif sort == "add_time_asc":
                subscription_list.sort(key=lambda x: x["created_at"] or "")
            elif sort == "expire_time_desc":
                subscription_list.sort(key=lambda x: x["expire_time"] or "", reverse=True)
            elif sort == "expire_time_asc":
                subscription_list.sort(key=lambda x: x["expire_time"] or "")
            elif sort == "device_count_desc":
                subscription_list.sort(key=lambda x: x["current_devices"], reverse=True)
            elif sort == "device_count_asc":
                subscription_list.sort(key=lambda x: x["current_devices"])
            elif sort == "apple_count_desc":
                subscription_list.sort(key=lambda x: x["apple_count"], reverse=True)
            elif sort == "apple_count_asc":
                subscription_list.sort(key=lambda x: x["apple_count"])
            elif sort == "online_devices_desc":
                subscription_list.sort(key=lambda x: x["online_devices"], reverse=True)
            elif sort == "online_devices_asc":
                subscription_list.sort(key=lambda x: x["online_devices"])
            elif sort == "device_limit_desc":
                subscription_list.sort(key=lambda x: x["device_limit"], reverse=True)
            elif sort == "device_limit_asc":
                subscription_list.sort(key=lambda x: x["device_limit"])
        response_data = {
            "subscriptions": subscription_list,
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size
        }
        return ResponseBase(data=response_data)
    except Exception as e:
        logger.error(f"获取订阅列表失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"获取订阅列表失败: {str(e)}")
@router.get("/subscriptions/statistics", response_model=ResponseBase)
def get_subscriptions_statistics(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        stats = subscription_service.get_subscription_stats()
        return ResponseBase(data=stats)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取订阅统计失败: {str(e)}")
@router.post("/subscriptions", response_model=ResponseBase)
def create_subscription(
    subscription_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        user_service = UserService(db)
        user = user_service.get(subscription_data.get("user_id"))
        if not user:
            return ResponseBase(success=False, message="用户不存在")
        existing_subscriptions = subscription_service.get_all_by_user_id(user.id)
        if existing_subscriptions:
            return ResponseBase(success=False, message="用户已有订阅")
        expire_days = subscription_data.get("expire_days", 30)
        expire_time = datetime.now() + timedelta(days=expire_days)
        v2ray_key = secrets.token_urlsafe(16)
        clash_key = secrets.token_urlsafe(16)
        current_time = datetime.now()
        device_limit = subscription_data.get("device_limit", 3)
        is_active = subscription_data.get("is_active", True)
        db.execute(v2ray_insert_query, {
            "user_id": user.id,
            "subscription_url": v2ray_key,
            "device_limit": device_limit,
            "current_devices": 0,
            "is_active": is_active,
            "expire_time": expire_time,
            "created_at": current_time,
            "updated_at": current_time
        })
        db.execute(clash_insert_query, {
            "user_id": user.id,
            "subscription_url": clash_key,
            "device_limit": device_limit,
            "current_devices": 0,
            "is_active": is_active,
            "expire_time": expire_time,
            "created_at": current_time,
            "updated_at": current_time
        })
        db.commit()
        return ResponseBase(message="订阅创建成功", data={
            "v2ray_subscription": v2ray_key,
            "clash_subscription": clash_key
        })
    except Exception as e:
        db.rollback()
        return ResponseBase(success=False, message=f"创建订阅失败: {str(e)}")
@router.put("/subscriptions/{subscription_id}", response_model=ResponseBase)
def update_subscription(
    subscription_id: int,
    subscription_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.get(subscription_id)
        if not subscription:
            return ResponseBase(success=False, message="订阅不存在")
        
        # 使用ORM方式更新，确保数据正确保存到数据库
        updated = False
        
        if "device_limit" in subscription_data:
            subscription.device_limit = subscription_data["device_limit"]
            updated = True
            logger.info(f"更新订阅 {subscription_id} 的设备限制为: {subscription_data['device_limit']}")
        
        if "is_active" in subscription_data:
            subscription.is_active = subscription_data["is_active"]
            updated = True
            logger.info(f"更新订阅 {subscription_id} 的激活状态为: {subscription_data['is_active']}")
        
        if "expire_days" in subscription_data:
            expire_days = subscription_data["expire_days"]
            if expire_days > 0:
                expire_time = datetime.now() + timedelta(days=expire_days)
            else:
                expire_time = None
            subscription.expire_time = expire_time
            updated = True
            logger.info(f"更新订阅 {subscription_id} 的到期时间（通过天数）: {expire_time}")
        
        if "expire_time" in subscription_data:
            try:
                expire_time_str = subscription_data["expire_time"]
                # 处理不同的日期格式
                if 'T' in expire_time_str:
                    expire_time = datetime.fromisoformat(expire_time_str.replace('Z', '+00:00'))
                else:
                    # 处理 YYYY-MM-DD 格式
                    expire_time = datetime.fromisoformat(expire_time_str)
                subscription.expire_time = expire_time
                updated = True
                logger.info(f"更新订阅 {subscription_id} 的到期时间: {expire_time}")
            except ValueError as e:
                logger.error(f"订阅 {subscription_id} 时间格式错误: {expire_time_str}, 错误: {str(e)}")
                return ResponseBase(success=False, message=f"时间格式错误: {str(e)}")
        
        if updated:
            subscription.updated_at = datetime.now()
            db.commit()
            db.refresh(subscription)
            logger.info(f"订阅 {subscription_id} 更新成功，已提交到数据库")
            return ResponseBase(message="订阅更新成功")
        else:
            return ResponseBase(message="没有需要更新的字段")
    except Exception as e:
        db.rollback()
        logger.error(f"更新订阅 {subscription_id} 失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"更新订阅失败: {str(e)}")
@router.get("/subscriptions/{subscription_id}", response_model=ResponseBase)
def get_subscription_detail(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.get(subscription_id)
        if not subscription:
            return ResponseBase(success=False, message="订阅不存在")
        user = subscription.user if hasattr(subscription, 'user') else None
        user_info = {
            "id": user.id,
            "username": user.username,
            "email": user.email
        } if user else {"id": subscription.user_id, "username": "未知用户", "email": "未知邮箱"}
        devices = subscription_service.get_devices_by_subscription_id(subscription_id)
        device_list = []
        for device in devices:
            device_data = {
                "id": device.id,
                "name": device.device_name,
                "type": device.device_type,
                "ip": device.ip_address,
                "user_agent": device.user_agent,
                "last_access": format_beijing_time(device.last_access) if device.last_access else None,
                "is_active": device.is_active,
                "created_at": format_beijing_time(device.created_at) if device.created_at else None
            }
            device_list.append(device_data)
        subscription_data = {
            "id": subscription.id,
            "user": user_info,
            "subscription_url": subscription.subscription_url,
            "device_limit": subscription.device_limit,
            "current_devices": subscription.current_devices,
            "is_active": subscription.is_active,
            "expire_time": format_beijing_time(subscription.expire_time) if subscription.expire_time else None,
            "created_at": format_beijing_time(subscription.created_at) if subscription.created_at else None,
            "updated_at": format_beijing_time(subscription.updated_at) if subscription.updated_at else None,
            "devices": device_list
        }
        return ResponseBase(data=subscription_data)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取订阅详情失败: {str(e)}")
@router.put("/subscriptions/{subscription_id}/reset", response_model=ResponseBase)
def reset_subscription(
    subscription_id: int,
    reason: str = None,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.get(subscription_id)
        if not subscription:
            return ResponseBase(success=False, message="订阅不存在")
        success = subscription_service.reset_subscription(
            subscription_id=subscription_id,
            user_id=subscription.user_id,
            reset_type="admin",
            reason=reason or "管理员重置"
        )
        if success:
            return ResponseBase(message="订阅重置成功")
        else:
            return ResponseBase(success=False, message="订阅重置失败")
    except Exception as e:
        return ResponseBase(success=False, message=f"重置订阅失败: {str(e)}")
@router.post("/subscriptions/user/{user_id}/reset-all", response_model=ResponseBase)
def reset_user_all_subscriptions(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        user_subscriptions = db.query(Subscription).filter(Subscription.user_id == user_id).all()
        if not user_subscriptions:
            return ResponseBase(success=False, message="用户没有订阅")
        success_count = 0
        for subscription in user_subscriptions:
            if subscription.is_active:
                success = subscription_service.reset_subscription(
                    subscription_id=subscription.id,
                    user_id=user_id,
                    reset_type="admin",
                    reason="管理员重置"
                )
                if success:
                    success_count += 1
        if success_count > 0:
            return ResponseBase(message=f"成功重置 {success_count} 个订阅")
        else:
            return ResponseBase(success=False, message="没有找到可重置的活跃订阅")
    except Exception as e:
        return ResponseBase(success=False, message=f"重置订阅失败: {str(e)}")
@router.delete("/subscriptions/{subscription_id}", response_model=ResponseBase)
def delete_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        success = subscription_service.delete(subscription_id)
        if success:
            return ResponseBase(message="订阅删除成功")
        else:
            return ResponseBase(success=False, message="订阅删除失败")
    except Exception as e:
        return ResponseBase(success=False, message=f"删除订阅失败: {str(e)}")
@router.delete("/subscriptions/user/{user_id}/delete-all", response_model=ResponseBase)
def delete_user_all_data(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        user_service = UserService(db)
        user = user_service.get(user_id)
        if not user:
            return ResponseBase(success=False, message="用户不存在")
        if user.is_admin:
            return ResponseBase(success=False, message="不能删除管理员用户")
        success = user_service.delete(user_id)
        if success:
            return ResponseBase(message="用户及其所有数据删除成功")
        else:
            return ResponseBase(success=False, message="删除用户失败")
    except Exception as e:
        return ResponseBase(success=False, message=f"删除用户失败: {str(e)}")
@router.get("/system-settings", response_model=ResponseBase)
def get_system_settings(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        settings_service = SettingsService(db)
        settings = settings_service.get_system_settings()
        return ResponseBase(data=settings.dict())
    except Exception as e:
        return ResponseBase(success=False, message=f"获取系统设置失败: {str(e)}")
@router.put("/system-settings", response_model=ResponseBase)
def update_system_settings(
    settings: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        settings_service = SettingsService(db)
        success = settings_service.update_system_settings(settings)
        if success:
            return ResponseBase(message="系统设置更新成功")
        else:
            return ResponseBase(success=False, message="系统设置更新失败")
    except Exception as e:
        return ResponseBase(success=False, message=f"更新系统设置失败: {str(e)}")
@router.get("/registration-settings", response_model=ResponseBase)
def get_registration_settings(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        settings_service = SettingsService(db)
        reg_config = settings_service.get_registration_config()
        return ResponseBase(data=reg_config)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取注册设置失败: {str(e)}")
@router.put("/registration-settings", response_model=ResponseBase)
def update_registration_settings(
    reg_config: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        settings_service = SettingsService(db)
        success = settings_service.update_registration_config(reg_config)
        if success:
            return ResponseBase(message="注册设置更新成功")
        else:
            return ResponseBase(success=False, message="注册设置更新失败")
    except Exception as e:
        return ResponseBase(success=False, message=f"更新注册设置失败: {str(e)}")
@router.get("/notification-settings", response_model=ResponseBase)
def get_notification_settings(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        settings_service = SettingsService(db)
        notif_config = settings_service.get_notification_config()
        return ResponseBase(data=notif_config)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取通知设置失败: {str(e)}")
@router.put("/notification-settings", response_model=ResponseBase)
def update_notification_settings(
    notif_config: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        settings_service = SettingsService(db)
        success = settings_service.update_notification_config(notif_config)
        if success:
            return ResponseBase(message="通知设置更新成功")
        else:
            return ResponseBase(success=False, message="通知设置更新失败")
    except Exception as e:
        return ResponseBase(success=False, message=f"更新通知设置失败: {str(e)}")
@router.get("/security-settings", response_model=ResponseBase)
def get_security_settings(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        settings_service = SettingsService(db)
        security_config = settings_service.get_security_config()
        return ResponseBase(data=security_config)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取安全设置失败: {str(e)}")
@router.put("/security-settings", response_model=ResponseBase)
def update_security_settings(
    security_config: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        settings_service = SettingsService(db)
        success = settings_service.update_security_config(security_config)
        if success:
            return ResponseBase(message="安全设置更新成功")
        else:
            return ResponseBase(success=False, message="安全设置更新失败")
    except Exception as e:
        return ResponseBase(success=False, message=f"更新安全设置失败: {str(e)}")
@router.get("/configs", response_model=ResponseBase)
def get_configs(
    category: str = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        settings_service = SettingsService(db)
        if category:
            configs = settings_service.get_configs_by_category(category)
        else:
            configs = settings_service.get_all_configs()
        total = len(configs)
        start = (page - 1) * size
        end = start + size
        paginated_configs = configs[start:end]
        config_list = []
        for config in paginated_configs:
            config_data = {
                "key": config.key,
                "value": config.value,
                "type": config.type,
                "category": config.category,
                "display_name": config.display_name,
                "description": config.description,
                "is_public": config.is_public,
                "sort_order": config.sort_order,
                "created_at": format_beijing_time(config.created_at) if config.created_at else None,
                "updated_at": format_beijing_time(config.updated_at) if config.updated_at else None
            }
            config_list.append(config_data)
        return ResponseBase(data={
            "configs": config_list,
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size
        })
    except Exception as e:
        return ResponseBase(success=False, message=f"获取配置列表失败: {str(e)}")
@router.get("/configs/{config_key}", response_model=ResponseBase)
def get_config_detail(
    config_key: str,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        settings_service = SettingsService(db)
        config = settings_service.get_config(config_key)
        if not config:
            return ResponseBase(success=False, message="配置不存在")
        config_data = {
            "key": config.key,
            "value": config.value,
            "type": config.type,
            "category": config.category,
            "display_name": config.display_name,
            "description": config.description,
            "is_public": config.is_public,
            "sort_order": config.sort_order,
            "created_at": format_beijing_time(config.created_at) if config.created_at else None,
            "updated_at": format_beijing_time(config.updated_at) if config.updated_at else None
        }
        return ResponseBase(data=config_data)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取配置详情失败: {str(e)}")
@router.put("/configs/{config_key}", response_model=ResponseBase)
def update_config(
    config_key: str,
    config_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        settings_service = SettingsService(db)
        success = settings_service.set_config_value(
            config_key,
            config_data.get("value"),
            config_data.get("type", "string")
        )
        if success:
            return ResponseBase(message="配置更新成功")
        else:
            return ResponseBase(success=False, message="配置更新失败")
    except Exception as e:
        return ResponseBase(success=False, message=f"更新配置失败: {str(e)}")
@router.get("/email-configs", response_model=ResponseBase)
def get_email_configs(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        settings_service = SettingsService(db)
        email_configs = settings_service.get_configs_by_category('email')
        config_list = []
        for config in email_configs:
            config_data = {
                "key": config.key,
                "value": config.value,
                "type": config.type,
                "display_name": config.display_name,
                "description": config.description,
                "is_public": config.is_public,
                "sort_order": config.sort_order
            }
            config_list.append(config_data)
        return ResponseBase(data={"email_configs": config_list})
    except Exception as e:
        return ResponseBase(success=False, message=f"获取邮件配置失败: {str(e)}")
@router.put("/email-configs", response_model=ResponseBase)
def update_email_configs(
    email_configs: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        settings_service = SettingsService(db)
        success = settings_service.update_smtp_config(email_configs)
        if success:
            return ResponseBase(message="邮件配置更新成功")
        else:
            return ResponseBase(success=False, message="邮件配置更新失败")
    except Exception as e:
        return ResponseBase(success=False, message=f"更新邮件配置失败: {str(e)}")
@router.get("/email-queue", response_model=ResponseBase)
def get_email_queue(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        email_service = EmailQueueProcessor()
        emails = email_service.get_email_queue(page=page, size=size, status=status)
        total = email_service.get_email_queue_count(status=status)
        email_list = []
        for email in emails:
            email_data = {
                "id": email.id,
                "to_email": email.to_email,
                "subject": email.subject,
                "email_type": email.email_type,
                "content_type": email.content_type,
                "status": email.status,
                "retry_count": email.retry_count,
                "max_retries": email.max_retries,
                "created_at": format_beijing_time(email.created_at) if email.created_at else None,
                "sent_at": format_beijing_time(email.sent_at) if email.sent_at else None,
                "error_message": email.error_message
            }
            email_list.append(email_data)
        return ResponseBase(data={
            "emails": email_list,
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size
        })
    except Exception as e:
        return ResponseBase(success=False, message=f"获取邮件队列失败: {str(e)}")
@router.get("/email-queue/statistics", response_model=ResponseBase)
def get_email_queue_statistics(
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        email_service = EmailQueueProcessor()
        stats = email_service.get_queue_stats()
        return ResponseBase(data=stats)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取邮件队列统计失败: {str(e)}")
@router.get("/email-queue/{email_id}", response_model=ResponseBase)
def get_email_detail(
    email_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        email_service = EmailQueueProcessor()
        email = email_service.get_email_by_id(email_id)
        if not email:
            return ResponseBase(success=False, message="邮件不存在")
        email_data = {
            "id": email.id,
            "to_email": email.to_email,
            "subject": email.subject,
            "content": email.content,
            "content_type": email.content_type,
            "email_type": email.email_type,
            "status": email.status,
            "retry_count": email.retry_count,
            "max_retries": email.max_retries,
            "created_at": format_beijing_time(email.created_at) if email.created_at else None,
            "sent_at": format_beijing_time(email.sent_at) if email.sent_at else None,
            "error_message": email.error_message
        }
        return ResponseBase(data=email_data)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取邮件详情失败: {str(e)}")
@router.post("/email-queue/{email_id}/retry", response_model=ResponseBase)
def retry_email(
    email_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        email_service = EmailQueueProcessor()
        success = email_service.retry_email(email_id)
        if success:
            return ResponseBase(message="邮件重试成功")
        else:
            return ResponseBase(success=False, message="邮件重试失败")
    except Exception as e:
        return ResponseBase(success=False, message=f"邮件重试失败: {str(e)}")
@router.delete("/email-queue/{email_id}", response_model=ResponseBase)
def delete_email_from_queue(
    email_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        email_service = EmailQueueProcessor()
        success = email_service.delete_email_from_queue(email_id)
        if success:
            return ResponseBase(message="邮件删除成功")
        else:
            return ResponseBase(success=False, message="邮件删除失败")
    except Exception as e:
        return ResponseBase(success=False, message=f"删除邮件失败: {str(e)}")
@router.post("/email-queue/clear", response_model=ResponseBase)
def clear_email_queue(
    status: str = Query(None),
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        email_service = EmailQueueProcessor()
        success = email_service.clear_email_queue(status=status)
        if success:
            return ResponseBase(message="邮件队列清空成功")
        else:
            return ResponseBase(success=False, message="邮件队列清空失败")
    except Exception as e:
        return ResponseBase(success=False, message=f"清空邮件队列失败: {str(e)}")
@router.post("/email-queue/start", response_model=ResponseBase)
def start_email_queue_processor(
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        processor = get_email_queue_processor()
        processor.start_processing()
        return ResponseBase(success=True, message="邮件队列处理器已启动")
    except Exception as e:
        return ResponseBase(success=False, message=f"启动邮件队列处理器失败: {str(e)}")
@router.post("/email-queue/stop", response_model=ResponseBase)
def stop_email_queue_processor(
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        processor = get_email_queue_processor()
        processor.stop_processing()
        return ResponseBase(success=True, message="邮件队列处理器已停止")
    except Exception as e:
        return ResponseBase(success=False, message=f"停止邮件队列处理器失败: {str(e)}")
@router.post("/email-queue/restart", response_model=ResponseBase)
def restart_email_queue_processor(
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        processor = get_email_queue_processor()
        processor.force_restart()
        return ResponseBase(success=True, message="邮件队列处理器已重启")
    except Exception as e:
        return ResponseBase(success=False, message=f"重启邮件队列处理器失败: {str(e)}")
@router.get("/nodes", response_model=ResponseBase)
def get_nodes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        node_service = NodeService(db)
        skip = (page - 1) * size
        nodes = node_service.get_nodes_with_pagination(skip=skip, limit=size)
        total = node_service.get_total_nodes()
        return ResponseBase(data={
            "nodes": nodes,
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size
        })
    except Exception as e:
        return ResponseBase(success=False, message=f"获取节点列表失败: {str(e)}")
@router.get("/nodes/{node_id}", response_model=ResponseBase)
def get_node_detail(
    node_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        node_service = NodeService(db)
        node = node_service.get_node(node_id)
        if not node:
            return ResponseBase(success=False, message="节点不存在")
        return ResponseBase(data=node)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取节点详情失败: {str(e)}")
@router.post("/nodes", response_model=ResponseBase)
def create_node(
    node_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    # 已废弃：节点现在从文件读取，不支持在数据库中创建
    return ResponseBase(success=False, message="节点管理已改为从文件读取，请通过配置更新功能更新节点")
@router.put("/nodes/{node_id}", response_model=ResponseBase)
def update_node(
    node_id: int,
    node_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    # 已废弃：节点现在从文件读取，不支持在数据库中更新
    return ResponseBase(success=False, message="节点管理已改为从文件读取，请通过配置更新功能更新节点")
@router.delete("/nodes/{node_id}", response_model=ResponseBase)
def delete_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    # 已废弃：节点现在从文件读取，不支持在数据库中删除
    return ResponseBase(success=False, message="节点管理已改为从文件读取，请通过配置更新功能更新节点")
@router.get("/packages", response_model=ResponseBase)
def get_packages(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        package_service = PackageService(db)
        skip = (page - 1) * size
        packages = package_service.get_all_packages(skip=skip, limit=size)
        total = package_service.count()
        package_list = []
        for package in packages:
            package_dict = {
                'id': package.id,
                'name': package.name,
                'description': package.description,
                'price': float(package.price),
                'duration_days': package.duration_days,
                'device_limit': package.device_limit,
                'bandwidth_limit': package.bandwidth_limit,
                'sort_order': package.sort_order,
                'is_active': package.is_active,
                'created_at': format_beijing_time(package.created_at) if package.created_at else None,
                'updated_at': format_beijing_time(package.updated_at) if package.updated_at else None
            }
            package_list.append(package_dict)
        return ResponseBase(data={
            "packages": package_list,
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size
        })
    except Exception as e:
        return ResponseBase(success=False, message=f"获取套餐列表失败: {str(e)}")
@router.post("/packages", response_model=ResponseBase)
def create_package(
    package_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        check_query = text("SELECT id FROM packages WHERE name = :name")
        existing_package = db.execute(check_query, {"name": package_data.get("name")}).first()
        if existing_package:
            return ResponseBase(success=False, message="套餐名称已存在")
        current_time = datetime.now()
        result = db.execute(insert_query, {
            "name": package_data["name"],
            "description": package_data.get("description", ""),
            "price": package_data.get("price", 0),
            "duration_days": package_data.get("duration_days", 30),
            "device_limit": package_data.get("device_limit", 3),
            "bandwidth_limit": package_data.get("bandwidth_limit", 0),
            "sort_order": package_data.get("sort_order", 0),
            "is_active": package_data.get("is_active", True),
            "created_at": current_time,
            "updated_at": current_time
        })
        db.commit()
        package_id = result.lastrowid
        return ResponseBase(message="套餐创建成功", data={"package_id": package_id})
    except Exception as e:
        db.rollback()
        return ResponseBase(success=False, message=f"创建套餐失败: {str(e)}")
@router.put("/packages/{package_id}", response_model=ResponseBase)
def update_package(
    package_id: int,
    package_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        check_query = text("SELECT id FROM packages WHERE id = :package_id")
        existing_package = db.execute(check_query, {"package_id": package_id}).first()
        if not existing_package:
            return ResponseBase(success=False, message="套餐不存在")
        update_fields = []
        update_values = {"package_id": package_id}
        if "name" in package_data:
            update_fields.append("name = :name")
            update_values["name"] = package_data["name"]
        if "description" in package_data:
            update_fields.append("description = :description")
            update_values["description"] = package_data["description"]
        if "price" in package_data:
            update_fields.append("price = :price")
            update_values["price"] = package_data["price"]
        if "duration_days" in package_data:
            update_fields.append("duration_days = :duration_days")
            update_values["duration_days"] = package_data["duration_days"]
        if "device_limit" in package_data:
            update_fields.append("device_limit = :device_limit")
            update_values["device_limit"] = package_data["device_limit"]
        if "bandwidth_limit" in package_data:
            update_fields.append("bandwidth_limit = :bandwidth_limit")
            update_values["bandwidth_limit"] = package_data["bandwidth_limit"]
        if "sort_order" in package_data:
            update_fields.append("sort_order = :sort_order")
            update_values["sort_order"] = package_data["sort_order"]
        if "is_active" in package_data:
            update_fields.append("is_active = :is_active")
            update_values["is_active"] = package_data["is_active"]
        if update_fields:
            update_fields.append("updated_at = :updated_at")
            update_values["updated_at"] = datetime.now()
            db.execute(update_query, update_values)
            db.commit()
            return ResponseBase(message="套餐更新成功")
        else:
            return ResponseBase(message="没有需要更新的字段")
    except Exception as e:
        db.rollback()
        return ResponseBase(success=False, message=f"更新套餐失败: {str(e)}")
@router.delete("/packages/{package_id}", response_model=ResponseBase)
def delete_package(
    package_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        check_query = text("SELECT id FROM packages WHERE id = :package_id")
        existing_package = db.execute(check_query, {"package_id": package_id}).first()
        if not existing_package:
            return ResponseBase(success=False, message="套餐不存在")
        usage_query = text("SELECT id FROM orders WHERE package_id = :package_id LIMIT 1")
        usage_check = db.execute(usage_query, {"package_id": package_id}).first()
        if usage_check:
            return ResponseBase(success=False, message="套餐正在被使用，无法删除")
        delete_query = text("DELETE FROM packages WHERE id = :package_id")
        db.execute(delete_query, {"package_id": package_id})
        db.commit()
        return ResponseBase(message="套餐删除成功")
    except Exception as e:
        db.rollback()
        return ResponseBase(success=False, message=f"删除套餐失败: {str(e)}")
@router.get("/system-logs", response_model=ResponseBase)
def get_system_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    log_type: str = Query(None),
    log_level: str = Query(None),
    start_time: str = Query(None),
    end_time: str = Query(None),
    keyword: str = Query(None),
    module: str = Query(None),
    username: str = Query(None),
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        start_dt = None
        end_dt = None
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            except ValueError:
                pass
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            except ValueError:
                pass
        if keyword:
            logs = log_manager.search_logs(keyword, log_type or "app", start_dt, end_dt)
        else:
            logs = log_manager.get_recent_logs(limit=10000)
        filtered_logs = logs
        if log_level:
            filtered_logs = [log for log in filtered_logs if log.get("level", "").upper() == log_level.upper()]
        if module:
            filtered_logs = [log for log in filtered_logs if module.lower() in log.get("module", "").lower()]
        if username:
            filtered_logs = [log for log in filtered_logs if username.lower() in log.get("username", "").lower()]
        total = len(filtered_logs)
        start_index = (page - 1) * size
        end_index = start_index + size
        paginated_logs = filtered_logs[start_index:end_index]
        return ResponseBase(data={
            "logs": paginated_logs,
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size
        })
    except Exception as e:
        return ResponseBase(success=False, message=f"获取系统日志失败: {str(e)}")
@router.post("/backup", response_model=ResponseBase)
def create_backup(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        return ResponseBase(message="数据备份创建成功")
    except Exception as e:
        return ResponseBase(success=False, message=f"创建数据备份失败: {str(e)}")
@router.get("/backups", response_model=ResponseBase)
def get_backups(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        backups = []
        return ResponseBase(data={"backups": backups})
    except Exception as e:
        return ResponseBase(success=False, message=f"获取备份列表失败: {str(e)}")
@router.post("/maintenance/clear-cache", response_model=ResponseBase)
def clear_cache(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        node_service = NodeService(db)
        node_service.clear_cache()
        node_service.close()
        return ResponseBase(message="系统缓存清理成功（包括节点缓存）")
    except Exception as e:
        return ResponseBase(success=False, message=f"清理系统缓存失败: {str(e)}")
@router.post("/maintenance/optimize-db", response_model=ResponseBase)
def optimize_database(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        return ResponseBase(message="数据库优化完成")
    except Exception as e:
        return ResponseBase(success=False, message=f"数据库优化失败: {str(e)}")
@router.get("/profile", response_model=ResponseBase)
def get_admin_profile(
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        settings_service = SettingsService(db)
        display_name = settings_service.get_config_value(
            f"admin_{current_admin.id}_display_name",
            ""
        )
        avatar_url = settings_service.get_config_value(
            f"admin_{current_admin.id}_avatar_url",
            ""
        )
        phone = settings_service.get_config_value(
            f"admin_{current_admin.id}_phone",
            ""
        )
        bio = settings_service.get_config_value(
            f"admin_{current_admin.id}_bio",
            ""
        )
        if hasattr(current_admin, 'display_name') and current_admin.display_name:
            display_name = current_admin.display_name
        if hasattr(current_admin, 'avatar_url') and current_admin.avatar_url:
            avatar_url = current_admin.avatar_url
        elif hasattr(current_admin, 'avatar') and current_admin.avatar:
            avatar_url = current_admin.avatar
        if hasattr(current_admin, 'phone') and current_admin.phone:
            phone = current_admin.phone
        elif hasattr(current_admin, 'phone_number') and current_admin.phone_number:
            phone = current_admin.phone_number
        if hasattr(current_admin, 'bio') and current_admin.bio:
            bio = current_admin.bio
        profile_data = {
            "username": current_admin.username or '',
            "email": current_admin.email or '',
            "display_name": display_name or '',
            "avatar_url": avatar_url or '',
            "phone": phone or '',
            "bio": bio or '',
            "created_at": format_beijing_time(current_admin.created_at) if current_admin.created_at else None,
            "last_login": format_beijing_time(current_admin.last_login) if hasattr(current_admin, 'last_login') and current_admin.last_login else None
        }
        return ResponseBase(data=profile_data)
    except Exception as e:
        logger.error(f"获取个人资料失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"获取个人资料失败: {str(e)}")
@router.put("/profile", response_model=ResponseBase)
def update_admin_profile(
    profile_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        settings_service = SettingsService(db)
        has_updates = False
        field_mapping = {
            'display_name': f"admin_{current_admin.id}_display_name",
            'avatar_url': f"admin_{current_admin.id}_avatar_url",
            'phone': f"admin_{current_admin.id}_phone",
            'bio': f"admin_{current_admin.id}_bio"
        }
        for field, config_key in field_mapping.items():
            if field in profile_data:
                value = profile_data[field]
                settings_service.set_config_value(
                    config_key,
                    str(value) if value else '',
                    config_type='string'
                )
                has_updates = True
        if hasattr(current_admin, 'display_name') and 'display_name' in profile_data:
            current_admin.display_name = profile_data['display_name']
            has_updates = True
        if hasattr(current_admin, 'avatar_url') and 'avatar_url' in profile_data:
            current_admin.avatar_url = profile_data['avatar_url']
            has_updates = True
        elif hasattr(current_admin, 'avatar') and 'avatar_url' in profile_data:
            current_admin.avatar = profile_data['avatar_url']
            has_updates = True
        if hasattr(current_admin, 'phone') and 'phone' in profile_data:
            current_admin.phone = profile_data['phone']
            has_updates = True
        elif hasattr(current_admin, 'phone_number') and 'phone' in profile_data:
            current_admin.phone_number = profile_data['phone']
            has_updates = True
        if hasattr(current_admin, 'bio') and 'bio' in profile_data:
            current_admin.bio = profile_data['bio']
            has_updates = True
        if has_updates:
            db.commit()
            db.refresh(current_admin)
            return ResponseBase(message="个人资料更新成功")
        else:
            return ResponseBase(message="没有需要更新的数据")
    except Exception as e:
        db.rollback()
        logger.error(f"更新个人资料失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"更新个人资料失败: {str(e)}")
@router.post("/change-password", response_model=ResponseBase)
def change_admin_password(
    password_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        current_password = password_data.get('current_password')
        new_password = password_data.get('new_password')
        if not current_password or not new_password:
            return ResponseBase(success=False, message="请提供当前密码和新密码")
        if not verify_password(current_password, current_admin.hashed_password):
            return ResponseBase(success=False, message="当前密码错误")
        is_valid, message = validate_password_strength(new_password)
        if not is_valid:
            return ResponseBase(success=False, message=f"新密码不符合安全要求: {message}")
        current_admin.hashed_password = get_password_hash(new_password)
        db.commit()
        return ResponseBase(message="密码修改成功")
    except Exception as e:
        db.rollback()
        return ResponseBase(success=False, message=f"修改密码失败: {str(e)}")
@router.get("/login-history", response_model=ResponseBase)
def get_admin_login_history(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        user_service = UserService(db)
        login_history_list = user_service.get_login_history(current_admin.id, limit=size * page)
        skip = (page - 1) * size
        paginated_history = login_history_list[skip:skip + size]
        formatted_history = []
        for login in paginated_history:
            device_info = "未知设备"
            if login.user_agent:
                user_agent = login.user_agent.lower()
                if 'chrome' in user_agent:
                    device_info = "Chrome"
                elif 'firefox' in user_agent:
                    device_info = "Firefox"
                elif 'safari' in user_agent:
                    device_info = "Safari"
                elif 'edge' in user_agent:
                    device_info = "Edge"
                elif 'mobile' in user_agent or 'android' in user_agent:
                    device_info = "移动设备"
            formatted_history.append({
                "id": login.id,
                "login_time": login.login_time.isoformat() if login.login_time else None,
                "ip_address": login.ip_address or "未知",
                "location": login.location or "未知",
                "device": device_info,
                "status": login.login_status or "success"
            })
        total = len(login_history_list)
        pages = (total + size - 1) // size if total > 0 else 1
        return ResponseBase(data={
            "login_history": formatted_history,
            "total": total,
            "page": page,
            "size": size,
            "pages": pages
        })
    except Exception as e:
        logger.error(f"获取登录历史失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"获取登录历史失败: {str(e)}")
@router.get("/security-settings", response_model=ResponseBase)
def get_admin_security_settings(
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        settings_service = SettingsService(db)
        login_notification = settings_service.get_config_value(
            f"admin_{current_admin.id}_login_notification",
            "true"
        )
        notification_email = settings_service.get_config_value(
            f"admin_{current_admin.id}_notification_email",
            ""
        )
        session_timeout = settings_service.get_config_value(
            f"admin_{current_admin.id}_session_timeout",
            "120"
        )
        if isinstance(login_notification, str):
            login_notification = login_notification.lower() in ('true', '1', 'yes', 'on')
        security_settings = {
            "login_notification": login_notification,
            "notification_email": notification_email or '',
            "session_timeout": session_timeout
        }
        return ResponseBase(data=security_settings)
    except Exception as e:
        logger.error(f"获取安全设置失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"获取安全设置失败: {str(e)}")
@router.put("/security-settings", response_model=ResponseBase)
def update_admin_security_settings(
    security_data: dict,
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        allowed_fields = ['login_notification', 'notification_email', 'session_timeout']
        update_data = {}
        for field in allowed_fields:
            if field in security_data:
                update_data[field] = security_data[field]
        if hasattr(current_admin, 'login_notification'):
            for field, value in update_data.items():
                if hasattr(current_admin, field):
                    setattr(current_admin, field, value)
        settings_service = SettingsService(db)
        for key, value in update_data.items():
            settings_key = f"admin_{current_admin.id}_{key}"
            settings_service.set_config_value(
                settings_key,
                str(value),
                config_type='string'
            )
        db.commit()
        return ResponseBase(message="安全设置更新成功")
    except Exception as e:
        db.rollback()
        logger.error(f"更新安全设置失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"更新安全设置失败: {str(e)}")
@router.get("/notification-settings", response_model=ResponseBase)
def get_admin_notification_settings(
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        settings_service = SettingsService(db)
        email_enabled = settings_service.get_config_value(
            f"admin_{current_admin.id}_notification_email_enabled",
            "true"
        )
        system_notification = settings_service.get_config_value(
            f"admin_{current_admin.id}_notification_system_notification",
            "true"
        )
        security_notification = settings_service.get_config_value(
            f"admin_{current_admin.id}_notification_security_notification",
            "true"
        )
        frequency = settings_service.get_config_value(
            f"admin_{current_admin.id}_notification_frequency",
            "realtime"
        )
        if isinstance(email_enabled, str):
            email_enabled = email_enabled.lower() in ('true', '1', 'yes', 'on')
        if isinstance(system_notification, str):
            system_notification = system_notification.lower() in ('true', '1', 'yes', 'on')
        if isinstance(security_notification, str):
            security_notification = security_notification.lower() in ('true', '1', 'yes', 'on')
        notification_settings = {
            "email_enabled": email_enabled,
            "system_notification": system_notification,
            "security_notification": security_notification,
            "frequency": frequency
        }
        return ResponseBase(data=notification_settings)
    except Exception as e:
        logger.error(f"获取通知设置失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"获取通知设置失败: {str(e)}")
@router.put("/notification-settings", response_model=ResponseBase)
def update_admin_notification_settings(
    notification_data: dict,
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        settings_service = SettingsService(db)
        allowed_fields = ['email_enabled', 'system_notification', 'security_notification', 'frequency']
        update_data = {}
        for field in allowed_fields:
            if field in notification_data:
                update_data[field] = notification_data[field]
        for key, value in update_data.items():
            settings_key = f"admin_{current_admin.id}_notification_{key}"
            settings_service.set_config_value(
                settings_key,
                str(value),
                config_type='string' if key != 'frequency' else 'string'
            )
        db.commit()
        return ResponseBase(message="通知设置更新成功")
    except Exception as e:
        db.rollback()
        logger.error(f"更新通知设置失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"更新通知设置失败: {str(e)}")
@router.get("/logs-stats", response_model=ResponseBase)
def get_logs_stats(
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        stats = log_manager.get_log_stats()
        return ResponseBase(data=stats)
    except Exception as e:
        return ResponseBase(success=False, message=f"获取日志统计失败: {str(e)}")
@router.get("/export-logs", response_model=ResponseBase)
def export_logs(
    log_type: str = Query(None),
    log_level: str = Query(None),
    start_time: str = Query(None),
    end_time: str = Query(None),
    keyword: str = Query(None),
    module: str = Query(None),
    username: str = Query(None),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['时间', '级别', '模块', '用户', 'IP地址', '日志内容', '详细信息'])
        logs = log_manager.get_recent_logs(limit=10000)
        for log in logs:
            writer.writerow([
                log.get('timestamp', ''),
                log.get('level', ''),
                log.get('module', ''),
                log.get('username', ''),
                log.get('ip_address', ''),
                log.get('message', ''),
                log.get('details', '')
            ])
        csv_content = output.getvalue()
        output.close()
        return ResponseBase(data=csv_content, message="日志导出成功")
    except Exception as e:
        return ResponseBase(success=False, message=f"导出日志失败: {str(e)}")
@router.post("/clear-logs", response_model=ResponseBase)
def clear_logs(
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        result = log_manager.cleanup_old_logs(0)
        if result["success"]:
            return ResponseBase(
                data=result,
                message=f"日志清理成功，删除了 {result['deleted_count']} 个日志文件"
            )
        else:
            return ResponseBase(success=False, message=f"清理失败: {result.get('error', '未知错误')}")
    except Exception as e:
        return ResponseBase(success=False, message=f"清理日志失败: {str(e)}")
@router.delete("/subscriptions/{subscription_id}/devices/{device_id}", response_model=ResponseBase)
def remove_device(
    subscription_id: int,
    device_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        success = subscription_service.remove_device(device_id)
        if success:
            return ResponseBase(message="设备删除成功")
        else:
            return ResponseBase(success=False, message="设备删除失败")
    except Exception as e:
        return ResponseBase(success=False, message=f"删除设备失败: {str(e)}")
@router.delete("/subscriptions/{subscription_id}/devices", response_model=ResponseBase)
def clear_all_devices(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        success = subscription_service.delete_devices_by_subscription_id(subscription_id)
        if success:
            return ResponseBase(message="所有设备已清空")
        else:
            return ResponseBase(success=False, message="清空设备失败")
    except Exception as e:
        return ResponseBase(success=False, message=f"清空设备失败: {str(e)}")
@router.get("/subscriptions/{subscription_id}/devices", response_model=ResponseBase)
def get_subscription_devices(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        devices = db.execute(device_query, {'subscription_id': subscription_id}).fetchall()
        def infer_os_from_software(software_name: str) -> str:
            if not software_name or software_name == 'Unknown':
                return None
            software_lower = software_name.lower()
            ios_software = ['shadowrocket', 'quantumult', 'quantumult x', 'surge', 'loon',
                           'potatso', 'kitsunebi', 'pharos', 'anx', 'anxray']
            if any(keyword in software_lower for keyword in ios_software):
                return 'iOS'
            android_software = ['v2rayng', 'clash for android', 'clashandroid', 'surfboard',
                               'shadowsocks', 'shadowsocksr', 'ssr', 'ssrr']
            if any(keyword in software_lower for keyword in android_software):
                return 'Android'
            windows_software = ['clash for windows', 'clash-verge', 'clash verge', 'v2rayn',
                               'qv2ray', 'v2rayw', 'shadowsocks-windows']
            if any(keyword in software_lower for keyword in windows_software):
                return 'Windows'
            macos_software = ['clashx', 'clashx pro', 'surge', 'v2rayu', 'v2rayx',
                            'shadowsocksx', 'shadowsocksx-ng', 'clash for mac']
            if any(keyword in software_lower for keyword in macos_software):
                return 'macOS'
            return None
        device_list = []
        for device in devices:
            os_name = device.os_name or "-"
            if (os_name == "Unknown" or os_name == "-" or not os_name) and device.software_name:
                inferred_os = infer_os_from_software(device.software_name)
                if inferred_os:
                    os_name = inferred_os
            device_data = {
                "id": device.id,
                "device_name": device.device_name or "未知设备",
                "name": device.device_name or "未知设备",
                "device_type": device.device_type or "unknown",
                "type": device.device_type or "unknown",
                "ip_address": device.ip_address or "-",
                "ip": device.ip_address or "-",
                "user_agent": device.user_agent or "",
                "software_name": device.software_name or "",
                "software_version": device.software_version or "",
                "os_name": os_name,
                "os_version": device.os_version or "",
                "device_model": device.device_model or "",
                "device_brand": device.device_brand or "",
                "is_allowed": bool(device.is_allowed),
                "is_active": bool(device.is_active),
                "first_seen": _format_date(device.first_seen),
                "last_seen": _format_date(device.last_seen),
                "last_access": _format_date(device.last_access),
                "access_count": device.access_count or 0,
                "created_at": _format_date(device.created_at),
                "updated_at": _format_date(device.updated_at)
            }
            device_list.append(device_data)
        logger.info(f"获取订阅 {subscription_id} 的设备列表，共 {len(device_list)} 个设备")
        return ResponseBase(
            data={
                "devices": device_list,
                "total": len(device_list)
            },
            success=True,
            message="获取设备列表成功"
        )
    except Exception as e:
        logger.error(f"获取订阅设备列表失败: {e}", exc_info=True)
        return ResponseBase(
            success=False,
            message=f"获取设备列表失败: {str(e)}",
            data={"devices": [], "total": 0}
        )
@router.post("/subscriptions/batch-clear-devices", response_model=ResponseBase)
def batch_clear_devices(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        all_subscriptions = subscription_service.get_all()
        cleared_count = 0
        for subscription in all_subscriptions:
            subscription_service.clear_devices(subscription.id)
            subscription.current_devices = 0
            cleared_count += 1
        db.commit()
        return ResponseBase(message=f"成功清理 {cleared_count} 个用户的设备")
    except Exception as e:
        db.rollback()
        return ResponseBase(success=False, message=f"批量清理设备失败: {str(e)}")
@router.post("/subscriptions/{subscription_id}/send-email", response_model=ResponseBase)
def send_subscription_email(
    subscription_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.get(subscription_id)
        if not subscription:
            raise HTTPException(status_code=404, detail="订阅不存在")
        email_service = EmailService(db)
        if not email_service.is_email_enabled():
            return ResponseBase(success=False, message="邮件服务未启用，请检查SMTP配置")
        success = subscription_service.send_subscription_email(subscription.user_id, request=request)
        if success:
            return ResponseBase(message="订阅邮件已加入发送队列，将在后台处理")
        else:
            return ResponseBase(success=False, message="创建邮件队列失败")
    except HTTPException:
        raise
    except Exception as e:
        return ResponseBase(success=False, message=f"创建邮件队列失败: {str(e)}")
@router.post("/subscriptions/user/{user_id}/send-email", response_model=ResponseBase)
def send_subscription_email_by_user_id(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        email_service = EmailService(db)
        if not email_service.is_email_enabled():
            return ResponseBase(success=False, message="邮件服务未启用，请检查SMTP配置")
        success = subscription_service.send_subscription_email(user_id, request=request)
        if success:
            return ResponseBase(message="订阅邮件已加入发送队列，将在后台处理")
        else:
            return ResponseBase(success=False, message="创建邮件队列失败")
    except Exception as e:
        return ResponseBase(success=False, message=f"创建邮件队列失败: {str(e)}")
@router.get("/subscriptions/export")
def export_subscriptions(
    request: Request,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscriptions = db.query(Subscription).options(joinedload(Subscription.user)).all()
        domain_config = get_domain_config()
        base_url = domain_config.get_base_url(request, db).rstrip('/')
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            '用户ID', '用户名', '邮箱', '订阅密钥',
            '通用配置地址', 'Clash配置地址',
            '设备限制', '当前设备', '状态',
            '到期时间', '创建时间'
        ])
        for subscription in subscriptions:
            username = subscription.user.username if subscription.user else "未知"
            email = subscription.user.email if subscription.user else "未知"
            subscription_url = subscription.subscription_url or ""
            timestamp = int(time.time())
            ssr_url = f"{base_url}/api/v1/subscriptions/ssr/{subscription_url}?t={timestamp}" if subscription_url else ""
            clash_url = f"{base_url}/api/v1/subscriptions/clash/{subscription_url}?t={timestamp}" if subscription_url else ""
            status = "活跃" if subscription.is_active else "暂停"
            expire_time = subscription.expire_time.strftime('%Y-%m-%d %H:%M:%S') if subscription.expire_time else "无"
            created_at = subscription.created_at.strftime('%Y-%m-%d %H:%M:%S') if subscription.created_at else "无"
            writer.writerow([
                subscription.user_id,
                username,
                email,
                subscription_url,
                ssr_url,
                clash_url,
                subscription.device_limit,
                getattr(subscription, 'current_devices', 0),
                status,
                expire_time,
                created_at
            ])
        csv_content = output.getvalue()
        output.close()
        csv_bytes = ('\ufeff' + csv_content).encode('utf-8-sig')
        filename = f"subscriptions_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return FastAPIResponse(
            content=csv_bytes,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        logger.error(f"导出订阅数据失败: {str(e)}", exc_info=True)
        return ResponseBase(success=False, message=f"导出订阅数据失败: {str(e)}")
@router.get("/subscriptions/stats/apple", response_model=ResponseBase)
def get_apple_stats(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        result = db.execute(apple_query).fetchone()
        total_devices = result.total_count or 0
        apple_count = result.apple_count or 0
        return ResponseBase(data={
            "apple_devices": apple_count,
            "total_devices": total_devices,
            "apple_percentage": (apple_count / total_devices * 100) if total_devices > 0 else 0
        })
    except Exception as e:
        return ResponseBase(success=False, message=f"获取苹果设备统计失败: {str(e)}")
@router.get("/subscriptions/stats/online", response_model=ResponseBase)
def get_online_stats(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        subscription_service = SubscriptionService(db)
        result = db.execute(online_query).fetchone()
        total_devices = result.total_count or 0
        online_count = result.online_count or 0
        return ResponseBase(data={
            "online_devices": online_count,
            "total_devices": total_devices,
            "online_percentage": (online_count / total_devices * 100) if total_devices > 0 else 0
        })
    except Exception as e:
        return ResponseBase(success=False, message=f"获取在线设备统计失败: {str(e)}")
@router.post("/clash-config/regenerate", response_model=ResponseBase)
def regenerate_clash_config(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    try:
        service = ConfigUpdateService(db)
        if service.is_running():
            return ResponseBase(success=False, message="配置更新任务已在运行中")
        background_tasks.add_task(service.run_update_task)
        return ResponseBase(message="Clash配置重新生成任务已启动")
    except Exception as e:
        return ResponseBase(
            success=False,
            message=f"重新生成Clash配置失败: {str(e)}"
        )