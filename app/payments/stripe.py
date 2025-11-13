import logging
import json
import requests
from typing import Dict, Any, Optional
from app.contracts.payment_interface import PaymentInterface, PaymentRequest, PaymentResponse, PaymentNotify

logger = logging.getLogger(__name__)


class StripePayment(PaymentInterface):
    """Stripe支付实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.publishable_key = config.get('stripe_publishable_key', '')
        self.secret_key = config.get('stripe_secret_key', '')
        self.webhook_secret = config.get('stripe_webhook_secret', '')
        self.base_url = 'https://api.stripe.com/v1'
    
    def pay(self, request: PaymentRequest) -> PaymentResponse:
        """创建Stripe支付订单"""
        try:
            # 创建支付意图
            payment_intent_data = {
                'amount': request.total_amount,  # Stripe使用分为单位
                'currency': 'usd',
                'metadata': {
                    'trade_no': request.trade_no,
                    'user_id': str(request.user_id),
                    'subject': request.subject
                },
                'automatic_payment_methods': {
                    'enabled': True
                }
            }
            
            headers = {
                'Authorization': f'Bearer {self.secret_key}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # 转换数据格式
            form_data = self._dict_to_form_data(payment_intent_data)
            
            response = requests.post(
                f'{self.base_url}/payment_intents',
                headers=headers,
                data=form_data,
                timeout=30
            )
            
            result = response.json()
            
            if response.status_code == 200:
                client_secret = result.get('client_secret')
                if client_secret:
                    # 返回客户端密钥，前端使用Stripe.js处理支付
                    return PaymentResponse(
                        type=2,  # Stripe客户端密钥
                        data=client_secret,
                        trade_no=request.trade_no
                    )
                else:
                    raise Exception("未获取到Stripe客户端密钥")
            else:
                error_msg = result.get('error', {}).get('message', '未知错误')
                raise Exception(f"Stripe支付创建失败: {error_msg}")
                
        except Exception as e:
            raise Exception(f"创建Stripe支付订单失败: {str(e)}")
    
    def verify_notify(self, params: Dict[str, Any]) -> Optional[PaymentNotify]:
        """验证Stripe支付回调"""
        try:
            # Stripe webhook验证
            event_type = params.get('type')
            data = params.get('data', {})
            payment_intent = data.get('object', {})
            
            if event_type == 'payment_intent.succeeded':
                trade_no = payment_intent.get('metadata', {}).get('trade_no')
                amount = payment_intent.get('amount', 0)
                
                if trade_no:
                    return PaymentNotify(
                        trade_no=trade_no,
                        callback_no=payment_intent.get('id'),
                        amount=amount,
                        status='success'
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"验证Stripe回调失败: {str(e)}", exc_info=True)
            return None
    
    def get_config_form(self) -> Dict[str, Any]:
        """获取Stripe配置表单"""
        return {
            'stripe_publishable_key': {
                'label': 'Stripe公钥',
                'type': 'input',
                'required': True,
                'description': 'Stripe公钥，用于前端'
            },
            'stripe_secret_key': {
                'label': 'Stripe私钥',
                'type': 'input',
                'required': True,
                'description': 'Stripe私钥，用于后端'
            },
            'stripe_webhook_secret': {
                'label': 'Stripe Webhook密钥',
                'type': 'input',
                'required': False,
                'description': 'Stripe Webhook签名密钥'
            }
        }
    
    def _dict_to_form_data(self, data: Dict[str, Any]) -> str:
        """将字典转换为表单数据格式"""
        form_parts = []
        for key, value in data.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    form_parts.append(f"{key}[{sub_key}]={sub_value}")
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        for sub_key, sub_value in item.items():
                            form_parts.append(f"{key}[{i}][{sub_key}]={sub_value}")
                    else:
                        form_parts.append(f"{key}[{i}]={item}")
            else:
                form_parts.append(f"{key}={value}")
        
        return '&'.join(form_parts)
