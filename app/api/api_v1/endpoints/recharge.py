from decimal import Decimal
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Body
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.core.domain_config import get_domain_config
from app.utils.security import get_current_user
from app.schemas.common import ResponseBase
from app.schemas.payment import PaymentCreate
from app.services.recharge import RechargeService
from app.services.payment import PaymentService
from app.services.order import OrderService
from app.utils.timezone import format_beijing_time
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/create", response_model=ResponseBase)
def create_recharge(
    request: Request,
    recharge_data: dict = Body(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        amount = recharge_data.get('amount')
        payment_method = recharge_data.get('payment_method', 'alipay')
        if not amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请提供充值金额")
        if amount < 20:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="充值金额不能少于20元")
        ip_address = None
        user_agent = None
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
        recharge_service = RechargeService(db)
        recharge = recharge_service.create_recharge(
            user_id=current_user.id,
            amount=Decimal(str(amount)),
            payment_method=payment_method,
            ip_address=ip_address,
            user_agent=user_agent
        )
        payment_url = None
        payment_error = None
        try:
            domain_config = get_domain_config()
            base_url = domain_config.get_base_url(None, db)
            base_url = base_url.strip() if base_url else base_url
            payment_service = PaymentService(db)
            payment_request = PaymentCreate(
                order_no=recharge.order_no,
                amount=float(amount),
                currency="CNY",
                payment_method=payment_method or "alipay",
                subject=f"CBoard账户充值-{recharge.order_no}",
                body=f"充值订单号：{recharge.order_no}",
                notify_url=f"{base_url}/api/v1/payment/notify/{payment_method or 'alipay'}".strip(),
                return_url=f"{base_url}/payment/success".strip()
            )
            payment_response = payment_service.create_payment(payment_request)
            if payment_response.status == "failed" or not payment_response.payment_url:
                logger.warning(f"充值支付创建失败: {payment_response}")
                payment_error = "支付创建失败，请检查支付配置"
            else:
                payment_url = payment_response.payment_url
                if settings.DEBUG:
                    logger.debug(f"充值支付URL生成成功: {payment_url[:50] if payment_url else 'None'}...")
        except Exception as e:
            payment_error = str(e)
            logger.warning(f"充值订单创建成功，但支付URL生成失败: {payment_error}", exc_info=True)
        recharge_service.update_payment_info(recharge.id, payment_url=payment_url, payment_qr_code=payment_url)
        if payment_url:
            return ResponseBase(
                message="充值订单创建成功",
                data={
                    "recharge_id": recharge.id,
                    "order_no": recharge.order_no,
                    "amount": float(recharge.amount),
                    "payment_url": payment_url,
                    "payment_qr_code": payment_url,
                    "status": recharge.status
                }
            )
        else:
            return ResponseBase(
                success=True,
                message="充值订单创建成功，但支付链接生成失败",
                data={
                    "recharge_id": recharge.id,
                    "order_no": recharge.order_no,
                    "amount": float(recharge.amount),
                    "payment_url": None,
                    "payment_qr_code": None,
                    "payment_error": payment_error or "支付链接生成失败，可能是网络问题或支付配置问题",
                    "note": "您可以稍后通过充值记录重新生成支付链接",
                    "status": recharge.status
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建充值订单失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"创建充值订单失败: {str(e)}")

@router.get("/", response_model=ResponseBase)
def get_user_recharges(
    page: int = 1,
    size: int = 20,
    status: Optional[str] = None,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        recharge_service = RechargeService(db)
        skip = (page - 1) * size
        recharges, total = recharge_service.get_user_recharges(
            user_id=current_user.id,
            skip=skip,
            limit=size,
            status=status
        )
        recharge_list = []
        for recharge in recharges:
            recharge_list.append({
                "id": recharge.id,
                "order_no": recharge.order_no,
                "amount": float(recharge.amount),
                "status": recharge.status,
                "payment_method": recharge.payment_method,
                "created_at": format_beijing_time(recharge.created_at),
                "paid_at": format_beijing_time(recharge.paid_at),
                "ip_address": recharge.ip_address
            })
        return ResponseBase(
            data={
                "recharges": recharge_list,
                "total": total,
                "page": page,
                "size": size,
                "pages": (total + size - 1) // size
            }
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取充值记录失败: {str(e)}")

@router.get("/{recharge_id}", response_model=ResponseBase)
def get_recharge_detail(
    recharge_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        recharge_service = RechargeService(db)
        recharge = recharge_service.get_by_id(recharge_id)
        if not recharge:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="充值记录不存在")
        if recharge.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此充值记录")
        return ResponseBase(
            data={
                "id": recharge.id,
                "order_no": recharge.order_no,
                "amount": float(recharge.amount),
                "status": recharge.status,
                "payment_method": recharge.payment_method,
                "payment_url": recharge.payment_url,
                "payment_qr_code": recharge.payment_qr_code,
                "payment_transaction_id": recharge.payment_transaction_id,
                "ip_address": recharge.ip_address,
                "created_at": format_beijing_time(recharge.created_at),
                "paid_at": format_beijing_time(recharge.paid_at)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取充值记录详情失败: {str(e)}")

@router.post("/{recharge_id}/cancel", response_model=ResponseBase)
def cancel_recharge(
    recharge_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        recharge_service = RechargeService(db)
        recharge = recharge_service.get_by_id(recharge_id)
        if not recharge:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="充值记录不存在")
        if recharge.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作此充值记录")
        success = recharge_service.cancel_recharge(recharge_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能取消待支付的充值订单")
        return ResponseBase(message="充值订单已取消")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"取消充值订单失败: {str(e)}")
