from datetime import datetime, timezone
from typing import Any
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.order import OrderCreate
from app.schemas.common import ResponseBase
from app.services.order import OrderService
from app.services.package import PackageService
from app.services.subscription import SubscriptionService
from app.utils.security import get_current_user
from app.utils.timezone import format_beijing_time
from app.models.user import User
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

def _validate_order_access(order, current_user):
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作此订单")
    return order

def _serialize_order(order):
    return {
        "id": order.id,
        "order_no": order.order_no,
        "package_name": order.package.name if order.package else "未知套餐",
        "package_duration": order.package.duration_days if order.package else 0,
        "package_device_limit": order.package.device_limit if order.package else 0,
        "amount": float(order.amount) if order.amount else 0,
        "status": order.status,
        "payment_method": getattr(order, 'payment_method_name', '未知'),
        "created_at": format_beijing_time(order.created_at) if order.created_at else None,
        "payment_time": format_beijing_time(order.payment_time) if order.payment_time else None,
        "expire_time": format_beijing_time(order.expire_time) if order.expire_time else None
    }

@router.post("/create", response_model=ResponseBase)
def create_order(
    order_data: OrderCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    order_service = OrderService(db)
    package_service = PackageService(db)
    package = package_service.get(order_data.package_id)
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="套餐不存在")
    coupon_id = None
    discount_amount = 0
    final_amount = float(package.price)
    if order_data.coupon_code:
        from app.services.coupon import CouponService
        from app.schemas.coupon import CouponValidate
        coupon_service = CouponService(db)
        validate_data = CouponValidate(
            code=order_data.coupon_code,
            amount=Decimal(str(package.price)),
            package_id=order_data.package_id
        )
        is_valid, error_msg, discount = coupon_service.validate_coupon(validate_data, current_user.id)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg or "优惠券验证失败")
        coupon = coupon_service.get_by_code(order_data.coupon_code)
        if coupon:
            coupon_id = coupon.id
            discount_amount = float(discount) if discount else 0
            final_amount = max(0, float(package.price) - discount_amount)
    use_balance = getattr(order_data, 'use_balance', False) or order_data.payment_method == "balance"
    balance_amount = getattr(order_data, 'balance_amount', None)
    user_balance = current_user.balance or Decimal('0')
    actual_payment_amount = final_amount
    used_balance = Decimal('0')
    if use_balance:
        if balance_amount is not None:
            used_balance = Decimal(str(min(balance_amount, float(user_balance), final_amount)))
        else:
            used_balance = Decimal(str(min(float(user_balance), final_amount)))
        if used_balance > user_balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"余额不足，当前余额：¥{float(user_balance)}，尝试使用：¥{float(used_balance)}"
            )
        actual_payment_amount = final_amount - float(used_balance)
        if actual_payment_amount <= 0:
            actual_payment_amount = 0
            order_data.payment_method = "balance"
        else:
            order_data.payment_method = "alipay"
    try:
        order = order_service.create_order(
            user_id=current_user.id,
            package_id=order_data.package_id,
            payment_method=order_data.payment_method,
            amount=final_amount,
            coupon_id=coupon_id,
            discount_amount=discount_amount
        )
        db.commit()
        if coupon_id:
            from app.services.coupon import CouponService
            coupon_service = CouponService(db)
            coupon_service.use_coupon(coupon_id, current_user.id, order.id, Decimal(str(discount_amount)))
            db.commit()
        if use_balance and used_balance > 0:
            user = db.query(User).filter(User.id == current_user.id).first()
            user.balance = user_balance - used_balance
            if actual_payment_amount <= 0:
                order.status = "paid"
                order.payment_time = datetime.now(timezone.utc)
                order.payment_method_name = "余额支付"
                db.commit()
                subscription_service = SubscriptionService(db)
                subscription_service.process_paid_order(order)
                db.commit()
                logger.info(f"余额支付订单创建成功: order_no={order.order_no}, user_id={current_user.id}, order_id={order.id}")
                return ResponseBase(
                    success=True,
                    message="订单创建成功，已使用余额支付",
                    data={
                        "order_id": order.id,
                        "order_no": order.order_no,
                        "amount": float(order.amount),
                        "status": "paid",
                        "payment_method": "balance",
                        "remaining_balance": float(user.balance),
                        "package_id": order.package_id,
                        "package_name": package.name if package else None
                    }
                )
            else:
                order.amount = actual_payment_amount
                order.payment_method_name = f"余额支付(¥{float(used_balance)})+支付宝"
                db.commit()
                logger.info(f"余额+支付宝合并支付订单创建成功: order_no={order.order_no}, 余额支付:¥{float(used_balance)}, 支付宝支付:¥{actual_payment_amount}")
        logger.info(f"订单创建成功: order_no={order.order_no}, user_id={current_user.id}, order_id={order.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"订单创建失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"订单创建失败: {str(e)}")
    payment_url = None
    payment_error = None
    try:
        if actual_payment_amount > 0:
            payment_url = order_service.generate_payment_url(order)
            logger.debug(f"支付URL生成成功: {payment_url[:50] if payment_url else 'None'}...")
        else:
            logger.debug("订单已全额使用余额支付，无需生成支付URL")
    except Exception as e:
        payment_error = str(e)
        logger.warning(f"订单创建成功，但支付URL生成失败: {payment_error}")
    response_data = {
        "order_id": order.id,
        "order_no": order.order_no,
        "amount": float(final_amount),
        "package_id": order.package_id,
        "package_name": package.name if package else None
    }
    if use_balance and used_balance > 0:
        user = db.query(User).filter(User.id == current_user.id).first()
        response_data["used_balance"] = float(used_balance)
        response_data["remaining_balance"] = float(user.balance)
        response_data["payment_method"] = "mixed" if actual_payment_amount > 0 else "balance"
    if payment_url:
        response_data["payment_url"] = payment_url
        response_data["payment_qr_code"] = payment_url
        return ResponseBase(
            success=True,
            message="订单创建成功" + (f"，已使用余额 ¥{float(used_balance)}" if use_balance and used_balance > 0 else ""),
            data=response_data
        )
    else:
        if actual_payment_amount > 0:
            response_data["payment_url"] = None
            response_data["payment_qr_code"] = None
            response_data["payment_error"] = payment_error or "支付链接生成失败，可能是网络问题或支付配置问题"
            response_data["note"] = "您可以稍后通过订单详情页重新生成支付链接"
            return ResponseBase(success=True, message="订单创建成功，但支付链接生成失败", data=response_data)
        else:
            response_data["status"] = "paid"
            return ResponseBase(success=True, message="订单创建成功，已使用余额支付", data=response_data)

@router.get("/", response_model=ResponseBase)
def get_user_orders(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str = Query("", description="订单状态筛选"),
    payment_method: str = Query("", description="支付方式筛选"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    try:
        order_service = OrderService(db)
        skip = (page - 1) * size
        orders, total = order_service.get_user_orders(
            user_id=current_user.id,
            skip=skip,
            limit=size,
            status=status if status else None,
            payment_method=payment_method if payment_method else None
        )
        order_list = []
        for order in orders:
            try:
                order_list.append(_serialize_order(order))
            except Exception:
                continue
        return ResponseBase(data={
            "orders": order_list,
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size
        })
    except Exception:
        return ResponseBase(data={"orders": [], "total": 0, "page": page, "size": size, "pages": 0})

@router.get("/{order_no}/status", response_model=ResponseBase)
def get_order_status(
    order_no: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    order_service = OrderService(db)
    order = order_service.get_by_order_no(order_no)
    _validate_order_access(order, current_user)
    return ResponseBase(data={
        "order_no": order.order_no,
        "status": order.status,
        "amount": order.amount,
        "payment_method_id": order.payment_method_id,
        "created_at": format_beijing_time(order.created_at) if order.created_at else None,
        "payment_time": format_beijing_time(order.payment_time) if order.payment_time else None
    })

@router.post("/{order_no}/cancel", response_model=ResponseBase)
def cancel_order(
    order_no: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    order_service = OrderService(db)
    order = order_service.get_by_order_no(order_no)
    _validate_order_access(order, current_user)
    if order.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能取消待支付的订单")
    success = order_service.cancel_order(order_no)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="取消订单失败")
    return ResponseBase(message="订单取消成功")

@router.post("/{order_no}/pay", response_model=ResponseBase)
def pay_order(
    order_no: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    order_service = OrderService(db)
    order = order_service.get_by_order_no(order_no)
    _validate_order_access(order, current_user)
    if order.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能支付待支付的订单")
    payment_url = order_service.generate_payment_url(order)
    return ResponseBase(
        message="支付链接生成成功",
        data={
            "order_no": order.order_no,
            "amount": order.amount,
            "payment_url": payment_url,
            "payment_qr_code": payment_url
        }
    )

@router.post("/payment/notify", response_model=ResponseBase)
def payment_notify(db: Session = Depends(get_db)) -> Any:
    return ResponseBase(message="success")

@router.get("/stats", response_model=ResponseBase)
def get_user_order_stats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    try:
        order_service = OrderService(db)
        orders, total = order_service.get_user_orders(user_id=current_user.id, skip=0, limit=1000)
        total_amount = sum(float(order.amount) if order.amount else 0 for order in orders)
        pending_count = len([order for order in orders if order.status == 'pending'])
        paid_count = len([order for order in orders if order.status == 'paid'])
        cancelled_count = len([order for order in orders if order.status == 'cancelled'])
        return ResponseBase(data={
            "total": total,
            "pending": pending_count,
            "paid": paid_count,
            "cancelled": cancelled_count,
            "totalAmount": total_amount
        })
    except Exception as e:
        return ResponseBase(success=False, message=f"获取订单统计失败: {str(e)}")
