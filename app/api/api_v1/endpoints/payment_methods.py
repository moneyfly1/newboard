from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.payment import PaymentMethodService
from app.schemas.payment import (
    PaymentMethod, PaymentMethodCreate, PaymentMethodUpdate,
    PaymentMethodList, PaymentMethodPublic
)
from app.utils.security import get_current_admin_user

router = APIRouter()

def _check_method_exists(method, detail="支付方式不存在"):
    if not method:
        raise HTTPException(status_code=404, detail=detail)

@router.get("/", response_model=PaymentMethodList)
def get_payment_methods(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    type: Optional[str] = Query(None, description="支付类型过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    skip = (page - 1) * size
    service = PaymentMethodService(db)
    payment_methods = service.get_payment_methods(skip=skip, limit=size, type_filter=type, status_filter=status)
    total = len(service.get_payment_methods())
    return PaymentMethodList(items=payment_methods, total=total, page=page, size=size)

@router.get("/active", response_model=List[PaymentMethodPublic])
def get_active_payment_methods(db: Session = Depends(get_db)):
    service = PaymentMethodService(db)
    methods = service.get_active_payment_methods()
    return [
        PaymentMethodPublic(
            id=method.id,
            name=method.name,
            type=method.type,
            status=method.status,
            sort_order=method.sort_order,
            description=method.description,
            created_at=method.created_at,
            updated_at=method.updated_at
        )
        for method in methods
    ]

@router.get("/{payment_method_id}", response_model=PaymentMethod)
def get_payment_method(
    payment_method_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentMethodService(db)
    payment_method = service.get_payment_method(payment_method_id)
    _check_method_exists(payment_method)
    return payment_method

@router.post("/", response_model=PaymentMethod)
def create_payment_method(
    payment_method: PaymentMethodCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentMethodService(db)
    return service.create_payment_method(payment_method)

@router.put("/{payment_method_id}", response_model=PaymentMethod)
def update_payment_method(
    payment_method_id: int,
    payment_method: PaymentMethodUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentMethodService(db)
    updated_method = service.update_payment_method(payment_method_id, payment_method)
    _check_method_exists(updated_method)
    return updated_method

@router.delete("/{payment_method_id}")
def delete_payment_method(
    payment_method_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentMethodService(db)
    success = service.delete_payment_method(payment_method_id)
    _check_method_exists(success, "支付方式不存在")
    return {"message": "支付方式删除成功"}

@router.put("/{payment_method_id}/status", response_model=PaymentMethod)
def update_payment_method_status(
    payment_method_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    if status not in ["active", "inactive"]:
        raise HTTPException(status_code=400, detail="状态值无效")
    service = PaymentMethodService(db)
    updated_method = service.update_payment_method_status(payment_method_id, status)
    _check_method_exists(updated_method)
    return updated_method

@router.put("/{payment_method_id}/config", response_model=PaymentMethod)
def update_payment_method_config(
    payment_method_id: int,
    config: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentMethodService(db)
    updated_method = service.update_payment_method_config(payment_method_id, config)
    _check_method_exists(updated_method)
    return updated_method

@router.get("/{payment_method_id}/config")
def get_payment_method_config(
    payment_method_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentMethodService(db)
    config = service.get_payment_method_config(payment_method_id)
    _check_method_exists(config, "支付方式不存在")
    return {"config": config}

@router.post("/bulk-enable")
def bulk_enable_payment_methods(
    method_ids: List[int],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentMethodService(db)
    count = service.bulk_update_status(method_ids, "active")
    return {"message": f"成功启用 {count} 个支付方式"}

@router.post("/bulk-disable")
def bulk_disable_payment_methods(
    method_ids: List[int],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentMethodService(db)
    count = service.bulk_update_status(method_ids, "inactive")
    return {"message": f"成功禁用 {count} 个支付方式"}

@router.post("/bulk-delete")
def bulk_delete_payment_methods(
    method_ids: List[int],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentMethodService(db)
    count = service.bulk_delete(method_ids)
    return {"message": f"成功删除 {count} 个支付方式"}

@router.get("/export")
def export_payment_methods(
    type: Optional[str] = Query(None, description="支付类型过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    service = PaymentMethodService(db)
    payment_methods = service.get_payment_methods(type_filter=type, status_filter=status)
    return {"data": payment_methods, "filename": f"payment_methods_{type or 'all'}_{status or 'all'}.json"}
