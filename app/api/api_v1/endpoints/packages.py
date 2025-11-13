from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.common import ResponseBase
from app.services.package import PackageService
from app.api.api_v1.endpoints.common import handle_api_error

router = APIRouter()

def _serialize_package(pkg):
    return {
        "id": pkg.id,
        "name": pkg.name,
        "price": float(pkg.price),
        "duration_days": pkg.duration_days,
        "device_limit": pkg.device_limit,
        "description": pkg.description,
        "is_active": pkg.is_active,
        "sort_order": getattr(pkg, 'sort_order', 1),
        "bandwidth_limit": getattr(pkg, 'bandwidth_limit', None)
    }

@router.get("/", response_model=ResponseBase)
@handle_api_error("获取套餐列表")
def get_packages(db: Session = Depends(get_db)) -> Any:
    package_service = PackageService(db)
    packages = package_service.get_active_packages()
    package_list = [_serialize_package(pkg) for pkg in packages]
    return ResponseBase(data={"packages": package_list}, message="获取套餐列表成功")

@router.get("/{package_id}", response_model=ResponseBase)
def get_package(package_id: int, db: Session = Depends(get_db)) -> Any:
    package_service = PackageService(db)
    package = package_service.get(package_id)
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="套餐不存在")
    return ResponseBase(data={
        "package": {
            "id": package.id,
            "name": package.name,
            "price": package.price,
            "duration_days": package.duration_days,
            "device_limit": package.device_limit,
            "description": package.description,
            "is_active": package.is_active
        }
    }) 