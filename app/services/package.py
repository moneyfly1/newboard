"""套餐服务"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.package import Package
from app.schemas.package import PackageCreate, PackageUpdate


class PackageService:
    """套餐服务类"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, package_id: int) -> Optional[Package]:
        return self.db.query(Package).filter(Package.id == package_id).first()

    def get_by_name(self, name: str) -> Optional[Package]:
        return self.db.query(Package).filter(Package.name == name).first()

    def get_all(self, skip: int = 0, limit: int = 100, active_only: bool = False) -> List[Package]:
        query = self.db.query(Package)
        if active_only:
            query = query.filter(Package.is_active == True)
        return query.offset(skip).limit(limit).all()

    def get_active_packages(self) -> List[Package]:
        return self.db.query(Package).filter(Package.is_active == True).all()

    def get_all_packages(self, skip: int = 0, limit: int = 100) -> List[Package]:
        return self.get_all(skip, limit, active_only=False)

    def count(self) -> int:
        return self.db.query(Package).count()

    def create(self, package: PackageCreate) -> Package:
        db_package = Package(**package.dict())
        self.db.add(db_package)
        self.db.commit()
        self.db.refresh(db_package)
        return db_package

    def update(self, package_id: int, package: PackageUpdate) -> Optional[Package]:
        db_package = self.get(package_id)
        if not db_package:
            return None
        update_data = package.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_package, field, value)
        self.db.commit()
        self.db.refresh(db_package)
        return db_package

    def delete(self, package_id: int) -> bool:
        db_package = self.get(package_id)
        if not db_package:
            return False
        self.db.delete(db_package)
        self.db.commit()
        return True

    def _update_status(self, package_id: int, is_active: bool) -> bool:
        db_package = self.get(package_id)
        if not db_package:
            return False
        db_package.is_active = is_active
        self.db.commit()
        return True

    def deactivate(self, package_id: int) -> bool:
        return self._update_status(package_id, False)

    def activate(self, package_id: int) -> bool:
        return self._update_status(package_id, True)
