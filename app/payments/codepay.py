import logging
import json
import requests
import hashlib
import time
from typing import Dict, Any, Optional
from urllib.parse import urlencode
from app.contracts.payment_interface import PaymentInterface, PaymentRequest, PaymentResponse, PaymentNotify

logger = logging.getLogger(__name__)


class CodepayPayment(PaymentInterface):
    """码支付实现（支持支付宝、微信、QQ钱包等）"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.codepay_id = config.get('codepay_id', '')  # 码支付ID
        self.codepay_token = config.get('codepay_token', '')  # 码支付Token
        self.codepay_type = config.get('codepay_type', '1')  # 支付类型：1=支付宝，2=QQ钱包，3=微信
        self.gateway_url = config.get('codepay_gateway', 'https://api.xiuxiu888.com/creat_order')
        
    def pay(self, request: PaymentRequest) -> PaymentResponse:
        """创建码支付订单"""
        try:
            if not self.codepay_id or not self.codepay_token:
                raise Exception("码支付配置不完整：缺少ID或Token")
            
            # 金额转换为元，保留2位小数
            total_amount_yuan = request.total_amount / 100
            total_amount_str = f"{total_amount_yuan:.2f}"
            
            # 构建请求参数
            params = {
                'id': self.codepay_id,
                'type': self.codepay_type,  # 1=支付宝，2=QQ钱包，3=微信
                'price': total_amount_str,
                'pay_id': request.trade_no,  # 商户订单号
                'notify_url': request.notify_url,
                'return_url': request.return_url,
                'param': json.dumps({
                    'subject': request.subject,
                    'body': request.body
                })
            }
            
            # 生成签名
            sign = self._generate_sign(params)
            params['sign'] = sign
            
            logger.info(f"码支付请求参数: {params}")
            
            # 发送请求
            response = requests.post(
                self.gateway_url,
                data=params,
                timeout=30,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            result = response.json()
            logger.info(f"码支付响应: {result}")
            
            if result.get('code') == 1:
                # 成功
                pay_url = result.get('pay_url', '')
                qrcode = result.get('qrcode', '')
                
                if qrcode:
                    # 返回二维码
                    return PaymentResponse(
                        type=0,  # 二维码类型
                        data=qrcode,
                        trade_no=request.trade_no
                    )
                elif pay_url:
                    # 返回跳转URL
                    return PaymentResponse(
                        type=1,  # 跳转URL类型
                        data=pay_url,
                        trade_no=request.trade_no
                    )
                else:
                    raise Exception("码支付返回数据格式错误")
            else:
                error_msg = result.get('msg', '未知错误')
                raise Exception(f"码支付创建失败: {error_msg}")
                
        except Exception as e:
            logger.error(f"码支付订单创建失败: {str(e)}")
            raise Exception(f"码支付订单创建失败: {str(e)}")
    
    def verify_notify(self, params: Dict[str, Any]) -> Optional[PaymentNotify]:
        """验证码支付回调"""
        try:
            logger.info(f"码支付回调参数: {params}")
            
            # 验证签名
            if not self._verify_sign(params):
                logger.error("码支付回调签名验证失败")
                return None
            
            logger.info("码支付回调签名验证成功")
            
            # 检查支付状态
            pay_no = params.get('pay_no', '')  # 平台订单号
            pay_id = params.get('pay_id', '')  # 商户订单号
            money = params.get('money', '0')  # 金额（元）
            status = params.get('status', '')  # 支付状态
            
            if status != 'success':
                logger.warning(f"支付状态不是成功: {status}")
                return None
            
            if not pay_id:
                logger.error("回调中缺少订单号(pay_id)")
                return None
            
            logger.info(f"订单号: {pay_id}, 平台订单号: {pay_no}, 金额: {money}")
            
            return PaymentNotify(
                trade_no=pay_id,  # 使用商户订单号
                callback_no=pay_no,  # 使用平台订单号
                amount=int(float(money) * 100),  # 转换为分
                status='success'
            )
            
        except Exception as e:
            logger.error(f"验证码支付回调失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_config_form(self) -> Dict[str, Any]:
        """获取码支付配置表单"""
        return {
            'codepay_type': {
                'label': '支付类型',
                'type': 'select',
                'required': True,
                'options': [
                    {'value': '1', 'label': '支付宝'},
                    {'value': '2', 'label': 'QQ钱包'},
                    {'value': '3', 'label': '微信支付'}
                ],
                'default': '1',
                'description': '选择码支付的支付类型'
            },
            'codepay_id': {
                'label': '码支付ID',
                'type': 'input',
                'required': True,
                'description': '码支付商户ID'
            },
            'codepay_token': {
                'label': '码支付Token',
                'type': 'input',
                'required': True,
                'description': '码支付通信密钥Token'
            },
            'codepay_gateway': {
                'label': '网关地址',
                'type': 'input',
                'required': True,
                'default': 'https://api.xiuxiu888.com/creat_order',
                'description': '码支付API网关地址'
            }
        }
    
    def _generate_sign(self, params: Dict[str, Any]) -> str:
        """生成MD5签名"""
        # 排除sign参数
        filtered_params = {k: v for k, v in params.items() if k != 'sign' and v}
        # 按键名排序
        sorted_params = sorted(filtered_params.items())
        # 构建签名字符串
        sign_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
        sign_string += f"&key={self.codepay_token}"
        # MD5加密并转大写
        sign = hashlib.md5(sign_string.encode('utf-8')).hexdigest().upper()
        return sign
    
    def _verify_sign(self, params: Dict[str, Any]) -> bool:
        """验证MD5签名"""
        try:
            sign = params.get('sign', '')
            if not sign:
                logger.error("缺少签名字段")
                return False
            
            # 生成签名
            calculated_sign = self._generate_sign(params)
            
            # 比较签名（不区分大小写）
            if sign.upper() != calculated_sign.upper():
                logger.error(f"签名不匹配: 收到={sign}, 计算={calculated_sign}")
                return False
            
            logger.info("签名验证成功")
            return True
            
        except Exception as e:
            logger.error(f"验证签名失败: {str(e)}")
            return False

