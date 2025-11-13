from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

# 支付方式枚举
class PaymentMethodEnum(str, Enum):
    alipay = "alipay"
    wechat = "wechat"
    bank_transfer = "bank_transfer"
    yipay = "yipay"

# 为了向后兼容，创建别名（但会被后面的类定义覆盖，所以直接使用 PaymentMethodEnum）
# PaymentMethod = PaymentMethodEnum  # 注释掉，因为后面有同名的类

# 支付状态枚举
class PaymentStatus(str, Enum):
    pending = "pending"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"
    refunded = "refunded"

# 支付创建请求
class PaymentCreate(BaseModel):
    order_no: str = Field(..., description="订单号")
    amount: float = Field(..., gt=0, description="支付金额")
    currency: str = Field(default="CNY", description="货币类型")
    payment_method: str = Field(..., description="支付方式")
    subject: str = Field(..., description="支付主题")
    body: str = Field(default="", description="支付描述")
    return_url: Optional[str] = Field(None, description="支付完成返回地址")
    notify_url: Optional[str] = Field(None, description="支付通知地址")

# 支付请求（别名）
PaymentRequest = PaymentCreate

# 支付更新请求
class PaymentUpdate(BaseModel):
    status: Optional[PaymentStatus] = Field(None, description="支付状态")
    gateway_response: Optional[str] = Field(None, description="网关响应")
    callback_data: Optional[Dict[str, Any]] = Field(None, description="回调数据")

# 支付响应
class PaymentResponse(BaseModel):
    id: int
    payment_url: Optional[str] = Field(None, description="支付链接")
    order_no: str = Field(..., description="订单号")
    amount: float = Field(..., description="支付金额")
    payment_method: PaymentMethodEnum = Field(..., description="支付方式")
    status: PaymentStatus = Field(..., description="支付状态")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True

# 支付回调
class PaymentCallback(BaseModel):
    trade_no: str = Field(..., description="交易号")
    out_trade_no: str = Field(..., description="商户订单号")
    trade_status: str = Field(..., description="交易状态")
    total_amount: float = Field(..., description="交易金额")
    buyer_id: Optional[str] = Field(None, description="买家ID")
    seller_id: Optional[str] = Field(None, description="卖家ID")
    gmt_payment: Optional[datetime] = Field(None, description="支付时间")
    sign: str = Field(..., description="签名")

# 支付配置
class PaymentConfigCreate(BaseModel):
    payment_method: PaymentMethodEnum = Field(..., description="支付方式")
    is_enabled: bool = Field(default=True, description="是否启用")
    config_data: Dict[str, Any] = Field(..., description="配置数据")
    display_name: str = Field(..., description="显示名称")
    description: Optional[str] = Field(None, description="描述")
    icon: Optional[str] = Field(None, description="图标")
    sort_order: int = Field(default=0, description="排序")

# 支付配置更新
class PaymentConfigUpdate(BaseModel):
    is_enabled: Optional[bool] = Field(None, description="是否启用")
    config_data: Optional[Dict[str, Any]] = Field(None, description="配置数据")
    display_name: Optional[str] = Field(None, description="显示名称")
    description: Optional[str] = Field(None, description="描述")
    icon: Optional[str] = Field(None, description="图标")
    sort_order: Optional[int] = Field(None, description="排序")

# 支付配置响应
class PaymentConfigResponse(BaseModel):
    id: int
    payment_method: PaymentMethodEnum
    is_enabled: bool
    config_data: Dict[str, Any]
    display_name: str
    description: Optional[str]
    icon: Optional[str]
    sort_order: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# 支付统计
class PaymentStatistics(BaseModel):
    total_amount: float = Field(..., description="总金额")
    total_count: int = Field(..., description="总数量")
    pending_count: int = Field(..., description="待处理数量")
    success_count: int = Field(..., description="成功数量")
    failed_count: int = Field(..., description="失败数量")
    success_rate: float = Field(..., description="成功率")
    alipay_amount: float = Field(..., description="支付宝金额")
    wechat_amount: float = Field(..., description="微信支付金额")

# 支付统计别名
PaymentStats = PaymentStatistics

# 退款请求
class RefundRequest(BaseModel):
    payment_id: int = Field(..., description="支付ID")
    amount: float = Field(..., description="退款金额")
    reason: str = Field(..., description="退款原因")
    description: Optional[str] = Field(None, description="退款描述")

# 退款响应
class RefundResponse(BaseModel):
    id: int
    payment_id: int
    amount: float
    reason: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# 支付通知
class PaymentNotification(BaseModel):
    payment_id: int
    status: PaymentStatus
    message: str
    timestamp: datetime
    data: Optional[Dict[str, Any]] = None

# 支付错误
class PaymentError(BaseModel):
    error_code: str = Field(..., description="错误代码")
    error_message: str = Field(..., description="错误消息")
    error_detail: Optional[str] = Field(None, description="错误详情")
    timestamp: datetime = Field(default_factory=datetime.now, description="错误时间")

# 支付验证
class PaymentVerification(BaseModel):
    payment_id: int = Field(..., description="支付ID")
    signature: str = Field(..., description="签名")
    timestamp: datetime = Field(..., description="时间戳")
    nonce: str = Field(..., description="随机数")

# 支付查询
class PaymentQuery(BaseModel):
    order_no: Optional[str] = Field(None, description="订单号")
    transaction_id: Optional[str] = Field(None, description="交易号")
    payment_method: Optional[PaymentMethodEnum] = Field(None, description="支付方式")
    status: Optional[PaymentStatus] = Field(None, description="支付状态")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")
    page: int = Field(default=1, ge=1, description="页码")
    size: int = Field(default=20, ge=1, le=100, description="每页数量")

# 支付结果
class PaymentResult(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="结果消息")
    data: Optional[Dict[str, Any]] = Field(None, description="结果数据")
    error_code: Optional[str] = Field(None, description="错误代码")
    error_message: Optional[str] = Field(None, description="错误消息")

# 支付方式信息
class PaymentMethodInfo(BaseModel):
    method: PaymentMethodEnum = Field(..., description="支付方式")
    name: str = Field(..., description="支付名称")
    description: str = Field(..., description="支付描述")
    icon: str = Field(..., description="支付图标")
    is_enabled: bool = Field(..., description="是否启用")
    min_amount: Optional[float] = Field(None, description="最小金额")
    max_amount: Optional[float] = Field(None, description="最大金额")
    fees: Optional[Dict[str, float]] = Field(None, description="手续费")
    supported_currencies: list[str] = Field(default=["CNY"], description="支持的货币")

# 支付网关配置
class PaymentGatewayConfig(BaseModel):
    gateway_name: str = Field(..., description="网关名称")
    api_key: str = Field(..., description="API密钥")
    api_secret: str = Field(..., description="API密钥")
    merchant_id: Optional[str] = Field(None, description="商户ID")
    gateway_url: str = Field(..., description="网关地址")
    callback_url: str = Field(..., description="回调地址")
    return_url: str = Field(..., description="返回地址")
    is_sandbox: bool = Field(default=False, description="是否沙箱环境")
    timeout: int = Field(default=30, description="超时时间(秒)")
    retry_times: int = Field(default=3, description="重试次数")

# 支付回调处理结果
class PaymentCallbackResult(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="处理结果")
    payment_id: Optional[int] = Field(None, description="支付ID")
    order_no: Optional[str] = Field(None, description="订单号")
    transaction_id: Optional[str] = Field(None, description="交易号")
    amount: Optional[float] = Field(None, description="金额")
    status: Optional[PaymentStatus] = Field(None, description="状态")
    processed_at: datetime = Field(default_factory=datetime.now, description="处理时间") 

class PaymentMethodBase(BaseModel):
    name: str = Field(..., description="支付方式名称")
    type: str = Field(..., description="支付类型")
    status: str = Field("active", description="状态")
    sort_order: int = Field(0, description="排序")
    description: Optional[str] = Field(None, description="描述")

class PaymentMethodCreate(PaymentMethodBase):
    config: Optional[Dict[str, Any]] = Field(None, description="支付配置信息")

class PaymentMethodUpdate(BaseModel):
    name: Optional[str] = Field(None, description="支付方式名称")
    type: Optional[str] = Field(None, description="支付类型")
    status: Optional[str] = Field(None, description="状态")
    sort_order: Optional[int] = Field(None, description="排序")
    description: Optional[str] = Field(None, description="描述")
    config: Optional[Dict[str, Any]] = Field(None, description="支付配置信息")

class PaymentMethodSchema(PaymentMethodBase):
    id: int
    config: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PaymentMethodList(BaseModel):
    items: List[PaymentMethodSchema]
    total: int
    page: int
    size: int

# 安全的公开接口响应模型（不包含敏感信息）
class PaymentMethodPublic(BaseModel):
    """公开接口使用的支付方式模型（不包含敏感信息）"""
    id: int
    name: str = Field(..., description="支付方式名称")
    type: str = Field(..., description="支付类型")
    status: str = Field("active", description="状态")
    sort_order: int = Field(0, description="排序")
    description: Optional[str] = Field(None, description="描述")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# 各种支付方式的配置Schema
class AlipayConfig(BaseModel):
    app_id: str = Field(..., description="支付宝App ID")
    merchant_private_key: str = Field(..., description="商户私钥")
    alipay_public_key: str = Field(..., description="支付宝公钥")
    return_url: str = Field(..., description="同步回调地址")
    notify_url: str = Field(..., description="异步回调地址")

class WechatConfig(BaseModel):
    mch_id: str = Field(..., description="微信商户号")
    app_id: str = Field(..., description="微信App ID")
    api_key: str = Field(..., description="API密钥")
    cert_path: str = Field(..., description="证书路径")
    notify_url: str = Field(..., description="异步回调地址")

class PayPalConfig(BaseModel):
    client_id: str = Field(..., description="PayPal Client ID")
    secret: str = Field(..., description="PayPal Secret")
    environment: str = Field("sandbox", description="环境: sandbox, live")

class StripeConfig(BaseModel):
    publishable_key: str = Field(..., description="Stripe Publishable Key")
    secret_key: str = Field(..., description="Stripe Secret Key")
    webhook_secret: str = Field(..., description="Webhook Secret")

class BankTransferConfig(BaseModel):
    bank_name: str = Field(..., description="银行名称")
    account_name: str = Field(..., description="账户名")
    account_number: str = Field(..., description="账号")
    branch: str = Field(..., description="开户行")
    notes: str = Field(..., description="转账备注要求")

class CryptoConfig(BaseModel):
    currency: List[str] = Field(..., description="支持的币种")
    wallet_address: str = Field(..., description="钱包地址")
    network: str = Field("mainnet", description="网络: mainnet, testnet")

# 支付交易相关Schema
class PaymentTransactionBase(BaseModel):
    order_id: int = Field(..., description="订单ID")
    user_id: int = Field(..., description="用户ID")
    payment_method_id: int = Field(..., description="支付方式ID")
    amount: int = Field(..., description="支付金额（分）")
    currency: str = Field("CNY", description="货币")

class PaymentTransactionCreate(PaymentTransactionBase):
    pass

class PaymentTransactionUpdate(BaseModel):
    status: Optional[str] = Field(None, description="状态")
    external_transaction_id: Optional[str] = Field(None, description="第三方交易号")
    payment_data: Optional[Dict[str, Any]] = Field(None, description="支付相关数据")
    callback_data: Optional[Dict[str, Any]] = Field(None, description="回调数据")

class PaymentTransaction(PaymentTransactionBase):
    id: int
    transaction_id: str
    external_transaction_id: Optional[str] = None
    status: str
    payment_data: Optional[Dict[str, Any]] = None
    callback_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PaymentTransactionList(BaseModel):
    items: List[PaymentTransaction]
    total: int
    page: int
    size: int

# 支付回调相关Schema
class PaymentCallbackBase(BaseModel):
    payment_transaction_id: int
    callback_type: str
    callback_data: Dict[str, Any]

class PaymentCallbackCreate(PaymentCallbackBase):
    pass

class PaymentCallbackUpdate(BaseModel):
    processed: Optional[bool] = None
    processing_result: Optional[str] = None

class PaymentCallback(PaymentCallbackBase):
    id: int
    processed: bool
    processing_result: Optional[str]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True 
# 为了向后兼容，PaymentMethod 指向枚举（用于类型转换）
# 注意：PaymentMethodSchema 用于数据库模型序列化
PaymentMethod = PaymentMethodEnum
