from typing import Optional
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime

class PackageBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal
    duration_days: int
    device_limit: int = 3
    is_active: bool = True

class PackageCreate(PackageBase):
    pass

class PackageUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    duration_days: Optional[int] = None
    device_limit: Optional[int] = None
    bandwidth_limit: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None

class Package(PackageBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PackageList(BaseModel):
    packages: list[Package]
    total: int
    page: int
    size: int
    pages: int
