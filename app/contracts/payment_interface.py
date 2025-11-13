from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel


class PaymentRequest(BaseModel):
    """支付请求数据模型"""
    trade_no: str
    total_amount: int  # 金额（分）
    subject: str
    body: str
    notify_url: str
    return_url: str
    user_id: int


class PaymentResponse(BaseModel):
    """支付响应数据模型"""
    type: int  # 0: 二维码, 1: 跳转URL
    data: str  # 二维码URL或跳转URL
    trade_no: str


class PaymentNotify(BaseModel):
    """支付回调数据模型"""
    trade_no: str
    callback_no: str
    amount: int
    status: str


class PaymentInterface(ABC):
    """支付接口抽象类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    @abstractmethod
    def pay(self, request: PaymentRequest) -> PaymentResponse:
        """创建支付订单"""
        pass
    
    @abstractmethod
    def verify_notify(self, params: Dict[str, Any]) -> Optional[PaymentNotify]:
        """验证支付回调"""
        pass
    
    @abstractmethod
    def get_config_form(self) -> Dict[str, Any]:
        """获取配置表单"""
        pass
