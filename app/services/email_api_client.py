"""邮件API客户端服务 - 用于通过API端点获取邮件模板所需的用户、订阅等信息"""
import json
import logging
from typing import Any, Dict, Optional

import requests
from fastapi import Request
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class EmailAPIClient:
    """邮件API客户端类"""

    def __init__(self, request: Request, db: Session):
        self.request = request
        self.db = db
        self.base_url = self._get_base_url()

    def _get_base_url(self) -> str:
        """获取API基础URL"""
        from app.core.domain_config import get_domain_config

        domain_config = get_domain_config()
        base_url = domain_config.get_email_base_url(self.request, self.db)

        return base_url

    def _make_api_request(self, endpoint: str, method: str = "GET", data: dict = None) -> Optional[Dict[str, Any]]:
        """发送API请求"""
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=10)
            else:
                return None

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API请求失败: {endpoint}, 状态码: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"API请求异常: {endpoint}, 错误: {str(e)}", exc_info=True)
            return None

    def get_user_info(self, user_id: int) -> Dict[str, Any]:
        """通过数据库直接获取用户信息"""
        try:
            from sqlalchemy import text

            query = text("""
                SELECT 
                    u.id,
                    u.username,
                    u.email,
                    u.is_verified,
                    u.created_at,
                    u.last_login
                FROM users u
                WHERE u.id = :user_id
            """)

            result = self.db.execute(query, {'user_id': user_id}).first()
            if result:
                return {
                    'id': result.id,
                    'username': result.username or '用户',
                    'email': result.email or '',
                    'nickname': result.username or '用户',
                    'status': 'active',
                    'is_verified': bool(result.is_verified) if result.is_verified is not None else False,
                    'created_at': result.created_at if result.created_at else '未知',
                    'last_login': result.last_login if result.last_login else '从未登录',
                    'avatar_url': '',
                    'phone': '',
                    'country': '',
                    'timezone': ''
                }
            return {}
        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}", exc_info=True)
            return {}

    def get_subscription_info(self, subscription_id: int) -> Dict[str, Any]:
        """通过数据库直接获取订阅信息"""
        try:
            from datetime import datetime, timezone
            from sqlalchemy import text

            query = text("""
                SELECT 
                    s.id,
                    s.user_id,
                    s.subscription_url,
                    s.device_limit,
                    s.current_devices,
                    s.is_active,
                    s.expire_time,
                    s.created_at,
                    s.updated_at,
                    u.username,
                    u.email,
                    p.name as package_name,
                    p.description as package_description,
                    p.price as package_price,
                    p.duration_days as package_duration,
                    p.bandwidth_limit as package_bandwidth_limit
                FROM subscriptions s
                LEFT JOIN users u ON s.user_id = u.id
                LEFT JOIN packages p ON s.package_id = p.id
                WHERE s.id = :subscription_id
            """)

            result = self.db.execute(query, {'subscription_id': subscription_id}).first()
            if result:
                remaining_days = 0
                if result.expire_time:
                    try:
                        if isinstance(result.expire_time, str):
                            expire_time = datetime.fromisoformat(result.expire_time.replace('Z', '+00:00'))
                            if expire_time.tzinfo is None:
                                expire_time = expire_time.replace(tzinfo=timezone.utc)
                        elif hasattr(result.expire_time, 'date'):
                            expire_time = result.expire_time
                            if expire_time.tzinfo is None:
                                expire_time = expire_time.replace(tzinfo=timezone.utc)
                        else:
                            remaining_days = 0
                            expire_time = None

                        if expire_time:
                            now = datetime.now(timezone.utc)
                            remaining_days = max(0, (expire_time - now).days)
                    except Exception as e:
                        logger.warning(f"计算剩余天数失败: {str(e)}")
                        remaining_days = 0

                device_limit = result.device_limit if result.device_limit is not None else 3

                return {
                    'id': result.id,
                    'user_id': result.user_id,
                    'subscription_url': result.subscription_url or '',
                    'device_limit': device_limit,
                    'current_devices': result.current_devices or 0,
                    'max_devices': device_limit,
                    'is_active': bool(result.is_active) if result.is_active is not None else True,
                    'expire_time': result.expire_time if result.expire_time else '永久',
                    'remaining_days': remaining_days,
                    'created_at': result.created_at if result.created_at else '未知',
                    'updated_at': result.updated_at if result.updated_at else '未知',
                    'username': result.username or '用户',
                    'nickname': result.username or '用户',
                    'user_email': result.email or '',
                    'package_name': result.package_name or '标准套餐',
                    'package_description': result.package_description or '网络服务套餐',
                    'package_price': float(result.package_price) if result.package_price is not None else 0.0,
                    'package_duration': result.package_duration or 30,
                    'package_bandwidth_limit': result.package_bandwidth_limit or '无限制'
                }
            return {}
        except Exception as e:
            logger.error(f"获取订阅信息失败: {str(e)}", exc_info=True)
            return {}

    def get_user_dashboard_info(self, user_id: int) -> Dict[str, Any]:
        """通过API获取用户仪表板信息（包含订阅信息）"""
        try:
            endpoint = f"/api/v1/users/dashboard"
            result = self._make_api_request(endpoint)

            if result and result.get('success'):
                data = result.get('data', {})
                return {
                    'id': data.get('id'),
                    'username': data.get('username', '用户'),
                    'email': data.get('email', ''),
                    'nickname': data.get('nickname') or data.get('username', '用户'),
                    'subscription_id': data.get('subscription_id'),
                    'subscription_url': data.get('subscription_url', ''),
                    'device_limit': data.get('device_limit', 3),
                    'current_devices': data.get('current_devices', 0),
                    'max_devices': data.get('device_limit', 3),
                    'is_active': data.get('is_active', True),
                    'expire_time': data.get('expire_time', '永久'),
                    'remaining_days': data.get('remaining_days', 0),
                    'package_name': data.get('package_name', '未知套餐'),
                    'package_description': data.get('package_description', '无描述'),
                    'package_price': data.get('package_price', 0.0),
                    'package_duration': data.get('package_duration', 0),
                    'package_bandwidth_limit': data.get('package_bandwidth_limit')
                }
            return {}
        except Exception as e:
            logger.error(f"获取用户仪表板信息失败: {str(e)}", exc_info=True)
            return {}

    def get_subscription_urls(self, subscription_url: str) -> Dict[str, str]:
        """通过API获取订阅地址"""
        try:
            if not subscription_url:
                return {
                    'v2ray_url': '',
                    'clash_url': '',
                    'ssr_url': ''
                }

            subscription_urls = {
                'v2ray_url': f"{self.base_url}/api/v1/subscriptions/ssr/{subscription_url}",
                'clash_url': f"{self.base_url}/api/v1/subscriptions/clash/{subscription_url}",
                'ssr_url': f"{self.base_url}/api/v1/subscriptions/ssr/{subscription_url}"
            }

            return subscription_urls
        except Exception as e:
            logger.error(f"获取订阅地址失败: {str(e)}", exc_info=True)
            return {
                'v2ray_url': '',
                'clash_url': '',
                'ssr_url': ''
            }

    def get_complete_subscription_data(self, subscription_id: int) -> Dict[str, Any]:
        """获取完整的订阅数据（通过API）"""
        try:
            subscription_info = self.get_subscription_info(subscription_id)
            if not subscription_info:
                logger.warning(f"订阅信息获取失败: subscription_id={subscription_id}")
                return {}

            user_info = self.get_user_info(subscription_info.get('user_id', 0))
            subscription_url = subscription_info.get('subscription_url', '')
            subscription_urls = self.get_subscription_urls(subscription_url)

            complete_data = {
                **subscription_info,
                **user_info,
                **subscription_urls,
                'subscription_id': subscription_id,
                'base_url': self.base_url
            }

            return complete_data

        except Exception as e:
            logger.error(f"获取完整订阅数据失败: {str(e)}", exc_info=True)
            return {}

    def get_order_info(self, order_id: int) -> Dict[str, Any]:
        """通过API获取订单信息"""
        try:
            endpoint = f"/api/v1/orders/{order_id}"
            result = self._make_api_request(endpoint)

            if result and result.get('success'):
                order_data = result.get('data', {})
                return {
                    'id': order_data.get('id'),
                    'order_no': order_data.get('order_no', ''),
                    'user_id': order_data.get('user_id'),
                    'amount': order_data.get('amount', 0.0),
                    'status': order_data.get('status', ''),
                    'payment_method_name': order_data.get('payment_method_name', ''),
                    'created_at': order_data.get('created_at', '未知'),
                    'updated_at': order_data.get('updated_at', '未知'),
                    'username': order_data.get('username', '用户'),
                    'user_email': order_data.get('user_email', ''),
                    'package_name': order_data.get('package_name', '未知套餐'),
                    'package_description': order_data.get('package_description', '无描述'),
                    'package_price': order_data.get('package_price', 0.0),
                    'package_duration': order_data.get('package_duration', 0),
                    'base_url': self.base_url
                }
            return {}
        except Exception as e:
            logger.error(f"获取订单信息失败: {str(e)}", exc_info=True)
            return {}

    def get_complete_user_data(self, user_id: int) -> Dict[str, Any]:
        """获取完整的用户数据（包含订阅信息）"""
        try:
            from datetime import datetime, timezone
            from sqlalchemy import text

            user_info = self.get_user_info(user_id)
            if not user_info:
                return {}

            try:
                query = text("""
                    SELECT 
                        s.id,
                        s.subscription_url,
                        s.device_limit,
                        s.current_devices,
                        s.is_active,
                        s.expire_time,
                        p.name as package_name
                    FROM subscriptions s
                    LEFT JOIN packages p ON s.package_id = p.id
                    WHERE s.user_id = :user_id
                    ORDER BY s.created_at DESC
                    LIMIT 1
                """)

                result = self.db.execute(query, {'user_id': user_id}).first()

                if result:
                    remaining_days = 0
                    expire_time = result.expire_time
                    if expire_time:
                        try:
                            if isinstance(expire_time, str):
                                expire_time_obj = datetime.fromisoformat(expire_time.replace('Z', '+00:00'))
                                if expire_time_obj.tzinfo is None:
                                    expire_time_obj = expire_time_obj.replace(tzinfo=timezone.utc)
                            else:
                                expire_time_obj = expire_time
                                if expire_time_obj.tzinfo is None:
                                    expire_time_obj = expire_time_obj.replace(tzinfo=timezone.utc)

                            now = datetime.now(timezone.utc)
                            remaining_days = max(0, (expire_time_obj - now).days)
                        except Exception as e:
                            logger.warning(f"计算剩余天数失败: {str(e)}")
                            remaining_days = 0

                    subscription_url = result.subscription_url or ''
                    subscription_urls = {}
                    if subscription_url:
                        subscription_urls = self.get_subscription_urls(subscription_url)

                    device_limit = result.device_limit if result.device_limit is not None else 0

                    user_info.update({
                        'subscription_id': result.id,
                        'subscription_url': subscription_url,
                        'device_limit': device_limit,
                        'current_devices': result.current_devices or 0,
                        'is_active': bool(result.is_active) if result.is_active is not None else False,
                        'expire_time': expire_time,
                        'remaining_days': remaining_days,
                        'package_name': result.package_name or '',
                        **subscription_urls
                    })
                else:
                    user_info.update({
                        'subscription_id': None,
                        'subscription_url': '',
                        'device_limit': 0,
                        'current_devices': 0,
                        'is_active': False,
                        'expire_time': None,
                        'remaining_days': 0,
                        'package_name': '',
                        'v2ray_url': '',
                        'clash_url': '',
                        'ssr_url': ''
                    })
            except Exception as e:
                logger.error(f"获取订阅信息失败: {str(e)}", exc_info=True)
                user_info.update({
                    'subscription_id': None,
                    'subscription_url': '',
                    'device_limit': 0,
                    'current_devices': 0,
                    'is_active': False,
                    'expire_time': None,
                    'remaining_days': 0,
                    'package_name': '',
                    'v2ray_url': '',
                    'clash_url': '',
                    'ssr_url': ''
                })

            user_info['base_url'] = self.base_url
            return user_info

        except Exception as e:
            logger.error(f"获取完整用户数据失败: {str(e)}", exc_info=True)
            return {}
