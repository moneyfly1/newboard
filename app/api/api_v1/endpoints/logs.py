from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from datetime import datetime, timedelta
from fastapi.responses import FileResponse
from app.schemas.common import ResponseBase
from app.utils.security import get_current_admin_user
from app.services.logging import log_manager
from app.api.api_v1.endpoints.common import handle_api_error

router = APIRouter()

def _validate_log_filename(filename: str):
    if not filename.endswith('.log'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能操作.log文件")

def _parse_date(date_str: Optional[str]):
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="日期格式错误，请使用ISO格式")

@router.get("/files", response_model=ResponseBase)
@handle_api_error("获取日志文件列表")
def get_log_files(current_admin = Depends(get_current_admin_user)) -> Any:
    log_files = log_manager.get_log_files()
    return ResponseBase(data={"log_files": log_files, "count": len(log_files)})

@router.get("/read/{filename}", response_model=ResponseBase)
@handle_api_error("读取日志文件")
def read_log_file(filename: str, lines: int = Query(100, ge=1, le=1000), current_admin = Depends(get_current_admin_user)) -> Any:
    _validate_log_filename(filename)
    log_content = log_manager.read_log_file(filename, lines)
    return ResponseBase(data={"filename": filename, "lines": len(log_content), "content": log_content})

@router.get("/search", response_model=ResponseBase)
@handle_api_error("搜索日志")
def search_logs(query: str = Query(..., min_length=1), log_type: str = Query("app", regex="^(app|error|access|security|all)$"), start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None), current_admin = Depends(get_current_admin_user)) -> Any:
    start_dt = _parse_date(start_date)
    end_dt = _parse_date(end_date)
    results = log_manager.search_logs(query, log_type, start_dt, end_dt)
    return ResponseBase(data={"query": query, "log_type": log_type, "results": results, "count": len(results)})

@router.get("/stats", response_model=ResponseBase)
@handle_api_error("获取日志统计")
def get_log_stats(current_admin = Depends(get_current_admin_user)) -> Any:
    stats = log_manager.get_log_stats()
    return ResponseBase(data=stats)

@router.post("/cleanup", response_model=ResponseBase)
@handle_api_error("清理旧日志")
def cleanup_old_logs(days: int = Query(30, ge=1, le=365), current_admin = Depends(get_current_admin_user)) -> Any:
    result = log_manager.cleanup_old_logs(days)
    if result["success"]:
        return ResponseBase(data=result, message=f"清理完成，删除了 {result['deleted_count']} 个旧日志文件")
    return ResponseBase(success=False, message=f"清理失败: {result.get('error', '未知错误')}")

@router.delete("/delete/{filename}", response_model=ResponseBase)
@handle_api_error("删除日志文件")
def delete_log_file(filename: str, current_admin = Depends(get_current_admin_user)) -> Any:
    _validate_log_filename(filename)
    log_path = log_manager.log_dir / filename
    if not log_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="日志文件不存在")
    log_path.unlink()
    return ResponseBase(message="日志文件删除成功")

@router.get("/download/{filename}")
@handle_api_error("下载日志文件")
def download_log_file(filename: str, current_admin = Depends(get_current_admin_user)):
    _validate_log_filename(filename)
    log_path = log_manager.log_dir / filename
    if not log_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="日志文件不存在")
    return FileResponse(path=str(log_path), filename=filename, media_type='text/plain')

@router.get("/realtime/{log_type}", response_model=ResponseBase)
@handle_api_error("获取实时日志")
def get_realtime_logs(log_type: str = Path(..., regex="^(app|error|access|security)$"), lines: int = Query(50, ge=1, le=200), current_admin = Depends(get_current_admin_user)) -> Any:
    filename = f"{log_type}.log"
    log_content = log_manager.read_log_file(filename, lines)
    return ResponseBase(data={"log_type": log_type, "lines": len(log_content), "content": log_content, "timestamp": datetime.now().isoformat()})

@router.get("/errors/recent", response_model=ResponseBase)
@handle_api_error("获取最近错误日志")
def get_recent_errors(hours: int = Query(24, ge=1, le=168), current_admin = Depends(get_current_admin_user)) -> Any:
    start_date = datetime.now() - timedelta(hours=hours)
    results = log_manager.search_logs("ERROR", "error", start_date)
    return ResponseBase(data={"errors": results, "count": len(results), "hours": hours, "start_date": start_date.isoformat()})

@router.get("/security/recent", response_model=ResponseBase)
@handle_api_error("获取最近安全事件")
def get_recent_security_events(hours: int = Query(24, ge=1, le=168), current_admin = Depends(get_current_admin_user)) -> Any:
    start_date = datetime.now() - timedelta(hours=hours)
    results = log_manager.search_logs("SECURITY_EVENT", "security", start_date)
    return ResponseBase(data={"security_events": results, "count": len(results), "hours": hours, "start_date": start_date.isoformat()})
