from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class NodeBase(BaseModel):
    name: str = Field(..., description="节点名称")
    region: str = Field(..., description="地区")
    type: str = Field(..., description="节点类型")
    status: str = Field(default="offline", description="节点状态")
    load: float = Field(default=0.0, description="负载百分比")
    speed: float = Field(default=0.0, description="速度(MB/s)")
    uptime: int = Field(default=0, description="在线时间(秒)")
    latency: int = Field(default=0, description="延迟(毫秒)")
    description: Optional[str] = Field(None, description="节点描述")
    config: Optional[str] = Field(None, description="节点配置（敏感信息）")
    is_recommended: bool = Field(default=False, description="是否推荐")
    is_active: bool = Field(default=True, description="是否启用")

class NodeCreate(NodeBase):
    pass

class NodeUpdate(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    load: Optional[float] = None
    speed: Optional[float] = None
    uptime: Optional[int] = None
    latency: Optional[int] = None
    description: Optional[str] = None
    config: Optional[str] = None
    is_recommended: Optional[bool] = None
    is_active: Optional[bool] = None

class Node(NodeBase):
    id: int
    last_test: Optional[datetime] = None
    last_update: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# 安全的公开接口响应模型（不包含敏感信息）
class NodePublic(BaseModel):
    """公开接口使用的节点模型（不包含敏感信息）"""
    id: int
    name: str = Field(..., description="节点名称")
    region: str = Field(..., description="地区")
    type: str = Field(..., description="节点类型")
    status: str = Field(default="offline", description="节点状态")
    load: float = Field(default=0.0, description="负载百分比")
    speed: float = Field(default=0.0, description="速度(MB/s)")
    uptime: int = Field(default=0, description="在线时间(秒)")
    latency: int = Field(default=0, description="延迟(毫秒)")
    description: Optional[str] = Field(None, description="节点描述")
    is_recommended: bool = Field(default=False, description="是否推荐")
    is_active: bool = Field(default=True, description="是否启用")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class NodeList(BaseModel):
    items: list[Node]
    total: int
    page: int
    size: int

class NodePublicList(BaseModel):
    """公开接口使用的节点列表（不包含敏感信息）"""
    items: list[NodePublic]
    total: int
    page: int
    size: int

