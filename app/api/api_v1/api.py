from fastapi import APIRouter

from app.api.api_v1.endpoints import (
    auth, users, subscriptions, orders, packages,
    payment, payment_methods, payment_config, nodes, notifications, admin, config,
    statistics, settings, email_stats, device_management, announcements,
    software_config, config_update, monitoring, backup, logs, tickets, coupons, recharge
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["订阅"])
api_router.include_router(orders.router, prefix="/orders", tags=["订单"])
api_router.include_router(packages.router, prefix="/packages", tags=["套餐"])
api_router.include_router(payment.router, prefix="/payment", tags=["支付"])
api_router.include_router(payment_methods.router, prefix="/payment-methods", tags=["支付方式"])
api_router.include_router(payment_config.router, prefix="/payment-config", tags=["支付配置"])
api_router.include_router(nodes.router, prefix="/nodes", tags=["节点"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["通知"])
api_router.include_router(admin.router, prefix="/admin", tags=["管理员"])
api_router.include_router(config.router, prefix="/config", tags=["配置"])
api_router.include_router(statistics.router, prefix="/statistics", tags=["统计"])
api_router.include_router(settings.router, prefix="/settings", tags=["设置"])
api_router.include_router(email_stats.router, prefix="/email-stats", tags=["邮件统计"])
api_router.include_router(device_management.router, prefix="/admin/devices", tags=["设备管理"])
api_router.include_router(announcements.router, prefix="/announcements", tags=["公告"])
api_router.include_router(software_config.router, prefix="/software-config", tags=["软件配置"])
api_router.include_router(config_update.router, prefix="/admin/config-update", tags=["配置更新"])
api_router.include_router(monitoring.router, prefix="/admin/monitoring", tags=["系统监控"])
api_router.include_router(backup.router, prefix="/admin/backup", tags=["备份管理"])
api_router.include_router(logs.router, prefix="/admin/logs", tags=["日志管理"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["工单管理"])
api_router.include_router(coupons.router, prefix="/coupons", tags=["优惠券管理"])
api_router.include_router(recharge.router, prefix="/recharge", tags=["充值管理"])