import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.notification import NotificationCreate
from app.schemas.common import ResponseBase
from app.services.notification_service import NotificationCRUDService
from app.utils.security import get_current_user, get_current_admin_user

logger = logging.getLogger(__name__)
router = APIRouter()

def _serialize_notification(notif) -> dict:
    return {
        "id": notif.id,
        "title": notif.title,
        "content": notif.content,
        "type": notif.type,
        "is_read": notif.is_read,
        "created_at": notif.created_at.isoformat(),
        "read_at": notif.read_at.isoformat() if notif.read_at else None
    }

def _build_pagination_response(notifications, total, page, size):
    return ResponseBase(data={
        "notifications": [_serialize_notification(notif) for notif in notifications],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    })

@router.get("/user-notifications", response_model=ResponseBase)
def get_user_notifications(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    notification_service = NotificationCRUDService(db)
    skip = (page - 1) * size
    notifications, total = notification_service.get_user_notifications(
        user_id=current_user.id, skip=skip, limit=size, unread_only=unread_only
    )
    return _build_pagination_response(notifications, total, page, size)

@router.get("/unread-count", response_model=ResponseBase)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    notification_service = NotificationCRUDService(db)
    count = notification_service.get_unread_count(current_user.id)
    return ResponseBase(data={"count": count})

@router.post("/{notification_id}/read", response_model=ResponseBase)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    notification_service = NotificationCRUDService(db)
    success = notification_service.mark_as_read(notification_id, current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在")
    return ResponseBase(message="标记成功")

@router.post("/mark-all-read", response_model=ResponseBase)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    notification_service = NotificationCRUDService(db)
    count = notification_service.mark_all_as_read(current_user.id)
    return ResponseBase(message=f"已标记 {count} 条通知为已读", data={"count": count})

@router.get("/admin/notifications", response_model=ResponseBase)
def get_admin_notifications(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    notification_type: str = Query(None),
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    notification_service = NotificationCRUDService(db)
    skip = (page - 1) * size
    notifications, total = notification_service.get_system_notifications(skip, size)
    if notification_type:
        notifications = [n for n in notifications if n.type == notification_type]
        total = len(notifications)
    return _build_pagination_response(notifications, total, page, size)

@router.post("/admin/notifications", response_model=ResponseBase)
def create_notification(
    notification_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    notification_service = NotificationCRUDService(db)
    notification = notification_service.create(NotificationCreate(**notification_data))
    return ResponseBase(message="通知创建成功", data={"notification_id": notification.id})

@router.post("/admin/notifications/broadcast", response_model=ResponseBase)
def broadcast_notification(
    notification_data: dict,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    from app.services.user import UserService
    from app.services.notification_service import NotificationService
    notification_crud_service = NotificationCRUDService(db)
    notification_service = NotificationService(db)
    user_service = UserService(db)
    users = user_service.get_multi()
    notification_type = notification_data.get("type", "system")
    send_email = notification_data.get("send_email", False)
    created_count = 0
    email_sent_count = 0
    for user in users:
        if not notification_service.should_send_notification(user, notification_type):
            continue
        try:
            notification_crud_service.create(NotificationCreate(
                user_id=user.id,
                title=notification_data["title"],
                content=notification_data["content"],
                type=notification_type
            ))
            created_count += 1
            if send_email:
                try:
                    from app.services.email_template_enhanced import EmailTemplateEnhanced
                    html_content = EmailTemplateEnhanced.get_broadcast_notification_template(
                        title=notification_data["title"],
                        content=notification_data["content"]
                    )
                    success = notification_service._send_notification_email(
                        user=user,
                        notification_type=notification_type,
                        subject=notification_data["title"],
                        html_content=html_content,
                        email_type='broadcast'
                    )
                    if success:
                        email_sent_count += 1
                except Exception as e:
                    logger.error(f"发送邮件失败 (user_id={user.id}): {e}", exc_info=True)
                    continue
        except Exception as e:
            logger.error(f"创建通知失败 (user_id={user.id}): {e}", exc_info=True)
            continue
    message = f"广播通知成功，已发送给 {created_count} 个用户"
    if send_email:
        message += f"，邮件已发送给 {email_sent_count} 个用户"
    return ResponseBase(
        message=message,
        data={"sent_count": created_count, "email_sent_count": email_sent_count if send_email else 0}
    )

@router.delete("/admin/notifications/{notification_id}", response_model=ResponseBase)
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
) -> Any:
    notification_service = NotificationCRUDService(db)
    success = notification_service.delete(notification_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在")
    return ResponseBase(message="通知删除成功") 