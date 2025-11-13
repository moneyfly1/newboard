import logging
import json
from typing import Dict, Any, Optional
from app.contracts.payment_interface import PaymentInterface, PaymentRequest, PaymentResponse, PaymentNotify

logger = logging.getLogger(__name__)


class BankTransferPayment(PaymentInterface):
    """银行转账支付实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bank_name = config.get('bank_name', '')
        self.bank_account = config.get('bank_account', '')
        self.bank_branch = config.get('bank_branch', '')
        self.account_holder = config.get('account_holder', '')
    
    def pay(self, request: PaymentRequest) -> PaymentResponse:
        """创建银行转账支付订单"""
        try:
            # 银行转账不需要实际的支付URL，返回银行信息
            bank_info = {
                'bank_name': self.bank_name,
                'bank_account': self.bank_account,
                'bank_branch': self.bank_branch,
                'account_holder': self.account_holder,
                'amount': request.total_amount / 100,  # 转换为元
                'trade_no': request.trade_no,
                'subject': request.subject
            }
            
            # 将银行信息编码为JSON字符串
            bank_info_json = json.dumps(bank_info, ensure_ascii=False)
            
            return PaymentResponse(
                type=3,  # 银行转账信息
                data=bank_info_json,
                trade_no=request.trade_no
            )
            
        except Exception as e:
            raise Exception(f"创建银行转账支付订单失败: {str(e)}")
    
    def verify_notify(self, params: Dict[str, Any]) -> Optional[PaymentNotify]:
        """验证银行转账支付回调（手动确认）"""
        try:
            # 银行转账需要手动确认，这里返回None
            # 实际应用中，管理员需要手动确认转账
            return None
            
        except Exception as e:
            logger.error(f"验证银行转账回调失败: {str(e)}", exc_info=True)
            return None
    
    def get_config_form(self) -> Dict[str, Any]:
        """获取银行转账配置表单"""
        return {
            'bank_name': {
                'label': '银行名称',
                'type': 'input',
                'required': True,
                'description': '收款银行名称'
            },
            'bank_account': {
                'label': '银行账号',
                'type': 'input',
                'required': True,
                'description': '收款银行账号'
            },
            'bank_branch': {
                'label': '开户支行',
                'type': 'input',
                'required': False,
                'description': '开户支行名称'
            },
            'account_holder': {
                'label': '账户持有人',
                'type': 'input',
                'required': True,
                'description': '银行账户持有人姓名'
            }
        }
