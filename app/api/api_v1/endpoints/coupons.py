from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.coupon import CouponCreate, CouponUpdate, CouponValidate
from app.schemas.common import ResponseBase
from app.services.coupon import CouponService
from app.models.coupon import CouponType, CouponStatus
from app.utils.security import get_current_user, get_current_admin_user
from app.api.api_v1.endpoints.common import handle_api_error
import json

router = APIRouter()

def _serialize_coupon(c):
    return {
        "id": c.id,
        "code": c.code,
        "name": c.name,
        "description": c.description,
        "type": c.type.value,
        "discount_value": float(c.discount_value),
        "min_amount": float(c.min_amount) if c.min_amount else 0,
        "max_discount": float(c.max_discount) if c.max_discount else None,
        "valid_from": c.valid_from.isoformat(),
        "valid_until": c.valid_until.isoformat(),
        "total_quantity": c.total_quantity,
        "used_quantity": c.used_quantity,
        "max_uses_per_user": c.max_uses_per_user,
        "status": c.status.value,
        "created_at": c.created_at.isoformat()
    }

def _parse_enum(enum_class, value):
    if not value:
        return None
    try:
        return enum_class(value)
    except ValueError:
        return None

@router.get("/available", response_model=ResponseBase)
@handle_api_error("获取可用优惠券")
def get_available_coupons(current_user = Depends(get_current_user), db: Session = Depends(get_db)) -> Any:
    coupon_service = CouponService(db)
    coupons = coupon_service.get_user_coupons(current_user.id)
    return ResponseBase(data={"coupons": coupons})

@router.post("/validate", response_model=ResponseBase)
@handle_api_error("验证优惠券")
def validate_coupon(validate_data: CouponValidate, current_user = Depends(get_current_user), db: Session = Depends(get_db)) -> Any:
    coupon_service = CouponService(db)
    is_valid, error_msg, discount_amount = coupon_service.validate_coupon(validate_data, current_user.id)
    if not is_valid:
        return ResponseBase(success=False, message=error_msg)
    return ResponseBase(message="优惠券可用", data={"valid": True, "discount_amount": float(discount_amount) if discount_amount else 0})

@router.post("/admin", response_model=ResponseBase)
@handle_api_error("创建优惠券")
def create_coupon(coupon_in: CouponCreate, current_admin = Depends(get_current_admin_user), db: Session = Depends(get_db)) -> Any:
    coupon_service = CouponService(db)
    if coupon_in.code:
        existing = coupon_service.get_by_code(coupon_in.code)
        if existing:
            raise HTTPException(status_code=400, detail="优惠券码已存在")
    coupon = coupon_service.create(coupon_in, current_admin.id)
    return ResponseBase(message="优惠券创建成功", data={"id": coupon.id, "code": coupon.code})

@router.get("/admin", response_model=ResponseBase)
@handle_api_error("获取优惠券列表")
def get_all_coupons(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), status: Optional[str] = Query(None), type: Optional[str] = Query(None), keyword: Optional[str] = Query(None), current_admin = Depends(get_current_admin_user), db: Session = Depends(get_db)) -> Any:
    coupon_service = CouponService(db)
    coupon_status = _parse_enum(CouponStatus, status)
    coupon_type = _parse_enum(CouponType, type)
    skip = (page - 1) * size
    coupons, total = coupon_service.get_all(skip, size, coupon_status, coupon_type, keyword)
    return ResponseBase(data={"coupons": [_serialize_coupon(c) for c in coupons], "total": total, "page": page, "size": size, "pages": (total + size - 1) // size})

@router.get("/admin/{coupon_id}", response_model=ResponseBase)
@handle_api_error("获取优惠券详情")
def get_coupon(coupon_id: int, current_admin = Depends(get_current_admin_user), db: Session = Depends(get_db)) -> Any:
    coupon_service = CouponService(db)
    coupon = coupon_service.get(coupon_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    applicable_packages = None
    if coupon.applicable_packages:
        try:
            applicable_packages = json.loads(coupon.applicable_packages)
        except (json.JSONDecodeError, TypeError):
            pass
    data = _serialize_coupon(coupon)
    data.update({"applicable_packages": applicable_packages, "updated_at": coupon.updated_at.isoformat() if coupon.updated_at else None})
    return ResponseBase(data=data)

@router.put("/admin/{coupon_id}", response_model=ResponseBase)
@handle_api_error("更新优惠券")
def update_coupon(coupon_id: int, coupon_in: CouponUpdate, current_admin = Depends(get_current_admin_user), db: Session = Depends(get_db)) -> Any:
    coupon_service = CouponService(db)
    coupon = coupon_service.update(coupon_id, coupon_in)
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    return ResponseBase(message="优惠券更新成功")

@router.delete("/admin/{coupon_id}", response_model=ResponseBase)
@handle_api_error("删除优惠券")
def delete_coupon(coupon_id: int, current_admin = Depends(get_current_admin_user), db: Session = Depends(get_db)) -> Any:
    coupon_service = CouponService(db)
    success = coupon_service.delete(coupon_id)
    if not success:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    return ResponseBase(message="优惠券删除成功")

@router.get("/admin/statistics", response_model=ResponseBase)
@handle_api_error("获取优惠券统计")
def get_coupon_statistics(current_admin = Depends(get_current_admin_user), db: Session = Depends(get_db)) -> Any:
    coupon_service = CouponService(db)
    stats = coupon_service.get_statistics()
    return ResponseBase(data=stats)
