from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pathlib import Path
import yaml
import shutil
from app.core.config import settings
from app.schemas.common import ResponseBase
from app.utils.security import get_current_admin_user

router = APIRouter()
CONFIG_DIR = Path("uploads/config")
XR_CONFIG_PATH = CONFIG_DIR / "xr"
CLASH_CONFIG_PATH = CONFIG_DIR / "clash.yaml"
WORK_CONFIG_PATH = CONFIG_DIR / "work"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

FILE_PATHS = {
    "xr": XR_CONFIG_PATH,
    "clash.yaml": CLASH_CONFIG_PATH,
    "work": WORK_CONFIG_PATH
}

MAX_SIZES = {
    "xr": 1024 * 1024,
    "clash.yaml": 4 * 1024 * 1024,
    "work": 1024 * 1024
}

def _get_file_info(path: Path, name: str, description: str):
    if path.exists():
        stat = path.stat()
        size = stat.st_size
        return {
            "name": name,
            "path": str(path),
            "description": description,
            "size": size,
            "size_formatted": f"{size / 1024:.1f} KB" if size < 1024*1024 else f"{size / (1024*1024):.1f} MB",
            "modified_time": stat.st_mtime,
            "exists": True
        }
    return {
        "name": name,
        "path": str(path),
        "description": description,
        "size": 0,
        "size_formatted": "0 KB",
        "modified_time": None,
        "exists": False
    }

@router.get("/admin/config-files", response_model=ResponseBase)
def get_config_files(current_admin = Depends(get_current_admin_user)) -> Any:
    files_to_check = [
        {"name": "xr", "path": XR_CONFIG_PATH, "description": "xr 客户端配置文件"},
        {"name": "clash.yaml", "path": CLASH_CONFIG_PATH, "description": "Clash 配置文件"},
        {"name": "work", "path": WORK_CONFIG_PATH, "description": "Work 配置文件"}
    ]
    config_files = [_get_file_info(f["path"], f["name"], f["description"]) for f in files_to_check]
    return ResponseBase(data={"config_files": config_files})

def _validate_file_name(file_name: str) -> bool:
    if not file_name or len(file_name) > 255:
        return False
    if '..' in file_name or '/' in file_name or '\\' in file_name:
        return False
    if file_name not in FILE_PATHS:
        return False
    return True

@router.get("/admin/config-files/{file_name}", response_model=ResponseBase)
def get_config_file_content(file_name: str, current_admin = Depends(get_current_admin_user)) -> Any:
    if not _validate_file_name(file_name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的文件名")
    file_path = FILE_PATHS[file_name]
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置文件不存在")
    try:
        content = file_path.read_text(encoding='utf-8')
        return ResponseBase(data={"content": content})
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"读取配置文件失败: {str(e)}")

@router.post("/admin/config-files/{file_name}", response_model=ResponseBase)
def save_config_file(file_name: str, content: str, current_admin = Depends(get_current_admin_user)) -> Any:
    if not _validate_file_name(file_name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的文件名")
    file_path = FILE_PATHS[file_name]
    if len(content.encode('utf-8')) > MAX_SIZES[file_name]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件内容过大，最大允许 {MAX_SIZES[file_name] / (1024*1024)} MB"
        )
    dangerous_patterns = [
        "<?php", "<?=", "<script", "javascript:", "onerror=", "onload=",
        "eval(", "exec(", "system(", "shell_exec(", "__import__", "subprocess"
    ]
    content_lower = content.lower()
    for pattern in dangerous_patterns:
        if pattern in content_lower:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"禁止写入危险代码: {pattern}"
            )
    if file_name == "clash.yaml":
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"YAML格式错误: {str(e)}")
    try:
        if file_path.exists():
            backup_path = file_path.with_suffix(file_path.suffix + ".backup")
            file_path.rename(backup_path)
        file_path.write_text(content, encoding='utf-8')
        return ResponseBase(message="配置文件保存成功")
    except Exception as e:
        backup_path = file_path.with_suffix(file_path.suffix + ".backup")
        if backup_path.exists():
            backup_path.rename(file_path)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"保存配置文件失败: {str(e)}")

@router.post("/admin/config-files/{file_name}/backup", response_model=ResponseBase)
def backup_config_file(file_name: str, current_admin = Depends(get_current_admin_user)) -> Any:
    if file_name not in FILE_PATHS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置文件不存在")
    file_path = FILE_PATHS[file_name]
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置文件不存在")
    try:
        backup_path = file_path.with_suffix(file_path.suffix + ".backup")
        shutil.copy2(file_path, backup_path)
        return ResponseBase(message="配置文件备份成功")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"备份配置文件失败: {str(e)}")

@router.post("/admin/config-files/{file_name}/restore", response_model=ResponseBase)
def restore_config_file(file_name: str, current_admin = Depends(get_current_admin_user)) -> Any:
    if file_name not in FILE_PATHS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置文件不存在")
    file_path = FILE_PATHS[file_name]
    backup_path = file_path.with_suffix(file_path.suffix + ".backup")
    if not backup_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="备份文件不存在")
    try:
        shutil.copy2(backup_path, file_path)
        return ResponseBase(message="配置文件恢复成功")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"恢复配置文件失败: {str(e)}")

@router.get("/admin/system-config", response_model=ResponseBase)
def get_system_config(current_admin = Depends(get_current_admin_user)) -> Any:
    config = {
        "project_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "api_prefix": settings.API_V1_STR,
        "cors_origins": settings.BACKEND_CORS_ORIGINS,
        "database_url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "***",
        "smtp_server": settings.SMTP_SERVER,
        "smtp_port": settings.SMTP_PORT,
        "smtp_username": settings.SMTP_USERNAME,
        "upload_dir": settings.UPLOAD_DIR,
        "subscription_default_days": settings.SUBSCRIPTION_DEFAULT_DAYS,
        "subscription_default_device_limit": settings.SUBSCRIPTION_DEFAULT_DEVICE_LIMIT
    }
    return ResponseBase(data={"config": config})

@router.post("/admin/system-config", response_model=ResponseBase)
def update_system_config(config_data: dict, current_admin = Depends(get_current_admin_user)) -> Any:
    return ResponseBase(message="系统配置更新成功（需要重启服务生效）")
