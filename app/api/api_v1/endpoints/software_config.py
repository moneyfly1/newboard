from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from datetime import datetime
from app.core.database import get_db
from app.schemas.common import ResponseBase
from app.utils.security import get_current_admin_user, get_current_user

router = APIRouter()

class SoftwareConfigUpdate(BaseModel):
    clash_windows_url: str = ""
    v2rayn_url: str = ""
    mihomo_windows_url: str = ""
    sparkle_windows_url: str = ""
    hiddify_windows_url: str = ""
    flash_windows_url: str = ""
    clash_android_url: str = ""
    v2rayng_url: str = ""
    hiddify_android_url: str = ""
    flash_macos_url: str = ""
    mihomo_macos_url: str = ""
    sparkle_macos_url: str = ""
    shadowrocket_url: str = ""

@router.get("/", response_model=ResponseBase)
def get_software_config(
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        config = db.execute(text("""
            SELECT key, value
            FROM system_configs 
            WHERE key LIKE 'software_%'
        """)).fetchall()
        software_config = {}
        for row in config:
            software_config[row.key] = row.value
        default_config = {
            "clash_windows_url": software_config.get("software_clash_windows_url", ""),
            "v2rayn_url": software_config.get("software_v2rayn_url", ""),
            "mihomo_windows_url": software_config.get("software_mihomo_windows_url", ""),
            "sparkle_windows_url": software_config.get("software_sparkle_windows_url", ""),
            "hiddify_windows_url": software_config.get("software_hiddify_windows_url", ""),
            "flash_windows_url": software_config.get("software_flash_windows_url", ""),
            "clash_android_url": software_config.get("software_clash_android_url", ""),
            "v2rayng_url": software_config.get("software_v2rayng_url", ""),
            "hiddify_android_url": software_config.get("software_hiddify_android_url", ""),
            "flash_macos_url": software_config.get("software_flash_macos_url", ""),
            "mihomo_macos_url": software_config.get("software_mihomo_macos_url", ""),
            "sparkle_macos_url": software_config.get("software_sparkle_macos_url", ""),
            "shadowrocket_url": software_config.get("software_shadowrocket_url", "")
        }
        return ResponseBase(data=default_config)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取软件配置失败: {str(e)}")

@router.put("/", response_model=ResponseBase)
def update_software_config(
    config_data: SoftwareConfigUpdate,
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        config_updates = {
            "software_clash_windows_url": config_data.clash_windows_url,
            "software_v2rayn_url": config_data.v2rayn_url,
            "software_mihomo_windows_url": config_data.mihomo_windows_url,
            "software_sparkle_windows_url": config_data.sparkle_windows_url,
            "software_hiddify_windows_url": config_data.hiddify_windows_url,
            "software_flash_windows_url": config_data.flash_windows_url,
            "software_clash_android_url": config_data.clash_android_url,
            "software_v2rayng_url": config_data.v2rayng_url,
            "software_hiddify_android_url": config_data.hiddify_android_url,
            "software_flash_macos_url": config_data.flash_macos_url,
            "software_mihomo_macos_url": config_data.mihomo_macos_url,
            "software_sparkle_macos_url": config_data.sparkle_macos_url,
            "software_shadowrocket_url": config_data.shadowrocket_url
        }
        current_time = datetime.now()
        for key, value in config_updates.items():
            check_query = text('SELECT id FROM system_configs WHERE key = :key AND type = \'software\'')
            existing = db.execute(check_query, {"key": key}).first()
            if existing:
                update_query = text("""
                    UPDATE system_configs 
                    SET value = :value, updated_at = :updated_at
                    WHERE key = :key AND type = 'software'
                """)
                db.execute(update_query, {"value": str(value), "updated_at": current_time, "key": key})
            else:
                insert_query = text("""
                    INSERT INTO system_configs (key, value, type, category, display_name, description, is_public, sort_order, created_at, updated_at)
                    VALUES (:key, :value, 'software', 'system', :display_name, :description, false, 0, :created_at, :updated_at)
                """)
                db.execute(insert_query, {
                    "key": key,
                    "value": str(value),
                    "display_name": key.replace('_', ' ').title(),
                    "description": f"Software configuration for {key}",
                    "created_at": current_time,
                    "updated_at": current_time
                })
        db.commit()
        return ResponseBase(message="软件配置更新成功")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新软件配置失败: {str(e)}")
