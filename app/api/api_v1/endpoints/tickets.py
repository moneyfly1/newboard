from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime
from app.core.database import get_db
from app.schemas.ticket import (
    TicketCreate, TicketUpdate, TicketInDB, TicketReplyCreate,
    TicketReplyInDB, TicketRating, TicketAttachmentInDB
)
from app.schemas.common import ResponseBase, PaginationParams
from app.services.ticket import TicketService
from app.models.ticket import TicketStatus, TicketType, TicketPriority
from app.utils.security import get_current_user, get_current_admin_user
from app.api.api_v1.endpoints.common import handle_api_error, format_error_response

router = APIRouter()

def _parse_ticket_status(status: Optional[str]):
    if not status:
        return None
    try:
        return TicketStatus(status)
    except ValueError:
        return None

def _parse_ticket_type(type: Optional[str]):
    if not type:
        return None
    try:
        return TicketType(type)
    except ValueError:
        return None

def _parse_ticket_priority(priority: Optional[str]):
    if not priority:
        return None
    try:
        return TicketPriority(priority)
    except ValueError:
        return None

@router.post("/", response_model=ResponseBase)
@handle_api_error("创建工单")
def create_ticket(
    ticket_in: TicketCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    ticket_service = TicketService(db)
    ticket = ticket_service.create(ticket_in, current_user.id)
    return ResponseBase(
        message="工单创建成功",
        data={"id": ticket.id, "ticket_no": ticket.ticket_no}
    )

@router.get("/", response_model=ResponseBase)
@handle_api_error("获取工单列表")
def get_user_tickets(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    ticket_service = TicketService(db)
    skip = (page - 1) * size
    tickets, total = ticket_service.get_user_tickets(
        current_user.id, skip, size, _parse_ticket_status(status), _parse_ticket_type(type)
    )
    return ResponseBase(
        data={
            "tickets": [
                {
                    "id": t.id,
                    "ticket_no": t.ticket_no,
                    "title": t.title,
                    "type": t.type.value,
                    "status": t.status.value,
                    "priority": t.priority.value,
                    "created_at": t.created_at.isoformat(),
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                    "replies_count": len(t.replies) if t.replies else 0
                }
                for t in tickets
            ],
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size
        }
    )

@router.get("/{ticket_id}", response_model=ResponseBase)
@handle_api_error("获取工单详情")
def get_ticket(
    ticket_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    ticket_service = TicketService(db)
    ticket = ticket_service.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.user_id != current_user.id and not getattr(current_user, 'is_admin', False):
        raise HTTPException(status_code=403, detail="无权访问此工单")
    return ResponseBase(
        data={
            "id": ticket.id,
            "ticket_no": ticket.ticket_no,
            "title": ticket.title,
            "content": ticket.content,
            "type": ticket.type.value,
            "status": ticket.status.value,
            "priority": ticket.priority.value,
            "assigned_to": ticket.assigned_to,
            "rating": ticket.rating,
            "rating_comment": ticket.rating_comment,
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
            "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
            "replies": [
                {
                    "id": r.id,
                    "content": r.content,
                    "is_admin": r.is_admin == "true",
                    "user_id": r.user_id,
                    "created_at": r.created_at.isoformat()
                }
                for r in ticket.replies
            ],
            "attachments": [
                {
                    "id": a.id,
                    "file_name": a.file_name,
                    "file_path": a.file_path,
                    "file_size": a.file_size,
                    "created_at": a.created_at.isoformat()
                }
                for a in ticket.attachments
            ]
        }
    )

@router.post("/{ticket_id}/replies", response_model=ResponseBase)
@handle_api_error("添加工单回复")
def add_ticket_reply(
    ticket_id: int,
    reply_in: TicketReplyCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    ticket_service = TicketService(db)
    ticket = ticket_service.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    is_admin = getattr(current_user, 'is_admin', False)
    if ticket.user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="无权回复此工单")
    reply = ticket_service.add_reply(ticket_id, reply_in, current_user.id, is_admin)
    if not reply:
        raise HTTPException(status_code=400, detail="添加回复失败")
    return ResponseBase(message="回复添加成功", data={"reply_id": reply.id})

@router.post("/{ticket_id}/rating", response_model=ResponseBase)
@handle_api_error("添加工单评价")
def add_ticket_rating(
    ticket_id: int,
    rating_data: TicketRating,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    ticket_service = TicketService(db)
    ticket = ticket_service.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权评价此工单")
    if ticket.status != TicketStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="只能评价已解决的工单")
    success = ticket_service.add_rating(ticket_id, rating_data.rating, rating_data.rating_comment)
    if not success:
        raise HTTPException(status_code=400, detail="添加评价失败")
    return ResponseBase(message="评价添加成功")

@router.get("/admin/{ticket_id}", response_model=ResponseBase)
@handle_api_error("获取工单详情（管理员）")
def get_admin_ticket(
    ticket_id: int,
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    ticket_service = TicketService(db)
    ticket = ticket_service.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    return ResponseBase(
        data={
            "id": ticket.id,
            "ticket_no": ticket.ticket_no,
            "title": ticket.title,
            "content": ticket.content,
            "type": ticket.type.value,
            "status": ticket.status.value,
            "priority": ticket.priority.value,
            "user_id": ticket.user_id,
            "assigned_to": ticket.assigned_to,
            "admin_notes": ticket.admin_notes,
            "rating": ticket.rating,
            "rating_comment": ticket.rating_comment,
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
            "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
            "replies": [
                {
                    "id": r.id,
                    "content": r.content,
                    "is_admin": r.is_admin == "true",
                    "user_id": r.user_id,
                    "created_at": r.created_at.isoformat()
                }
                for r in ticket.replies
            ],
            "attachments": [
                {
                    "id": a.id,
                    "file_name": a.file_name,
                    "file_path": a.file_path,
                    "file_size": a.file_size,
                    "created_at": a.created_at.isoformat()
                }
                for a in ticket.attachments
            ]
        }
    )

@router.get("/admin/all", response_model=ResponseBase)
@handle_api_error("获取所有工单")
def get_all_tickets(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    ticket_service = TicketService(db)
    skip = (page - 1) * size
    tickets, total = ticket_service.get_all_tickets(
        skip, size, _parse_ticket_status(status), _parse_ticket_type(type),
        _parse_ticket_priority(priority), assigned_to, keyword
    )
    return ResponseBase(
        data={
            "tickets": [
                {
                    "id": t.id,
                    "ticket_no": t.ticket_no,
                    "title": t.title,
                    "type": t.type.value,
                    "status": t.status.value,
                    "priority": t.priority.value,
                    "user_id": t.user_id,
                    "assigned_to": t.assigned_to,
                    "created_at": t.created_at.isoformat(),
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                    "replies_count": len(t.replies) if t.replies else 0
                }
                for t in tickets
            ],
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size
        }
    )

@router.put("/admin/{ticket_id}", response_model=ResponseBase)
@handle_api_error("更新工单")
def update_ticket(
    ticket_id: int,
    ticket_in: TicketUpdate,
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    ticket_service = TicketService(db)
    ticket = ticket_service.update(ticket_id, ticket_in)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    return ResponseBase(message="工单更新成功")

@router.get("/admin/statistics", response_model=ResponseBase)
@handle_api_error("获取工单统计")
def get_ticket_statistics(
    current_admin = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    ticket_service = TicketService(db)
    stats = ticket_service.get_statistics()
    return ResponseBase(data=stats)
