from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.core.database import Base

class SystemConfig(Base):
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text, nullable=True)
    type = Column(String(50), nullable=False)  # string, number, boolean, json, text
    category = Column(String(50), nullable=False)  # general, payment, email, notification, theme, announcement
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, default=False)  # 是否公开配置
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<SystemConfig(id={self.id}, key='{self.key}', category='{self.category}')>"

class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    type = Column(String(50), default='info')  # info, warning, success, error
    is_active = Column(Boolean, default=True)
    is_pinned = Column(Boolean, default=False)  # 是否置顶
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    target_users = Column(String(50), default='all')  # all, admin, user
    created_by = Column(Integer, nullable=False)  # 创建者用户ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Announcement(id={self.id}, title='{self.title}', type='{self.type}')>"

class ThemeConfig(Base):
    __tablename__ = "theme_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    config = Column(JSON, nullable=True)  # 主题配置参数
    preview_image = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<ThemeConfig(id={self.id}, name='{self.name}', display_name='{self.display_name}')>" 