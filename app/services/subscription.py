"""订阅服务"""
import base64
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple

import yaml
from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from app.models.subscription import Device, Subscription
from app.models.user import User
from app.models.user_activity import SubscriptionReset
from app.schemas.subscription import SubscriptionCreate
from app.utils.security import generate_subscription_url

logger = logging.getLogger(__name__)


class SubscriptionService:
    """订阅服务类"""

    def __init__(self, db: Session):
        self.db = db

    def _get_config_from_db(self, key: str, config_type: str) -> Optional[str]:
        try:
            query = text(f'SELECT value FROM system_configs WHERE "key" = :key AND type = :type')
            result = self.db.execute(query, {'key': key, 'type': config_type}).first()
            return result.value if result else None
        except Exception as e:
            logger.warning(f"获取配置失败 ({key}, {config_type}): {e}")
            return None

    def _calculate_remaining_days(self, expire_time: Optional[datetime]) -> int:
        if not expire_time:
            return 0
        now = datetime.now(timezone.utc)
        if expire_time.tzinfo is None:
            expire_time = expire_time.replace(tzinfo=timezone.utc)
        if expire_time > now:
            return (expire_time - now).days
        return 0

    def _get_base_url_for_email(self) -> str:
        from app.core.domain_config import get_domain_config
        domain_config = get_domain_config()
        return domain_config.get_email_base_url(None, self.db).rstrip('/')

    def _ensure_timezone(self, dt: datetime) -> datetime:
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def _sync_device_count(self, subscription_id: int):
        try:
            actual_count = self.db.query(Device).filter(
                Device.subscription_id == subscription_id,
                Device.is_active == True
            ).count()
            subscription = self.get(subscription_id)
            if subscription:
                subscription.current_devices = actual_count
                self.db.commit()
        except Exception as e:
            logger.warning(f"同步设备数量失败: {e}")

    def _get_project_root(self) -> Path:
        return Path(__file__).parent.parent.parent.parent.resolve()

    def _get_config_file_path(self, file_key: str, default_file: str) -> str:
        project_root = self._get_project_root()
        try:
            from app.services.config_update_service import ConfigUpdateService
            config_service = ConfigUpdateService(self.db)
            config = config_service.get_config()
            target_dir = config.get("target_dir", "./uploads/config")
            target_file = config.get(file_key, default_file)
            if os.path.isabs(target_dir):
                return os.path.join(target_dir, target_file)
            return str((project_root / target_dir / target_file).resolve())
        except Exception as e:
            logger.warning(f"获取配置路径失败，使用默认路径: {e}")
            return str((project_root / "uploads" / "config" / default_file).resolve())

    def _read_config_file(self, file_path: str, config_key: str, config_type: str, default_msg: str) -> str:
        # 优先从数据库读取
        config = self._get_config_from_db(config_key, config_type)
        if config:
            logger.info(f"✅ 从数据库读取配置: {config_key}")
            return config
        # 降级：从文件读取
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content and content.strip():
                        logger.info(f"✅ 从文件读取配置: {file_path}")
                        return content
            except Exception as e:
                logger.warning(f"读取配置文件失败 {file_path}: {e}")
        else:
            logger.warning(f"配置文件不存在: {file_path}")
        return default_msg

    def get(self, subscription_id: int) -> Optional[Subscription]:
        return self.db.query(Subscription).filter(Subscription.id == subscription_id).first()

    def get_by_user_id(self, user_id: int) -> Optional[Subscription]:
        return self.db.query(Subscription).filter(Subscription.user_id == user_id).first()

    def get_all_by_user_id(self, user_id: int, limit: int = 10) -> List[Subscription]:
        return self.db.query(Subscription).filter(Subscription.user_id == user_id).order_by(Subscription.created_at.desc()).limit(limit).all()

    def create(self, subscription_in: SubscriptionCreate) -> Subscription:
        subscription = Subscription(
            user_id=subscription_in.user_id,
            subscription_url=generate_subscription_url(),
            device_limit=subscription_in.device_limit,
            expire_time=subscription_in.expire_time,
            is_active=True,
            current_devices=0
        )
        self.db.add(subscription)
        self.db.flush()
        self.db.refresh(subscription)
        return subscription

    def update_subscription_key(self, subscription_id: int, new_key: str = None) -> bool:
        subscription = self.get(subscription_id)
        if not subscription:
            return False
        subscription.subscription_url = new_key or generate_subscription_url()
        self.db.commit()
        return True

    def delete(self, subscription_id: int) -> bool:
        subscription = self.get(subscription_id)
        if not subscription:
            return False
        self.db.delete(subscription)
        self.db.commit()
        return True

    def get_devices_by_subscription_id(self, subscription_id: int) -> List[Device]:
        return self.db.query(Device).filter(Device.subscription_id == subscription_id).all()

    def get_device(self, device_id: int) -> Optional[Device]:
        return self.db.query(Device).filter(Device.id == device_id).first()

    def delete_device(self, device_id: int) -> bool:
        device = self.get_device(device_id)
        if not device:
            return False
        subscription_id = device.subscription_id
        try:
            self.db.delete(device)
            self.db.commit()
            self._sync_device_count(subscription_id)
            return True
        except Exception as e:
            logger.error(f"删除设备失败: {e}", exc_info=True)
            self.db.rollback()
            return False

    def delete_devices_by_subscription_id(self, subscription_id: int) -> bool:
        devices = self.get_devices_by_subscription_id(subscription_id)
        for device in devices:
            self.db.delete(device)
        self.db.commit()
        subscription = self.get(subscription_id)
        if subscription:
            subscription.current_devices = 0
            self.db.commit()
        return True

    def get_active_subscriptions(self, limit: int = 1000) -> List[Subscription]:
        """获取有效订阅（限制数量避免内存溢出）"""
        now = datetime.now(timezone.utc)
        return self.db.query(Subscription).filter(
            or_(Subscription.expire_time.is_(None), Subscription.expire_time > now)
        ).limit(limit).all()

    def get_expired_subscriptions(self, limit: int = 1000) -> List[Subscription]:
        """获取过期的订阅（限制数量避免内存溢出）"""
        now = datetime.now(timezone.utc)
        return self.db.query(Subscription).filter(
            and_(Subscription.expire_time.isnot(None), Subscription.expire_time <= now)
        ).limit(limit).all()

    def get_subscription_stats(self) -> dict:
        """获取订阅统计（使用count避免加载所有数据）"""
        from sqlalchemy import func
        now = datetime.now(timezone.utc)
        total = self.db.query(Subscription).count()
        active = self.db.query(func.count(Subscription.id)).filter(
            or_(Subscription.expire_time.is_(None), Subscription.expire_time > now)
        ).scalar() or 0
        expired = self.count_expired()
        return {
            "total": total,
            "active": active,
            "expired": expired,
            "active_rate": (active / total * 100) if total > 0 else 0
        }

    def get_subscriptions_with_pagination(self, skip: int = 0, limit: int = 20, search: str = None, status: str = None) -> Tuple[List[Subscription], int]:
        from sqlalchemy.orm import joinedload
        query = self.db.query(Subscription).join(User, Subscription.user_id == User.id).options(joinedload(Subscription.user))
        if not status or status == 'active':
            query = query.filter(Subscription.is_active == True)
        elif status == 'inactive':
            query = query.filter(Subscription.is_active == False)
        elif status == 'expired':
            query = query.filter(Subscription.expire_time < datetime.now(timezone.utc))
        if search:
            query = query.filter(or_(
                User.username.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                Subscription.subscription_url.ilike(f'%{search}%')
            ))
        total = query.count()
        return query.offset(skip).limit(limit).all(), total

    def reset_subscription(self, subscription_id: int, user_id: int, reset_type: str = "manual", reason: str = None) -> bool:
        subscription = self.get(subscription_id)
        if not subscription:
            return False
        old_subscription_url = subscription.subscription_url
        device_count_before = self.db.query(Device).filter(Device.subscription_id == subscription_id).count()
        new_key = generate_subscription_url()
        subscription.subscription_url = new_key
        self.delete_devices_by_subscription_id(subscription_id)
        subscription.current_devices = 0
        self.db.commit()
        reset_record = SubscriptionReset(
            user_id=user_id,
            subscription_id=subscription_id,
            reset_type=reset_type,
            reason=reason,
            old_subscription_url=old_subscription_url,
            new_subscription_url=new_key,
            device_count_before=device_count_before,
            device_count_after=0,
            reset_by="user"
        )
        self.db.add(reset_record)
        self.db.commit()
        try:
            from app.services.email import EmailService
            user = self.db.query(User).filter(User.id == user_id).first()
            if user and user.email:
                email_service = EmailService(self.db)
                from app.utils.timezone import get_beijing_time_str
                email_service.send_subscription_reset_notification(
                    user_email=user.email,
                    username=user.username,
                    new_subscription_url=new_key,
                    reset_time=get_beijing_time_str('%Y-%m-%d %H:%M:%S'),
                    reset_reason=reason or "订阅重置",
                    subscription_id=subscription_id,
                    request=None
                )
                logger.info(f"已发送订阅重置通知邮件到: {user.email}")
        except Exception as e:
            logger.error(f"发送订阅重置通知邮件失败: {e}", exc_info=True)
        return True

    def generate_ssr_subscription(self, subscription: Subscription) -> str:
        # 优先从数据库获取节点
        config_str = self._get_config_from_db('v2ray_config', 'v2ray')
        if config_str:
            try:
                # 如果是base64编码，解码后返回
                decoded = base64.b64decode(config_str).decode('utf-8')
                logger.info(f"✅ 从数据库读取SSR订阅")
                return decoded
            except:
                # 如果不是base64，直接返回
                logger.info(f"✅ 从数据库读取SSR订阅（非base64）")
                return config_str
        # 降级：从文件获取节点
        v2ray_path = self._get_config_file_path('v2ray_file', 'xr')
        if os.path.exists(v2ray_path):
            try:
                with open(v2ray_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        try:
                            decoded = base64.b64decode(content).decode('utf-8')
                            logger.info(f"✅ 从文件读取SSR订阅: {v2ray_path}")
                            return decoded
                        except:
                            logger.info(f"✅ 从文件读取SSR订阅（非base64）: {v2ray_path}")
                            return content
            except Exception as e:
                logger.warning(f"读取V2Ray配置文件失败 {v2ray_path}: {e}")
        return "# 暂无可用节点"

    def generate_clash_subscription(self, subscription: Subscription) -> dict:
        # 优先从数据库获取Clash配置
        config_str = self._get_config_from_db('clash_config', 'clash')
        if config_str:
            try:
                config = yaml.safe_load(config_str)
                if config and isinstance(config, dict) and 'proxies' in config:
                    logger.info(f"✅ 从数据库读取Clash订阅，包含 {len(config.get('proxies', []))} 个节点")
                    # 确保proxy-groups中的节点引用正确
                    if "proxy-groups" in config and isinstance(config["proxy-groups"], list):
                        proxy_names = [p.get('name') for p in config.get('proxies', []) if p.get('name')]
                        for group in config["proxy-groups"]:
                            if isinstance(group, dict) and group.get("type") == "select":
                                existing_proxies = group.get("proxies", [])
                                special_items = [p for p in existing_proxies if p in ['DIRECT', 'REJECT', '♻️ 自动选择', '🚀 节点选择', '🎯 全球直连', '🛑 全球拦截', '🐟 漏网之鱼']]
                                group["proxies"] = special_items + proxy_names
                    return config
            except Exception as e:
                logger.warning(f"解析数据库Clash配置失败: {e}")
        # 降级：从文件获取Clash配置
        clash_path = self._get_config_file_path('clash_file', 'clash.yaml')
        if os.path.exists(clash_path):
            try:
                with open(clash_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config and isinstance(config, dict) and 'proxies' in config:
                        logger.info(f"✅ 从文件读取Clash订阅: {clash_path}，包含 {len(config.get('proxies', []))} 个节点")
                        if "proxy-groups" in config and isinstance(config["proxy-groups"], list):
                            proxy_names = [p.get('name') for p in config.get('proxies', []) if p.get('name')]
                            for group in config["proxy-groups"]:
                                if isinstance(group, dict) and group.get("type") == "select":
                                    existing_proxies = group.get("proxies", [])
                                    special_items = [p for p in existing_proxies if p in ['DIRECT', 'REJECT', '♻️ 自动选择', '🚀 节点选择', '🎯 全球直连', '🛑 全球拦截', '🐟 漏网之鱼']]
                                    group["proxies"] = special_items + proxy_names
                        return config
            except Exception as e:
                logger.warning(f"读取Clash配置文件失败 {clash_path}: {e}")
        return {"error": "暂无可用节点"}


    def count(self) -> int:
        return self.db.query(Subscription).count()

    def count_active(self) -> int:
        return self.db.query(Subscription).filter(Subscription.is_active == True).count()

    def count_expiring_soon(self, days: int = 7) -> int:
        cutoff_date = datetime.now(timezone.utc) + timedelta(days=days)
        return self.db.query(Subscription).filter(
            and_(
                Subscription.is_active == True,
                Subscription.expire_time <= cutoff_date,
                Subscription.expire_time > datetime.now(timezone.utc)
            )
        ).count()

    def generate_v2ray_subscription(self, subscription: Subscription) -> dict:
        # 优先从数据库获取V2Ray配置
        config_str = self._get_config_from_db('v2ray_config', 'v2ray')
        if config_str:
            try:
                # 如果是base64编码，解码后解析
                try:
                    decoded = base64.b64decode(config_str).decode('utf-8')
                    # 尝试解析为JSON
                    try:
                        config = json.loads(decoded)
                        logger.info(f"✅ 从数据库读取V2Ray订阅（JSON）")
                        return config
                    except:
                        # 如果不是JSON，返回原始内容（可能是订阅链接列表）
                        logger.info(f"✅ 从数据库读取V2Ray订阅（文本）")
                        return {"content": decoded}
                except:
                    # 如果不是base64，直接返回
                    logger.info(f"✅ 从数据库读取V2Ray订阅（原始）")
                    return {"content": config_str}
            except Exception as e:
                logger.warning(f"解析数据库V2Ray配置失败: {e}")
        # 降级：从文件获取V2Ray配置
        v2ray_path = self._get_config_file_path('v2ray_file', 'xr')
        if os.path.exists(v2ray_path):
            try:
                with open(v2ray_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        try:
                            decoded = base64.b64decode(content).decode('utf-8')
                            try:
                                config = json.loads(decoded)
                                logger.info(f"✅ 从文件读取V2Ray订阅（JSON）: {v2ray_path}")
                                return config
                            except:
                                logger.info(f"✅ 从文件读取V2Ray订阅（文本）: {v2ray_path}")
                                return {"content": decoded}
                        except:
                            logger.info(f"✅ 从文件读取V2Ray订阅（原始）: {v2ray_path}")
                            return {"content": content}
            except Exception as e:
                logger.warning(f"读取V2Ray配置文件失败 {v2ray_path}: {e}")
        return {"error": "暂无可用节点"}

    def get_invalid_clash_config(self) -> str:
        config = self._get_config_from_db('clash_config_invalid', 'clash_invalid')
        return config if config else self._get_default_invalid_clash_config_str()

    def get_invalid_v2ray_config(self) -> str:
        config = self._get_config_from_db('v2ray_config_invalid', 'v2ray_invalid')
        return config if config else self._get_default_invalid_v2ray_config_str()


    def _get_default_invalid_clash_config_str(self) -> str:
        return """# Clash失效配置文件
# 此配置用于无效用户（订阅过期、用户禁用、设备超限等）

port: 7890
socks-port: 7891
allow-lan: true
mode: Rule
log-level: info
external-controller: :9090

proxies: []

proxy-groups:
  - name: "Proxy"
    type: select
    proxies: []

rules:
  - MATCH,DIRECT
"""

    def _get_default_invalid_v2ray_config_str(self) -> str:
        return """{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [],
  "outbounds": [
    {
      "protocol": "direct",
      "settings": {}
    }
  ],
  "routing": {
    "rules": [
      {
        "type": "field",
        "outboundTag": "direct",
        "network": "tcp,udp"
      }
    ]
  }
}"""

    def get_v2ray_config(self) -> str:
        v2ray_path = self._get_config_file_path('v2ray_file', 'xr')
        return self._read_config_file(v2ray_path, 'v2ray_config', 'v2ray', "# V2Ray配置未设置\n# 请联系管理员配置V2Ray节点信息")

    def get_clash_config(self) -> str:
        clash_path = self._get_config_file_path('clash_file', 'clash.yaml')
        config_str = self._read_config_file(clash_path, 'clash_config', 'clash', "# Clash配置未设置\n# 请联系管理员配置Clash节点信息")
        if config_str and not config_str.startswith("#"):
            try:
                import yaml
                config = yaml.safe_load(config_str)
                if config and isinstance(config, dict):
                    if 'proxy-groups' in config and isinstance(config['proxy-groups'], list):
                        seen_names = set()
                        unique_groups = []
                        for group in config['proxy-groups']:
                            if isinstance(group, dict) and 'name' in group:
                                if group['name'] not in seen_names:
                                    seen_names.add(group['name'])
                                    unique_groups.append(group)
                            else:
                                unique_groups.append(group)
                        config['proxy-groups'] = unique_groups
                        return yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False)
            except Exception as e:
                logger.warning(f"清理Clash配置中的重复proxy-groups失败: {e}")
        return config_str

    def send_subscription_email(self, user_id: int, request=None) -> bool:
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            subscription = self.db.query(Subscription).filter(Subscription.user_id == user_id).first()
            if not subscription:
                return False
            from app.services.email import EmailService
            email_service = EmailService(self.db)
            return email_service.send_subscription_email(user.email, {"subscription_id": subscription.id}, request=request)
        except Exception as e:
            logger.error(f"发送订阅邮件失败: {e}", exc_info=True)
            return False

    def process_paid_order(self, order) -> bool:
        try:
            from app.models.package import Package
            user = self.db.query(User).filter(User.id == order.user_id).first()
            package = self.db.query(Package).filter(Package.id == order.package_id).first()
            if not user or not package:
                return False
            current_subscription = self.db.query(Subscription).filter(
                Subscription.user_id == user.id,
                Subscription.is_active == True
            ).first()
            new_device_limit = package.device_limit
            new_expire_time = self._calculate_expire_time(current_subscription, package, order.created_at)
            if current_subscription and current_subscription.is_active:
                if package.device_limit > current_subscription.device_limit:
                    self._handle_device_upgrade(user, current_subscription, package, new_device_limit, new_expire_time)
                else:
                    self._handle_subscription_renewal(current_subscription, new_expire_time)
            else:
                if current_subscription:
                    self._reactivate_expired_subscription(current_subscription, package, new_device_limit, new_expire_time)
                else:
                    self._create_new_subscription_from_order(user, package, new_device_limit, new_expire_time)
            if order.status != "paid":
                order.status = "paid"
                logger.info(f"在process_paid_order中更新订单状态为paid: {order.order_no}")
            if not order.payment_time:
                order.payment_time = datetime.now(timezone.utc)
                logger.info(f"在process_paid_order中设置支付时间: {order.order_no}")
            self.db.commit()
            self.db.refresh(order)
            logger.info(f"订阅更新完成，订单 {order.order_no} 状态: {order.status}, 支付时间: {order.payment_time}")
            try:
                self.send_subscription_email(user.id)
            except Exception as e:
                logger.error(f"发送订阅邮件失败: {e}", exc_info=True)
            try:
                from app.services.notification_service import NotificationService
                NotificationService(self.db).send_payment_success_notification(order)
            except Exception as e:
                logger.error(f"发送支付成功通知失败: {e}", exc_info=True)
            return True
        except Exception as e:
            try:
                self.db.rollback()
            except Exception as rollback_error:
                logger.error(f"回滚失败: {rollback_error}", exc_info=True)
            logger.error(f"处理订单支付失败: {e}", exc_info=True)
            return False

    def _calculate_expire_time(self, current_subscription, package, order_time):
        package_duration = timedelta(days=package.duration_days)
        order_time = self._ensure_timezone(order_time)
        if current_subscription and current_subscription.is_active:
            expire_time = self._ensure_timezone(current_subscription.expire_time)
            now = datetime.now(timezone.utc)
            if expire_time > now:
                return expire_time + package_duration
            else:
                return now + package_duration
        else:
            return datetime.now(timezone.utc) + package_duration

    def _update_subscription_common(self, subscription, package, device_limit, expire_time):
        expire_time = self._ensure_timezone(expire_time)
        subscription.package_id = package.id
        subscription.device_limit = device_limit
        subscription.expire_time = expire_time
        subscription.is_active = True
        subscription.status = 'active'
        subscription.updated_at = datetime.now(timezone.utc)

    def _handle_device_upgrade(self, user, current_subscription, package, new_device_limit, new_expire_time):
        self._update_subscription_common(current_subscription, package, new_device_limit, new_expire_time)

    def _handle_subscription_renewal(self, current_subscription, new_expire_time):
        new_expire_time = self._ensure_timezone(new_expire_time)
        current_subscription.expire_time = new_expire_time
        current_subscription.is_active = True
        current_subscription.status = 'active'
        current_subscription.updated_at = datetime.now(timezone.utc)

    def _create_new_subscription_from_order(self, user, package, device_limit, expire_time):
        expire_time = self._ensure_timezone(expire_time)
        subscription = Subscription(
            user_id=user.id,
            package_id=package.id,
            subscription_url=generate_subscription_url(),
            device_limit=device_limit,
            is_active=True,
            current_devices=0,
            status='active',
            created_at=datetime.now(timezone.utc),
            expire_time=expire_time
        )
        self.db.add(subscription)
        self.db.flush()
        try:
            from app.services.notification_service import NotificationService
            NotificationService(self.db).send_subscription_created_notification(subscription)
        except Exception as e:
            logger.error(f"发送订阅创建通知失败: {e}", exc_info=True)

    def _reactivate_expired_subscription(self, current_subscription, package, device_limit, expire_time):
        self._update_subscription_common(current_subscription, package, device_limit, expire_time)

    def check_expired_subscriptions(self):
        try:
            from app.utils.timezone import get_beijing_time
            now = get_beijing_time()
            expired_subscriptions = self.db.query(Subscription).filter(
                and_(Subscription.is_active == True, Subscription.expire_time < now)
            ).all()
            for subscription in expired_subscriptions:
                subscription.device_limit = 0
                subscription.is_active = False
                subscription.updated_at = now
            self.db.commit()
            return len(expired_subscriptions)
        except Exception as e:
            self.db.rollback()
            logger.error(f"处理过期订阅失败: {e}", exc_info=True)
            return 0

    def remove_device(self, device_id: int) -> bool:
        return self.delete_device(device_id)

    def clear_devices(self, subscription_id: int) -> bool:
        return self.delete_devices_by_subscription_id(subscription_id)

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Subscription]:
        return self.db.query(Subscription).offset(skip).limit(limit).all()

    def count_expired(self) -> int:
        """统计过期订阅数量（使用count避免加载所有数据）"""
        from sqlalchemy import func
        now = datetime.now(timezone.utc)
        return self.db.query(func.count(Subscription.id)).filter(
            and_(Subscription.expire_time.isnot(None), Subscription.expire_time <= now)
        ).scalar() or 0

    def sync_current_devices(self, subscription_id: int) -> bool:
        try:
            device_count_query = text("SELECT COUNT(*) FROM devices WHERE subscription_id = :subscription_id AND is_allowed = 1")
            actual_count = self.db.execute(device_count_query, {'subscription_id': subscription_id}).scalar() or 0
            subscription = self.get(subscription_id)
            if subscription:
                old_count = subscription.current_devices
                subscription.current_devices = actual_count
                self.db.commit()
                logger.info(f"同步订阅 {subscription_id} 的设备数量: {old_count} -> {actual_count}")
                return True
            logger.warning(f"订阅 {subscription_id} 不存在，无法同步设备数量")
            return False
        except Exception as e:
            logger.error(f"同步设备数量失败: {e}", exc_info=True)
            self.db.rollback()
            return False
