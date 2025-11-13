import logging
import json
import requests
import base64
from typing import Dict, Any, Optional
from app.contracts.payment_interface import PaymentInterface, PaymentRequest, PaymentResponse, PaymentNotify

logger = logging.getLogger(__name__)


class PaypalPayment(PaymentInterface):
    """PayPal支付实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client_id = config.get('paypal_client_id', '')
        self.client_secret = config.get('paypal_secret', '')
        self.mode = config.get('paypal_mode', 'sandbox')  # sandbox or live
        
        # 根据模式设置API端点
        if self.mode == 'live':
            self.base_url = 'https://api.paypal.com'
        else:
            self.base_url = 'https://api.sandbox.paypal.com'
        
        self.access_token = None
    
    def pay(self, request: PaymentRequest) -> PaymentResponse:
        """创建PayPal支付订单"""
        try:
            # 获取访问令牌
            if not self.access_token:
                self.access_token = self._get_access_token()
            
            # 创建支付订单
            payment_data = {
                'intent': 'sale',
                'payer': {
                    'payment_method': 'paypal'
                },
                'transactions': [{
                    'amount': {
                        'total': str(request.total_amount / 100),  # 转换为美元
                        'currency': 'USD'
                    },
                    'description': request.subject,
                    'item_list': {
                        'items': [{
                            'name': request.subject,
                            'description': request.body,
                            'quantity': '1',
                            'price': str(request.total_amount / 100),
                            'currency': 'USD'
                        }]
                    }
                }],
                'redirect_urls': {
                    'return_url': request.return_url,
                    'cancel_url': request.return_url + '?cancel=1'
                }
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.access_token}'
            }
            
            response = requests.post(
                f'{self.base_url}/v1/payments/payment',
                headers=headers,
                data=json.dumps(payment_data),
                timeout=30
            )
            
            result = response.json()
            
            if response.status_code == 201:
                # 获取支付链接
                approval_url = None
                for link in result.get('links', []):
                    if link.get('rel') == 'approval_url':
                        approval_url = link.get('href')
                        break
                
                if approval_url:
                    return PaymentResponse(
                        type=1,  # 跳转URL
                        data=approval_url,
                        trade_no=request.trade_no
                    )
                else:
                    raise Exception("未找到PayPal支付链接")
            else:
                error_msg = result.get('message', '未知错误')
                raise Exception(f"PayPal支付创建失败: {error_msg}")
                
        except Exception as e:
            raise Exception(f"创建PayPal支付订单失败: {str(e)}")
    
    def verify_notify(self, params: Dict[str, Any]) -> Optional[PaymentNotify]:
        """验证PayPal支付回调"""
        try:
            payment_id = params.get('paymentId')
            payer_id = params.get('PayerID')
            
            if not payment_id or not payer_id:
                return None
            
            # 执行支付
            if not self.access_token:
                self.access_token = self._get_access_token()
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.access_token}'
            }
            
            execute_data = {
                'payer_id': payer_id
            }
            
            response = requests.post(
                f'{self.base_url}/v1/payments/payment/{payment_id}/execute',
                headers=headers,
                data=json.dumps(execute_data),
                timeout=30
            )
            
            result = response.json()
            
            if response.status_code == 200:
                state = result.get('state')
                if state == 'approved':
                    # 获取交易金额
                    amount = 0
                    for transaction in result.get('transactions', []):
                        amount_info = transaction.get('amount', {})
                        amount = int(float(amount_info.get('total', 0)) * 100)
                        break
                    
                    return PaymentNotify(
                        trade_no=payment_id,
                        callback_no=payment_id,
                        amount=amount,
                        status='success'
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"验证PayPal回调失败: {str(e)}", exc_info=True)
            return None
    
    def get_config_form(self) -> Dict[str, Any]:
        """获取PayPal配置表单"""
        return {
            'paypal_client_id': {
                'label': 'PayPal客户端ID',
                'type': 'input',
                'required': True,
                'description': 'PayPal应用客户端ID'
            },
            'paypal_secret': {
                'label': 'PayPal客户端密钥',
                'type': 'input',
                'required': True,
                'description': 'PayPal应用客户端密钥'
            },
            'paypal_mode': {
                'label': 'PayPal模式',
                'type': 'select',
                'required': True,
                'options': [
                    {'value': 'sandbox', 'label': '沙箱模式'},
                    {'value': 'live', 'label': '生产模式'}
                ],
                'default': 'sandbox',
                'description': 'PayPal API环境模式'
            }
        }
    
    def _get_access_token(self) -> str:
        """获取PayPal访问令牌"""
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = 'grant_type=client_credentials'
        
        response = requests.post(
            f'{self.base_url}/v1/oauth2/token',
            headers=headers,
            data=data,
            timeout=30
        )
        
        result = response.json()
        
        if response.status_code == 200:
            return result.get('access_token')
        else:
            raise Exception(f"获取PayPal访问令牌失败: {result.get('error_description', '未知错误')}")
