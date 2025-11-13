"""支付配置服务"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.payment_config import PaymentConfig
from app.schemas.payment_config import PaymentConfigCreate, PaymentConfigUpdate


class PaymentConfigService:
    """支付配置服务类"""

    def __init__(self, db: Session):
        self.db = db

    def get_payment_configs(self, skip: int = 0, limit: int = 100, pay_type_filter: Optional[str] = None, status_filter: Optional[int] = None) -> List[PaymentConfig]:
        query = self.db.query(PaymentConfig)
        if pay_type_filter:
            query = query.filter(PaymentConfig.pay_type == pay_type_filter)
        if status_filter is not None:
            query = query.filter(PaymentConfig.status == status_filter)
        return query.order_by(PaymentConfig.sort_order, PaymentConfig.id).offset(skip).limit(limit).all()

    def get_payment_config(self, payment_config_id: int) -> Optional[PaymentConfig]:
        return self.db.query(PaymentConfig).filter(PaymentConfig.id == payment_config_id).first()

    def get_payment_config_by_type(self, pay_type: str) -> Optional[PaymentConfig]:
        return self.db.query(PaymentConfig).filter(PaymentConfig.pay_type == pay_type, PaymentConfig.status == 1).first()

    def get_active_payment_configs(self) -> List[PaymentConfig]:
        return self.db.query(PaymentConfig).filter(PaymentConfig.status == 1).order_by(PaymentConfig.sort_order, PaymentConfig.id).all()

    def create_payment_config(self, payment_config: PaymentConfigCreate) -> PaymentConfig:
        db_payment_config = PaymentConfig(**payment_config.dict())
        self.db.add(db_payment_config)
        self.db.commit()
        self.db.refresh(db_payment_config)
        return db_payment_config

    def update_payment_config(self, payment_config_id: int, payment_config: PaymentConfigUpdate) -> Optional[PaymentConfig]:
        db_payment_config = self.get_payment_config(payment_config_id)
        if not db_payment_config:
            return None
        update_data = payment_config.dict(exclude_unset=True)
        current_config = db_payment_config.get_config()
        if 'config_json' in update_data:
            config_json = update_data.pop('config_json')
            current_config.update(update_data)
            if config_json:
                current_config.update(config_json)
        else:
            current_config.update(update_data)
        db_payment_config.set_config(current_config)
        self.db.commit()
        self.db.refresh(db_payment_config)
        return db_payment_config

    def delete_payment_config(self, payment_config_id: int) -> bool:
        db_payment_config = self.get_payment_config(payment_config_id)
        if not db_payment_config:
            return False
        self.db.delete(db_payment_config)
        self.db.commit()
        return True

    def update_payment_config_status(self, payment_config_id: int, status: int) -> Optional[PaymentConfig]:
        db_payment_config = self.get_payment_config(payment_config_id)
        if not db_payment_config:
            return None
        db_payment_config.status = status
        self.db.commit()
        self.db.refresh(db_payment_config)
        return db_payment_config

    def update_payment_config_config(self, payment_config_id: int, config: Dict[str, Any]) -> Optional[PaymentConfig]:
        db_payment_config = self.get_payment_config(payment_config_id)
        if not db_payment_config:
            return None
        db_payment_config.set_config(config)
        self.db.commit()
        self.db.refresh(db_payment_config)
        return db_payment_config

    def get_payment_config_config(self, payment_config_id: int) -> Optional[Dict[str, Any]]:
        db_payment_config = self.get_payment_config(payment_config_id)
        return db_payment_config.get_config() if db_payment_config else None

    def _test_config(self, config: Dict[str, Any], required_fields: List[str], success_msg: str) -> Dict[str, Any]:
        for field in required_fields:
            if not config.get(field):
                return {"success": False, "message": f"缺少必要配置: {field}"}
        return {"success": True, "message": success_msg}

    def test_payment_config(self, payment_config_id: int) -> Dict[str, Any]:
        db_payment_config = self.get_payment_config(payment_config_id)
        if not db_payment_config:
            return {"success": False, "message": "支付配置不存在"}
        try:
            config = db_payment_config.get_config()
            test_map = {
                "alipay": (["app_id", "merchant_private_key", "alipay_public_key"], "支付宝配置验证通过"),
                "wechat": (["app_id", "mch_id", "api_key"], "微信支付配置验证通过"),
                "paypal": (["client_id", "secret"], "PayPal配置验证通过"),
                "stripe": (["publishable_key", "secret_key"], "Stripe配置验证通过")
            }
            if db_payment_config.pay_type in test_map:
                fields, msg = test_map[db_payment_config.pay_type]
                return self._test_config(config, fields, msg)
            return {"success": True, "message": "配置验证通过"}
        except Exception as e:
            return {"success": False, "message": f"配置验证失败: {str(e)}"}

    def _bulk_operation(self, payment_config_ids: List[int], operation: str, value: Any = None) -> int:
        query = self.db.query(PaymentConfig).filter(PaymentConfig.id.in_(payment_config_ids))
        if operation == 'update':
            result = query.update({"status": value}, synchronize_session=False)
        else:
            result = query.delete(synchronize_session=False)
        self.db.commit()
        return result

    def bulk_update_status(self, payment_config_ids: List[int], status: int) -> int:
        return self._bulk_operation(payment_config_ids, 'update', status)

    def bulk_delete(self, payment_config_ids: List[int]) -> int:
        return self._bulk_operation(payment_config_ids, 'delete')

    def get_payment_config_stats(self) -> Dict[str, Any]:
        total_configs = self.db.query(PaymentConfig).count()
        active_configs = self.db.query(PaymentConfig).filter(PaymentConfig.status == 1).count()
        type_stats = {}
        types = self.db.query(PaymentConfig.pay_type).distinct().all()
        for (pay_type,) in types:
            count = self.db.query(PaymentConfig).filter(PaymentConfig.pay_type == pay_type, PaymentConfig.status == 1).count()
            type_stats[pay_type] = count
        return {
            "total_configs": total_configs,
            "active_configs": active_configs,
            "inactive_configs": total_configs - active_configs,
            "type_stats": type_stats
        }
