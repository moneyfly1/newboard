from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.services.email import EmailService
from app.services.email_queue_processor import get_email_queue_processor
from app.utils.security import get_current_admin_user
from app.schemas.common import ResponseBase
from app.api.api_v1.endpoints.common import handle_api_error

router = APIRouter()

@router.get("/overview")
@handle_api_error("获取邮件概览统计")
def get_email_overview_stats(db: Session = Depends(get_db), current_user = Depends(get_current_admin_user)):
    email_service = EmailService(db)
    queue_processor = get_email_queue_processor()
    basic_stats = email_service.get_email_stats()
    queue_stats = queue_processor.get_queue_stats()
    overview = {
        "basic_stats": basic_stats,
        "queue_stats": queue_stats,
        "system_status": {
            "email_enabled": email_service.is_email_enabled(),
            "queue_processor_running": queue_processor.is_running,
            "smtp_configured": bool(email_service.get_smtp_config())
        }
    }
    return ResponseBase(data=overview)

@router.get("/daily")
@handle_api_error("获取每日统计")
def get_daily_email_stats(days: int = 7, db: Session = Depends(get_db), current_user = Depends(get_current_admin_user)):
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="天数必须在1-365之间")
    email_service = EmailService(db)
    daily_stats = email_service.get_daily_email_stats(days)
    return ResponseBase(data=daily_stats)

@router.get("/by-type")
@handle_api_error("获取类型统计")
def get_email_stats_by_type(db: Session = Depends(get_db), current_user = Depends(get_current_admin_user)):
    email_service = EmailService(db)
    type_stats = email_service.get_email_stats_by_type()
    return ResponseBase(data=type_stats)

@router.get("/queue/status")
@handle_api_error("获取队列状态")
def get_queue_processor_status(current_user = Depends(get_current_admin_user)):
    queue_processor = get_email_queue_processor()
    status_info = {
        "is_running": queue_processor.is_running,
        "batch_size": queue_processor.batch_size,
        "processing_interval": queue_processor.processing_interval,
        "max_retries": queue_processor.max_retries,
        "retry_delays": queue_processor.retry_delays
    }
    return ResponseBase(data=status_info)

@router.post("/queue/start")
@handle_api_error("启动队列处理器")
def start_queue_processor(current_user = Depends(get_current_admin_user)):
    queue_processor = get_email_queue_processor()
    queue_processor.start_processing()
    return ResponseBase(message="邮件队列处理器已启动")

@router.post("/queue/stop")
@handle_api_error("停止队列处理器")
def stop_queue_processor(current_user = Depends(get_current_admin_user)):
    queue_processor = get_email_queue_processor()
    queue_processor.stop_processing()
    return ResponseBase(message="邮件队列处理器已停止")

@router.post("/queue/pause")
@handle_api_error("暂停队列处理器")
def pause_queue_processor(duration_minutes: int = 0, current_user = Depends(get_current_admin_user)):
    queue_processor = get_email_queue_processor()
    queue_processor.pause_processing(duration_minutes)
    message = f"邮件队列处理器已暂停" + (f"，将在 {duration_minutes} 分钟后自动恢复" if duration_minutes > 0 else "")
    return ResponseBase(message=message)

@router.post("/queue/resume")
@handle_api_error("恢复队列处理器")
def resume_queue_processor(current_user = Depends(get_current_admin_user)):
    queue_processor = get_email_queue_processor()
    queue_processor.resume_processing()
    return ResponseBase(message="邮件队列处理器已恢复")

@router.post("/queue/retry-failed")
@handle_api_error("重试失败邮件")
def retry_failed_emails(email_ids: List[int] = None, current_user = Depends(get_current_admin_user)):
    queue_processor = get_email_queue_processor()
    result = queue_processor.retry_failed_emails(email_ids)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    message = f"成功重试 {result['retried']} 封失败邮件" + (f"（共 {len(email_ids)} 封）" if email_ids else f"（共 {result['total_failed']} 封）")
    return ResponseBase(message=message, data=result)

@router.get("/queue/stats")
@handle_api_error("获取队列统计")
def get_queue_detailed_stats(current_user = Depends(get_current_admin_user)):
    queue_processor = get_email_queue_processor()
    queue_stats = queue_processor.get_queue_stats()
    return ResponseBase(data=queue_stats)

@router.post("/cleanup")
@handle_api_error("清理旧邮件")
def cleanup_old_emails(days: int = 30, db: Session = Depends(get_db), current_user = Depends(get_current_admin_user)):
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="天数必须在1-365之间")
    email_service = EmailService(db)
    deleted_count = email_service.cleanup_old_emails(days)
    return ResponseBase(message=f"成功清理 {deleted_count} 封旧邮件")

@router.get("/smtp/config")
@handle_api_error("获取SMTP配置")
def get_smtp_config(db: Session = Depends(get_db), current_user = Depends(get_current_admin_user)):
    email_service = EmailService(db)
    smtp_config = email_service.get_smtp_config()
    safe_config = {
        "host": smtp_config.get("host"),
        "port": smtp_config.get("port"),
        "encryption": smtp_config.get("encryption"),
        "from_name": smtp_config.get("from_name"),
        "from_email": smtp_config.get("from_email"),
        "username": smtp_config.get("username", "")[:3] + "***" if smtp_config.get("username") else "",
        "password": "***" if smtp_config.get("password") else "",
        "enabled": email_service.is_email_enabled()
    }
    return ResponseBase(data=safe_config)

@router.get("/performance")
@handle_api_error("获取性能统计")
def get_email_performance_stats(db: Session = Depends(get_db), current_user = Depends(get_current_admin_user)):
    email_service = EmailService(db)
    queue_processor = get_email_queue_processor()
    basic_stats = email_service.get_email_stats()
    queue_stats = queue_processor.get_queue_stats()
    total_emails = basic_stats["total"]
    success_rate = (basic_stats["sent"] / total_emails) * 100 if total_emails > 0 else 0
    performance_stats = {
        "total_emails": total_emails,
        "success_rate": round(success_rate, 2),
        "pending_rate": round((basic_stats["pending"] / total_emails) * 100, 2) if total_emails > 0 else 0,
        "failure_rate": round((basic_stats["failed"] / total_emails) * 100, 2) if total_emails > 0 else 0,
        "average_retry_count": queue_stats.get("retry_distribution", {}),
        "queue_health": "healthy" if queue_stats.get("pending", 0) < 100 else "warning" if queue_stats.get("pending", 0) < 500 else "critical"
    }
    return ResponseBase(data=performance_stats)
