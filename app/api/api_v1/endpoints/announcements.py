import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.schemas.common import ResponseBase
from app.utils.security import get_current_user, get_current_admin_user

logger = logging.getLogger(__name__)
router = APIRouter()

def _format_announcement(announcement):
    return {
        "id": announcement.id,
        "title": announcement.title,
        "content": announcement.content,
        "type": announcement.type,
        "created_at": announcement.created_at if announcement.created_at else None,
        "updated_at": announcement.updated_at if announcement.updated_at else None
    }

def _handle_error(e: Exception, operation: str, db: Session = None):
    if db:
        db.rollback()
    logger.error(f"{operation}失败: {e}", exc_info=True)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{operation}失败: {str(e)}")

@router.get("/", response_model=ResponseBase)
def get_announcements(current_user = Depends(get_current_user), db: Session = Depends(get_db)) -> Any:
    try:
        announcements = db.execute(text("SELECT id, title, content, type, created_at, updated_at FROM announcements WHERE is_active = 1 ORDER BY created_at DESC LIMIT 10")).fetchall()
        notifications = db.execute(text("SELECT id, title, content, type, created_at, NULL as updated_at FROM notifications WHERE type = 'system' OR type = 'announcement' ORDER BY created_at DESC LIMIT 10")).fetchall()
        all_items = [_format_announcement(a) for a in announcements] + [_format_announcement(n) for n in notifications]
        all_items.sort(key=lambda x: x['created_at'] or '', reverse=True)
        return ResponseBase(data=all_items[:10])
    except Exception as e:
        _handle_error(e, "获取公告列表", db)

@router.get("/{announcement_id}", response_model=ResponseBase)
def get_announcement_detail(announcement_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)) -> Any:
    try:
        announcement = db.execute(text("SELECT id, title, content, created_at, updated_at FROM announcements WHERE id = :announcement_id AND is_active = 1"), {'announcement_id': announcement_id}).fetchone()
        if not announcement:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公告不存在")
        return ResponseBase(data={
            "id": announcement.id,
            "title": announcement.title,
            "content": announcement.content,
            "created_at": announcement.created_at.isoformat() if announcement.created_at else None,
            "updated_at": announcement.updated_at.isoformat() if announcement.updated_at else None
        })
    except HTTPException:
        raise
    except Exception as e:
        _handle_error(e, "获取公告详情", db)

@router.post("/admin/publish", response_model=ResponseBase)
def publish_announcement(announcement_data: dict, current_admin = Depends(get_current_admin_user), db: Session = Depends(get_db)) -> Any:
    try:
        title = announcement_data.get('title', '')
        content = announcement_data.get('content', '')
        announcement_type = announcement_data.get('type', 'system')
        send_email = announcement_data.get('send_email', False)
        if not title or not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标题和内容不能为空")
        db.execute(text("INSERT INTO notifications (user_id, title, content, type, is_read, created_at) VALUES (NULL, :title, :content, :type, 0, datetime('now'))"), {'title': title, 'content': content, 'type': announcement_type})
        db.execute(text("INSERT INTO announcements (title, content, type, is_active, is_pinned, target_users, created_by, created_at, updated_at) VALUES (:title, :content, :type, 1, 0, 'all', :created_by, datetime('now'), datetime('now'))"), {'title': title, 'content': content, 'type': announcement_type, 'created_by': current_admin.id})
        db.commit()
        email_sent_count = 0
        if send_email:
            try:
                from app.services.user import UserService
                from app.services.notification_service import NotificationService
                from app.services.email_template_enhanced import EmailTemplateEnhanced
                user_service = UserService(db)
                notification_service = NotificationService(db)
                users = user_service.get_multi()
                notification_type = 'marketing' if announcement_type == 'marketing' else 'system'
                for user in users:
                    if not notification_service.should_send_notification(user, notification_type):
                        continue
                    try:
                        html_content = EmailTemplateEnhanced.get_announcement_email_template(title=title, content=content)
                        if notification_service._send_notification_email(user=user, notification_type=notification_type, subject=title, html_content=html_content, email_type='announcement'):
                            email_sent_count += 1
                    except Exception as e:
                        logger.error(f"发送公告邮件失败 (user_id={user.id}): {e}", exc_info=True)
            except Exception as e:
                logger.error(f"发送公告邮件失败: {e}", exc_info=True)
        message = "公告发布成功"
        if send_email:
            message += f"，邮件已发送给 {email_sent_count} 个用户"
        return ResponseBase(message=message, data={"email_sent_count": email_sent_count} if send_email else None)
    except HTTPException:
        raise
    except Exception as e:
        _handle_error(e, "发布公告", db)

@router.get("/admin/list", response_model=ResponseBase)
def get_admin_announcements(page: int = 1, size: int = 20, current_admin = Depends(get_current_admin_user), db: Session = Depends(get_db)) -> Any:
    try:
        skip = (page - 1) * size
        announcements = db.execute(text("SELECT id, title, content, type, is_active, created_at, updated_at FROM announcements ORDER BY created_at DESC LIMIT :limit OFFSET :offset"), {'limit': size, 'offset': skip}).fetchall()
        total = db.execute(text("SELECT COUNT(*) FROM announcements")).fetchone()[0]
        return ResponseBase(data={
            "announcements": [{"id": a.id, "title": a.title, "content": a.content, "type": a.type, "is_active": a.is_active, "created_at": a.created_at if a.created_at else None, "updated_at": a.updated_at if a.updated_at else None} for a in announcements],
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size
        })
    except Exception as e:
        _handle_error(e, "获取公告列表", db)

@router.put("/admin/{announcement_id}", response_model=ResponseBase)
def update_announcement(announcement_id: int, announcement_data: dict, current_admin = Depends(get_current_admin_user), db: Session = Depends(get_db)) -> Any:
    try:
        title = announcement_data.get('title', '')
        content = announcement_data.get('content', '')
        announcement_type = announcement_data.get('type', 'system')
        status_val = announcement_data.get('status', 'published')
        if not title or not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标题和内容不能为空")
        db.execute(text("UPDATE announcements SET title = :title, content = :content, type = :type, is_active = :is_active, updated_at = datetime('now') WHERE id = :announcement_id"), {'title': title, 'content': content, 'type': announcement_type, 'is_active': 1 if status_val == 'published' else 0, 'announcement_id': announcement_id})
        db.execute(text("UPDATE notifications SET title = :title, content = :content, type = :type WHERE id = :announcement_id"), {'title': title, 'content': content, 'type': announcement_type, 'announcement_id': announcement_id})
        db.commit()
        return ResponseBase(message="公告更新成功")
    except HTTPException:
        raise
    except Exception as e:
        _handle_error(e, "更新公告", db)

@router.delete("/admin/{announcement_id}", response_model=ResponseBase)
def delete_announcement(announcement_id: int, current_admin = Depends(get_current_admin_user), db: Session = Depends(get_db)) -> Any:
    try:
        db.execute(text("DELETE FROM announcements WHERE id = :announcement_id"), {'announcement_id': announcement_id})
        db.execute(text("DELETE FROM notifications WHERE id = :announcement_id"), {'announcement_id': announcement_id})
        db.commit()
        return ResponseBase(message="公告删除成功")
    except Exception as e:
        _handle_error(e, "删除公告", db)
