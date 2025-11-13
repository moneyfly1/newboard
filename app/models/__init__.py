from .user import User
from .subscription import Subscription, Device
from .order import Order
from .package import Package
from .email import EmailQueue
from .notification import EmailTemplate, Notification
from .node import Node
from .payment import PaymentTransaction, PaymentCallback
from .payment_config import PaymentConfig
from .config import SystemConfig, Announcement, ThemeConfig
from .user_activity import UserActivity, SubscriptionReset, LoginHistory
from .verification_code import VerificationCode
from .verification_attempt import VerificationAttempt
from .login_attempt import LoginAttempt
from .ticket import Ticket, TicketReply, TicketAttachment, TicketStatus, TicketType, TicketPriority
from .coupon import Coupon, CouponUsage, CouponType, CouponStatus
from .recharge import RechargeRecord

# 设置关系
from sqlalchemy.orm import relationship

# User关系
User.subscriptions = relationship("Subscription", back_populates="user")
User.orders = relationship("Order", back_populates="user")
User.payments = relationship("PaymentTransaction", back_populates="user")
User.notifications = relationship("Notification", back_populates="user")
User.activities = relationship("UserActivity", back_populates="user")
User.subscription_resets = relationship("SubscriptionReset", back_populates="user")
User.login_history = relationship("LoginHistory", back_populates="user")
User.devices = relationship("Device", back_populates="user")
User.recharge_records = relationship("RechargeRecord", back_populates="user")

# Subscription关系
Subscription.user = relationship("User", back_populates="subscriptions")
Subscription.devices = relationship("Device", back_populates="subscription")

# Device关系
Device.subscription = relationship("Subscription", back_populates="devices")

# Order关系
Order.user = relationship("User", back_populates="orders")
Order.package = relationship("Package", back_populates="orders")
Order.payments = relationship("PaymentTransaction", back_populates="order")

# Package关系
Package.orders = relationship("Order", back_populates="package")

# Payment关系
PaymentTransaction.user = relationship("User", back_populates="payments")
PaymentTransaction.order = relationship("Order", back_populates="payments")

# Notification关系
Notification.user = relationship("User", back_populates="notifications")

# RechargeRecord关系
RechargeRecord.user = relationship("User", back_populates="recharge_records")

__all__ = [
    "User",
    "Subscription", 
    "Device",
    "Order",
    "Package", 
    "EmailQueue",
    "EmailTemplate",
    "Node",
    "PaymentTransaction",
    "PaymentConfig",
    "PaymentCallback",
    "Notification",
    "SystemConfig",
    "Announcement",
    "ThemeConfig",
    "UserActivity",
    "SubscriptionReset",
    "LoginHistory",
    "VerificationCode",
    "VerificationAttempt",
    "LoginAttempt",
    "Ticket",
    "TicketReply",
    "TicketAttachment",
    "TicketStatus",
    "TicketType",
    "TicketPriority",
    "Coupon",
    "CouponUsage",
    "CouponType",
    "CouponStatus",
    "RechargeRecord"
] 