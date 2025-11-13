"""
用户账号清理相关定时任务
检测30天未登录且无有效套餐的用户，先提醒，一周后删除
"""
import schedule
import time
import threading
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.core.database import SessionLocal
from app.models.user import User
from app.models.subscription import Subscription
from app.services.email import EmailService
from app.services.user import UserService

logger = logging.getLogger(__name__)


class UserCleanupScheduler:
    """用户清理调度器"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self._execution_lock = threading.Lock()  # 任务执行锁，防止并发执行
    
    def start(self):
        """启动定时任务"""
        if self.running:
            logger.warning("用户清理调度器已在运行")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True, name="UserCleanupScheduler")
        self.thread.start()
        logger.info("用户清理定时任务已启动")
    
    def stop(self):
        """停止定时任务"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                logger.warning("用户清理调度器线程未能在5秒内停止")
        logger.info("用户清理定时任务已停止")
    
    def _run_scheduler(self):
        """运行调度器"""
        # 设置定时任务
        self._setup_schedules()
        
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"用户清理定时任务执行错误: {e}", exc_info=True)
                # 出错后等待更长时间再继续，避免快速重试导致资源耗尽
                time.sleep(60)
    
    def _setup_schedules(self):
        """设置定时任务"""
        # 每天凌晨2点检查需要提醒的用户
        schedule.every().day.at("02:00").do(self._check_users_for_deletion_warning)
        
        # 每天凌晨3点检查需要删除的用户
        schedule.every().day.at("03:00").do(self._check_users_for_deletion)
        
        logger.info("用户清理定时任务已设置完成")
    
    def _check_users_for_deletion_warning(self):
        """检查需要提醒的用户（30天未登录且无有效套餐）"""
        # 使用锁防止并发执行
        if not self._execution_lock.acquire(blocking=False):
            logger.warning("用户删除提醒任务正在执行中，跳过本次执行")
            return
        
        try:
            db = SessionLocal()
            # 计算30天前的日期
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            # 查找符合条件的用户：
            # 1. 30天未登录（last_login为None或小于cutoff_date）
            # 2. 没有有效套餐（没有订阅或订阅已过期）
            # 3. 不是管理员
            # 4. 还没有被标记为待删除提醒
            
            # 先获取所有有有效订阅的用户ID
            valid_subscription_user_ids = db.query(Subscription.user_id).filter(
                Subscription.expire_time > datetime.utcnow()
            ).distinct().all()
            valid_subscription_user_ids = [uid[0] for uid in valid_subscription_user_ids]
            
            # 查找符合条件的用户
            users = db.query(User).filter(
                and_(
                    User.is_admin == False,
                    or_(
                        User.last_login == None,
                        User.last_login < cutoff_date
                    ),
                    ~User.id.in_(valid_subscription_user_ids) if valid_subscription_user_ids else True
                )
            ).all()
            
            email_service = EmailService(db)
            warned_count = 0
            
            for user in users:
                # 检查用户是否有有效订阅
                has_valid_subscription = db.query(Subscription).filter(
                    and_(
                        Subscription.user_id == user.id,
                        Subscription.expire_time > datetime.utcnow()
                    )
                ).first() is not None
                
                if has_valid_subscription:
                    continue
                
                # 检查是否已经发送过提醒（通过检查用户邮箱是否在最近7天内收到过删除提醒邮件）
                from app.models.email import EmailQueue
                recent_warning = db.query(EmailQueue).filter(
                    and_(
                        EmailQueue.to_email == user.email,
                        EmailQueue.email_type == 'account_deletion_warning',
                        EmailQueue.created_at >= datetime.utcnow() - timedelta(days=7)
                    )
                ).first()
                
                if recent_warning:
                    continue  # 已经发送过提醒，跳过
                
                # 发送删除提醒邮件
                try:
                    if email_service.send_account_deletion_warning_email(
                        user_email=user.email,
                        username=user.username,
                        last_login=user.last_login,
                        request=None
                    ):
                        warned_count += 1
                        logger.info(f"已发送账号删除提醒邮件到: {user.email}")
                except Exception as e:
                    logger.error(f"发送账号删除提醒邮件失败 ({user.email}): {e}", exc_info=True)
            
            logger.info(f"账号删除提醒检查完成: 发送了 {warned_count} 封提醒邮件")
                
        except Exception as e:
            logger.error(f"检查需要提醒的用户失败: {e}", exc_info=True)
        finally:
            if 'db' in locals():
                db.close()
            self._execution_lock.release()
    
    def _check_users_for_deletion(self):
        """检查需要删除的用户（已提醒7天后）"""
        # 使用锁防止并发执行
        if not self._execution_lock.acquire(blocking=False):
            logger.warning("用户删除任务正在执行中，跳过本次执行")
            return
        
        try:
            db = SessionLocal()
            # 计算37天前的日期（30天未登录 + 7天宽限期）
            cutoff_date = datetime.utcnow() - timedelta(days=37)
            
            # 查找符合条件的用户：
            # 1. 37天未登录
            # 2. 没有有效套餐
            # 3. 不是管理员
            # 4. 在7天前收到过删除提醒
            
            from app.models.email import EmailQueue
            
            # 获取7天前收到过删除提醒的用户邮箱列表
            warning_cutoff = datetime.utcnow() - timedelta(days=7)
            warned_emails = db.query(EmailQueue.to_email).filter(
                and_(
                    EmailQueue.email_type == 'account_deletion_warning',
                    EmailQueue.created_at <= warning_cutoff
                )
            ).distinct().all()
            warned_emails = [email[0] for email in warned_emails]
            
            if not warned_emails:
                logger.info("没有需要删除的用户")
                return
            
            # 获取所有有有效订阅的用户ID（这些用户不应该被删除）
            valid_subscription_user_ids = db.query(Subscription.user_id).filter(
                Subscription.expire_time > datetime.utcnow()
            ).distinct().all()
            valid_subscription_user_ids = [uid[0] for uid in valid_subscription_user_ids]
            
            # 查找符合条件的用户
            users = db.query(User).filter(
                and_(
                    User.is_admin == False,
                    User.email.in_(warned_emails),
                    or_(
                        User.last_login == None,
                        User.last_login < cutoff_date
                    ),
                    ~User.id.in_(valid_subscription_user_ids) if valid_subscription_user_ids else True
                )
            ).all()
            
            user_service = UserService(db)
            email_service = EmailService(db)
            deleted_count = 0
            
            for user in users:
                # 再次检查用户是否有有效订阅（可能在提醒后购买了套餐）
                has_valid_subscription = db.query(Subscription).filter(
                    and_(
                        Subscription.user_id == user.id,
                        Subscription.expire_time > datetime.utcnow()
                    )
                ).first() is not None
                
                if has_valid_subscription:
                    continue  # 有有效订阅，不删除
                
                # 检查最后登录时间（可能在提醒后登录了）
                if user.last_login and user.last_login >= (datetime.utcnow() - timedelta(days=30)):
                    continue  # 最近30天内登录过，不删除
                
                # 删除用户前发送删除确认邮件
                try:
                    from app.utils.timezone import get_beijing_time_str
                    deletion_data = {
                        'reason': '30天未登录且无有效套餐',
                        'deletion_date': get_beijing_time_str('%Y-%m-%d %H:%M:%S'),
                        'data_retention_period': '0天（已立即删除）'
                    }
                    email_service.send_account_deletion_email(
                        user_email=user.email,
                        username=user.username,
                        deletion_data=deletion_data
                    )
                except Exception as e:
                    logger.error(f"发送删除确认邮件失败 ({user.email}): {e}", exc_info=True)
                    # 即使邮件发送失败，也继续删除用户
                
                # 删除用户
                try:
                    if user_service.delete(user.id):
                        db.commit()
                        deleted_count += 1
                        logger.info(f"已删除用户: {user.username} ({user.email})")
                    else:
                        logger.warning(f"删除用户失败: {user.username} ({user.email})")
                except Exception as e:
                    logger.error(f"删除用户时出错 ({user.username}): {e}", exc_info=True)
                    db.rollback()
            
            logger.info(f"账号删除检查完成: 删除了 {deleted_count} 个用户")
                
        except Exception as e:
            logger.error(f"检查需要删除的用户失败: {e}", exc_info=True)
        finally:
            if 'db' in locals():
                db.close()
            self._execution_lock.release()


# 全局调度器实例
user_cleanup_scheduler = UserCleanupScheduler()


def start_user_cleanup_scheduler():
    """启动用户清理调度器"""
    user_cleanup_scheduler.start()


def stop_user_cleanup_scheduler():
    """停止用户清理调度器"""
    user_cleanup_scheduler.stop()
