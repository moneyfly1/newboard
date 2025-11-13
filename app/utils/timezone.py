"""时区工具函数 - 统一使用北京时间（UTC+8）"""
from datetime import datetime, timedelta, timezone
from typing import Optional

BEIJING_TZ = timezone(timedelta(hours=8))


def get_beijing_time() -> datetime:
    """获取当前北京时间（UTC+8）"""
    return datetime.now(BEIJING_TZ)


def get_beijing_time_str(format: str = '%Y-%m-%d %H:%M:%S') -> str:
    """获取当前北京时间的字符串格式"""
    return get_beijing_time().strftime(format)


def utc_to_beijing(utc_dt: datetime) -> datetime:
    """将UTC时间转换为北京时间"""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)

    return utc_dt.astimezone(BEIJING_TZ)


def beijing_to_utc(beijing_dt: datetime) -> datetime:
    """将北京时间转换为UTC时间"""
    if beijing_dt.tzinfo is None:
        beijing_dt = beijing_dt.replace(tzinfo=BEIJING_TZ)

    return beijing_dt.astimezone(timezone.utc)


def format_beijing_time(dt: Optional[datetime], format: str = '%Y-%m-%d %H:%M:%S') -> Optional[str]:
    """格式化datetime为北京时间字符串"""
    if dt is None:
        return None

    if isinstance(dt, str):
        return dt

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    beijing_dt = dt.astimezone(BEIJING_TZ)
    return beijing_dt.strftime(format)
