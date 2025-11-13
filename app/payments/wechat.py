import logging
import json
import hashlib
import hmac
import time
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional
from app.contracts.payment_interface import PaymentInterface, PaymentRequest, PaymentResponse, PaymentNotify

logger = logging.getLogger(__name__)


class WechatPayment(PaymentInterface):
    """微信支付实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.app_id = config.get('wechat_app_id', '')
        self.mch_id = config.get('wechat_mch_id', '')
        self.api_key = config.get('wechat_api_key', '')
        self.cert_path = config.get('wechat_cert_path', '')
        self.key_path = config.get('wechat_key_path', '')
        self.gateway_url = 'https://api.mch.weixin.qq.com/pay/unifiedorder'
    
    def pay(self, request: PaymentRequest) -> PaymentResponse:
        """创建微信支付订单"""
        try:
            # 构建请求参数
            params = {
                'appid': self.app_id,
                'mch_id': self.mch_id,
                'nonce_str': self._generate_nonce_str(),
                'body': request.subject,
                'detail': request.body,
                'out_trade_no': request.trade_no,
                'total_fee': request.total_amount,  # 微信支付金额单位为分
                'spbill_create_ip': '127.0.0.1',
                'notify_url': request.notify_url,
                'trade_type': 'NATIVE',  # 扫码支付
                'product_id': request.trade_no
            }
            
            # 生成签名
            params['sign'] = self._generate_sign(params)
            
            # 转换为XML
            xml_data = self._dict_to_xml(params)
            
            # 发送请求
            response = requests.post(
                self.gateway_url,
                data=xml_data,
                headers={'Content-Type': 'application/xml'},
                timeout=30
            )
            
            # 解析响应
            result = self._xml_to_dict(response.text)
            
            if result.get('return_code') == 'SUCCESS' and result.get('result_code') == 'SUCCESS':
                qr_code = result.get('code_url', '')
                return PaymentResponse(
                    type=0,  # 二维码
                    data=qr_code,
                    trade_no=request.trade_no
                )
            else:
                error_msg = result.get('err_code_des', result.get('return_msg', '未知错误'))
                raise Exception(f"微信支付创建失败: {error_msg}")
                
        except Exception as e:
            # 如果微信支付API失败，记录错误并抛出异常
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"微信支付创建失败: {str(e)}", exc_info=True)
            raise Exception(f"微信支付创建失败: {str(e)}")
    
    def verify_notify(self, params: Dict[str, Any]) -> Optional[PaymentNotify]:
        """验证微信支付回调"""
        try:
            # 验证签名
            if not self._verify_sign(params):
                return None
            
            # 检查交易状态
            return_code = params.get('return_code')
            result_code = params.get('result_code')
            
            if return_code != 'SUCCESS' or result_code != 'SUCCESS':
                return None
            
            return PaymentNotify(
                trade_no=params.get('out_trade_no'),
                callback_no=params.get('transaction_id'),
                amount=int(params.get('total_fee', 0)),
                status='success'
            )
            
        except Exception as e:
            logger.error(f"验证微信支付回调失败: {str(e)}", exc_info=True)
            return None
    
    def get_config_form(self) -> Dict[str, Any]:
        """获取微信支付配置表单"""
        return {
            'wechat_app_id': {
                'label': '微信APPID',
                'type': 'input',
                'required': True,
                'description': '微信开放平台应用ID'
            },
            'wechat_mch_id': {
                'label': '微信商户号',
                'type': 'input',
                'required': True,
                'description': '微信支付商户号'
            },
            'wechat_api_key': {
                'label': '微信API密钥',
                'type': 'input',
                'required': True,
                'description': '微信支付API密钥'
            },
            'wechat_cert_path': {
                'label': '微信证书路径',
                'type': 'input',
                'required': False,
                'description': '微信支付证书文件路径'
            },
            'wechat_key_path': {
                'label': '微信私钥路径',
                'type': 'input',
                'required': False,
                'description': '微信支付私钥文件路径'
            }
        }
    
    def _generate_nonce_str(self) -> str:
        """生成随机字符串"""
        import random
        import string
        return ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    
    def _generate_sign(self, params: Dict[str, Any]) -> str:
        """生成MD5签名"""
        # 过滤空值并排序
        filtered_params = {k: v for k, v in params.items() if v and k != 'sign'}
        sorted_params = sorted(filtered_params.items())
        
        # 构建待签名字符串
        sign_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
        sign_string += f"&key={self.api_key}"
        
        # 生成MD5签名并转大写
        return hashlib.md5(sign_string.encode('utf-8')).hexdigest().upper()
    
    def _verify_sign(self, params: Dict[str, Any]) -> bool:
        """验证MD5签名"""
        try:
            sign = params.get('sign', '')
            calculated_sign = self._generate_sign(params)
            return sign == calculated_sign
        except Exception as e:
            logger.error(f"验证签名失败: {str(e)}", exc_info=True)
            return False
    
    def _dict_to_xml(self, params: Dict[str, Any]) -> str:
        """字典转XML"""
        xml_parts = ['<xml>']
        for key, value in params.items():
            xml_parts.append(f'<{key}><![CDATA[{value}]]></{key}>')
        xml_parts.append('</xml>')
        return ''.join(xml_parts)
    
    def _xml_to_dict(self, xml_string: str) -> Dict[str, Any]:
        """XML转字典"""
        try:
            root = ET.fromstring(xml_string)
            result = {}
            for child in root:
                result[child.tag] = child.text
            return result
        except Exception as e:
            logger.error(f"解析XML失败: {str(e)}", exc_info=True)
            return {}
