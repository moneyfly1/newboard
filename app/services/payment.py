"""支付服务"""
import hashlib
import hmac
import logging
import random
import string
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.domain_config import get_domain_config
from app.core.settings_manager import settings_manager
from app.models.payment import PaymentCallback, PaymentMethod as PaymentMethodModel, PaymentTransaction
from app.models.payment_config import PaymentConfig
from app.schemas.payment import (
    PaymentCallback,
    PaymentCallbackCreate,
    PaymentCallbackUpdate,
    PaymentConfigCreate,
    PaymentConfigUpdate,
    PaymentCreate,
    PaymentMethodCreate,
    PaymentMethodEnum,
    PaymentMethodUpdate,
    PaymentResponse,
    PaymentStatus,
    PaymentTransactionCreate,
    PaymentTransactionUpdate,
)

logger = logging.getLogger('payment')

PAYMENT_METHOD_NAMES = {
    "alipay": "支付宝",
    "yipay": "易支付",
    "yipay_alipay": "易支付-支付宝",
    "yipay_wxpay": "易支付-微信",
    "codepay_alipay": "码支付-支付宝",
    "codepay_wechat": "码支付-微信",
    "codepay_qq": "码支付-QQ钱包",
    "wechat": "微信支付",
    "paypal": "PayPal",
    "stripe": "Stripe",
    "bank_transfer": "银行转账",
    "crypto": "加密货币"
}


def _get_payment_method_name(payment_type: str) -> str:
    return PAYMENT_METHOD_NAMES.get(payment_type, payment_type)


class PaymentService:
    """支付服务类"""

    def __init__(self, db: Session):
        self.db = db
        self.request = None

    def _get_client_ip(self, request=None) -> str:
        req = request or self.request
        if not req:
            return '127.0.0.1'
        forwarded_for = req.headers.get('X-Forwarded-For')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
            if client_ip:
                return client_ip
        real_ip = req.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        forwarded = req.headers.get('X-Forwarded')
        if forwarded:
            return forwarded.split(',')[0].strip()
        if hasattr(req, 'client') and req.client:
            return req.client.host
        return '127.0.0.1'

    def _normalize_url(self, url: str) -> str:
        return url.strip() if url else ''

    def _format_pem_key(self, key: str, key_type: str = 'private') -> str:
        if not key:
            return ''
        key = key.strip()
        if key.startswith('-----BEGIN'):
            return key
        if key_type == 'private':
            return f"-----BEGIN RSA PRIVATE KEY-----\n{key}\n-----END RSA PRIVATE KEY-----"
        return f"-----BEGIN PUBLIC KEY-----\n{key}\n-----END PUBLIC KEY-----"

    def _ensure_production_gateway(self, gateway_url: str) -> str:
        if not gateway_url or 'alipaydev.com' in gateway_url:
            return 'https://openapi.alipay.com/gateway.do'
        return gateway_url

    def is_payment_enabled(self) -> bool:
        return settings_manager.is_payment_enabled(self.db)

    def get_default_payment_method(self) -> str:
        return settings_manager.get_default_payment_method(self.db)

    def get_payment_currency(self) -> str:
        return settings_manager.get_payment_currency(self.db)

    def get_payment_config(self, config_id: int) -> Optional[PaymentConfig]:
        return self.db.query(PaymentConfig).filter(PaymentConfig.id == config_id).first()

    def get_payment_config_by_name(self, name: str) -> Optional[PaymentConfig]:
        return self.db.query(PaymentConfig).filter(PaymentConfig.name == name).first()

    def get_active_payment_configs(self) -> List[PaymentConfig]:
        return self.db.query(PaymentConfig).filter(
            PaymentConfig.status == 1
        ).order_by(PaymentConfig.sort_order, PaymentConfig.id).all()

    def get_default_payment_config(self) -> Optional[PaymentConfig]:
        default_method = self.get_default_payment_method()
        if default_method:
            return self.get_payment_config_by_name(default_method)
        return self.db.query(PaymentConfig).filter(
            PaymentConfig.status == 1
        ).order_by(PaymentConfig.sort_order, PaymentConfig.id).first()

    def get_available_payment_methods(self) -> List[Dict[str, Any]]:
        result_methods = []
        method_keys = set()
        try:
            methods = self.db.query(PaymentMethodModel).filter(
                PaymentMethodModel.status == "active"
            ).order_by(PaymentMethodModel.sort_order, PaymentMethodModel.id).all()
            for method in methods:
                if method.type not in method_keys:
                    result_methods.append({
                        "key": method.type,
                        "name": method.name,
                        "description": method.description or f"使用{method.name}支付",
                        "icon": f"/icons/{method.type}.png",
                        "enabled": True
                    })
                    method_keys.add(method.type)
        except Exception:
            pass
        configs = self.get_active_payment_configs()
        for config in configs:
            if config.pay_type not in method_keys:
                result_methods.append({
                    "key": config.pay_type,
                    "name": PAYMENT_METHOD_NAMES.get(config.pay_type, config.pay_type),
                    "description": f"使用{PAYMENT_METHOD_NAMES.get(config.pay_type, config.pay_type)}支付",
                    "icon": f"/icons/{config.pay_type}.png",
                    "enabled": True
                })
                method_keys.add(config.pay_type)
        if result_methods:
            return result_methods
        return [
            {"key": "alipay", "name": "支付宝", "description": "使用支付宝扫码支付", "icon": "/icons/alipay.png", "enabled": True},
            {"key": "wechat", "name": "微信支付", "description": "使用微信扫码支付", "icon": "/icons/wechat.png", "enabled": True},
            {"key": "bank_transfer", "name": "银行转账", "description": "通过银行转账支付", "icon": "/icons/bank.png", "enabled": True}
        ]

    def _create_config(self, model_class, create_data):
        obj = model_class(**create_data.dict())
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def _update_config(self, obj, update_data):
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(obj, field, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def create_payment_config(self, config_in: PaymentConfigCreate) -> PaymentConfig:
        return self._create_config(PaymentConfig, config_in)

    def update_payment_config(self, config_id: int, config_in: PaymentConfigUpdate) -> Optional[PaymentConfig]:
        config = self.get_payment_config(config_id)
        return self._update_config(config, config_in) if config else None

    def delete_payment_config(self, config_id: int) -> bool:
        config = self.get_payment_config(config_id)
        if not config:
            return False
        self.db.delete(config)
        self.db.commit()
        return True

    def create_payment_transaction(self, transaction_in: PaymentTransactionCreate) -> PaymentTransaction:
        return self._create_config(PaymentTransaction, transaction_in)

    def get_payment_transaction(self, transaction_id: str) -> Optional[PaymentTransaction]:
        return self.db.query(PaymentTransaction).filter(
            PaymentTransaction.transaction_id == transaction_id
        ).first()

    def update_payment_transaction(self, transaction_id: str, transaction_in: PaymentTransactionUpdate) -> Optional[PaymentTransaction]:
        transaction = self.get_payment_transaction(transaction_id)
        return self._update_config(transaction, transaction_in) if transaction else None

    def create_payment(self, payment_request: PaymentCreate, request=None) -> PaymentResponse:
        logger.info(f"创建支付请求: payment_method={payment_request.payment_method}, order_no={payment_request.order_no}, amount={payment_request.amount}")
        if request:
            self.request = request
        if not self.is_payment_enabled():
            return self._create_failed_response(payment_request, "支付功能未启用")
        payment_method = self.db.query(PaymentMethodModel).filter(
            PaymentMethodModel.type == payment_request.payment_method
        ).first()
        if not payment_method:
            config = self._get_default_payment_config(payment_request.payment_method)
            payment_method_config = {
                "type": payment_request.payment_method,
                "name": _get_payment_method_name(payment_request.payment_method),
                "config": config
            }
        else:
            if payment_method.status != "active":
                return self._create_failed_response(payment_request, "支付方式未启用")
            method_config = payment_method.config or {}
            if not method_config or not method_config.get('app_id'):
                method_config = self._get_default_payment_config(payment_method.type)
            payment_method_config = {
                "type": payment_method.type,
                "name": payment_method.name,
                "config": method_config
            }
        currency = payment_request.currency or self.get_payment_currency()
        try:
            payment_creators = {
                "alipay": self._create_alipay_payment,
                "yipay": self._create_yipay_payment,
                "yipay_alipay": self._create_yipay_payment,
                "yipay_wxpay": self._create_yipay_payment,
                "codepay_alipay": self._create_codepay_payment,
                "codepay_wechat": self._create_codepay_payment,
                "codepay_qq": self._create_codepay_payment,
                "wechat": self._create_wechat_payment,
                "paypal": self._create_paypal_payment,
                "stripe": self._create_stripe_payment,
                "bank_transfer": self._create_bank_transfer_payment,
                "crypto": self._create_crypto_payment
            }
            payment_type = payment_method_config["type"]
            creator = payment_creators.get(payment_type)
            if creator:
                return creator(payment_method_config["config"], payment_request, currency)
            else:
                return self._create_failed_response(payment_request, "不支持的支付方式")
        except Exception as e:
            logger.error(f"创建支付失败: {str(e)}", exc_info=True)
            return self._create_failed_response(payment_request, f"创建支付失败: {str(e)}")

    def _create_failed_response(self, payment_request: PaymentCreate, message: str = "支付创建失败") -> PaymentResponse:
        try:
            payment_method_enum = PaymentMethodEnum(payment_request.payment_method)
        except ValueError:
            payment_method_enum = PaymentMethodEnum.alipay
        try:
            status_enum = PaymentStatus("failed")
        except ValueError:
            status_enum = PaymentStatus.failed
        return PaymentResponse(
            id=0,
            payment_url=None,
            order_no=payment_request.order_no,
            amount=payment_request.amount,
            payment_method=payment_method_enum,
            status=status_enum,
            created_at=datetime.now(timezone.utc)
        )

    def _get_default_payment_config(self, payment_type: str) -> Dict[str, Any]:
        if payment_type == 'alipay':
            return self._get_alipay_config_from_system()
        elif payment_type in ['yipay', 'yipay_alipay', 'yipay_wxpay']:
            return self._get_yipay_config_from_system(payment_type)
        return {}

    def _get_alipay_config_from_system(self) -> Dict[str, Any]:
        try:
            payment_config = self.db.query(PaymentConfig).filter(
                PaymentConfig.pay_type == 'alipay',
                PaymentConfig.status == 1
            ).first()
            if payment_config:
                return self._build_alipay_config(payment_config.get_config(), is_payment_config=True)
            from app.models.config import SystemConfig
            configs = self.db.query(SystemConfig).filter(
                SystemConfig.key.in_(['alipay_app_id', 'alipay_private_key', 'alipay_public_key', 'alipay_gateway'])
            ).all()
            config_dict = {config.key: config.value for config in configs}
            return self._build_alipay_config(config_dict, is_payment_config=False)
        except Exception as e:
            logger.error(f"获取支付宝配置失败: {str(e)}", exc_info=True)
            return {}

    def _build_alipay_config(self, config_dict: Dict[str, Any], is_payment_config: bool = False) -> Dict[str, Any]:
        base_url = get_domain_config().get_base_url(None, self.db)
        base_url = self._normalize_url(base_url)
        private_key = self._format_pem_key(
            config_dict.get('merchant_private_key' if is_payment_config else 'alipay_private_key', ''),
            'private'
        )
        public_key = self._format_pem_key(config_dict.get('alipay_public_key', ''), 'public')
        notify_url = self._normalize_url(
            config_dict.get('notify_url') or f"{base_url}/api/v1/payment/notify/alipay"
        )
        return_url = self._normalize_url(
            config_dict.get('return_url') or f"{base_url}/payment/success"
        )
        gateway_url = self._ensure_production_gateway(config_dict.get('gateway_url', ''))
        alipay_config = {
            'app_id': config_dict.get('app_id'),
            'merchant_private_key': private_key,
            'alipay_public_key': public_key,
            'gateway_url': gateway_url,
            'notify_url': notify_url,
            'return_url': return_url,
            'debug': False
        }
        if alipay_config['app_id'] and alipay_config['merchant_private_key'] and alipay_config['alipay_public_key']:
            return alipay_config
        return {}

    def _get_yipay_config_from_system(self, payment_type: str = 'yipay_alipay') -> Dict[str, Any]:
        try:
            payment_config = self.db.query(PaymentConfig).filter(
                PaymentConfig.pay_type == payment_type,
                PaymentConfig.status == 1
            ).first()
            if not payment_config:
                return {}
            config_dict = payment_config.get_config()
            base_url = get_domain_config().get_base_url(None, self.db)
            base_url = self._normalize_url(base_url)
            if payment_type == 'yipay_alipay':
                yipay_type = 'alipay'
            elif payment_type == 'yipay_wxpay':
                yipay_type = 'wxpay'
            else:
                yipay_type = config_dict.get('yipay_type', 'alipay')
            yipay_config = {
                'yipay_pid': config_dict.get('yipay_pid', ''),
                'yipay_private_key': config_dict.get('yipay_private_key', ''),
                'yipay_public_key': config_dict.get('yipay_public_key', ''),
                'yipay_gateway': config_dict.get('yipay_gateway', 'https://pay.yi-zhifu.cn/'),
                'yipay_type': yipay_type,
                'notify_url': self._normalize_url(
                    config_dict.get('notify_url') or f"{base_url}/api/v1/payment/notify/yipay"
                ),
                'return_url': self._normalize_url(
                    config_dict.get('return_url') or f"{base_url}/payment/success"
                )
            }
            if yipay_config['yipay_pid'] and yipay_config['yipay_private_key'] and yipay_config['yipay_public_key']:
                return yipay_config
            return {}
        except Exception as e:
            logger.error(f"获取易支付配置失败: {str(e)}", exc_info=True)
            return {}

    def _create_payment_response(self, payment_request: PaymentCreate, payment_url: str,
                                transaction_id: str = None, status: str = "pending") -> PaymentResponse:
        if transaction_id:
            self.create_payment_transaction(PaymentTransactionCreate(
                order_id=0,
                user_id=0,
                payment_method_id=0,
                amount=int(payment_request.amount * 100),
                currency=payment_request.currency or "CNY"
            ))
        try:
            payment_method_enum = PaymentMethodEnum(payment_request.payment_method)
        except ValueError:
            payment_method_enum = PaymentMethodEnum.alipay
        try:
            status_enum = PaymentStatus(status) if isinstance(status, str) else status
        except (ValueError, TypeError):
            status_enum = PaymentStatus.pending
        return PaymentResponse(
            id=0,
            payment_url=payment_url,
            order_no=payment_request.order_no,
            amount=payment_request.amount,
            payment_method=payment_method_enum,
            status=status_enum,
            created_at=datetime.now(timezone.utc)
        )

    def _create_alipay_payment(self, config: Dict[str, Any], request: PaymentCreate, currency: str) -> PaymentResponse:
        try:
            transaction_id = request.order_no
            if config and config.get('app_id') and config.get('merchant_private_key'):
                return self._create_real_alipay_payment(config, request, currency, transaction_id)
            else:
                return self._create_failed_response(request, "支付宝配置不完整，请联系管理员配置真实的支付宝密钥")
        except Exception as e:
            logger.error(f"支付宝支付创建失败: {str(e)}", exc_info=True)
            return self._create_failed_response(request, f"支付宝支付创建失败: {str(e)}")

    def _create_real_alipay_payment(self, config: Dict[str, Any], request: PaymentCreate, currency: str, transaction_id: str) -> PaymentResponse:
        try:
            from app.payments.alipay import AlipayPayment
            from app.contracts.payment_interface import PaymentRequest
            gateway_url = self._ensure_production_gateway(config.get('gateway_url', 'https://openapi.alipay.com/gateway.do'))
            notify_url = self._normalize_url(config.get('notify_url', ''))
            return_url = self._normalize_url(config.get('return_url', ''))
            alipay_config = {
                'alipay_app_id': config.get('app_id', ''),
                'alipay_private_key': config.get('merchant_private_key', ''),
                'alipay_public_key': config.get('alipay_public_key', ''),
                'alipay_gateway': gateway_url,
                'notify_url': notify_url,
                'return_url': return_url
            }
            alipay_payment = AlipayPayment(alipay_config)
            payment_request = PaymentRequest(
                trade_no=transaction_id,
                total_amount=int(request.amount * 100),
                subject=f"CBoard套餐购买-{request.order_no}",
                body=f"订单号：{request.order_no}",
                notify_url=notify_url,
                return_url=return_url,
                user_id=0
            )
            max_retries = 1
            retry_count = 0
            payment_response = None
            last_error = None
            start_time = time.time()
            while retry_count <= max_retries:
                try:
                    payment_response = alipay_payment.pay(payment_request)
                    elapsed_time = time.time() - start_time
                    logger.info(f"支付宝API调用成功 (耗时: {elapsed_time:.2f}秒), 订单号: {request.order_no}")
                    break
                except Exception as e:
                    last_error = e
                    error_msg = str(e)
                    elapsed_time = time.time() - start_time
                    logger.warning(f"支付宝API调用失败 (尝试 {retry_count + 1}/{max_retries + 1}, 耗时: {elapsed_time:.2f}秒): {error_msg}")
                    if ("超时" in error_msg or "timeout" in error_msg.lower() or "响应较慢" in error_msg) and retry_count < max_retries:
                        retry_count += 1
                        time.sleep(0.5)
                        continue
                    else:
                        raise
            if not payment_response:
                error_msg = str(last_error) if last_error else "支付宝支付创建失败"
                raise Exception(error_msg)
            if payment_response.type == 0:
                qr_code_url = payment_response.data
                if not qr_code_url or (not qr_code_url.startswith('http://') and not qr_code_url.startswith('https://')):
                    raise Exception(f"支付宝返回的二维码格式无效: {qr_code_url}")
                return self._create_payment_response(request, qr_code_url, transaction_id)
            else:
                return self._create_payment_response(request, payment_response.data, transaction_id)
        except Exception as e:
            logger.error(f"支付宝支付创建失败: {str(e)}", exc_info=True)
            return self._create_failed_response(request, f"支付宝支付创建失败: {str(e)}")

    def _create_yipay_payment(self, config: Dict[str, Any], request: PaymentCreate, currency: str) -> PaymentResponse:
        try:
            transaction_id = request.order_no
            if config and config.get('yipay_pid') and config.get('yipay_private_key'):
                return self._create_real_yipay_payment(config, request, currency, transaction_id)
            else:
                return self._create_failed_response(request, "易支付配置不完整，请联系管理员配置真实的易支付密钥")
        except Exception as e:
            logger.error(f"易支付创建失败: {str(e)}", exc_info=True)
            return self._create_failed_response(request, f"易支付创建失败: {str(e)}")

    def _create_real_yipay_payment(self, config: Dict[str, Any], request: PaymentCreate, currency: str, transaction_id: str) -> PaymentResponse:
        try:
            from app.payments.yipay import YipayPayment
            from app.contracts.payment_interface import PaymentRequest
            base_url = get_domain_config().get_base_url(None, self.db)
            base_url = self._normalize_url(base_url)
            payment_type = request.payment_method
            if payment_type == 'yipay_alipay':
                yipay_type = 'alipay'
            elif payment_type == 'yipay_wxpay':
                yipay_type = 'wxpay'
            else:
                yipay_type = config.get('yipay_type', 'alipay')
            notify_url = self._normalize_url(
                config.get('notify_url') or f"{base_url}/api/v1/payment/notify/yipay"
            )
            return_url = self._normalize_url(
                config.get('return_url') or f"{base_url}/payment/success"
            )
            yipay_config = {
                'yipay_pid': config.get('yipay_pid', ''),
                'yipay_private_key': config.get('yipay_private_key', ''),
                'yipay_public_key': config.get('yipay_public_key', ''),
                'yipay_gateway': config.get('yipay_gateway', 'https://pay.yi-zhifu.cn/api/pay/create'),
                'yipay_type': yipay_type,
                'notify_url': notify_url,
                'return_url': return_url,
                'clientip': self._get_client_ip()
            }
            yipay_payment = YipayPayment(yipay_config)
            payment_request = PaymentRequest(
                trade_no=transaction_id,
                total_amount=int(request.amount * 100),
                subject=f"CBoard套餐购买-{request.order_no}",
                body=f"订单号：{request.order_no}",
                notify_url=notify_url,
                return_url=return_url,
                user_id=0
            )
            payment_response = yipay_payment.pay(payment_request)
            return self._create_payment_response(request, payment_response.data, transaction_id)
        except Exception as e:
            logger.error(f"易支付创建失败: {str(e)}", exc_info=True)
            return self._create_failed_response(request, f"易支付创建失败: {str(e)}")

    def _create_simple_payment(self, request: PaymentCreate, prefix: str, url_template: str) -> PaymentResponse:
        from app.utils.timezone import get_beijing_time_str
        transaction_id = f"{prefix}{get_beijing_time_str('%Y%m%d%H%M%S')}{request.order_no}"
        payment_url = url_template.format(transaction_id=transaction_id)
        return self._create_payment_response(request, payment_url, transaction_id)

    def _create_payment_with_error_handle(self, request: PaymentCreate, payment_type: str, create_func) -> PaymentResponse:
        try:
            return create_func()
        except Exception as e:
            logger.error(f"{payment_type}支付创建失败: {str(e)}", exc_info=True)
            return self._create_failed_response(request, f"{payment_type}支付创建失败: {str(e)}")

    def _create_wechat_payment(self, config: Dict[str, Any], request: PaymentCreate, currency: str) -> PaymentResponse:
        return self._create_payment_with_error_handle(request, "微信", lambda: self._create_simple_payment(request, "WX", "weixin://wxpay/bizpayurl?pr={transaction_id}"))

    def _create_paypal_payment(self, config: Dict[str, Any], request: PaymentCreate, currency: str) -> PaymentResponse:
        try:
            transaction_id = request.order_no
            if config and config.get('paypal_client_id') and config.get('paypal_secret'):
                return self._create_real_paypal_payment(config, request, currency, transaction_id)
            else:
                return self._create_failed_response(request, "PayPal配置不完整，请联系管理员配置真实的PayPal密钥")
        except Exception as e:
            logger.error(f"PayPal支付创建失败: {str(e)}", exc_info=True)
            return self._create_failed_response(request, f"PayPal支付创建失败: {str(e)}")

    def _create_real_paypal_payment(self, config: Dict[str, Any], request: PaymentCreate, currency: str, transaction_id: str) -> PaymentResponse:
        try:
            from app.payments.paypal import PaypalPayment
            from app.contracts.payment_interface import PaymentRequest
            base_url = get_domain_config().get_base_url(None, self.db)
            base_url = self._normalize_url(base_url)
            notify_url = self._normalize_url(
                config.get('notify_url') or f"{base_url}/api/v1/payment/notify/paypal"
            )
            return_url = self._normalize_url(
                config.get('return_url') or f"{base_url}/payment/success"
            )
            paypal_config = {
                'paypal_client_id': config.get('paypal_client_id', ''),
                'paypal_secret': config.get('paypal_secret', ''),
                'paypal_mode': config.get('paypal_mode', 'sandbox'),
                'notify_url': notify_url,
                'return_url': return_url
            }
            paypal_payment = PaypalPayment(paypal_config)
            payment_request = PaymentRequest(
                trade_no=transaction_id,
                total_amount=int(request.amount * 100),
                subject=f"CBoard套餐购买-{request.order_no}",
                body=f"订单号：{request.order_no}",
                notify_url=notify_url,
                return_url=return_url,
                user_id=0
            )
            payment_response = paypal_payment.pay(payment_request)
            return self._create_payment_response(request, payment_response.data, transaction_id)
        except Exception as e:
            logger.error(f"PayPal支付创建失败: {str(e)}", exc_info=True)
            return self._create_failed_response(request, f"PayPal支付创建失败: {str(e)}")

    def _create_stripe_payment(self, config: Dict[str, Any], request: PaymentCreate, currency: str) -> PaymentResponse:
        return self._create_payment_with_error_handle(request, "Stripe", lambda: self._create_simple_payment(request, "ST", "https://checkout.stripe.com/pay/{transaction_id}"))

    def _create_codepay_payment(self, config: Dict[str, Any], request: PaymentCreate, currency: str) -> PaymentResponse:
        try:
            transaction_id = request.order_no
            if config and config.get('codepay_id') and config.get('codepay_token'):
                return self._create_real_codepay_payment(config, request, currency, transaction_id)
            else:
                return self._create_failed_response(request, "码支付配置不完整，请联系管理员配置真实的码支付密钥")
        except Exception as e:
            logger.error(f"码支付创建失败: {str(e)}", exc_info=True)
            return self._create_failed_response(request, f"码支付创建失败: {str(e)}")

    def _create_real_codepay_payment(self, config: Dict[str, Any], request: PaymentCreate, currency: str, transaction_id: str) -> PaymentResponse:
        try:
            from app.payments.codepay import CodepayPayment
            from app.contracts.payment_interface import PaymentRequest
            base_url = get_domain_config().get_base_url(None, self.db)
            base_url = self._normalize_url(base_url)
            payment_type = request.payment_method
            # 根据支付方式确定码支付类型
            if payment_type == 'codepay_alipay':
                codepay_type = '1'
            elif payment_type == 'codepay_wechat':
                codepay_type = '3'
            elif payment_type == 'codepay_qq':
                codepay_type = '2'
            else:
                codepay_type = config.get('codepay_type', '1')
            notify_url = self._normalize_url(
                config.get('notify_url') or f"{base_url}/api/v1/payment/notify/codepay"
            )
            return_url = self._normalize_url(
                config.get('return_url') or f"{base_url}/payment/success"
            )
            codepay_config = {
                'codepay_id': config.get('codepay_id', ''),
                'codepay_token': config.get('codepay_token', ''),
                'codepay_type': codepay_type,
                'codepay_gateway': config.get('codepay_gateway', 'https://api.xiuxiu888.com/creat_order'),
                'notify_url': notify_url,
                'return_url': return_url
            }
            codepay_payment = CodepayPayment(codepay_config)
            payment_request = PaymentRequest(
                trade_no=transaction_id,
                total_amount=int(request.amount * 100),
                subject=f"CBoard套餐购买-{request.order_no}",
                body=f"订单号：{request.order_no}",
                notify_url=notify_url,
                return_url=return_url,
                user_id=0
            )
            payment_response = codepay_payment.pay(payment_request)
            return self._create_payment_response(request, payment_response.data, transaction_id)
        except Exception as e:
            logger.error(f"码支付创建失败: {str(e)}", exc_info=True)
            return self._create_failed_response(request, f"码支付创建失败: {str(e)}")

    def _create_bank_transfer_payment(self, config: Dict[str, Any], request: PaymentCreate, currency: str) -> PaymentResponse:
        def _create():
            from app.utils.timezone import get_beijing_time_str
            transaction_id = f"BT{get_beijing_time_str('%Y%m%d%H%M%S')}{request.order_no}"
            bank_info = {
                "bank_name": "中国银行",
                "account_name": "CBoard科技有限公司",
                "account_number": "1234567890123456789",
                "amount": request.amount,
                "currency": currency,
                "transaction_id": transaction_id
            }
            payment_url = str(bank_info)
            return self._create_payment_response(request, payment_url, transaction_id)
        return self._create_payment_with_error_handle(request, "银行转账", _create)

    def _create_crypto_payment(self, config: Dict[str, Any], request: PaymentCreate, currency: str) -> PaymentResponse:
        def _create():
            from app.utils.timezone import get_beijing_time_str
            transaction_id = f"CR{get_beijing_time_str('%Y%m%d%H%M%S')}{request.order_no}"
            crypto_info = {
                "wallet_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "amount": request.amount,
                "currency": "BTC",
                "transaction_id": transaction_id
            }
            payment_url = str(crypto_info)
            return self._create_payment_response(request, payment_url, transaction_id)
        return self._create_payment_with_error_handle(request, "加密货币", _create)

    def verify_payment_notify(self, payment_method: str, params: dict):
        try:
            verifiers = {
                'alipay': self._verify_alipay_notify,
                'yipay': self._verify_yipay_notify,
                'yipay_alipay': self._verify_yipay_notify,
                'yipay_wxpay': self._verify_yipay_notify,
                'codepay_alipay': self._verify_codepay_notify,
                'codepay_wechat': self._verify_codepay_notify,
                'codepay_qq': self._verify_codepay_notify,
                'wechat': self._verify_wechat_notify,
                'paypal': self._verify_paypal_notify
            }
            verifier = verifiers.get(payment_method)
            return verifier(params) if verifier else None
        except Exception as e:
            logger.error(f"验证支付回调失败: {str(e)}", exc_info=True)
            return None

    def _verify_alipay_notify(self, params: dict):
        try:
            from app.payments.alipay import AlipayPayment
            alipay_config = self._get_alipay_config_from_system()
            if not alipay_config:
                logger.warning("未找到支付宝配置")
                return None
            alipay_payment = AlipayPayment({
                'alipay_app_id': alipay_config.get('app_id', ''),
                'alipay_private_key': alipay_config.get('merchant_private_key', ''),
                'alipay_public_key': alipay_config.get('alipay_public_key', ''),
                'alipay_gateway': alipay_config.get('gateway_url', 'https://openapi.alipay.com/gateway.do')
            })
            notify = alipay_payment.verify_notify(params)
            if notify:
                logger.info(f"支付宝回调验证成功: 订单号={notify.trade_no}, 交易号={notify.callback_no}")
                return notify
            else:
                logger.warning("支付宝回调验证失败")
                return None
        except Exception as e:
            logger.error(f"验证支付宝回调失败: {str(e)}", exc_info=True)
            return None

    def _verify_yipay_notify(self, params: dict):
        try:
            from app.payments.yipay import YipayPayment
            payment_config = self.db.query(PaymentConfig).filter(
                PaymentConfig.pay_type == 'yipay',
                PaymentConfig.status == 1
            ).first()
            if not payment_config:
                logger.warning("未找到易支付配置")
                return None
            config_dict = payment_config.get_config()
            yipay_config = {
                'yipay_pid': config_dict.get('yipay_pid', ''),
                'yipay_private_key': config_dict.get('yipay_private_key', ''),
                'yipay_public_key': config_dict.get('yipay_public_key', ''),
                'yipay_gateway': config_dict.get('yipay_gateway', 'https://pay.yi-zhifu.cn/api/pay/create')
            }
            yipay_payment = YipayPayment(yipay_config)
            notify = yipay_payment.verify_notify(params)
            if notify:
                logger.info(f"易支付回调验证成功: 订单号={notify.trade_no}, 交易号={notify.callback_no}")
                return notify
            else:
                logger.warning("易支付回调验证失败")
                return None
        except Exception as e:
            logger.error(f"验证易支付回调失败: {str(e)}", exc_info=True)
            return None

    def _verify_wechat_notify(self, params: dict):
        return None

    def _verify_codepay_notify(self, params: dict):
        try:
            from app.payments.codepay import CodepayPayment
            # 查找码支付配置（支持所有码支付类型）
            payment_config = self.db.query(PaymentConfig).filter(
                PaymentConfig.pay_type.in_(['codepay_alipay', 'codepay_wechat', 'codepay_qq']),
                PaymentConfig.status == 1
            ).first()
            if not payment_config:
                logger.warning("未找到码支付配置")
                return None
            config_dict = payment_config.get_config()
            codepay_config = {
                'codepay_id': config_dict.get('codepay_id', ''),
                'codepay_token': config_dict.get('codepay_token', ''),
                'codepay_type': config_dict.get('codepay_type', '1'),
                'codepay_gateway': config_dict.get('codepay_gateway', 'https://api.xiuxiu888.com/creat_order')
            }
            codepay_payment = CodepayPayment(codepay_config)
            notify = codepay_payment.verify_notify(params)
            if notify:
                logger.info(f"码支付回调验证成功: 订单号={notify.trade_no}, 交易号={notify.callback_no}")
                return notify
            else:
                logger.warning("码支付回调验证失败")
                return None
        except Exception as e:
            logger.error(f"验证码支付回调失败: {str(e)}", exc_info=True)
            return None

    def _verify_paypal_notify(self, params: dict):
        try:
            from app.payments.paypal import PaypalPayment
            payment_config = self.db.query(PaymentConfig).filter(
                PaymentConfig.pay_type == 'paypal',
                PaymentConfig.status == 1
            ).first()
            if not payment_config:
                logger.warning("未找到PayPal配置")
                return None
            config_dict = payment_config.get_config()
            paypal_config = {
                'paypal_client_id': config_dict.get('paypal_client_id', ''),
                'paypal_secret': config_dict.get('paypal_secret', ''),
                'paypal_mode': config_dict.get('paypal_mode', 'sandbox')
            }
            paypal_payment = PaypalPayment(paypal_config)
            notify = paypal_payment.verify_notify(params)
            if notify:
                logger.info(f"PayPal回调验证成功: 订单号={notify.trade_no}, 交易号={notify.callback_no}")
                return notify
            else:
                logger.warning("PayPal回调验证失败")
                return None
        except Exception as e:
            logger.error(f"验证PayPal回调失败: {str(e)}", exc_info=True)
            return None

    def _generate_sign(self, params: Dict[str, Any], key: str, sign_type: str = 'md5', exclude_key: str = 'sign') -> str:
        sign_string = "&".join([f"{k}={v}" for k, v in sorted(params.items()) if k != exclude_key])
        if sign_type == 'md5':
            return hashlib.md5(sign_string.encode()).hexdigest()
        elif sign_type == 'md5_upper':
            return hashlib.md5((sign_string + f"&key={key}").encode()).hexdigest().upper()
        elif sign_type == 'hmac_sha512':
            return hmac.new(key.encode(), sign_string.encode(), hashlib.sha512).hexdigest()
        return ''

    def _generate_alipay_sign(self, params: Dict[str, Any], private_key: str) -> str:
        return self._generate_sign(params, private_key, 'md5', 'sign')

    def _generate_wechat_sign(self, params: Dict[str, Any], key: str) -> str:
        return self._generate_sign(params, key, 'md5_upper', 'sign')

    def _generate_crypto_sign(self, params: Dict[str, Any], secret_key: str) -> str:
        return self._generate_sign(params, secret_key, 'hmac_sha512', 'signature')

    def _generate_nonce_str(self) -> str:
        return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

    def _get_paypal_token(self, config) -> str:
        try:
            import requests
            auth_url = "https://api-m.sandbox.paypal.com/v1/oauth2/token" if config.get('sandbox') else "https://api-m.paypal.com/v1/oauth2/token"
            auth_response = requests.post(
                auth_url,
                data={"grant_type": "client_credentials"},
                auth=(config.get('client_id'), config.get('client_secret')),
                headers={"Accept": "application/json", "Accept-Language": "en_US"}
            )
            if auth_response.status_code == 200:
                return auth_response.json().get("access_token", "")
            else:
                raise Exception(f"PayPal认证失败: {auth_response.text}")
        except Exception as e:
            logger.error(f"PayPal token获取失败: {str(e)}", exc_info=True)
            return ""

    def _dict_to_xml(self, data: Dict[str, Any]) -> str:
        xml = "<xml>"
        for key, value in data.items():
            xml += f"<{key}>{value}</{key}>"
        xml += "</xml>"
        return xml

    def _xml_to_dict(self, xml: str) -> Dict[str, Any]:
        root = ET.fromstring(xml)
        return {child.tag: child.text for child in root}

class PaymentMethodService:
    def __init__(self, db: Session):
        self.db = db

    def get_payment_methods(self, skip: int = 0, limit: int = 100,
                          type_filter: Optional[str] = None,
                          status_filter: Optional[str] = None) -> List:
        query = self.db.query(PaymentMethodModel)
        if type_filter:
            query = query.filter(PaymentMethodModel.type == type_filter)
        if status_filter:
            query = query.filter(PaymentMethodModel.status == status_filter)
        return query.order_by(PaymentMethodModel.sort_order, PaymentMethodModel.id).offset(skip).limit(limit).all()

    def get_payment_method(self, payment_method_id: int):
        return self.db.query(PaymentMethodModel).filter(PaymentMethodModel.id == payment_method_id).first()

    def get_active_payment_methods(self) -> List:
        return self.db.query(PaymentMethodModel).filter(
            PaymentMethodModel.status == "active"
        ).order_by(PaymentMethodModel.sort_order, PaymentMethodModel.id).all()

    def _create_config(self, create_data):
        obj = PaymentMethodModel(**create_data.dict())
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def _update_config(self, obj, update_data):
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(obj, field, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def create_payment_method(self, payment_method: PaymentMethodCreate):
        return self._create_config(payment_method)

    def update_payment_method(self, payment_method_id: int, payment_method: PaymentMethodUpdate):
        db_payment_method = self.get_payment_method(payment_method_id)
        return self._update_config(db_payment_method, payment_method) if db_payment_method else None

    def delete_payment_method(self, payment_method_id: int) -> bool:
        db_payment_method = self.get_payment_method(payment_method_id)
        if not db_payment_method:
            return False
        self.db.delete(db_payment_method)
        self.db.commit()
        return True

    def update_payment_method_status(self, payment_method_id: int, status: str):
        db_payment_method = self.get_payment_method(payment_method_id)
        if not db_payment_method:
            return None
        db_payment_method.status = status
        self.db.commit()
        self.db.refresh(db_payment_method)
        return db_payment_method

    def update_payment_method_config(self, payment_method_id: int, config: Dict[str, Any]):
        db_payment_method = self.get_payment_method(payment_method_id)
        if not db_payment_method:
            return None
        db_payment_method.config = config
        self.db.commit()
        self.db.refresh(db_payment_method)
        return db_payment_method

    def get_payment_method_config(self, payment_method_id: int) -> Optional[Dict[str, Any]]:
        db_payment_method = self.get_payment_method(payment_method_id)
        return db_payment_method.config if db_payment_method else None

    def test_payment_method_config(self, payment_method_id: int) -> Dict[str, Any]:
        db_payment_method = self.get_payment_method(payment_method_id)
        if not db_payment_method:
            return {"success": False, "message": "支付方式不存在"}
        try:
            test_configs = {
                "alipay": ["app_id", "merchant_private_key", "alipay_public_key"],
                "wechat": ["mch_id", "app_id", "api_key"],
                "paypal": ["client_id", "secret"],
                "stripe": ["publishable_key", "secret_key"]
            }
            required_fields = test_configs.get(db_payment_method.type)
            if required_fields:
                for field in required_fields:
                    if not db_payment_method.config.get(field):
                        return {"success": False, "message": f"缺少必要配置: {field}"}
                return {"success": True, "message": f"{_get_payment_method_name(db_payment_method.type)}配置验证通过"}
            return {"success": True, "message": "配置验证通过"}
        except Exception as e:
            return {"success": False, "message": f"配置验证失败: {str(e)}"}

    def bulk_update_status(self, payment_method_ids: List[int], status: str) -> int:
        result = self.db.query(PaymentMethodModel).filter(
            PaymentMethodModel.id.in_(payment_method_ids)
        ).update({"status": status}, synchronize_session=False)
        self.db.commit()
        return result

    def bulk_delete(self, payment_method_ids: List[int]) -> int:
        result = self.db.query(PaymentMethodModel).filter(
            PaymentMethodModel.id.in_(payment_method_ids)
        ).delete(synchronize_session=False)
        self.db.commit()
        return result

class PaymentTransactionService:
    def __init__(self, db: Session):
        self.db = db

    def get_transactions(self, skip: int = 0, limit: int = 100,
                        user_id: Optional[int] = None,
                        order_id: Optional[int] = None,
                        status: Optional[str] = None) -> List[PaymentTransaction]:
        query = self.db.query(PaymentTransaction)
        if user_id:
            query = query.filter(PaymentTransaction.user_id == user_id)
        if order_id:
            query = query.filter(PaymentTransaction.order_id == order_id)
        if status:
            query = query.filter(PaymentTransaction.status == status)
        return query.order_by(desc(PaymentTransaction.created_at)).offset(skip).limit(limit).all()

    def get_transaction(self, transaction_id: int) -> Optional[PaymentTransaction]:
        return self.db.query(PaymentTransaction).filter(
            PaymentTransaction.id == transaction_id
        ).first()

    def get_transaction_by_external_id(self, external_id: str) -> Optional[PaymentTransaction]:
        return self.db.query(PaymentTransaction).filter(
            PaymentTransaction.external_transaction_id == external_id
        ).first()

    def _create_config(self, create_data):
        db_transaction = PaymentTransaction(
            **create_data.dict(),
            transaction_id=str(uuid.uuid4())
        )
        self.db.add(db_transaction)
        self.db.commit()
        self.db.refresh(db_transaction)
        return db_transaction

    def _update_config(self, obj, update_data):
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(obj, field, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def create_transaction(self, transaction: PaymentTransactionCreate) -> PaymentTransaction:
        return self._create_config(transaction)

    def update_transaction(self, transaction_id: int, transaction: PaymentTransactionUpdate) -> Optional[PaymentTransaction]:
        db_transaction = self.get_transaction(transaction_id)
        return self._update_config(db_transaction, transaction) if db_transaction else None

    def update_transaction_status(self, transaction_id: int, status: str) -> Optional[PaymentTransaction]:
        db_transaction = self.get_transaction(transaction_id)
        if not db_transaction:
            return None
        db_transaction.status = status
        self.db.commit()
        self.db.refresh(db_transaction)
        return db_transaction

    def get_user_transactions(self, user_id: int, limit: int = 50) -> List[PaymentTransaction]:
        return self.db.query(PaymentTransaction).filter(
            PaymentTransaction.user_id == user_id
        ).order_by(desc(PaymentTransaction.created_at)).limit(limit).all()

    def get_order_transactions(self, order_id: int, limit: int = 50) -> List[PaymentTransaction]:
        return self.db.query(PaymentTransaction).filter(
            PaymentTransaction.order_id == order_id
        ).order_by(desc(PaymentTransaction.created_at)).limit(limit).all()
