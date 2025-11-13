from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class SubscriptionBase(BaseModel):
    device_limit: int = 3

class SubscriptionCreate(SubscriptionBase):
    user_id: int
    package_name: Optional[str] = None
    duration_days: Optional[int] = None
    status: Optional[str] = "active"
    expire_time: Optional[datetime] = None

class SubscriptionUpdate(BaseModel):
    device_limit: Optional[int] = None
    is_active: Optional[bool] = None
    expire_time: Optional[datetime] = None

class SubscriptionInDB(SubscriptionBase):
    id: int
    user_id: int
    subscription_url: str
    current_devices: int
    is_active: bool
    expire_time: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Subscription(SubscriptionInDB):
    pass

class DeviceBase(BaseModel):
    device_name: Optional[str] = None
    device_type: Optional[str] = None

class DeviceCreate(DeviceBase):
    subscription_id: int
    device_fingerprint: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class DeviceUpdate(BaseModel):
    device_name: Optional[str] = None
    is_active: Optional[bool] = None

class DeviceInDB(DeviceBase):
    id: int
    subscription_id: int
    device_fingerprint: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    last_access: datetime
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class Device(DeviceInDB):
    pass

class SubscriptionWithDevices(Subscription):
    devices: List[Device] = [] 