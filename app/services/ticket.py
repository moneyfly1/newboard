"""工单服务"""
import secrets
import string
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from app.models.ticket import Ticket, TicketAttachment, TicketPriority, TicketReply, TicketStatus, TicketType
from app.models.user import User
from app.schemas.ticket import TicketCreate, TicketReplyCreate, TicketUpdate


def generate_ticket_no() -> str:
    """生成工单号"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = ''.join(secrets.choice(string.digits) for _ in range(4))
    return f"TK{timestamp}{random_str}"


class TicketService:
    """工单服务类"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, ticket_id: int) -> Optional[Ticket]:
        return self.db.query(Ticket).filter(Ticket.id == ticket_id).first()

    def get_by_ticket_no(self, ticket_no: str) -> Optional[Ticket]:
        return self.db.query(Ticket).filter(Ticket.ticket_no == ticket_no).first()

    def get_user_tickets(self, user_id: int, skip: int = 0, limit: int = 20, status: Optional[TicketStatus] = None, type: Optional[TicketType] = None) -> Tuple[List[Ticket], int]:
        query = self.db.query(Ticket).filter(Ticket.user_id == user_id)
        if status:
            query = query.filter(Ticket.status == status)
        if type:
            query = query.filter(Ticket.type == type)
        total = query.count()
        tickets = query.order_by(desc(Ticket.created_at)).offset(skip).limit(limit).all()
        return tickets, total

    def get_all_tickets(self, skip: int = 0, limit: int = 20, status: Optional[TicketStatus] = None, type: Optional[TicketType] = None, priority: Optional[TicketPriority] = None, assigned_to: Optional[int] = None, keyword: Optional[str] = None) -> Tuple[List[Ticket], int]:
        query = self.db.query(Ticket)
        if status:
            query = query.filter(Ticket.status == status)
        if type:
            query = query.filter(Ticket.type == type)
        if priority:
            query = query.filter(Ticket.priority == priority)
        if assigned_to:
            query = query.filter(Ticket.assigned_to == assigned_to)
        if keyword:
            query = query.filter(or_(Ticket.title.like(f"%{keyword}%"), Ticket.content.like(f"%{keyword}%"), Ticket.ticket_no.like(f"%{keyword}%")))
        total = query.count()
        tickets = query.order_by(desc(Ticket.created_at)).offset(skip).limit(limit).all()
        return tickets, total

    def create(self, ticket_in: TicketCreate, user_id: int) -> Ticket:
        ticket = Ticket(
            ticket_no=generate_ticket_no(),
            user_id=user_id,
            title=ticket_in.title,
            content=ticket_in.content,
            type=ticket_in.type,
            priority=ticket_in.priority,
            status=TicketStatus.PENDING
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def update(self, ticket_id: int, ticket_in: TicketUpdate) -> Optional[Ticket]:
        ticket = self.get(ticket_id)
        if not ticket:
            return None
        update_data = ticket_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(ticket, field, value)
        if ticket_in.status == TicketStatus.RESOLVED and not ticket.resolved_at:
            ticket.resolved_at = datetime.now(timezone.utc)
        if ticket_in.status == TicketStatus.CLOSED and not ticket.closed_at:
            ticket.closed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def delete(self, ticket_id: int) -> bool:
        ticket = self.get(ticket_id)
        if not ticket:
            return False
        self.db.delete(ticket)
        self.db.commit()
        return True

    def add_reply(self, ticket_id: int, reply_in: TicketReplyCreate, user_id: int, is_admin: bool = False) -> Optional[TicketReply]:
        ticket = self.get(ticket_id)
        if not ticket:
            return None
        if is_admin:
            if ticket.status == TicketStatus.PENDING:
                ticket.status = TicketStatus.PROCESSING
            elif ticket.status == TicketStatus.CANCELLED:
                ticket.status = TicketStatus.PROCESSING
            ticket.updated_at = datetime.now(timezone.utc)
            self.db.commit()
        reply = TicketReply(ticket_id=ticket_id, user_id=user_id, content=reply_in.content, is_admin="true" if is_admin else "false")
        self.db.add(reply)
        self.db.commit()
        self.db.refresh(reply)
        return reply

    def add_rating(self, ticket_id: int, rating: int, rating_comment: Optional[str] = None) -> bool:
        ticket = self.get(ticket_id)
        if not ticket:
            return False
        ticket.rating = rating
        ticket.rating_comment = rating_comment
        self.db.commit()
        return True

    def get_statistics(self) -> dict:
        return {
            "total": self.db.query(Ticket).count(),
            "pending": self.db.query(Ticket).filter(Ticket.status == TicketStatus.PENDING).count(),
            "processing": self.db.query(Ticket).filter(Ticket.status == TicketStatus.PROCESSING).count(),
            "resolved": self.db.query(Ticket).filter(Ticket.status == TicketStatus.RESOLVED).count(),
            "closed": self.db.query(Ticket).filter(Ticket.status == TicketStatus.CLOSED).count()
        }
