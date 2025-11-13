from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.domain_config import get_domain_config
from app.services.payment_config import PaymentConfigService
from app.schemas.payment_config import (
    PaymentConfig, PaymentConfigCreate, PaymentConfigUpdate,
    PaymentConfigList, PaymentConfigPublic
)
from app.utils.security import get_current_admin_user

router = APIRouter()

def _check_config_exists(config, detail="支付配置不存在"):
    if not config:
        raise HTTPException(status_code=404, detail=detail)

@router.get("/", response_model=PaymentConfigList)
def get_payment_configs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    pay_type: Optional[str] = Query(None, description="支付类型过滤"),
    status: Optional[int] = Query(None, description="状态过滤"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    skip = (page - 1) * size
    service = PaymentConfigService(db)
    payment_configs = service.get_payment_configs(skip=skip, limit=size, pay_type_filter=pay_type, status_filter=status)
    total = len(service.get_payment_configs())
    return PaymentConfigList(items=payment_configs, total=total, page=page, size=size)

@router.get("/active", response_model=List[PaymentConfigPublic])
def get_active_payment_configs(db: Session = Depends(get_db)):
    service = PaymentConfigService(db)
    configs = service.get_active_payment_configs()
    return [
        PaymentConfigPublic(
            id=config.id,
            pay_type=config.pay_type,
            pay_name=getattr(config, 'pay_name', None),
            pay_check=getattr(config, 'pay_check', None),
            pay_method=getattr(config, 'pay_method', None),
            pay_client=getattr(config, 'pay_client', None),
            status=config.status,
            sort_order=config.sort_order,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
        for config in configs
    ]

@router.get("/{payment_config_id}", response_model=PaymentConfig)
def get_payment_config(
    payment_config_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentConfigService(db)
    payment_config = service.get_payment_config(payment_config_id)
    _check_config_exists(payment_config)
    return payment_config

@router.post("/", response_model=PaymentConfig)
def create_payment_config(
    payment_config: PaymentConfigCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    # 如果回调地址为空，自动填充默认值
    domain_config = get_domain_config()
    base_url = domain_config.get_base_url(request, db)
    
    config_dict = payment_config.dict()
    if not config_dict.get('notify_url'):
        # 根据支付类型生成回调地址
        pay_type = config_dict.get('pay_type', 'alipay')
        if pay_type == 'alipay':
            config_dict['notify_url'] = f"{base_url}/api/v1/payment/notify/alipay"
        elif pay_type in ['yipay_alipay', 'yipay_wxpay']:
            config_dict['notify_url'] = f"{base_url}/api/v1/payment/notify/yipay"
        elif pay_type == 'wechat':
            config_dict['notify_url'] = f"{base_url}/api/v1/payment/notify/wechat"
        else:
            config_dict['notify_url'] = f"{base_url}/api/v1/payment/notify/{pay_type}"
    
    if not config_dict.get('return_url'):
        config_dict['return_url'] = f"{base_url}/payment/success"
    
    # 重新创建 PaymentConfigCreate 对象
    payment_config = PaymentConfigCreate(**config_dict)
    service = PaymentConfigService(db)
    return service.create_payment_config(payment_config)

@router.put("/{payment_config_id}", response_model=PaymentConfig)
def update_payment_config(
    payment_config_id: int,
    payment_config: PaymentConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    # 如果回调地址为空，自动填充默认值
    service = PaymentConfigService(db)
    existing_config = service.get_payment_config(payment_config_id)
    if existing_config:
        domain_config = get_domain_config()
        base_url = domain_config.get_base_url(request, db)
        
        config_dict = payment_config.dict(exclude_unset=True)
        pay_type = config_dict.get('pay_type') or existing_config.pay_type
        
        # 如果 notify_url 为空或未提供，使用默认值
        if 'notify_url' not in config_dict or not config_dict.get('notify_url'):
            if pay_type == 'alipay':
                config_dict['notify_url'] = f"{base_url}/api/v1/payment/notify/alipay"
            elif pay_type in ['yipay_alipay', 'yipay_wxpay']:
                config_dict['notify_url'] = f"{base_url}/api/v1/payment/notify/yipay"
            elif pay_type == 'wechat':
                config_dict['notify_url'] = f"{base_url}/api/v1/payment/notify/wechat"
            else:
                config_dict['notify_url'] = f"{base_url}/api/v1/payment/notify/{pay_type}"
        
        # 如果 return_url 为空或未提供，使用默认值
        if 'return_url' not in config_dict or not config_dict.get('return_url'):
            config_dict['return_url'] = f"{base_url}/payment/success"
        
        # 重新创建 PaymentConfigUpdate 对象
        payment_config = PaymentConfigUpdate(**config_dict)
    
    updated_config = service.update_payment_config(payment_config_id, payment_config)
    _check_config_exists(updated_config)
    return updated_config

@router.delete("/{payment_config_id}")
def delete_payment_config(
    payment_config_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentConfigService(db)
    success = service.delete_payment_config(payment_config_id)
    _check_config_exists(success, "支付配置不存在")
    return {"message": "支付配置删除成功"}

@router.put("/{payment_config_id}/status", response_model=PaymentConfig)
def update_payment_config_status(
    payment_config_id: int,
    status: int = Query(..., description="状态值：1启用，0禁用"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    if status not in [0, 1]:
        raise HTTPException(status_code=400, detail="状态值无效")
    service = PaymentConfigService(db)
    updated_config = service.update_payment_config_status(payment_config_id, status)
    _check_config_exists(updated_config)
    return updated_config

@router.put("/{payment_config_id}/config", response_model=PaymentConfig)
def update_payment_config_config(
    payment_config_id: int,
    config: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentConfigService(db)
    updated_config = service.update_payment_config_config(payment_config_id, config)
    _check_config_exists(updated_config)
    return updated_config

@router.get("/{payment_config_id}/config")
def get_payment_config_config(
    payment_config_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentConfigService(db)
    config = service.get_payment_config_config(payment_config_id)
    _check_config_exists(config, "支付配置不存在")
    return {"config": config}

@router.post("/bulk-enable")
def bulk_enable_payment_configs(
    config_ids: List[int],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentConfigService(db)
    count = service.bulk_update_status(config_ids, 1)
    return {"message": f"成功启用 {count} 个支付配置"}

@router.post("/bulk-disable")
def bulk_disable_payment_configs(
    config_ids: List[int],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentConfigService(db)
    count = service.bulk_update_status(config_ids, 0)
    return {"message": f"成功禁用 {count} 个支付配置"}

@router.post("/bulk-delete")
def bulk_delete_payment_configs(
    config_ids: List[int],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentConfigService(db)
    count = service.bulk_delete(config_ids)
    return {"message": f"成功删除 {count} 个支付配置"}

@router.get("/stats/summary")
def get_payment_config_stats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentConfigService(db)
    return service.get_payment_config_stats()

@router.get("/export")
def export_payment_configs(
    pay_type: Optional[str] = Query(None, description="支付类型过滤"),
    status: Optional[int] = Query(None, description="状态过滤"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentConfigService(db)
    payment_configs = service.get_payment_configs(pay_type_filter=pay_type, status_filter=status)
    return {"data": payment_configs, "filename": f"payment_configs_{pay_type or 'all'}_{status or 'all'}.json"}
