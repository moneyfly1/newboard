from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from app.core.database import Base

class PaymentConfig(Base):
    """支付配置模型（移植自cboard项目）"""
    __tablename__ = "payment_configs"

    id = Column(Integer, primary_key=True, index=True)
    pay_type = Column(String(50), nullable=False, comment="支付类型")
    app_id = Column(Text, comment="支付宝/微信App ID")
    merchant_private_key = Column(Text, comment="商户私钥")
    alipay_public_key = Column(Text, comment="支付宝公钥")

    # 微信支付字段
    wechat_app_id = Column(Text, comment="微信App ID")
    wechat_mch_id = Column(Text, comment="微信商户号")
    wechat_api_key = Column(Text, comment="微信API密钥")

    # PayPal字段
    paypal_client_id = Column(Text, comment="PayPal Client ID")
    paypal_secret = Column(Text, comment="PayPal Secret")

    # Stripe字段
    stripe_publishable_key = Column(Text, comment="Stripe Publishable Key")
    stripe_secret_key = Column(Text, comment="Stripe Secret Key")

    # 银行转账字段
    bank_name = Column(Text, comment="银行名称")
    account_name = Column(Text, comment="账户名")
    account_number = Column(Text, comment="账号")

    # 加密货币字段
    wallet_address = Column(Text, comment="钱包地址")

    status = Column(Integer, default=1, comment="状态：1启用，0禁用")
    return_url = Column(Text, comment="同步回调地址")
    notify_url = Column(Text, comment="异步回调地址")
    sort_order = Column(Integer, default=0, comment="排序")

    # 扩展配置JSON
    config_json = Column(JSON, comment="扩展配置")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def get_config(self) -> dict:
        """获取配置字典"""
        config = {
            'pay_type': self.pay_type,
            'status': self.status,
            'return_url': self.return_url,
            'notify_url': self.notify_url,
            'sort_order': self.sort_order
        }

        # 根据支付类型添加特定配置
        if self.pay_type == 'alipay':
            config.update({
                'app_id': self.app_id,
                'merchant_private_key': self.merchant_private_key,
                'alipay_public_key': self.alipay_public_key
            })
        elif self.pay_type == 'wechat':
            config.update({
                'app_id': self.wechat_app_id,
                'mch_id': self.wechat_mch_id,
                'api_key': self.wechat_api_key
            })
        elif self.pay_type == 'paypal':
            config.update({
                'client_id': self.paypal_client_id,
                'secret': self.paypal_secret
            })
        elif self.pay_type == 'stripe':
            config.update({
                'publishable_key': self.stripe_publishable_key,
                'secret_key': self.stripe_secret_key
            })
        elif self.pay_type == 'bank_transfer':
            config.update({
                'bank_name': self.bank_name,
                'account_name': self.account_name,
                'account_number': self.account_number
            })
        elif self.pay_type == 'crypto':
            config.update({
                'wallet_address': self.wallet_address
            })

        # 合并扩展配置
        if self.config_json:
            config.update(self.config_json)

        return config

    def set_config(self, config: dict):
        """设置配置"""
        self.pay_type = config.get('pay_type', self.pay_type)
        self.status = config.get('status', self.status)
        self.return_url = config.get('return_url', self.return_url)
        self.notify_url = config.get('notify_url', self.notify_url)
        self.sort_order = config.get('sort_order', self.sort_order)

        # 根据支付类型设置特定配置
        if self.pay_type == 'alipay':
            self.app_id = config.get('app_id')
            self.merchant_private_key = config.get('merchant_private_key')
            self.alipay_public_key = config.get('alipay_public_key')
        elif self.pay_type == 'wechat':
            self.wechat_app_id = config.get('app_id')
            self.wechat_mch_id = config.get('mch_id')
            self.wechat_api_key = config.get('api_key')
        elif self.pay_type == 'paypal':
            self.paypal_client_id = config.get('client_id')
            self.paypal_secret = config.get('secret')
        elif self.pay_type == 'stripe':
            self.stripe_publishable_key = config.get('publishable_key')
            self.stripe_secret_key = config.get('secret_key')
        elif self.pay_type == 'bank_transfer':
            self.bank_name = config.get('bank_name')
            self.account_name = config.get('account_name')
            self.account_number = config.get('account_number')
        elif self.pay_type == 'crypto':
            self.wallet_address = config.get('wallet_address')

        # 保存扩展配置
        self.config_json = {k: v for k, v in config.items()
                          if k not in ['pay_type', 'status', 'return_url', 'notify_url', 'sort_order',
                                     'app_id', 'merchant_private_key', 'alipay_public_key',
                                     'mch_id', 'api_key', 'client_id', 'secret',
                                     'publishable_key', 'secret_key', 'bank_name',
                                     'account_name', 'account_number', 'wallet_address']}

    class Config:
        from_attributes = True
