from fastapi import FastAPI, Request, status, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uvicorn
from datetime import datetime
import logging
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.api_v1.api import api_router
from app.core.database import init_database
from app.middleware.maintenance import maintenance_middleware
from app.schemas.common import ResponseBase

logger = logging.getLogger(__name__)
from app.models import (
    User, Subscription, Device, Order, Package, EmailQueue, 
    EmailTemplate, Notification, Node, PaymentTransaction, 
    PaymentConfig, PaymentCallback, SystemConfig, Announcement, 
    ThemeConfig, UserActivity, SubscriptionReset, LoginHistory,
    Ticket, Coupon, RechargeRecord, LoginAttempt, VerificationAttempt
)
from app.services.email_queue_processor import get_email_queue_processor
from app.tasks.notification_tasks import start_notification_scheduler, stop_notification_scheduler

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="CBoard Modern - 现代化订阅管理系统",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 设置CORS - 生产环境应限制为特定域名
cors_origins = settings.BACKEND_CORS_ORIGINS
if not settings.DEBUG:
    cors_origins = [str(origin) for origin in cors_origins if str(origin).startswith("https://")]
    if not cors_origins:
        cors_origins = [settings.BASE_URL] if settings.BASE_URL else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    expose_headers=[],
    max_age=3600,
)

# 添加维护模式中间件（优先检查）
app.middleware("http")(maintenance_middleware)

# 全局异常处理器（隐藏生产环境敏感信息）
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器，根据DEBUG模式决定是否显示详细错误"""
    import traceback
    from app.utils.response import sanitize_error_message
    
    error_str = str(exc)
    error_type = type(exc).__name__
    
    logger.error(f"全局异常捕获 [{error_type}]: {error_str}", exc_info=True)
    
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": sanitize_error_message(exc.detail, settings.DEBUG),
                "data": None
            }
        )
    
    error_message = sanitize_error_message(
        f"服务器错误: {error_str}" if settings.DEBUG else "服务器错误，请稍后重试或联系管理员",
        settings.DEBUG
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": error_message,
            "data": None
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理器"""
    from app.utils.response import sanitize_error_message
    
    errors = exc.errors()
    error_details = []
    for error in errors:
        field = ".".join(str(loc) for loc in error["loc"])
        error_details.append(f"{field}: {error['msg']}")
    
    if settings.DEBUG:
        error_message = f"请求验证失败: {', '.join(error_details)}"
    else:
        error_message = "请求参数错误，请检查输入"
    
    error_message = sanitize_error_message(error_message, settings.DEBUG)
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": error_message,
            "data": None
        }
    )

# 包含API路由
app.include_router(api_router, prefix=settings.API_V1_STR)

# 添加兼容路由：/notify -> /api/v1/payment/notify/alipay
# 注意：这只是临时兼容方案，建议在支付宝开放平台中直接配置正确的URL
from app.api.api_v1.endpoints.payment import payment_notify
from app.core.database import get_db

@app.post("/notify")
async def legacy_notify_route(request: Request, db: Session = Depends(get_db)):
    """
    兼容旧的回调URL配置
    重定向到正确的支付宝回调处理函数
    建议：在支付宝开放平台中将回调URL修改为 /api/v1/payment/notify/alipay
    """
    logger.info("收到兼容路由 /notify 的请求，转发到支付宝回调处理")
    return await payment_notify("alipay", request, db)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 应用启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库和启动邮件队列处理器"""
    import asyncio
    import gc

    try:
        init_database()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}", exc_info=True)

    try:
        from app.core.cache import redis_cache
        if redis_cache.is_connected():
            logger.info("Redis 缓存连接成功")
        else:
            logger.warning("Redis 缓存连接失败，将使用内存缓存作为后备")
    except Exception as e:
        logger.warning(f"Redis 缓存初始化失败（不影响应用运行）: {e}", exc_info=True)

    try:
        email_processor = get_email_queue_processor()
        email_processor.start_processing(force=True)
        logger.info("邮件队列处理器已启动")
    except Exception as e:
        logger.warning(f"邮件队列处理器启动失败（不影响应用运行）: {e}", exc_info=True)

    try:
        from app.tasks.notification_tasks import start_notification_scheduler
        start_notification_scheduler()
        logger.info("通知调度器已启动")
    except ImportError as e:
        logger.warning(f"通知调度器模块导入失败（不影响应用运行）: {e}")
    except Exception as e:
        logger.warning(f"通知调度器启动失败（不影响应用运行）: {e}", exc_info=True)

    try:
        from app.tasks.user_cleanup_tasks import start_user_cleanup_scheduler
        start_user_cleanup_scheduler()
        logger.info("用户清理调度器已启动")
    except ImportError as e:
        logger.warning(f"用户清理调度器模块导入失败（不影响应用运行）: {e}")
    except Exception as e:
        logger.warning(f"用户清理调度器启动失败（不影响应用运行）: {e}", exc_info=True)

    async def periodic_memory_cleanup():
        """定期清理内存"""
        while True:
            await asyncio.sleep(3600)
            try:
                from app.services.monitoring import SystemMonitor

                monitor = SystemMonitor()
                monitor.clear_old_metrics(hours=6)

                gc.collect()
                logger.debug("定期内存清理完成")
            except Exception as e:
                logger.warning(f"内存清理失败: {e}")

    asyncio.create_task(periodic_memory_cleanup())
    logger.info("内存清理任务已启动")

# 应用关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时停止邮件队列处理器"""
    try:
        email_processor = get_email_queue_processor()
        email_processor.stop_processing()
        logger.info("邮件队列处理器已停止")
        
        # 停止通知调度器
        stop_notification_scheduler()
        logger.info("通知调度器已停止")
        
        # 停止用户清理调度器
        try:
            from app.tasks.user_cleanup_tasks import stop_user_cleanup_scheduler
            stop_user_cleanup_scheduler()
            logger.info("用户清理调度器已停止")
        except Exception as e:
            logger.warning(f"停止用户清理调度器失败: {e}")
    except Exception as e:
        logger.error(f"停止服务失败: {e}", exc_info=True)

@app.get("/")
async def root():
    return {"message": "CBoard Modern API", "version": settings.VERSION}

@app.get("/health")
async def health_check():
    """健康检查端点"""
    try:
        from app.core.database import get_db
        from sqlalchemy import text
        
        # 检查系统健康状态（可选，如果模块不存在则跳过）
        system_health = {"status": "healthy", "message": "系统正常"}
        try:
            from app.services.monitoring import system_monitor
            system_health = system_monitor.check_system_health()
        except ImportError:
            # monitoring 模块不存在，跳过系统监控检查
            system_health = {"status": "healthy", "message": "系统监控模块未启用"}
        except Exception as e:
            system_health = {"status": "warning", "message": f"系统监控检查失败: {str(e)}"}
        
        # 检查数据库连接
        db_health = {"status": "healthy", "message": "数据库连接正常"}
        try:
            db = next(get_db())
            db.execute(text("SELECT 1"))
            db.close()
        except Exception as e:
            db_health = {"status": "error", "message": f"数据库连接失败: {str(e)}"}
        
        # 确定整体状态
        overall_status = "healthy"
        if db_health["status"] != "healthy":
            overall_status = "unhealthy"
        elif system_health.get("status") not in ["healthy", "warning"]:
            overall_status = "unhealthy"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "system": system_health,
            "database": db_health,
            "version": settings.VERSION
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"健康检查失败: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # 禁用自动重载，避免订阅更新时服务器重启
        log_level="info"
    )
