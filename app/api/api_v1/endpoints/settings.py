from typing import Any, List, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.schemas.config import (
    SystemConfigCreate, SystemConfigUpdate, SystemConfigInDB,
    AnnouncementCreate, AnnouncementUpdate, AnnouncementInDB,
    ThemeConfigCreate, ThemeConfigUpdate, ThemeConfigInDB,
    SystemSettings, ConfigCategory, ConfigUpdateRequest
)
from app.schemas.common import ResponseBase, PaginationParams
from app.services.settings import SettingsService
from app.utils.security import get_current_user, get_current_admin_user

router = APIRouter()

@router.get("/public-settings", response_model=ResponseBase)
def get_public_settings(db: Session = Depends(get_db)) -> Any:
    try:
        settings_service = SettingsService(db)
        public_configs = settings_service.get_public_configs()
        settings = {}
        for config in public_configs:
            try:
                settings[config.key] = settings_service.get_config_value(config.key)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"获取配置值失败: {config.key}, {e}")
        
        system_keys = ['site_name', 'site_description', 'logo_url', 'maintenance_mode', 'maintenance_message']
        for key in system_keys:
            try:
                query = text("SELECT value FROM system_configs WHERE key = :key AND type = 'system'")
                result = db.execute(query, {"key": key}).first()
                if result:
                    if key == 'maintenance_mode':
                        settings[key] = result.value.lower() == 'true' if result.value else False
                    else:
                        settings[key] = result.value
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"查询系统配置失败: {key}, {e}")
        
        try:
            registration_query = text("SELECT value FROM system_configs WHERE key = 'registration_enabled' AND category = 'registration'")
            registration_result = db.execute(registration_query).first()
            if registration_result:
                settings['allowRegistration'] = registration_result.value.lower() == 'true'
            else:
                settings['allowRegistration'] = True
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"查询注册配置失败: {e}")
            settings['allowRegistration'] = True
        
        # 设置默认值
        if 'site_name' not in settings:
            settings['site_name'] = 'CBoard Modern'
        if 'site_description' not in settings:
            settings['site_description'] = '现代化的代理服务管理平台'
        if 'maintenance_mode' not in settings:
            settings['maintenance_mode'] = False
        if 'maintenance_message' not in settings:
            settings['maintenance_message'] = '系统维护中，请稍后再试'
        if 'allowRegistration' not in settings:
            settings['allowRegistration'] = True
        
        return ResponseBase(data=settings)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"获取公共设置失败: {e}", exc_info=True)
        # 返回默认设置，而不是抛出错误
        return ResponseBase(data={
            'site_name': 'CBoard Modern',
            'site_description': '现代化的代理服务管理平台',
            'maintenance_mode': False,
            'maintenance_message': '系统维护中，请稍后再试',
            'allowRegistration': True
        })

@router.get("/announcements", response_model=ResponseBase)
def get_announcements(
    target_users: str = Query('all'),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    settings_service = SettingsService(db)
    announcements = settings_service.get_active_announcements(target_users)
    return ResponseBase(
        data={
            "announcements": [
                {
                    "id": announcement.id,
                    "title": announcement.title,
                    "content": announcement.content,
                    "type": announcement.type,
                    "is_pinned": announcement.is_pinned,
                    "created_at": announcement.created_at.isoformat()
                }
                for announcement in announcements
            ]
        }
    )

@router.get("/admin/settings", response_model=ResponseBase)
def get_system_settings(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    settings = settings_service.get_system_settings()
    return ResponseBase(data=settings.dict())

@router.put("/admin/settings", response_model=ResponseBase)
def update_system_settings(
    settings: Dict[str, Any],
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    try:
        success = settings_service.update_system_settings(settings)
        if success:
            return ResponseBase(message="系统设置更新成功")
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="系统设置更新失败")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"系统设置更新失败: {str(e)}")

@router.get("/admin/configs", response_model=ResponseBase)
def get_configs_by_category(
    category: str = Query(None),
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    if category:
        configs = settings_service.get_configs_by_category(category)
    else:
        configs = settings_service.get_all_configs()
    categories = {}
    for config in configs:
        if config.category not in categories:
            categories[config.category] = []
        categories[config.category].append({
            "id": config.id,
            "key": config.key,
            "value": config.value,
            "type": config.type,
            "display_name": config.display_name,
            "description": config.description,
            "is_public": config.is_public,
            "sort_order": config.sort_order,
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat() if config.updated_at else None
        })
    return ResponseBase(data={"categories": categories})

@router.post("/admin/configs", response_model=ResponseBase)
def create_config(
    config_data: SystemConfigCreate,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    try:
        config = settings_service.create_config(config_data)
        return ResponseBase(message="配置创建成功", data={"config_id": config.id})
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"配置创建失败: {str(e)}")

@router.put("/admin/configs/{config_key}", response_model=ResponseBase)
def update_config(
    config_key: str,
    config_data: SystemConfigUpdate,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    try:
        config = settings_service.update_config(config_key, config_data)
        if not config:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")
        return ResponseBase(message="配置更新成功")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"配置更新失败: {str(e)}")

@router.delete("/admin/configs/{config_key}", response_model=ResponseBase)
def delete_config(
    config_key: str,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    success = settings_service.delete_config(config_key)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")
    return ResponseBase(message="配置删除成功")

@router.post("/admin/configs/initialize", response_model=ResponseBase)
def initialize_configs(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    try:
        settings_service.initialize_default_configs()
        return ResponseBase(message="默认配置初始化成功")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"配置初始化失败: {str(e)}")

@router.get("/admin/announcements", response_model=ResponseBase)
def get_announcements_admin(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    announcements, total = settings_service.get_all_announcements(page, size)
    return ResponseBase(
        data={
            "announcements": [
                {
                    "id": announcement.id,
                    "title": announcement.title,
                    "content": announcement.content,
                    "type": announcement.type,
                    "is_active": announcement.is_active,
                    "is_pinned": announcement.is_pinned,
                    "start_time": announcement.start_time.isoformat() if announcement.start_time else None,
                    "end_time": announcement.end_time.isoformat() if announcement.end_time else None,
                    "target_users": announcement.target_users,
                    "created_by": announcement.created_by,
                    "created_at": announcement.created_at.isoformat(),
                    "updated_at": announcement.updated_at.isoformat() if announcement.updated_at else None
                }
                for announcement in announcements
            ],
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size
        }
    )

@router.get("/admin/announcements/{announcement_id}", response_model=ResponseBase)
def get_announcement_detail(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    announcement = settings_service.get_announcement(announcement_id)
    if not announcement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公告不存在")
    return ResponseBase(
        data={
            "id": announcement.id,
            "title": announcement.title,
            "content": announcement.content,
            "type": announcement.type,
            "is_active": announcement.is_active,
            "is_pinned": announcement.is_pinned,
            "start_time": announcement.start_time.isoformat() if announcement.start_time else None,
            "end_time": announcement.end_time.isoformat() if announcement.end_time else None,
            "target_users": announcement.target_users,
            "created_by": announcement.created_by,
            "created_at": announcement.created_at.isoformat(),
            "updated_at": announcement.updated_at.isoformat() if announcement.updated_at else None
        }
    )

@router.post("/admin/announcements", response_model=ResponseBase)
def create_announcement(
    announcement_data: AnnouncementCreate,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    try:
        announcement = settings_service.create_announcement(announcement_data, current_admin.id)
        return ResponseBase(message="公告创建成功", data={"announcement_id": announcement.id})
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"公告创建失败: {str(e)}")

@router.put("/admin/announcements/{announcement_id}", response_model=ResponseBase)
def update_announcement(
    announcement_id: int,
    announcement_data: AnnouncementUpdate,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    try:
        announcement = settings_service.update_announcement(announcement_id, announcement_data)
        if not announcement:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公告不存在")
        return ResponseBase(message="公告更新成功")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"公告更新失败: {str(e)}")

@router.delete("/admin/announcements/{announcement_id}", response_model=ResponseBase)
def delete_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    success = settings_service.delete_announcement(announcement_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公告不存在")
    return ResponseBase(message="公告删除成功")

@router.post("/admin/announcements/{announcement_id}/toggle-status", response_model=ResponseBase)
def toggle_announcement_status(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    success = settings_service.toggle_announcement_status(announcement_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公告不存在")
    return ResponseBase(message="公告状态切换成功")

@router.post("/admin/announcements/{announcement_id}/toggle-pin", response_model=ResponseBase)
def toggle_announcement_pin(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    success = settings_service.toggle_announcement_pin(announcement_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公告不存在")
    return ResponseBase(message="公告置顶状态切换成功")

@router.get("/admin/themes", response_model=ResponseBase)
def get_theme_configs(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    themes = settings_service.get_active_themes()
    return ResponseBase(
        data={
            "themes": [
                {
                    "id": theme.id,
                    "name": theme.name,
                    "display_name": theme.display_name,
                    "is_active": theme.is_active,
                    "is_default": theme.is_default,
                    "config": theme.config,
                    "preview_image": theme.preview_image,
                    "created_at": theme.created_at.isoformat(),
                    "updated_at": theme.updated_at.isoformat() if theme.updated_at else None
                }
                for theme in themes
            ]
        }
    )

@router.post("/admin/themes", response_model=ResponseBase)
def create_theme_config(
    theme_data: ThemeConfigCreate,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    try:
        theme = settings_service.create_theme_config(theme_data)
        return ResponseBase(message="主题配置创建成功", data={"theme_id": theme.id})
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"主题配置创建失败: {str(e)}")

@router.put("/admin/themes/{theme_id}", response_model=ResponseBase)
def update_theme_config(
    theme_id: int,
    theme_data: ThemeConfigUpdate,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    try:
        theme = settings_service.update_theme_config(theme_id, theme_data)
        if not theme:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="主题配置不存在")
        return ResponseBase(message="主题配置更新成功")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"主题配置更新失败: {str(e)}")

@router.delete("/admin/themes/{theme_id}", response_model=ResponseBase)
def delete_theme_config(
    theme_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    settings_service = SettingsService(db)
    success = settings_service.delete_theme_config(theme_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="主题配置不存在")
    return ResponseBase(message="主题配置删除成功")
