"""设备管理服务 - 负责处理订阅设备的识别、管理和限制"""
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DeviceManager:
    """设备管理器"""

    def __init__(self, db: Session):
        self.db = db

    def generate_device_hash(self, user_agent: str, ip_address: str, device_id: Optional[str] = None) -> str:
        """生成设备唯一标识 - 使用设备ID参数精确识别设备

        Args:
            user_agent: 用户代理
            ip_address: IP地址
            device_id: 设备ID（从URL参数获取，如果提供则优先使用）
        """
        if device_id and device_id.strip():
            return hashlib.sha256(f"device_id:{device_id.strip()}".encode('utf-8')).hexdigest()

        device_info = self.parse_user_agent(user_agent)
        device_features = []

        if device_info.get('software_name') and device_info['software_name'] != 'Unknown':
            device_features.append(f"software:{device_info['software_name']}")
            if device_info.get('software_version'):
                device_features.append(f"version:{device_info['software_version']}")

        if device_info.get('os_name') and device_info['os_name'] != 'Unknown':
            device_features.append(f"os:{device_info['os_name']}")
            if device_info.get('os_version'):
                device_features.append(f"os_version:{device_info['os_version']}")

        if device_info.get('device_model'):
            device_features.append(f"model:{device_info['device_model']}")
        if device_info.get('device_brand'):
            device_features.append(f"brand:{device_info['device_brand']}")

        iphone_match = re.search(r'iphone(\d+,\d+)', user_agent, re.IGNORECASE)
        if iphone_match:
            device_features.append(f"iphone:{iphone_match.group(1)}")

        ipad_match = re.search(r'ipad(\d+,\d+)', user_agent, re.IGNORECASE)
        if ipad_match:
            device_features.append(f"ipad:{ipad_match.group(1)}")

        android_match = re.search(r';\s*([^;]+)\s*build', user_agent, re.IGNORECASE)
        if android_match:
            device_features.append(f"android:{android_match.group(1).strip()}")

        if len(device_features) < 2:
            ua_parts = []
            for part in user_agent.split():
                if any(keyword in part.lower() for keyword in ['clash', 'v2ray', 'shadowrocket', 'quantumult', 'surge']):
                    ua_parts.append(part)
            device_string = '|'.join(ua_parts) if ua_parts else user_agent
        else:
            device_string = '|'.join(sorted(device_features))

        return hashlib.sha256(device_string.encode('utf-8')).hexdigest()

    def is_browser_request(self, user_agent: str) -> bool:
        """判断是否为浏览器请求"""
        if not user_agent:
            return False

        ua_lower = user_agent.lower()
        browser_keywords = [
            'mozilla', 'chrome', 'safari', 'firefox', 'edge', 'opera',
            'msie', 'trident', 'webkit', 'gecko', 'browser'
        ]

        is_browser = any(keyword in ua_lower for keyword in browser_keywords)
        proxy_keywords = [
            'clash',
            'clash for android',
            'clash-verge',
            'clashandroid',
            'clashx',
            'hiddify',
            'loon',
            'quantumult',
            'qv2ray',
            'shadowrocket',
            'shadowsocks',
            'shadowsocksr',
            'ssr',
            'ssrr',
            'surfboard',
            'surge',
            'v2ray',
            'v2rayn',
            'v2rayng'
        ]
        is_proxy_client = any(keyword in ua_lower for keyword in proxy_keywords)

        return is_browser and not is_proxy_client

    def parse_user_agent(self, user_agent: str) -> Dict[str, str]:
        """解析User-Agent，识别软件、操作系统、设备信息"""
        result = {
            'software_name': 'Unknown',
            'software_version': '',
            'os_name': 'Unknown',
            'os_version': '',
            'device_model': '',
            'device_brand': '',
            'software_category': 'unknown',
            'device_name': 'Unknown Device',
            'device_type': 'unknown'
        }

        rules = self.get_software_rules()
        ua_lower = user_agent.lower()

        matched_rule = None
        for rule in rules:
            pattern = rule['user_agent_pattern'].lower()
            if pattern in ua_lower:
                # 检查是否有更精确的匹配
                if not matched_rule or len(pattern) > len(matched_rule['user_agent_pattern']):
                    matched_rule = rule

        if not matched_rule:
            if 'hiddify' in ua_lower:
                matched_rule = {
                    'software_name': 'Hiddify',
                    'software_category': 'proxy'
                }

        if matched_rule:
            result['software_name'] = matched_rule['software_name']
            result['software_category'] = matched_rule['software_category']

        os_info = self._parse_os_info(user_agent)
        result.update(os_info)

        if result.get('os_name') == 'Unknown' and result.get('software_name') != 'Unknown':
            inferred_os = self._infer_os_from_software(result.get('software_name', ''))
            if inferred_os:
                result['os_name'] = inferred_os['os_name']
                if inferred_os.get('os_version'):
                    result['os_version'] = inferred_os['os_version']

        device_info = self._parse_device_info(user_agent, result.get('os_name'))
        result.update(device_info)

        if not result.get('device_model') and result.get('software_name') != 'Unknown':
            inferred_device = self._infer_device_from_software(result.get('software_name', ''))
            if inferred_device:
                if inferred_device.get('device_brand'):
                    result['device_brand'] = inferred_device['device_brand']
                if inferred_device.get('device_model'):
                    result['device_model'] = inferred_device['device_model']

        version_info = self._parse_version_info(user_agent)
        result.update(version_info)

        device_type = self._determine_device_type(user_agent, result)
        result['device_type'] = device_type

        device_name = self._generate_device_name(result)
        result['device_name'] = device_name

        return result

    def _parse_os_info(self, user_agent: str) -> Dict[str, str]:
        """解析操作系统信息"""
        result = {'os_name': 'Unknown', 'os_version': ''}
        ua_lower = user_agent.lower()

        if 'iphone' in ua_lower:
            result['os_name'] = 'iOS'
            ios_match = re.search(r'os (\d+)_(\d+)', user_agent, re.IGNORECASE)
            if ios_match:
                result['os_version'] = f"{ios_match.group(1)}.{ios_match.group(2)}"
        elif 'ipad' in ua_lower:
            result['os_name'] = 'iPadOS'
            ios_match = re.search(r'os (\d+)_(\d+)', user_agent, re.IGNORECASE)
            if ios_match:
                result['os_version'] = f"{ios_match.group(1)}.{ios_match.group(2)}"
        elif 'darwin' in ua_lower:
            darwin_match = re.search(r'darwin/(\d+)\.(\d+)\.?(\d+)?', user_agent, re.IGNORECASE)
            if darwin_match:
                darwin_major = int(darwin_match.group(1))
                darwin_minor = int(darwin_match.group(2))
                darwin_patch = int(darwin_match.group(3)) if darwin_match.group(3) else 0

                ios_major = darwin_major - 6
                if ios_major >= 10:
                    result['os_name'] = 'iOS'
                    result['os_version'] = f"{ios_major}.{darwin_minor}"
                    if darwin_patch > 0:
                        result['os_version'] += f".{darwin_patch}"
                elif ios_major >= 1:
                    result['os_name'] = 'macOS'
                    result['os_version'] = f"{ios_major}.{darwin_minor}"
        elif 'macintosh' in ua_lower or 'mac os' in ua_lower:
            result['os_name'] = 'macOS'
            mac_match = re.search(r'mac os x (\d+)[._](\d+)', user_agent, re.IGNORECASE)
            if mac_match:
                result['os_version'] = f"{mac_match.group(1)}.{mac_match.group(2)}"
        elif 'windows' in ua_lower:
            result['os_name'] = 'Windows'
            win_match = re.search(r'windows nt (\d+\.\d+)', user_agent, re.IGNORECASE)
            if win_match:
                result['os_version'] = win_match.group(1)
        elif 'android' in ua_lower:
            result['os_name'] = 'Android'
            android_match = re.search(r'android (\d+\.\d+)', user_agent, re.IGNORECASE)
            if android_match:
                result['os_version'] = android_match.group(1)
        elif 'linux' in ua_lower:
            result['os_name'] = 'Linux'

        return result

    def _infer_os_from_software(self, software_name: str) -> Optional[Dict[str, str]]:
        """根据软件名称推断操作系统"""
        if not software_name or software_name == 'Unknown':
            return None

        software_lower = software_name.lower()

        ios_software = [
            'anx',
            'anxray',
            'karing',
            'kitsunebi',
            'loon',
            'pharos',
            'potatso',
            'quantumult',
            'quantumult x',
            'shadowrocket',
            'stash',
            'surge'
        ]
        if any(keyword in software_lower for keyword in ios_software):
            return {'os_name': 'iOS', 'os_version': ''}

        android_software = [
            'clash for android',
            'clashandroid',
            'shadowsocks',
            'shadowsocksr',
            'ssr',
            'ssrr',
            'surfboard',
            'v2rayng'
        ]
        if any(keyword in software_lower for keyword in android_software):
            return {'os_name': 'Android', 'os_version': ''}

        windows_software = [
            'clash for windows',
            'clash verge',
            'clash-verge',
            'mihome part',
            'qv2ray',
            'shadowsocks-windows',
            'sparkle',
            'v2rayn',
            'v2rayw'
        ]
        if any(keyword in software_lower for keyword in windows_software):
            return {'os_name': 'Windows', 'os_version': ''}

        macos_software = [
            'clash for mac',
            'clashx',
            'clashx pro',
            'shadowsocksx',
            'shadowsocksx-ng',
            'surge',
            'v2rayu',
            'v2rayx'
        ]
        if any(keyword in software_lower for keyword in macos_software):
            return {'os_name': 'macOS', 'os_version': ''}

        linux_software = [
            'clash',
            'shadowsocks-libev',
            'v2ray',
            'v2ray-core'
        ]
        if any(keyword in software_lower for keyword in linux_software):
            if 'core' in software_lower or 'libev' in software_lower:
                return {'os_name': 'Linux', 'os_version': ''}

        return None

    def _infer_device_from_software(self, software_name: str) -> Optional[Dict[str, str]]:
        """根据软件名称推断设备信息"""
        if not software_name or software_name == 'Unknown':
            return None

        software_lower = software_name.lower()

        ios_software = [
            'anx',
            'anxray',
            'karing',
            'kitsunebi',
            'loon',
            'pharos',
            'potatso',
            'quantumult',
            'quantumult x',
            'shadowrocket',
            'stash',
            'surge'
        ]
        if any(keyword in software_lower for keyword in ios_software):
            return {'device_brand': 'Apple', 'device_model': ''}

        return None

    def _parse_device_info(self, user_agent: str, os_name: str = None) -> Dict[str, str]:
        """解析设备信息"""
        result = {'device_model': '', 'device_brand': ''}
        ua_lower = user_agent.lower()

        iphone_match = re.search(r'iphone(\d+,\d+)', user_agent, re.IGNORECASE)
        if iphone_match:
            result['device_brand'] = 'Apple'
            result['device_model'] = f"iPhone {iphone_match.group(1).replace(',', '.')}"

        ipad_match = re.search(r'ipad(\d+,\d+)', user_agent, re.IGNORECASE)
        if ipad_match:
            result['device_brand'] = 'Apple'
            result['device_model'] = f"iPad {ipad_match.group(1).replace(',', '.')}"

        if not result.get('device_model'):
            ios_software_keywords = [
                'anx',
                'anxray',
                'karing',
                'kitsunebi',
                'loon',
                'pharos',
                'potatso',
                'quantumult',
                'quantumult x',
                'shadowrocket',
                'stash',
                'surge'
            ]
            if any(keyword in ua_lower for keyword in ios_software_keywords):
                if os_name == 'iOS' or 'darwin' in ua_lower:
                    result['device_brand'] = 'Apple'
                    result['device_model'] = 'iPhone'

        if 'android' in ua_lower:
            device_match = re.search(r';\s*([^;]+)\s*build', user_agent, re.IGNORECASE)
            if device_match:
                device_name = device_match.group(1).strip()
                if any(brand in device_name.lower() for brand in ['samsung', 'galaxy']):
                    result['device_brand'] = 'Samsung'
                elif any(brand in device_name.lower() for brand in ['huawei', 'honor']):
                    result['device_brand'] = 'Huawei'
                elif any(brand in device_name.lower() for brand in ['xiaomi', 'redmi', 'mi ']):
                    result['device_brand'] = 'Xiaomi'
                elif any(brand in device_name.lower() for brand in ['oppo', 'oneplus']):
                    result['device_brand'] = 'OPPO'
                elif any(brand in device_name.lower() for brand in ['vivo', 'iqoo']):
                    result['device_brand'] = 'vivo'
                elif any(brand in device_name.lower() for brand in ['realme']):
                    result['device_brand'] = 'Realme'
                elif any(brand in device_name.lower() for brand in ['meizu']):
                    result['device_brand'] = 'Meizu'
                elif any(brand in device_name.lower() for brand in ['lenovo']):
                    result['device_brand'] = 'Lenovo'
                elif any(brand in device_name.lower() for brand in ['motorola']):
                    result['device_brand'] = 'Motorola'
                elif any(brand in device_name.lower() for brand in ['sony']):
                    result['device_brand'] = 'Sony'
                elif any(brand in device_name.lower() for brand in ['lg']):
                    result['device_brand'] = 'LG'
                elif any(brand in device_name.lower() for brand in ['htc']):
                    result['device_brand'] = 'HTC'
                elif any(brand in device_name.lower() for brand in ['asus']):
                    result['device_brand'] = 'ASUS'
                elif any(brand in device_name.lower() for brand in ['nokia']):
                    result['device_brand'] = 'Nokia'
                elif any(brand in device_name.lower() for brand in ['blackberry']):
                    result['device_brand'] = 'BlackBerry'
                elif any(brand in device_name.lower() for brand in ['google', 'pixel']):
                    result['device_brand'] = 'Google'
                else:
                    result['device_brand'] = 'Unknown'

                result['device_model'] = device_name

        return result

    def _parse_version_info(self, user_agent: str) -> Dict[str, str]:
        """解析软件版本信息"""
        result = {'software_version': ''}
        version_patterns = [
            r'(\d+\.\d+\.\d+)',
            r'(\d+\.\d+)',
            r'v(\d+\.\d+\.\d+)',
            r'version\s*(\d+\.\d+\.\d+)',
            r'(\d+\.\d+\.\d+\.\d+)'
        ]
        
        for pattern in version_patterns:
            match = re.search(pattern, user_agent, re.IGNORECASE)
            if match:
                result['software_version'] = match.group(1)
                break
        
        return result
    
    def _determine_device_type(self, user_agent: str, device_info: Dict[str, str]) -> str:
        """根据 User-Agent 和设备信息判断设备类型"""
        ua_lower = user_agent.lower()
        os_name = device_info.get('os_name', '').lower()
        software_name = device_info.get('software_name', '').lower()
        
        # 1. 根据操作系统判断（最可靠）
        if os_name == 'ipados' or 'ipad' in ua_lower:
            return 'tablet'
        elif os_name == 'ios':
            return 'mobile'
        elif os_name == 'android':
            # Android 可能是手机或平板，需要进一步判断
            if 'tablet' in ua_lower or 'pad' in ua_lower:
                return 'tablet'
            return 'mobile'
        elif os_name in ['windows', 'macos', 'linux']:
            return 'desktop'
        
        # 2. 根据软件名称判断（如果操作系统无法识别）
        # iOS 专用软件（通常是移动端）
        if any(keyword in software_name for keyword in ['shadowrocket', 'quantumult', 'surge', 'loon']):
            if 'ipad' in ua_lower:
                return 'tablet'
            return 'mobile'
        
        # 桌面端软件
        if any(keyword in software_name for keyword in ['clash for windows', 'clash-verge', 'v2rayn', 'qv2ray']):
            return 'desktop'
        
        # Clash Meta 可能是移动端或桌面端，需要结合其他信息
        if 'clash' in software_name:
            # 如果操作系统是 Windows/macOS/Linux，则是桌面端
            if os_name in ['windows', 'macos', 'linux']:
                return 'desktop'
            # 如果操作系统是 iOS/Android，则是移动端
            elif os_name in ['ios', 'android']:
                if 'ipad' in ua_lower or 'tablet' in ua_lower:
                    return 'tablet'
                return 'mobile'
        
        # 3. 根据 User-Agent 中的关键词判断
        if 'iphone' in ua_lower:
            return 'mobile'
        elif 'ipad' in ua_lower:
            return 'tablet'
        elif any(keyword in ua_lower for keyword in ['windows', 'macintosh', 'x11', 'linux']):
            return 'desktop'
        elif 'android' in ua_lower:
            if 'tablet' in ua_lower or 'pad' in ua_lower:
                return 'tablet'
            return 'mobile'
        
        # 4. 如果无法识别，返回 unknown
        return 'unknown'
    
    def _generate_device_name(self, device_info: Dict[str, str]) -> str:
        """生成设备名称"""
        parts = []
        
        # 添加软件名称
        if device_info.get('software_name') and device_info['software_name'] != 'Unknown':
            parts.append(device_info['software_name'])
        
        # 添加设备型号
        if device_info.get('device_model'):
            parts.append(device_info['device_model'])
        elif device_info.get('device_brand'):
            parts.append(device_info['device_brand'])
        
        # 添加操作系统
        if device_info.get('os_name') and device_info['os_name'] != 'Unknown':
            os_name = device_info['os_name']
            if device_info.get('os_version'):
                os_name += f" {device_info['os_version']}"
            parts.append(os_name)
        
        # 添加软件版本
        if device_info.get('software_version'):
            parts.append(f"v{device_info['software_version']}")
        
        if parts:
            return " - ".join(parts)
        else:
            return "Unknown Device"
    
    
    def get_software_rules(self) -> List[Dict[str, str]]:
        """获取软件识别规则"""
        try:
            result = self.db.execute(text("""
                SELECT software_name, software_category, user_agent_pattern, 
                       os_pattern, device_pattern, version_pattern
                FROM software_rules 
                WHERE is_active = 1
                ORDER BY software_name
            """)).fetchall()
            
            return [
                {
                    'software_name': row[0],
                    'software_category': row[1],
                    'user_agent_pattern': row[2],
                    'os_pattern': row[3],
                    'device_pattern': row[4],
                    'version_pattern': row[5]
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"获取软件规则失败: {e}", exc_info=True)
            return []
    
    def check_subscription_access(self, subscription_url: str, user_agent: str, ip_address: str, 
                                 subscription_type: str = 'ssr', device_id: Optional[str] = None) -> Dict[str, Any]:
        """检查订阅访问权限
        
        Args:
            subscription_url: 订阅密钥
            user_agent: 用户代理
            ip_address: IP地址
            subscription_type: 订阅类型 ('ssr' 通用订阅 或 'clash' Clash订阅)
            device_id: 设备ID（从URL参数获取，用于精确识别设备）
        """
        result = {
            'allowed': False,
            'status_code': 200,
            'message': '',
            'device_info': {},
            'access_type': 'allowed',
            'subscription_type': subscription_type
        }
        
        try:
            # 判断是否为浏览器请求
            if self.is_browser_request(user_agent):
                logger.info(f"浏览器访问，不记录设备和订阅次数: subscription_url={subscription_url}, user_agent={user_agent[:100]}")
                
                # 获取订阅信息用于记录日志
                subscription = self.db.execute(text("""
                    SELECT s.id, s.user_id
                    FROM subscriptions s
                    WHERE s.subscription_url = :subscription_url
                """), {'subscription_url': subscription_url}).fetchone()
                
                if subscription:
                    # 记录浏览器访问日志（但不记录设备和订阅次数）
                    self._log_access(subscription.id, None, ip_address, user_agent, 'browser_access', 200, '浏览器访问', subscription_type)
                    # 提交事务以确保日志被保存
                    try:
                        self.db.commit()
                    except:
                        pass
                
                result['allowed'] = True
                result['access_type'] = 'browser_access'
                return result
            
            # 获取订阅信息
            logger.info(f"检查订阅访问: subscription_url={subscription_url}, user_agent={user_agent[:100]}, ip={ip_address}, device_id={device_id}")
            
            subscription = self.db.execute(text("""
                SELECT s.id, s.user_id, s.device_limit, s.expire_time, s.is_active,
                       u.id as user_id, u.username, u.email
                FROM subscriptions s
                JOIN users u ON s.user_id = u.id
                WHERE s.subscription_url = :subscription_url
            """), {'subscription_url': subscription_url}).fetchone()
            
            if not subscription:
                logger.warning(f"订阅地址不存在: {subscription_url}")
                result['status_code'] = 404
                result['message'] = '订阅地址不存在'
                result['access_type'] = 'not_found'
                return result
            
            logger.info(f"找到订阅: id={subscription.id}, user_id={subscription.user_id}, device_limit={subscription.device_limit}, is_active={subscription.is_active}")
            
            # 检查订阅是否过期
            if subscription.expire_time:
                # 处理字符串格式的日期
                if isinstance(subscription.expire_time, str):
                    from datetime import datetime
                    try:
                        expire_time = datetime.fromisoformat(subscription.expire_time.replace('Z', '+00:00'))
                    except:
                        expire_time = datetime.strptime(subscription.expire_time, '%Y-%m-%d %H:%M:%S.%f')
                else:
                    expire_time = subscription.expire_time
                
                if expire_time < datetime.utcnow():
                    result['status_code'] = 403
                    result['message'] = '订阅已过期'
                    result['access_type'] = 'blocked_expired'
                    self._log_access(subscription.id, None, ip_address, user_agent, 'blocked_expired', 403, '订阅已过期', subscription_type)
                    return result
            
            # 解析设备信息
            device_info = self.parse_user_agent(user_agent)
            result['device_info'] = device_info
            
            # 如果无法识别软件名称，根据订阅类型设置默认值
            if device_info.get('software_name') == 'Unknown':
                if subscription_type == 'clash':
                    device_info['software_name'] = 'clash'
                    logger.info(f"根据订阅类型设置 software_name: Unknown -> clash (subscription_type={subscription_type})")
                elif subscription_type == 'ssr':
                    device_info['software_name'] = 'v2ray'
                    logger.info(f"根据订阅类型设置 software_name: Unknown -> v2ray (subscription_type={subscription_type})")
            
            # 如果识别为 Hiddify，根据订阅类型调整统计分类
            if device_info.get('software_name') == 'Hiddify':
                if subscription_type == 'ssr':
                    device_info['software_name'] = 'v2ray'
                    logger.info(f"根据订阅类型调整 Hiddify: Hiddify -> v2ray (subscription_type={subscription_type})")
            
            logger.info(f"设备信息解析完成: software_name={device_info.get('software_name')}, subscription_type={subscription_type}, user_agent={user_agent[:100]}")
            
            # 生成设备哈希（优先使用设备ID参数，实现精确识别）
            device_hash = self.generate_device_hash(user_agent, ip_address, device_id)
            
            # 检查设备是否已存在
            # 如果提供了设备ID，优先通过设备ID查找
            existing_device = None
            if device_id and device_id.strip():
                # 通过设备ID查找（最精确）
                existing_device = self.db.execute(text("""
                    SELECT id, is_allowed, access_count, first_seen, last_seen, ip_address
                    FROM devices
                    WHERE device_hash = :device_hash AND subscription_id = :subscription_id
                """), {
                    'device_hash': device_hash,
                    'subscription_id': subscription.id
                }).fetchone()
            
            # 如果没有找到，通过设备哈希查找（兼容没有设备ID的情况）
            if not existing_device:
                existing_device = self.db.execute(text("""
                    SELECT id, is_allowed, access_count, first_seen, last_seen, ip_address
                    FROM devices
                    WHERE device_hash = :device_hash AND subscription_id = :subscription_id
                """), {
                    'device_hash': device_hash,
                    'subscription_id': subscription.id
                }).fetchone()
            
            if existing_device:
                # 设备已存在，更新访问信息和UA记录
                logger.info(f"设备已存在: device_id={existing_device.id}, is_allowed={existing_device.is_allowed}, access_count={existing_device.access_count}")
                
                self.db.execute(text("""
                    UPDATE devices 
                    SET last_seen = CURRENT_TIMESTAMP, 
                        last_access = CURRENT_TIMESTAMP,
                        access_count = access_count + 1,
                        ip_address = :ip_address, 
                        user_agent = :user_agent,
                        device_ua = :device_ua,
                        software_name = :software_name,
                        software_version = :software_version,
                        os_name = :os_name,
                        os_version = :os_version,
                        device_model = :device_model,
                        device_brand = :device_brand,
                        device_name = :device_name,
                        device_type = :device_type
                    WHERE id = :device_id
                """), {
                    'device_id': existing_device.id,
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'device_ua': f"{user_agent}|{ip_address}",
                    'software_name': device_info.get('software_name', 'Unknown'),
                    'software_version': device_info.get('software_version', ''),
                    'os_name': device_info.get('os_name', 'Unknown'),
                    'os_version': device_info.get('os_version', ''),
                    'device_model': device_info.get('device_model', ''),
                    'device_brand': device_info.get('device_brand', ''),
                    'device_name': device_info.get('device_name', 'Unknown Device'),
                    'device_type': device_info.get('device_type', 'unknown')
                })
                logger.info(f"设备访问信息已更新: device_id={existing_device.id}, new_access_count={existing_device.access_count + 1}, software_name={device_info.get('software_name', 'Unknown')}")
                
                if existing_device.is_allowed:
                    result['allowed'] = True
                    result['access_type'] = 'allowed'
                    self._log_access(subscription.id, existing_device.id, ip_address, user_agent, 'allowed', 200, '访问成功', subscription_type)
                    logger.debug(f"设备访问允许: device_id={existing_device.id}")
                else:
                    result['status_code'] = 403
                    result['message'] = '设备数量已达上限'
                    result['access_type'] = 'blocked_device_limit'
                    self._log_access(subscription.id, existing_device.id, ip_address, user_agent, 'blocked_device_limit', 403, '设备数量已达上限', subscription_type)
                    logger.warning(f"设备访问被拒绝（已达上限）: device_id={existing_device.id}")
                
                # 同步设备数量
                from app.services.subscription import SubscriptionService
                subscription_service = SubscriptionService(self.db)
                subscription_service.sync_current_devices(subscription.id)
                
                self.db.commit()
                return result
            
            # 新设备，检查设备数量限制
            allowed_devices_count = self.db.execute(text("""
                SELECT COUNT(*) FROM devices 
                WHERE subscription_id = :subscription_id AND is_allowed = 1
            """), {'subscription_id': subscription.id}).scalar()
            
            logger.info(f"设备数量检查: subscription_id={subscription.id}, allowed_devices={allowed_devices_count}, device_limit={subscription.device_limit}")
            
            if allowed_devices_count >= subscription.device_limit:
                # 设备数量已达上限，记录但不允许
                device_id = self._create_device_record(
                    subscription.id, subscription.user_id, device_hash, 
                    ip_address, user_agent, device_info, False
                )
                
                result['status_code'] = 403
                result['message'] = f'设备数量已达上限（{subscription.device_limit}个）'
                result['access_type'] = 'blocked_device_limit'
                self._log_access(subscription.id, device_id, ip_address, user_agent, 'blocked_device_limit', 403, result['message'], subscription_type)
            else:
                # 允许新设备
                device_id = self._create_device_record(
                    subscription.id, subscription.user_id, device_hash, 
                    ip_address, user_agent, device_info, True
                )
                logger.info(f"新设备已创建: device_id={device_id}, subscription_id={subscription.id}, device_name={device_info.get('device_name', 'Unknown')}, software_name={device_info.get('software_name', 'Unknown')}, subscription_type={subscription_type}")
                
                result['allowed'] = True
                result['access_type'] = 'allowed'
                self._log_access(subscription.id, device_id, ip_address, user_agent, 'allowed', 200, '访问成功', subscription_type)
            
            # 同步订阅的设备数量（根据实际设备数量）
            from app.services.subscription import SubscriptionService
            subscription_service = SubscriptionService(self.db)
            sync_result = subscription_service.sync_current_devices(subscription.id)
            logger.info(f"同步订阅 {subscription.id} 的设备数量: sync_result={sync_result}")
            
            self.db.commit()
            logger.info(f"设备访问处理完成: subscription_id={subscription.id}, allowed={result['allowed']}, access_type={result['access_type']}")
            
        except Exception as e:
            logger.error(f"检查订阅访问权限失败: {e}", exc_info=True)
            result['status_code'] = 500
            result['message'] = '服务器内部错误'
            result['access_type'] = 'error'
            try:
                self.db.rollback()
            except:
                pass
        
        return result
    
    def _create_device_record(self, subscription_id: int, user_id: int, device_hash: str, 
                            ip_address: str, user_agent: str, device_info: Dict[str, str], 
                            is_allowed: bool) -> int:
        """创建设备记录"""
        result = self.db.execute(text("""
            INSERT INTO devices (
                user_id, subscription_id, device_ua, device_hash, device_fingerprint, 
                device_name, device_type, ip_address, user_agent,
                software_name, software_version, os_name, os_version, device_model, 
                device_brand, is_allowed, is_active, first_seen, last_seen, last_access, access_count
            ) VALUES (
                :user_id, :subscription_id, :device_ua, :device_hash, :device_fingerprint,
                :device_name, :device_type, :ip_address, :user_agent,
                :software_name, :software_version, :os_name, :os_version, :device_model,
                :device_brand, :is_allowed, :is_active, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1
            )
        """), {
            'user_id': user_id,
            'subscription_id': subscription_id,
            'device_ua': f"{user_agent}|{ip_address}",
            'device_hash': device_hash,
            'device_fingerprint': device_hash,  # 使用device_hash作为fingerprint
            'device_name': device_info.get('device_name', 'Unknown Device'),
            'device_type': device_info.get('device_type', 'unknown'),
            'ip_address': ip_address,
            'user_agent': user_agent,
            'software_name': device_info.get('software_name', 'Unknown'),
            'software_version': device_info.get('software_version', ''),
            'os_name': device_info.get('os_name', 'Unknown'),
            'os_version': device_info.get('os_version', ''),
            'device_model': device_info.get('device_model', ''),
            'device_brand': device_info.get('device_brand', ''),
            'is_allowed': is_allowed,
            'is_active': True
        })
        
        return result.lastrowid
    
    def _log_access(self, subscription_id: int, device_id: Optional[int], ip_address: str, 
                   user_agent: str, access_type: str, status_code: int, message: str, subscription_type: str = 'ssr'):
        """记录访问日志
        
        Args:
            subscription_type: 订阅类型 ('ssr' 通用订阅 或 'clash' Clash订阅)
        """
        try:
            # 在 access_type 中包含订阅类型信息，用于统计
            # 浏览器访问和错误访问不添加订阅类型前缀
            if access_type in ('browser_access', 'error'):
                access_type_with_subscription = access_type
            else:
                access_type_with_subscription = f"{subscription_type}_{access_type}"
            self.db.execute(text("""
                INSERT INTO subscription_access_logs (
                    subscription_id, device_id, ip_address, user_agent, 
                    access_type, response_status, response_message, access_time
                ) VALUES (
                    :subscription_id, :device_id, :ip_address, :user_agent,
                    :access_type, :response_status, :response_message, CURRENT_TIMESTAMP
                )
            """), {
                'subscription_id': subscription_id,
                'device_id': device_id,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'access_type': access_type_with_subscription,
                'response_status': status_code,
                'response_message': message
            })
        except Exception as e:
            logger.warning(f"记录访问日志失败: {e}")
    
    def get_user_devices(self, user_id: int, subscription_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取用户设备列表"""
        try:
            query = """
                SELECT d.*, s.subscription_url, u.username, u.email
                FROM devices d
                JOIN subscriptions s ON d.subscription_id = s.id
                JOIN users u ON d.user_id = u.id
                WHERE d.user_id = :user_id
            """
            params = {'user_id': user_id}
            
            if subscription_id:
                query += " AND d.subscription_id = :subscription_id"
                params['subscription_id'] = subscription_id
            
            query += " ORDER BY d.last_seen DESC"
            
            result = self.db.execute(text(query), params).fetchall()
            
            return [
                {
                    'id': row.id,
                    'user_id': row.user_id,
                    'subscription_id': row.subscription_id,
                    'subscription_url': row.subscription_url,
                    'username': row.username,
                    'email': row.email,
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
                    'first_seen': row.first_seen,
                    'last_seen': row.last_seen,
                    'access_count': row.access_count,
                    'created_at': row.created_at,
                    'updated_at': row.updated_at
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"获取用户设备列表失败: {e}", exc_info=True)
            return []
    
    def update_device_status(self, device_id: int, device_data: dict) -> bool:
        """更新设备状态"""
        try:
            # 验证设备存在
            device = self.db.execute(text("""
                SELECT id FROM devices WHERE id = :device_id
            """), {'device_id': device_id}).fetchone()
            
            if not device:
                return False
            
            # 构建更新SQL
            update_fields = []
            params = {'device_id': device_id}
            
            if 'is_allowed' in device_data:
                update_fields.append("is_allowed = :is_allowed")
                params['is_allowed'] = device_data['is_allowed']
            
            if not update_fields:
                return True  # 没有需要更新的字段
            
            # 执行更新
            update_sql = f"""
                UPDATE devices 
                SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = :device_id
            """
            
            self.db.execute(text(update_sql), params)
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"更新设备状态失败: {e}", exc_info=True)
            self.db.rollback()
            return False

    def delete_device(self, device_id: int, user_id: int) -> bool:
        """删除设备"""
        try:
            # 验证设备所有权
            device = self.db.execute(text("""
                SELECT id FROM devices 
                WHERE id = :device_id AND user_id = :user_id
            """), {'device_id': device_id, 'user_id': user_id}).fetchone()
            
            if not device:
                return False
            
            # 删除设备
            self.db.execute(text("""
                DELETE FROM devices WHERE id = :device_id
            """), {'device_id': device_id})
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"删除设备失败: {e}", exc_info=True)
            self.db.rollback()
            return False
    
    def clear_user_devices(self, subscription_id: int) -> int:
        """清理订阅的所有设备"""
        try:
            # 获取要删除的设备数量
            count_result = self.db.execute(text("""
                SELECT COUNT(*) FROM devices WHERE subscription_id = :subscription_id
            """), {'subscription_id': subscription_id}).fetchone()
            
            device_count = count_result[0] if count_result else 0
            
            # 删除所有设备
            self.db.execute(text("""
                DELETE FROM devices WHERE subscription_id = :subscription_id
            """), {'subscription_id': subscription_id})
            
            self.db.commit()
            return device_count
            
        except Exception as e:
            logger.error(f"清理用户设备失败: {e}", exc_info=True)
            self.db.rollback()
            return 0

    def get_subscription_device_stats(self, subscription_id: int) -> Dict[str, int]:
        """获取订阅设备统计"""
        try:
            result = self.db.execute(text("""
                SELECT 
                    COUNT(*) as total_devices,
                    SUM(CASE WHEN is_allowed = 1 THEN 1 ELSE 0 END) as allowed_devices,
                    SUM(CASE WHEN is_allowed = 0 THEN 1 ELSE 0 END) as blocked_devices
                FROM devices 
                WHERE subscription_id = :subscription_id
            """), {'subscription_id': subscription_id}).fetchone()
            
            return {
                'total_devices': result.total_devices or 0,
                'allowed_devices': result.allowed_devices or 0,
                'blocked_devices': result.blocked_devices or 0
            }
        except Exception as e:
            logger.error(f"获取订阅设备统计失败: {e}", exc_info=True)
            return {'total_devices': 0, 'allowed_devices': 0, 'blocked_devices': 0}
