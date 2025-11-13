from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from app.core.database import get_db
from app.schemas.common import ResponseBase
from app.utils.security import get_current_admin_user
from app.services.monitoring import system_monitor, api_monitor, DatabaseMonitor
from app.api.api_v1.endpoints.common import handle_api_error

router = APIRouter()

@router.get("/system/health", response_model=ResponseBase)
@handle_api_error("获取系统健康状态")
def get_system_health(current_admin = Depends(get_current_admin_user)) -> Any:
    health_status = system_monitor.check_system_health()
    return ResponseBase(data=health_status)

@router.get("/system/metrics", response_model=ResponseBase)
@handle_api_error("获取系统指标")
def get_system_metrics(current_admin = Depends(get_current_admin_user)) -> Any:
    metrics = system_monitor.get_system_metrics()
    return ResponseBase(data=metrics)

@router.get("/system/metrics/history", response_model=ResponseBase)
@handle_api_error("获取历史指标")
def get_metrics_history(hours: int = 24, current_admin = Depends(get_current_admin_user)) -> Any:
    if hours > 168:
        hours = 168
    history = system_monitor.get_metrics_history(hours)
    return ResponseBase(data={"history": history, "hours": hours, "count": len(history)})

@router.get("/database/health", response_model=ResponseBase)
@handle_api_error("获取数据库健康状态")
def get_database_health(db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    db_monitor = DatabaseMonitor(db)
    health_status = db_monitor.check_database_health()
    return ResponseBase(data=health_status)

@router.get("/database/stats", response_model=ResponseBase)
@handle_api_error("获取数据库统计")
def get_database_stats(db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    db_monitor = DatabaseMonitor(db)
    stats = db_monitor.get_database_stats()
    return ResponseBase(data=stats)

@router.get("/api/stats", response_model=ResponseBase)
@handle_api_error("获取API统计")
def get_api_stats(current_admin = Depends(get_current_admin_user)) -> Any:
    stats = api_monitor.get_api_stats()
    return ResponseBase(data=stats)

@router.get("/overview", response_model=ResponseBase)
@handle_api_error("获取监控概览")
def get_monitoring_overview(db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    system_health = system_monitor.check_system_health()
    db_monitor = DatabaseMonitor(db)
    db_health = db_monitor.check_database_health()
    db_stats = db_monitor.get_database_stats()
    api_stats = api_monitor.get_api_stats()
    current_metrics = system_monitor.get_system_metrics()
    overview = {
        "timestamp": datetime.now().isoformat(),
        "system": {"health": system_health, "current_metrics": current_metrics},
        "database": {"health": db_health, "stats": db_stats},
        "api": {"stats": api_stats},
        "summary": {
            "overall_status": "healthy" if system_health["status"] == "healthy" and db_health["status"] == "healthy" else "warning",
            "total_endpoints": len(api_stats),
            "total_requests": sum(stat["total_requests"] for stat in api_stats),
            "total_errors": sum(stat["total_errors"] for stat in api_stats)
        }
    }
    return ResponseBase(data=overview)

@router.post("/system/metrics/collect", response_model=ResponseBase)
@handle_api_error("收集系统指标")
def collect_system_metrics(current_admin = Depends(get_current_admin_user)) -> Any:
    metrics = system_monitor.get_system_metrics()
    return ResponseBase(data=metrics, message="系统指标收集成功")

@router.get("/alerts", response_model=ResponseBase)
@handle_api_error("获取系统告警")
def get_system_alerts(current_admin = Depends(get_current_admin_user)) -> Any:
    alerts = []
    system_health = system_monitor.check_system_health()
    if system_health["status"] != "healthy":
        alerts.append({
            "type": "system",
            "level": system_health["status"],
            "message": system_health["message"],
            "details": system_health.get("errors", []) + system_health.get("warnings", [])
        })
    api_stats = api_monitor.get_api_stats()
    for stat in api_stats:
        if stat["total_requests"] > 0:
            error_rate = stat["total_errors"] / stat["total_requests"]
            if error_rate > 0.1:
                alerts.append({
                    "type": "api",
                    "level": "warning",
                    "message": f"API端点 {stat['endpoint']} 错误率过高",
                    "details": [f"错误率: {error_rate:.2%}", f"总请求: {stat['total_requests']}", f"错误数: {stat['total_errors']}"]
                })
    return ResponseBase(data={"alerts": alerts, "count": len(alerts), "timestamp": datetime.now().isoformat()})
