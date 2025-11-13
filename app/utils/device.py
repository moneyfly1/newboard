"""设备工具函数"""
import hashlib
import re
from typing import Optional

from user_agents import parse


def generate_device_fingerprint(user_agent: str, ip_address: Optional[str] = None) -> str:
    """生成设备指纹"""
    ua = parse(user_agent)

    device_info = {
        'browser': ua.browser.family,
        'browser_version': ua.browser.version_string,
        'os': ua.os.family,
        'os_version': ua.os.version_string,
        'device': ua.device.family,
        'ip': ip_address or 'unknown'
    }

    fingerprint_str = (
        f"{device_info['browser']}_{device_info['browser_version']}_"
        f"{device_info['os']}_{device_info['os_version']}_"
        f"{device_info['device']}_{device_info['ip']}"
    )

    fingerprint = hashlib.sha256(fingerprint_str.encode()).hexdigest()
    return fingerprint


def detect_device_type(user_agent: str) -> str:
    """检测设备类型"""
    ua = parse(user_agent)

    if ua.is_mobile:
        return "mobile"
    elif ua.is_tablet:
        return "tablet"
    else:
        return "desktop"


def extract_device_name(user_agent: str) -> str:
    """提取设备名称"""
    ua = parse(user_agent)

    if ua.is_mobile:
        if ua.device.family != "Other":
            return f"{ua.device.family} {ua.os.family}"
        else:
            return f"Mobile {ua.os.family}"
    elif ua.is_tablet:
        if ua.device.family != "Other":
            return f"{ua.device.family} {ua.os.family}"
        else:
            return f"Tablet {ua.os.family}"
    else:
        return f"Desktop {ua.os.family}"


def is_valid_ip_address(ip: str) -> bool:
    """验证IP地址格式"""
    ipv4_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    ipv6_pattern = r'^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'

    return bool(re.match(ipv4_pattern, ip) or re.match(ipv6_pattern, ip))


def sanitize_user_agent(user_agent: str) -> str:
    """清理User-Agent字符串"""
    if not user_agent:
        return "Unknown"

    sanitized = re.sub(r'[^\w\s\-\.\/\(\)]', '', user_agent)

    if len(sanitized) > 500:
        sanitized = sanitized[:500]

    return sanitized or "Unknown"