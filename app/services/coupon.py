"""优惠券服务"""
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.models.coupon import Coupon, CouponStatus, CouponType, CouponUsage
from app.models.order import Order
from app.models.user import User
from app.schemas.coupon import CouponCreate, CouponUpdate, CouponValidate


class CouponService:
    """优惠券服务类"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, coupon_id: int) -> Optional[Coupon]:
        """根据ID获取优惠券"""
        return self.db.query(Coupon).filter(Coupon.id == coupon_id).first()

    def get_by_code(self, code: str) -> Optional[Coupon]:
        """根据优惠券码获取优惠券"""
        return self.db.query(Coupon).filter(Coupon.code == code).first()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
        status: Optional[CouponStatus] = None,
        type: Optional[CouponType] = None,
        keyword: Optional[str] = None
    ) -> Tuple[List[Coupon], int]:
        """获取所有优惠券"""
        query = self.db.query(Coupon)

        if status:
            query = query.filter(Coupon.status == status)
        if type:
            query = query.filter(Coupon.type == type)
        if keyword:
            query = query.filter(
                or_(
                    Coupon.code.like(f"%{keyword}%"),
                    Coupon.name.like(f"%{keyword}%")
                )
            )

        total = query.count()
        coupons = query.order_by(desc(Coupon.created_at)).offset(skip).limit(limit).all()

        return coupons, total

    def get_active_coupons(self) -> List[Coupon]:
        """获取所有有效优惠券"""
        now = datetime.now(timezone.utc)
        coupons = self.db.query(Coupon).filter(
            Coupon.status == CouponStatus.ACTIVE
        ).all()

        active_coupons = []
        for coupon in coupons:
            valid_from = coupon.valid_from
            valid_until = coupon.valid_until

            if valid_from.tzinfo is None:
                valid_from = valid_from.replace(tzinfo=timezone.utc)
            else:
                valid_from = valid_from.astimezone(timezone.utc)

            if valid_until.tzinfo is None:
                valid_until = valid_until.replace(tzinfo=timezone.utc)
            else:
                valid_until = valid_until.astimezone(timezone.utc)

            if valid_from <= now <= valid_until:
                active_coupons.append(coupon)

        return active_coupons

    def create(self, coupon_in: CouponCreate, created_by: Optional[int] = None) -> Coupon:
        """创建优惠券"""
        code = coupon_in.code
        if not code:
            code = Coupon.generate_code()
            while self.get_by_code(code):
                code = Coupon.generate_code()

        applicable_packages = None
        if coupon_in.applicable_packages:
            applicable_packages = json.dumps(coupon_in.applicable_packages)

        valid_from = coupon_in.valid_from
        valid_until = coupon_in.valid_until

        if valid_from.tzinfo is None:
            valid_from = valid_from.replace(tzinfo=timezone.utc)
        else:
            valid_from = valid_from.astimezone(timezone.utc)

        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)
        else:
            valid_until = valid_until.astimezone(timezone.utc)

        coupon = Coupon(
            code=code,
            name=coupon_in.name,
            description=coupon_in.description,
            type=coupon_in.type,
            discount_value=coupon_in.discount_value,
            min_amount=coupon_in.min_amount or Decimal('0'),
            max_discount=coupon_in.max_discount,
            valid_from=valid_from,
            valid_until=valid_until,
            total_quantity=coupon_in.total_quantity,
            max_uses_per_user=coupon_in.max_uses_per_user,
            status=coupon_in.status,
            applicable_packages=applicable_packages,
            created_by=created_by
        )

        self.db.add(coupon)
        self.db.commit()
        self.db.refresh(coupon)

        return coupon

    def update(self, coupon_id: int, coupon_in: CouponUpdate) -> Optional[Coupon]:
        """更新优惠券"""
        coupon = self.get(coupon_id)
        if not coupon:
            return None

        update_data = coupon_in.dict(exclude_unset=True)

        if 'applicable_packages' in update_data and update_data['applicable_packages'] is not None:
            update_data['applicable_packages'] = json.dumps(update_data['applicable_packages'])

        if 'valid_from' in update_data and update_data['valid_from'] is not None:
            valid_from = update_data['valid_from']
            if valid_from.tzinfo is None:
                update_data['valid_from'] = valid_from.replace(tzinfo=timezone.utc)
            else:
                update_data['valid_from'] = valid_from.astimezone(timezone.utc)

        if 'valid_until' in update_data and update_data['valid_until'] is not None:
            valid_until = update_data['valid_until']
            if valid_until.tzinfo is None:
                update_data['valid_until'] = valid_until.replace(tzinfo=timezone.utc)
            else:
                update_data['valid_until'] = valid_until.astimezone(timezone.utc)

        for field, value in update_data.items():
            setattr(coupon, field, value)

        self.db.commit()
        self.db.refresh(coupon)

        return coupon

    def delete(self, coupon_id: int) -> bool:
        """删除优惠券"""
        coupon = self.get(coupon_id)
        if not coupon:
            return False

        self.db.delete(coupon)
        self.db.commit()
        return True

    def validate_coupon(self, validate_data: CouponValidate, user_id: int) -> Tuple[bool, Optional[str], Optional[Decimal]]:
        """验证优惠券是否可用

        Returns:
            Tuple[是否可用, 错误消息, 折扣金额]
        """
        coupon = self.get_by_code(validate_data.code)

        if not coupon:
            return False, "优惠券不存在", None

        if coupon.status != CouponStatus.ACTIVE:
            return False, "优惠券已失效", None

        now = datetime.now(timezone.utc)

        valid_from = coupon.valid_from
        valid_until = coupon.valid_until

        if valid_from.tzinfo is None:
            valid_from = valid_from.replace(tzinfo=timezone.utc)
        else:
            valid_from = valid_from.astimezone(timezone.utc)

        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)
        else:
            valid_until = valid_until.astimezone(timezone.utc)

        if valid_from > now or valid_until < now:
            return False, "优惠券已过期", None

        if coupon.total_quantity and coupon.used_quantity >= coupon.total_quantity:
            return False, "优惠券已被领完", None

        if validate_data.amount < coupon.min_amount:
            return False, f"订单金额需达到 {coupon.min_amount} 元", None

        if coupon.applicable_packages:
            try:
                applicable_packages = json.loads(coupon.applicable_packages)
                if validate_data.package_id and validate_data.package_id not in applicable_packages:
                    return False, "此优惠券不适用于该套餐", None
            except (json.JSONDecodeError, TypeError):
                pass

        user_usage_count = self.db.query(CouponUsage).filter(
            and_(
                CouponUsage.coupon_id == coupon.id,
                CouponUsage.user_id == user_id
            )
        ).count()

        if user_usage_count >= coupon.max_uses_per_user:
            return False, "您已达到该优惠券的使用次数限制", None

        discount_amount = Decimal('0')
        if coupon.type == CouponType.DISCOUNT:
            discount_amount = validate_data.amount * (coupon.discount_value / Decimal('100'))
            if coupon.max_discount:
                discount_amount = min(discount_amount, coupon.max_discount)
        elif coupon.type == CouponType.FIXED:
            discount_amount = coupon.discount_value
        elif coupon.type == CouponType.FREE_DAYS:
            discount_amount = Decimal('0')

        discount_amount = min(discount_amount, validate_data.amount)

        return True, None, discount_amount

    def use_coupon(self, coupon_id: int, user_id: int, order_id: Optional[int], discount_amount: Decimal) -> Optional[CouponUsage]:
        """使用优惠券"""
        coupon = self.get(coupon_id)
        if not coupon:
            return None

        usage = CouponUsage(
            coupon_id=coupon_id,
            user_id=user_id,
            order_id=order_id,
            discount_amount=discount_amount
        )

        self.db.add(usage)
        coupon.used_quantity += 1
        self.db.flush()
        self.db.refresh(usage)

        return usage

    def get_user_coupons(self, user_id: int) -> List[dict]:
        """获取用户可用的优惠券列表"""
        active_coupons = self.get_active_coupons()
        user_coupons = []

        for coupon in active_coupons:
            user_usage_count = self.db.query(CouponUsage).filter(
                and_(
                    CouponUsage.coupon_id == coupon.id,
                    CouponUsage.user_id == user_id
                )
            ).count()

            if user_usage_count < coupon.max_uses_per_user:
                user_coupons.append({
                    "id": coupon.id,
                    "code": coupon.code,
                    "name": coupon.name,
                    "description": coupon.description,
                    "type": coupon.type.value,
                    "discount_value": float(coupon.discount_value),
                    "min_amount": float(coupon.min_amount) if coupon.min_amount else 0,
                    "max_discount": float(coupon.max_discount) if coupon.max_discount else None,
                    "valid_until": coupon.valid_until.isoformat(),
                    "remaining_uses": coupon.max_uses_per_user - user_usage_count
                })

        return user_coupons

    def get_statistics(self) -> dict:
        """获取优惠券统计"""
        total = self.db.query(Coupon).count()
        active = self.db.query(Coupon).filter(Coupon.status == CouponStatus.ACTIVE).count()
        expired = self.db.query(Coupon).filter(Coupon.status == CouponStatus.EXPIRED).count()
        total_usage = self.db.query(CouponUsage).count()

        return {
            "total": total,
            "active": active,
            "expired": expired,
            "total_usage": total_usage
        }

