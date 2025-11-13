from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class PaymentConfigBase(BaseModel):
    pay_type: str = Field(..., description="支付类型")
    app_id: Optional[str] = Field(None, description="支付宝/微信App ID")
    merchant_private_key: Optional[str] = Field(None, description="商户私钥")
    alipay_public_key: Optional[str] = Field(None, description="支付宝公钥")
    wechat_app_id: Optional[str] = Field(None, description="微信App ID")
    wechat_mch_id: Optional[str] = Field(None, description="微信商户号")
    wechat_api_key: Optional[str] = Field(None, description="微信API密钥")
    paypal_client_id: Optional[str] = Field(None, description="PayPal Client ID")
    paypal_secret: Optional[str] = Field(None, description="PayPal Secret")
    stripe_publishable_key: Optional[str] = Field(None, description="Stripe Publishable Key")
    stripe_secret_key: Optional[str] = Field(None, description="Stripe Secret Key")
    bank_name: Optional[str] = Field(None, description="银行名称")
    account_name: Optional[str] = Field(None, description="账户名")
    account_number: Optional[str] = Field(None, description="账号")
    wallet_address: Optional[str] = Field(None, description="钱包地址")
    status: int = Field(1, description="状态：1启用，0禁用")
    return_url: Optional[str] = Field(None, description="同步回调地址")
    notify_url: Optional[str] = Field(None, description="异步回调地址")
    sort_order: int = Field(0, description="排序")
    config_json: Optional[Dict[str, Any]] = Field(None, description="扩展配置")

class PaymentConfigCreate(PaymentConfigBase):
    pass

class PaymentConfigUpdate(BaseModel):
    pay_type: Optional[str] = None
    app_id: Optional[str] = None
    merchant_private_key: Optional[str] = None
    alipay_public_key: Optional[str] = None
    wechat_app_id: Optional[str] = None
    wechat_mch_id: Optional[str] = None
    wechat_api_key: Optional[str] = None
    paypal_client_id: Optional[str] = None
    paypal_secret: Optional[str] = None
    stripe_publishable_key: Optional[str] = None
    stripe_secret_key: Optional[str] = None
    bank_name: Optional[str] = None
    account_name: Optional[str] = None
    account_number: Optional[str] = None
    wallet_address: Optional[str] = None
    status: Optional[int] = None
    return_url: Optional[str] = None
    notify_url: Optional[str] = None
    sort_order: Optional[int] = None
    config_json: Optional[Dict[str, Any]] = None

class PaymentConfig(PaymentConfigBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PaymentConfigList(BaseModel):
    items: list[PaymentConfig]
    total: int
    page: int
    size: int

# 支付配置表单Schema
class AlipayConfigForm(BaseModel):
    app_id: str = Field(..., description="支付宝App ID")
    merchant_private_key: str = Field(..., description="商户私钥")
    alipay_public_key: str = Field(..., description="支付宝公钥")
    return_url: str = Field(..., description="同步回调地址")
    notify_url: str = Field(..., description="异步回调地址")

class WechatConfigForm(BaseModel):
    app_id: str = Field(..., description="微信App ID")
    mch_id: str = Field(..., description="商户号")
    api_key: str = Field(..., description="API密钥")
    notify_url: str = Field(..., description="异步回调地址")

class PayPalConfigForm(BaseModel):
    client_id: str = Field(..., description="PayPal Client ID")
    secret: str = Field(..., description="PayPal Secret")
    environment: str = Field("sandbox", description="环境")

class StripeConfigForm(BaseModel):
    publishable_key: str = Field(..., description="Stripe Publishable Key")
    secret_key: str = Field(..., description="Stripe Secret Key")

class BankTransferConfigForm(BaseModel):
    bank_name: str = Field(..., description="银行名称")
    account_name: str = Field(..., description="账户名")
    account_number: str = Field(..., description="账号")

class CryptoConfigForm(BaseModel):
    wallet_address: str = Field(..., description="钱包地址")
    currency: list[str] = Field(..., description="支持的币种")

# 安全的公开接口响应模型（不包含敏感信息）
class PaymentConfigPublic(BaseModel):
    """公开接口使用的支付配置模型（不包含敏感信息）"""
    id: int
    pay_type: str = Field(..., description="支付类型")
    pay_name: Optional[str] = Field(None, description="支付方式名称")
    pay_check: Optional[str] = Field(None, description="支付标识")
    pay_method: Optional[int] = Field(None, description="支付方式")
    pay_client: Optional[int] = Field(None, description="支付客户端")
    status: int = Field(1, description="状态：1启用，0禁用")
    sort_order: int = Field(0, description="排序")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
