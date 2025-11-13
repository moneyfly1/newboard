"""系统监控服务"""
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List

import psutil
from fastapi import Request
from sqlalchemy.orm import Session

from app.core.cache import redis_cache
from app.models.order import Order
from app.models.payment import PaymentTransaction
from app.models.subscription import Subscription
from app.models.user import User

logger = logging.getLogger(__name__)

CACHE_KEY_METRICS_HISTORY = "monitoring:metrics_history"
CACHE_KEY_LATEST_METRICS = "monitoring:latest_metrics"


class SystemMonitor:
    """系统监控类"""

    def __init__(self):
        self.max_history = 100
        self._fallback_history = []

    def get_system_metrics(self) -> Dict:
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            process = psutil.Process()
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "cpu": {"percent": cpu_percent, "count": psutil.cpu_count(), "load_avg": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None},
                "memory": {"percent": memory.percent, "used": memory.used, "total": memory.total, "available": memory.available},
                "disk": {"percent": (disk.used / disk.total) * 100, "used": disk.used, "total": disk.total, "free": disk.free},
                "network": {"bytes_sent": network.bytes_sent, "bytes_recv": network.bytes_recv, "packets_sent": network.packets_sent, "packets_recv": network.packets_recv},
                "process": {"memory": process.memory_info().rss, "cpu_percent": process.cpu_percent(), "pid": process.pid}
            }
            
            # 保存到 Redis
            if redis_cache.is_connected():
                try:
                    history_key = CACHE_KEY_METRICS_HISTORY
                    latest_key = CACHE_KEY_LATEST_METRICS
                    
                    # 保存最新指标
                    redis_cache.set(latest_key, metrics, ttl=3600)
                    
                    # 添加到历史记录列表
                    history = redis_cache.get(history_key, default=[])
                    if not isinstance(history, list):
                        history = []
                    
                    history.append(metrics)
                    if len(history) > self.max_history:
                        history = history[-self.max_history:]
                    
                    redis_cache.set(history_key, history, ttl=86400)
                except Exception as e:
                    logger.warning(f"保存监控指标到 Redis 失败: {e}")
            
            # 后备内存缓存
            self._fallback_history.append(metrics)
            if len(self._fallback_history) > self.max_history:
                self._fallback_history.pop(0)
            
            return metrics
        except Exception as e:
            logger.error(f"获取系统指标失败: {e}")
            return {}

    def get_metrics_history(self, hours: int = 24, limit: int = 100) -> List[Dict]:
        """获取监控指标历史记录"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # 从 Redis 获取
        if redis_cache.is_connected():
            try:
                history = redis_cache.get(CACHE_KEY_METRICS_HISTORY, default=[])
                if isinstance(history, list) and history:
                    filtered = [
                        metric for metric in history
                        if datetime.fromisoformat(metric["timestamp"]) > cutoff_time
                    ]
                    return filtered[-limit:] if len(filtered) > limit else filtered
            except Exception as e:
                logger.warning(f"从 Redis 获取监控历史失败: {e}")
        
        # 后备内存缓存
        filtered = [
            metric for metric in self._fallback_history
            if datetime.fromisoformat(metric["timestamp"]) > cutoff_time
        ]
        return filtered[-limit:] if len(filtered) > limit else filtered

    def clear_old_metrics(self, hours: int = 24):
        """清理旧的监控指标，释放内存"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # 清理 Redis 缓存
        if redis_cache.is_connected():
            try:
                history = redis_cache.get(CACHE_KEY_METRICS_HISTORY, default=[])
                if isinstance(history, list):
                    filtered = [
                        metric for metric in history
                        if datetime.fromisoformat(metric["timestamp"]) > cutoff_time
                    ]
                    if len(filtered) > self.max_history:
                        filtered = filtered[-self.max_history:]
                    redis_cache.set(CACHE_KEY_METRICS_HISTORY, filtered, ttl=86400)
            except Exception as e:
                logger.warning(f"清理 Redis 监控历史失败: {e}")
        
        # 清理内存缓存
        self._fallback_history = [
            metric for metric in self._fallback_history
            if datetime.fromisoformat(metric["timestamp"]) > cutoff_time
        ]
        if len(self._fallback_history) > self.max_history:
            self._fallback_history = self._fallback_history[-self.max_history:]

    def check_system_health(self) -> Dict:
        metrics = self.get_system_metrics()
        if not metrics:
            return {"status": "error", "message": "无法获取系统指标"}
        warnings = []
        errors = []
        checks = [("cpu", 90, 80, "CPU使用率"), ("memory", 95, 85, "内存使用率"), ("disk", 95, 85, "磁盘使用率")]
        for resource, error_threshold, warning_threshold, name in checks:
            percent = metrics[resource]["percent"]
            if percent > error_threshold:
                errors.append(f"{name}过高: {percent:.1f}%")
            elif percent > warning_threshold:
                warnings.append(f"{name}较高: {percent:.1f}%")
        if errors:
            status, message = "error", "系统存在严重问题"
        elif warnings:
            status, message = "warning", "系统存在潜在问题"
        else:
            status, message = "healthy", "系统运行正常"
        return {"status": status, "message": message, "warnings": warnings, "errors": errors, "metrics": metrics}

class DatabaseMonitor:
    """数据库监控类"""

    def __init__(self, db: Session):
        self.db = db

    def get_database_stats(self) -> Dict:
        """获取数据库统计信息（使用count避免加载所有数据）"""
        try:
            return {
                "users": {
                    "total": self.db.query(User).count(),
                    "active": self.db.query(User).filter(User.is_active == True).count(),
                    "admins": self.db.query(User).filter(User.is_admin == True).count()
                },
                "subscriptions": {
                    "total": self.db.query(Subscription).count(),
                    "active": self.db.query(Subscription).filter(Subscription.is_active == True).count()
                },
                "orders": {
                    "total": self.db.query(Order).count(),
                    "paid": self.db.query(Order).filter(Order.status == "paid").count()
                },
                "payments": {
                    "total": self.db.query(PaymentTransaction).count(),
                    "successful": self.db.query(PaymentTransaction).filter(PaymentTransaction.status == "success").count()
                }
            }
        except Exception as e:
            logger.error(f"获取数据库统计失败: {e}")
            return {}

    def check_database_health(self) -> Dict:
        try:
            from sqlalchemy import text
            self.db.execute(text("SELECT 1"))
            result = self.db.execute(text("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"))
            db_size = result.fetchone()[0] if result else 0
            result = self.db.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'"))
            table_count = result.fetchone()[0] if result else 0
            return {"status": "healthy", "message": "数据库连接正常", "size_bytes": db_size, "table_count": table_count}
        except Exception as e:
            logger.error(f"数据库健康检查失败: {e}")
            return {"status": "error", "message": f"数据库连接失败: {str(e)}"}

class APIMonitor:
    def __init__(self):
        self.request_counts = {}
        self.response_times = {}
        self.error_counts = {}

    def record_request(self, endpoint: str, method: str, response_time: float, status_code: int):
        key = f"{method}:{endpoint}"
        self.request_counts[key] = self.request_counts.get(key, 0) + 1
        if key not in self.response_times:
            self.response_times[key] = []
        self.response_times[key].append(response_time)
        if len(self.response_times[key]) > 100:
            self.response_times[key] = self.response_times[key][-100:]
        if status_code >= 400:
            self.error_counts[key] = self.error_counts.get(key, 0) + 1

    def get_api_stats(self) -> List[Dict]:
        stats = {}
        for key in self.request_counts:
            method, endpoint = key.split(":", 1)
            if endpoint not in stats:
                stats[endpoint] = {"endpoint": endpoint, "methods": {}, "total_requests": 0, "total_errors": 0, "avg_response_time": 0}
            times = self.response_times.get(key, [0])
            avg_time = sum(times) / len(times) if times else 0
            stats[endpoint]["methods"][method] = {"requests": self.request_counts[key], "errors": self.error_counts.get(key, 0), "avg_response_time": avg_time}
            stats[endpoint]["total_requests"] += self.request_counts[key]
            stats[endpoint]["total_errors"] += self.error_counts.get(key, 0)
        for endpoint in stats:
            total_time = sum(method_data["avg_response_time"] * method_data["requests"] for method_data in stats[endpoint]["methods"].values())
            total_count = sum(method_data["requests"] for method_data in stats[endpoint]["methods"].values())
            if total_count > 0:
                stats[endpoint]["avg_response_time"] = total_time / total_count
        return list(stats.values())

system_monitor = SystemMonitor()
api_monitor = APIMonitor()

async def monitoring_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    response_time = time.time() - start_time
    api_monitor.record_request(request.url.path, request.method, response_time, response.status_code)
    response.headers["X-Response-Time"] = f"{response_time:.3f}s"
    return response
