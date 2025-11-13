"""
工单模型
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class TicketStatus(str, enum.Enum):
    """工单状态"""
    PENDING = "pending"  # 待处理
    PROCESSING = "processing"  # 处理中
    RESOLVED = "resolved"  # 已解决
    CLOSED = "closed"  # 已关闭
    CANCELLED = "cancelled"  # 已取消


class TicketType(str, enum.Enum):
    """工单类型"""
    TECHNICAL = "technical"  # 技术问题
    BILLING = "billing"  # 账单问题
    ACCOUNT = "account"  # 账户问题
    OTHER = "other"  # 其他


class TicketPriority(str, enum.Enum):
    """工单优先级"""
    LOW = "low"  # 低
    NORMAL = "normal"  # 普通
    HIGH = "high"  # 高
    URGENT = "urgent"  # 紧急


class Ticket(Base):
    """工单模型"""
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_no = Column(String(50), unique=True, index=True, nullable=False, comment="工单编号")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    title = Column(String(200), nullable=False, comment="工单标题")
    content = Column(Text, nullable=False, comment="工单内容")
    type = Column(SQLEnum(TicketType), default=TicketType.OTHER, comment="工单类型")
    status = Column(SQLEnum(TicketStatus), default=TicketStatus.PENDING, comment="工单状态")
    priority = Column(SQLEnum(TicketPriority), default=TicketPriority.NORMAL, comment="优先级")
    
    # 管理员相关
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True, comment="分配给的管理员ID")
    admin_notes = Column(Text, nullable=True, comment="管理员备注")
    
    # 评价
    rating = Column(Integer, nullable=True, comment="用户评价（1-5星）")
    rating_comment = Column(Text, nullable=True, comment="评价内容")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")
    resolved_at = Column(DateTime(timezone=True), nullable=True, comment="解决时间")
    closed_at = Column(DateTime(timezone=True), nullable=True, comment="关闭时间")
    
    # 关系
    user = relationship("User", foreign_keys=[user_id], backref="tickets")
    assignee = relationship("User", foreign_keys=[assigned_to], backref="assigned_tickets")
    replies = relationship("TicketReply", back_populates="ticket", cascade="all, delete-orphan")
    attachments = relationship("TicketAttachment", back_populates="ticket", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Ticket(id={self.id}, ticket_no='{self.ticket_no}', status='{self.status}')>"


class TicketReply(Base):
    """工单回复模型"""
    __tablename__ = "ticket_replies"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, comment="工单ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="回复用户ID")
    content = Column(Text, nullable=False, comment="回复内容")
    is_admin = Column(String(10), default="false", comment="是否管理员回复")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    
    # 关系
    ticket = relationship("Ticket", back_populates="replies")
    user = relationship("User", backref="ticket_replies")
    
    def __repr__(self):
        return f"<TicketReply(id={self.id}, ticket_id={self.ticket_id})>"


class TicketAttachment(Base):
    """工单附件模型"""
    __tablename__ = "ticket_attachments"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, comment="工单ID")
    reply_id = Column(Integer, ForeignKey("ticket_replies.id"), nullable=True, comment="回复ID（可选）")
    file_name = Column(String(255), nullable=False, comment="文件名")
    file_path = Column(String(500), nullable=False, comment="文件路径")
    file_size = Column(Integer, nullable=True, comment="文件大小（字节）")
    file_type = Column(String(50), nullable=True, comment="文件类型")
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False, comment="上传用户ID")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    
    # 关系
    ticket = relationship("Ticket", back_populates="attachments")
    reply = relationship("TicketReply", backref="attachments")
    uploader = relationship("User", backref="ticket_attachments")
    
    def __repr__(self):
        return f"<TicketAttachment(id={self.id}, ticket_id={self.ticket_id}, file_name='{self.file_name}')>"

