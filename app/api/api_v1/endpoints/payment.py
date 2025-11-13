from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from urllib.parse import parse_qs
from app.core.database import get_db
from app.core.config import settings
from app.models.payment import PaymentTransaction
from app.models.payment_config import PaymentConfig
from app.models.order import Order
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentUpdate, PaymentResponse, PaymentCallback, PaymentMethod
from app.services.payment import PaymentService
from app.services.order import OrderService
from app.services.recharge import RechargeService
from app.utils.security import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

def _build_payment_response(payment):
    return PaymentResponse(
        id=payment.id,
        payment_url=payment.payment_data.get("payment_url", "") if payment.payment_data else "",
        order_no=payment.order.order_no if payment.order else "",
        amount=payment.amount / 100,
        payment_method=payment.payment_data.get("method", "") if payment.payment_data else "",
        status=payment.status,
        created_at=payment.created_at
    )

def _check_admin(current_user):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")

async def _get_alipay_params(request):
    params = {}
    try:
        form_data = await request.form()
        if form_data:
            params = {k: v for k, v in form_data.items()}
            logger.info(f"从form data获取支付宝回调参数: {len(params)}个参数")
    except Exception as e:
        logger.warning(f"从form data获取参数失败: {e}")
    if not params:
        try:
            query_params = dict(request.query_params)
            if query_params:
                params = query_params
                logger.info(f"从query string获取支付宝回调参数: {len(params)}个参数")
        except Exception as e:
            logger.warning(f"从query string获取参数失败: {e}")
    if not params:
        try:
            body = await request.body()
            if body:
                body_str = body.decode('utf-8')
                params = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(body_str).items()}
                if params:
                    logger.info(f"从body解析支付宝回调参数: {len(params)}个参数")
        except Exception as e:
            logger.warning(f"从body解析参数失败: {e}")
    if params:
        logger.info(f"支付宝回调参数列表: {list(params.keys())}")
        if 'out_trade_no' in params:
            logger.info(f"订单号: {params.get('out_trade_no')}")
        if 'trade_status' in params:
            logger.info(f"交易状态: {params.get('trade_status')}")
    else:
        logger.error("未获取到任何支付宝回调参数")
    return params

@router.post("/create")
async def create_payment(
    payment_data: PaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        order = db.query(Order).filter(
            Order.order_no == payment_data.order_no,
            Order.user_id == current_user.id
        ).first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
        if order.status != 'pending':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="订单状态不正确")
        payment_service = PaymentService(db)
        payment_response = payment_service.create_payment(payment_data, request)
        return {
            "payment_url": payment_response.payment_url,
            "order_no": payment_response.order_no,
            "amount": payment_response.amount,
            "payment_method": payment_response.payment_method,
            "status": payment_response.status
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        error_detail = f"创建支付订单失败: {str(e)}" if str(e) else "创建支付订单失败: 未知错误"
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail)

@router.get("/methods")
async def get_payment_methods(db: Session = Depends(get_db)):
    from app.schemas.common import ResponseBase
    payment_service = PaymentService(db)
    methods = payment_service.get_available_payment_methods()
    return ResponseBase(success=True, data=methods, message="获取支付方式成功")

@router.get("/transactions", response_model=List[PaymentResponse])
async def get_payment_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    order_no: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
):
    query = db.query(PaymentTransaction).filter(PaymentTransaction.user_id == current_user.id)
    if order_no:
        query = query.join(Order).filter(Order.order_no == order_no)
    payments = query.offset(skip).limit(limit).all()
    return [_build_payment_response(payment) for payment in payments]

@router.get("/transactions/{payment_id}", response_model=PaymentResponse)
async def get_payment_transaction(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    payment = db.query(PaymentTransaction).filter(
        PaymentTransaction.id == payment_id,
        PaymentTransaction.user_id == current_user.id
    ).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付交易不存在")
    return _build_payment_response(payment)

@router.post("/notify/{payment_method}")
async def payment_notify(
    payment_method: str,
    request: Request,
    db: Session = Depends(get_db)
):
    try:
        if payment_method in ['alipay']:
            params = await _get_alipay_params(request)
        elif payment_method in ['yipay']:
            params = dict(request.query_params)
        else:
            body = await request.body()
            if request.headers.get('content-type', '').startswith('application/json'):
                params = await request.json()
            else:
                params = dict(await request.form())
        logger.info(f"收到{payment_method}支付回调请求")
        logger.info(f"回调参数数量: {len(params) if params else 0}")
        if params:
            logger.info(f"回调参数键: {list(params.keys())}")
            if 'out_trade_no' in params:
                logger.info(f"订单号: {params.get('out_trade_no')}")
            if 'trade_status' in params:
                logger.info(f"交易状态: {params.get('trade_status')}")
            if 'sign' in params:
                logger.info(f"签名存在: 是")
            else:
                logger.warning(f"签名不存在: 回调参数中缺少sign字段")
        if settings.DEBUG:
            logger.debug(f"收到{payment_method}支付回调，完整参数: {params}")
        payment_service = PaymentService(db)
        notify = payment_service.verify_payment_notify(payment_method, params)
        if notify:
            if settings.DEBUG:
                logger.debug(f"支付回调验证成功，订单号: {notify.trade_no}")
            order_service = OrderService(db)
            recharge_service = RechargeService(db)
            order = order_service.get_by_order_no(notify.trade_no)
            if order:
                if order.status == "paid":
                    logger.info(f"订单 {notify.trade_no} 已经处理过了")
                    return {"status": "success", "message": "订单已处理"}
                payment_time = datetime.now(timezone.utc)
                success = order_service.complete_payment(notify.trade_no, payment_time, notify.callback_no)
                if success:
                    logger.info(f"订单 {notify.trade_no} 支付处理成功")
                    return {"status": "success", "message": "支付处理成功"}
                else:
                    logger.error(f"订单 {notify.trade_no} 支付处理失败")
                    return {"status": "failed", "message": "支付处理失败"}
            else:
                recharge = recharge_service.get_by_order_no(notify.trade_no)
                if recharge:
                    if recharge.status == "paid":
                        logger.info(f"充值订单 {notify.trade_no} 已经处理过了")
                        return {"status": "success", "message": "充值订单已处理"}
                    payment_time = datetime.now(timezone.utc)
                    success = recharge_service.mark_as_paid(recharge.id, notify.callback_no)
                    if success:
                        logger.info(f"充值订单 {notify.trade_no} 支付处理成功，用户余额已增加")
                        return {"status": "success", "message": "充值处理成功"}
                    else:
                        logger.error(f"充值订单 {notify.trade_no} 支付处理失败")
                        return {"status": "failed", "message": "充值处理失败"}
                else:
                    logger.warning(f"未找到订单或充值记录: {notify.trade_no}")
                    return {"status": "failed", "message": "订单不存在"}
        else:
            logger.warning(f"支付回调验证失败: payment_method={payment_method}, params_keys={list(params.keys()) if params else 'None'}")
            if params and 'out_trade_no' in params:
                logger.warning(f"验证失败的订单号: {params.get('out_trade_no')}")
            return {"status": "failed", "message": "支付验证失败"}
    except Exception as e:
        logger.error(f"支付回调处理异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"支付回调处理失败: {str(e)}")

@router.post("/refund/{payment_id}")
async def refund_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        payment = db.query(PaymentTransaction).filter(
            PaymentTransaction.id == payment_id,
            PaymentTransaction.user_id == current_user.id
        ).first()
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付交易不存在")
        if payment.status != 'success':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只有成功的支付才能申请退款")
        payment.status = 'refunded'
        db.commit()
        return {"status": "success", "message": "退款申请成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"退款申请失败: {str(e)}")

@router.get("/config")
async def get_payment_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_admin(current_user)
    configs = db.query(PaymentConfig).all()
    return configs

@router.post("/config")
async def update_payment_config(
    config_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_admin(current_user)
    try:
        for method, config in config_data.items():
            payment_config = db.query(PaymentConfig).filter(PaymentConfig.payment_method == method).first()
            if payment_config:
                payment_config.config_data = config
                payment_config.is_enabled = config.get('enabled', True)
            else:
                payment_config = PaymentConfig(
                    payment_method=method,
                    is_enabled=config.get('enabled', True),
                    config_data=config
                )
                db.add(payment_config)
        db.commit()
        return {"status": "success", "message": "支付配置更新成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新支付配置失败: {str(e)}")

@router.get("/statistics")
async def get_payment_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    _check_admin(current_user)
    try:
        query = db.query(PaymentTransaction)
        if start_date:
            query = query.filter(PaymentTransaction.created_at >= start_date)
        if end_date:
            query = query.filter(PaymentTransaction.created_at <= end_date)
        payments = query.all()
        total_amount = sum(p.amount for p in payments if p.status == 'success')
        total_count = len([p for p in payments if p.status == 'success'])
        pending_count = len([p for p in payments if p.status == 'pending'])
        failed_count = len([p for p in payments if p.status == 'failed'])
        alipay_amount = sum(p.amount for p in payments if p.payment_method == 'alipay' and p.status == 'success')
        wechat_amount = sum(p.amount for p in payments if p.payment_method == 'wechat' and p.status == 'success')
        return {
            "total_amount": total_amount,
            "total_count": total_count,
            "pending_count": pending_count,
            "failed_count": failed_count,
            "alipay_amount": alipay_amount,
            "wechat_amount": wechat_amount,
            "success_rate": (total_count / len(payments) * 100) if payments else 0
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取支付统计失败: {str(e)}")
