"""邮件服务"""
import json
import logging
import smtplib
import ssl
import traceback
from datetime import datetime, timedelta, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.settings_manager import settings_manager
from app.models.email import EmailQueue
from app.schemas.email import EmailQueueCreate
from app.services.email_template_enhanced import EmailTemplateEnhanced

logger = logging.getLogger(__name__)


class EmailService:
    """邮件服务类"""

    def __init__(self, db: Session):
        self.db = db

    def get_smtp_config(self) -> Dict[str, Any]:
        return settings_manager.get_smtp_config(self.db)

    def is_email_enabled(self) -> bool:
        return settings_manager.is_email_enabled(self.db)

    def _ensure_processor_running(self) -> bool:
        try:
            import time
            from app.services.email_queue_processor import get_email_queue_processor

            processor = get_email_queue_processor()
            if processor.is_running and processor.processing_thread and processor.processing_thread.is_alive():
                return True

            processor.start_processing(force=True)
            time.sleep(0.1)

            if processor.is_running and processor.processing_thread and processor.processing_thread.is_alive():
                return True
            else:
                logger.warning("邮件队列处理器启动失败，线程未运行，但继续运行应用")
                return False
        except Exception as e:
            logger.warning(f"启动邮件队列处理器时出错（继续运行）: {e}", exc_info=True)
            return False

    def create_email_queue(self, email_data: EmailQueueCreate) -> EmailQueue:
        if not self.is_email_enabled():
            raise Exception("邮件服务未配置或未启用")

        time_threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
        existing_email = self.db.query(EmailQueue).filter(
            EmailQueue.to_email == email_data.to_email,
            EmailQueue.email_type == email_data.email_type,
            EmailQueue.status == 'pending',
            EmailQueue.created_at >= time_threshold
        ).first()

        if existing_email:
            logger.info(f"检测到5分钟内已有相同的待发送邮件（ID: {existing_email.id}），跳过重复创建")
            return existing_email

        email_queue = EmailQueue(**email_data.dict())
        self.db.add(email_queue)
        self.db.commit()
        self.db.refresh(email_queue)

        try:
            self._ensure_processor_running()
        except Exception as e:
            logger.warning(f"自动启动处理器失败（不影响邮件入队）: {e}", exc_info=True)

        return email_queue

    def queue_email(self, email_data: EmailQueueCreate) -> bool:
        try:
            self.create_email_queue(email_data)
            return True
        except Exception as e:
            logger.error(f"创建邮件队列失败: {e}", exc_info=True)
            return False

    def get_pending_emails(self, limit: int = 10) -> List[EmailQueue]:
        return self.db.query(EmailQueue).filter(
            EmailQueue.status == 'pending'
        ).order_by(EmailQueue.created_at).limit(limit).all()

    def send_email(self, email_queue: EmailQueue) -> bool:
        try:
            smtp_config = self.get_smtp_config()
            msg = MIMEMultipart()
            msg['From'] = f"{smtp_config['from_name']} <{smtp_config['from_email']}>"
            msg['To'] = email_queue.to_email
            msg['Subject'] = email_queue.subject
            if email_queue.content_type == 'html':
                msg.attach(MIMEText(email_queue.content, 'html', 'utf-8'))
            else:
                msg.attach(MIMEText(email_queue.content, 'plain', 'utf-8'))
            if email_queue.attachments:
                try:
                    attachments_data = json.loads(email_queue.attachments)
                    for attachment in attachments_data:
                        if isinstance(attachment, dict) and 'filename' in attachment and 'content' in attachment:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(attachment['content'])
                            encoders.encode_base64(part)
                            part.add_header('Content-Disposition', f'attachment; filename= {attachment["filename"]}')
                            msg.attach(part)
                except json.JSONDecodeError:
                    pass
            context = ssl.create_default_context()
            timeout = 30
            server = None
            try:
                if smtp_config['encryption'] == 'ssl':
                    server = smtplib.SMTP_SSL(smtp_config['host'], smtp_config['port'], context=context, timeout=timeout)
                else:
                    server = smtplib.SMTP(smtp_config['host'], smtp_config['port'], timeout=timeout)
                    if smtp_config['encryption'] == 'tls':
                        server.starttls(context=context)
                username = smtp_config['username']
                if '@' not in username and smtp_config.get('from_email'):
                    username = smtp_config['from_email']
                    logger.debug(f"用户名不是邮箱格式，使用发件人邮箱: {username}")
                logger.debug(f"尝试使用用户名: {username} 登录SMTP服务器")
                server.login(username, smtp_config['password'])
                logger.debug("SMTP登录成功")
                server.send_message(msg)
                logger.info(f"邮件发送成功: {email_queue.to_email}")
                email_queue.status = 'sent'
                email_queue.sent_at = datetime.now()
                self.db.commit()
                return True
            finally:
                if server:
                    try:
                        server.quit()
                    except Exception:
                        pass
        except Exception as e:
            error_msg = str(e)
            logger.error(f"邮件发送失败: {email_queue.to_email}, 错误: {error_msg}")
            try:
                email_queue.status = 'failed'
                email_queue.error_message = error_msg[:500]
                self.db.commit()
            except Exception as db_error:
                logger.error(f"更新邮件状态失败: {db_error}", exc_info=True)
                self.db.rollback()
            return False

    def _send_template_email(self, to_email: str, subject: str, html_content: str, email_type: str, log_prefix: str = "发送邮件") -> bool:
        if not self.is_email_enabled():
            logger.warning(f"邮件服务未启用，无法{log_prefix}到: {to_email}")
            return False
        try:
            email_data = EmailQueueCreate(
                to_email=to_email,
                subject=subject,
                content=html_content,
                content_type='html',
                email_type=email_type
            )
            return self.queue_email(email_data)
        except Exception as e:
            logger.error(f"{log_prefix}失败: {e}", exc_info=True)
            traceback.print_exc()
            return False

    def send_verification_code_email(self, user_email: str, verification_code: str, username: str = None) -> bool:
        html_content = EmailTemplateEnhanced.get_verification_code_template(username or "用户", verification_code)
        return self._send_template_email(
            to_email=user_email,
            subject="注册验证码 - 网络服务",
            html_content=html_content,
            email_type='verification_code',
            log_prefix="发送验证码邮件"
        )

    def send_reset_password_email(self, user_email: str, token: str, username: str = None) -> bool:
        try:
            from app.core.domain_config import get_domain_config
            domain_config = get_domain_config()
            base_url = domain_config.get_email_base_url(None, self.db).rstrip('/')
            reset_url = f"{base_url}/reset-password?token={token}"
            html_content = EmailTemplateEnhanced.get_password_reset_template(
                username=username or "用户",
                reset_link=reset_url,
                request=None,
                db=self.db
            )
            return self._send_template_email(
                to_email=user_email,
                subject="密码重置 - 网络服务",
                html_content=html_content,
                email_type='reset_password',
                log_prefix="发送重置密码邮件"
            )
        except Exception as e:
            logger.error(f"发送重置密码邮件失败: {e}", exc_info=True)
            traceback.print_exc()
            return False

    def send_password_reset_verification_code_email(self, user_email: str, verification_code: str, username: str = None) -> bool:
        html_content = EmailTemplateEnhanced.get_password_reset_verification_code_template(username or "用户", verification_code)
        return self._send_template_email(
            to_email=user_email,
            subject="密码重置验证码 - 网络服务",
            html_content=html_content,
            email_type='reset_password_verification_code',
            log_prefix="发送密码重置验证码邮件"
        )

    def send_welcome_email(self, user_email: str, username: str, user_id: int = None, password: str = None) -> bool:
        if not user_id:
            logger.error("发送欢迎邮件失败: 缺少必需的 user_id 参数")
            return False
        try:
            html_content = EmailTemplateEnhanced.get_welcome_template(user_id=user_id, password=password, request=None, db=self.db)
            return self._send_template_email(
                to_email=user_email,
                subject="欢迎注册 - 网络服务",
                html_content=html_content,
                email_type='welcome',
                log_prefix="发送欢迎邮件"
            )
        except Exception as e:
            logger.error(f"发送欢迎邮件失败: {e}", exc_info=True)
            traceback.print_exc()
            return False

    def send_subscription_email(self, user_email: str, subscription_data: Dict[str, Any], request=None) -> bool:
        subscription_id = subscription_data.get('subscription_id')
        if not subscription_id:
            logger.error("发送订阅邮件失败: 缺少必需的 subscription_id 参数")
            return False
        try:
            html_content = EmailTemplateEnhanced.get_subscription_template(subscription_id=subscription_id, request=request, db=self.db)
            if not html_content or html_content in ["数据库连接不可用", "订阅信息不存在", "订阅信息获取失败"]:
                logger.error("发送订阅邮件失败: 无法获取订阅模板内容")
                return False
            return self._send_template_email(
                to_email=user_email,
                subject="您的服务配置信息 - 网络服务",
                html_content=html_content,
                email_type="subscription",
                log_prefix="发送订阅邮件"
            )
        except Exception as e:
            logger.error(f"发送订阅邮件失败: {e}", exc_info=True)
            traceback.print_exc()
            return False

    def send_subscription_expiry_reminder(self, subscription_id: int, is_expired: bool = False, request=None) -> bool:
        try:
            from app.models.subscription import Subscription
            from app.models.user import User
            subscription = self.db.query(Subscription).filter(Subscription.id == subscription_id).first()
            if not subscription:
                logger.error(f"订阅不存在: {subscription_id}")
                return False
            user = self.db.query(User).filter(User.id == subscription.user_id).first()
            if not user:
                logger.error(f"用户不存在: {subscription.user_id}")
                return False
            html_content = EmailTemplateEnhanced.get_expiration_template(subscription_id=subscription_id, is_expired=is_expired, request=request, db=self.db)
            return self._send_template_email(
                to_email=user.email,
                subject=f"{'服务已到期' if is_expired else '服务即将到期'} - 网络服务",
                html_content=html_content,
                email_type='subscription_expiry',
                log_prefix="发送订阅到期提醒"
            )
        except Exception as e:
            logger.error(f"发送订阅到期提醒失败: {e}", exc_info=True)
            traceback.print_exc()
            return False

    def send_subscription_reset_notification(self, user_email: str, username: str, new_subscription_url: str, reset_time: str, reset_reason: str, subscription_id: int = None, request=None) -> bool:
        if not subscription_id:
            logger.error("发送订阅重置通知失败: 缺少必需的 subscription_id 参数")
            return False
        try:
            html_content = EmailTemplateEnhanced.get_subscription_reset_template(
                subscription_id=subscription_id,
                reset_time=reset_time,
                reset_reason=reset_reason,
                request=request,
                db=self.db
            )
            subject = f"{settings_manager.get_site_name(self.db)} - 订阅重置通知"
            return self._send_template_email(
                to_email=user_email,
                subject=subject,
                html_content=html_content,
                email_type='subscription_reset',
                log_prefix="发送订阅重置通知"
            )
        except Exception as e:
            logger.error(f"发送订阅重置通知失败: {e}", exc_info=True)
            traceback.print_exc()
            return False

    def send_announcement_email(self, user_email: str, announcement_data: Dict[str, Any]) -> bool:
        try:
            site_name = settings_manager.get_site_name(self.db)
            title = announcement_data.get('title', '系统公告')
            announcement_content = announcement_data.get('content', '')
            html_content = EmailTemplateEnhanced.get_announcement_template(title=title, content=announcement_content, request=None, db=self.db)
            return self._send_template_email(
                to_email=user_email,
                subject=f"{site_name} - {title}",
                html_content=html_content,
                email_type='announcement',
                log_prefix="发送公告邮件"
            )
        except Exception as e:
            logger.error(f"发送公告邮件失败: {e}", exc_info=True)
            traceback.print_exc()
            return False

    def send_order_confirmation_email(self, user_email: str, username: str, order_data: Dict[str, Any]) -> bool:
        try:
            html_content = EmailTemplateEnhanced.get_order_confirmation_template(username, order_data)
            return self._send_template_email(
                to_email=user_email,
                subject="订单确认 - 网络服务",
                html_content=html_content,
                email_type='order_confirmation',
                log_prefix="发送下单确认邮件"
            )
        except Exception as e:
            logger.error(f"发送下单确认邮件失败: {e}", exc_info=True)
            traceback.print_exc()
            return False

    def send_payment_success_email(self, user_email: str, username: str, payment_data: Dict[str, Any]) -> bool:
        order_id = payment_data.get('order_id')
        if not order_id:
            logger.error("发送支付成功邮件失败: 缺少必需的 order_id 参数")
            return False
        try:
            html_content = EmailTemplateEnhanced.get_payment_success_template(order_id=order_id, request=None, db=self.db)
            if not html_content or html_content in ["数据库连接不可用", "订单信息不存在"]:
                logger.error("发送支付成功邮件失败: 无法获取订单模板内容")
                return False
            return self._send_template_email(
                to_email=user_email,
                subject="支付成功 - 网络服务",
                html_content=html_content,
                email_type='payment_success',
                log_prefix="发送支付成功邮件"
            )
        except Exception as e:
            logger.error(f"发送支付成功邮件失败: {e}", exc_info=True)
            traceback.print_exc()
            return False

    def send_account_deletion_warning_email(self, user_email: str, username: str, last_login, request=None) -> bool:
        try:
            html_content = EmailTemplateEnhanced.get_account_deletion_warning_template(username=username, email=user_email, last_login=last_login, request=request, db=self.db)
            return self._send_template_email(
                to_email=user_email,
                subject="账号删除提醒 - 网络服务",
                html_content=html_content,
                email_type='account_deletion_warning',
                log_prefix="发送账号删除提醒邮件"
            )
        except Exception as e:
            logger.error(f"发送账号删除提醒邮件失败: {e}", exc_info=True)
            traceback.print_exc()
            return False

    def send_account_deletion_email(self, user_email: str, username: str, deletion_data: Dict[str, Any]) -> bool:
        try:
            html_content = EmailTemplateEnhanced.get_account_deletion_template(username, deletion_data)
            return self._send_template_email(
                to_email=user_email,
                subject="账号删除确认 - 网络服务",
                html_content=html_content,
                email_type='account_deletion',
                log_prefix="发送账号删除邮件"
            )
        except Exception as e:
            logger.error(f"发送账号删除邮件失败: {e}", exc_info=True)
            traceback.print_exc()
            return False

    def send_renewal_confirmation_email(self, user_email: str, username: str, renewal_data: Dict[str, Any]) -> bool:
        try:
            html_content = EmailTemplateEnhanced.get_renewal_confirmation_template(username, renewal_data)
            return self._send_template_email(
                to_email=user_email,
                subject="续费成功 - 网络服务",
                html_content=html_content,
                email_type='renewal_confirmation',
                log_prefix="发送续费确认邮件"
            )
        except Exception as e:
            logger.error(f"发送续费确认邮件失败: {e}", exc_info=True)
            traceback.print_exc()
            return False

    def process_email_queue(self) -> Dict[str, int]:
        if not self.is_email_enabled():
            return {"sent": 0, "failed": 0, "total": 0}
        pending_emails = self.get_pending_emails(limit=50)
        sent_count = 0
        failed_count = 0
        for email_queue in pending_emails:
            if self.send_email(email_queue):
                sent_count += 1
            else:
                failed_count += 1
        return {"sent": sent_count, "failed": failed_count, "total": len(pending_emails)}

    def cleanup_old_emails(self, days: int = 30) -> int:
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = self.db.query(EmailQueue).filter(
            EmailQueue.created_at < cutoff_date,
            EmailQueue.status.in_(['sent', 'failed'])
        ).delete()
        self.db.commit()
        return deleted_count

    def get_email_stats(self) -> Dict[str, int]:
        total = self.db.query(EmailQueue).count()
        pending = self.db.query(EmailQueue).filter(EmailQueue.status == 'pending').count()
        sent = self.db.query(EmailQueue).filter(EmailQueue.status == 'sent').count()
        failed = self.db.query(EmailQueue).filter(EmailQueue.status == 'failed').count()
        return {"total": total, "pending": pending, "sent": sent, "failed": failed}

    def get_daily_email_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        stats = []
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
            total = self.db.query(EmailQueue).filter(
                EmailQueue.created_at >= start_date,
                EmailQueue.created_at < end_date
            ).count()
            sent = self.db.query(EmailQueue).filter(
                EmailQueue.created_at >= start_date,
                EmailQueue.created_at < end_date,
                EmailQueue.status == 'sent'
            ).count()
            failed = self.db.query(EmailQueue).filter(
                EmailQueue.created_at >= start_date,
                EmailQueue.created_at < end_date,
                EmailQueue.status == 'failed'
            ).count()
            stats.append({"date": start_date.strftime('%Y-%m-%d'), "total": total, "sent": sent, "failed": failed})
        return stats

    def send_email_direct(self, to_email: str, subject: str, content: str, html_content: Optional[str] = None) -> bool:
        try:
            smtp_config = self.get_smtp_config()
            if not smtp_config:
                return False
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{smtp_config.get('from_name', 'CBoard')} <{smtp_config.get('from_email', settings.EMAILS_FROM_EMAIL)}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            text_part = MIMEText(content, 'plain', 'utf-8')
            msg.attach(text_part)
            if html_content:
                html_part = MIMEText(html_content, 'html', 'utf-8')
                msg.attach(html_part)
            with smtplib.SMTP(smtp_config['host'], smtp_config['port']) as server:
                if smtp_config.get('tls', False):
                    server.starttls()
                server.login(smtp_config['user'], smtp_config['password'])
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"直接发送邮件失败: {e}", exc_info=True)
            return False

    def send_password_reset_email_direct(self, to_email: str, username: str, reset_url: str) -> bool:
        try:
            text_content, html_content = EmailTemplateEnhanced.get_password_reset_direct_template(username, reset_url, request=None, db=self.db)
            subject = "密码重置 - 网络服务"
            return self.send_email_direct(to_email, subject, text_content.strip(), html_content)
        except Exception as e:
            logger.error(f"发送密码重置邮件失败: {e}", exc_info=True)
            return False

    def get_email_stats_by_type(self) -> Dict[str, Any]:
        type_stats = self.db.query(
            EmailQueue.email_type,
            func.count(EmailQueue.id).label('count')
        ).group_by(EmailQueue.email_type).all()
        return {
            "by_type": {stat.email_type or 'unknown': stat.count for stat in type_stats},
            "total_types": len(type_stats)
        }
