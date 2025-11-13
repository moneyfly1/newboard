from typing import Any
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.utils.security import get_current_admin_user
from app.schemas.common import ResponseBase
from app.services.config_update_service import ConfigUpdateService

router = APIRouter()
_config_update_service = None

def get_config_update_service(db: Session) -> ConfigUpdateService:
    global _config_update_service
    _config_update_service = ConfigUpdateService(db)
    return _config_update_service

def _service_operation(operation_name: str, operation_func, *args, **kwargs):
    try:
        result = operation_func(*args, **kwargs)
        return ResponseBase(data=result) if result is not None else ResponseBase(message=f"{operation_name}成功")
    except Exception as e:
        return ResponseBase(success=False, message=f"{operation_name}失败: {str(e)}")

@router.get("/status", response_model=ResponseBase)
def get_config_update_status(db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    return _service_operation("获取状态", lambda: get_config_update_service(db).get_status())

@router.post("/start", response_model=ResponseBase)
def start_config_update(background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    try:
        service = get_config_update_service(db)
        if service.is_running():
            return ResponseBase(success=False, message="配置更新任务已在运行中")
        background_tasks.add_task(service.run_update_task)
        return ResponseBase(message="配置更新任务已启动")
    except Exception as e:
        return ResponseBase(success=False, message=f"启动失败: {str(e)}")

@router.post("/stop", response_model=ResponseBase)
def stop_config_update(db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    return _service_operation("停止", lambda: get_config_update_service(db).stop_update_task())

@router.get("/logs", response_model=ResponseBase)
def get_update_logs(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    return _service_operation("获取日志", lambda: get_config_update_service(db).get_logs(limit=limit))

@router.get("/config", response_model=ResponseBase)
def get_update_config(db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    return _service_operation("获取配置", lambda: get_config_update_service(db).get_config())

@router.put("/config", response_model=ResponseBase)
def update_config(config_data: dict, db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    return _service_operation("更新配置", lambda: get_config_update_service(db).update_config(config_data))

@router.get("/node-sources", response_model=ResponseBase)
def get_node_sources(db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    return _service_operation("获取节点源配置", lambda: get_config_update_service(db).get_node_sources())

@router.put("/node-sources", response_model=ResponseBase)
def update_node_sources(sources_data: dict, db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    return _service_operation("更新节点源配置", lambda: get_config_update_service(db).update_node_sources(sources_data))

@router.get("/filter-keywords", response_model=ResponseBase)
def get_filter_keywords(db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    return _service_operation("获取过滤关键词配置", lambda: get_config_update_service(db).get_filter_keywords())

@router.put("/filter-keywords", response_model=ResponseBase)
def update_filter_keywords(keywords_data: dict, db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    return _service_operation("更新过滤关键词配置", lambda: get_config_update_service(db).update_filter_keywords(keywords_data))

@router.get("/files", response_model=ResponseBase)
def get_generated_files(db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    return _service_operation("获取文件信息", lambda: get_config_update_service(db).get_generated_files())

@router.get("/schedule", response_model=ResponseBase)
def get_schedule_config(db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    return _service_operation("获取定时配置", lambda: get_config_update_service(db).get_schedule_config())

@router.put("/schedule", response_model=ResponseBase)
def update_schedule_config(schedule_data: dict, db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    return _service_operation("更新定时配置", lambda: get_config_update_service(db).update_schedule_config(schedule_data))

@router.post("/schedule/start", response_model=ResponseBase)
def start_scheduled_task(db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    return _service_operation("启动定时任务", lambda: get_config_update_service(db).start_scheduled_task())

@router.post("/schedule/stop", response_model=ResponseBase)
def stop_scheduled_task(db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    return _service_operation("停止定时任务", lambda: get_config_update_service(db).stop_scheduled_task())

@router.post("/logs/clear", response_model=ResponseBase)
def clear_logs(db: Session = Depends(get_db), current_admin = Depends(get_current_admin_user)) -> Any:
    try:
        service = get_config_update_service(db)
        service.logs.clear()
        from app.models.config import SystemConfig
        import json
        logs_record = db.query(SystemConfig).filter(SystemConfig.key == "config_update_logs").first()
        if logs_record:
            logs_record.value = json.dumps([])
            db.commit()
        return ResponseBase(message="日志已清理")
    except Exception as e:
        return ResponseBase(success=False, message=f"清理日志失败: {str(e)}")
