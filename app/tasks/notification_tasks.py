"""
通知相关定时任务
"""
import asyncio
import schedule
import time
import threading
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.services.notification_service import NotificationService
from app.services.subscription import SubscriptionService

logger = logging.getLogger(__name__)


class NotificationScheduler:
    """通知调度器"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self._execution_lock = threading.Lock()  # 任务执行锁，防止并发执行
    
    def start(self):
        """启动定时任务"""
        if self.running:
            logger.warning("通知调度器已在运行")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True, name="NotificationScheduler")
        self.thread.start()
        logger.info("通知定时任务已启动")
    
    def stop(self):
        """停止定时任务"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                logger.warning("通知调度器线程未能在5秒内停止")
        logger.info("通知定时任务已停止")
    
    def _run_scheduler(self):
        """运行调度器"""
        # 设置定时任务
        self._setup_schedules()
        
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"定时任务执行错误: {e}", exc_info=True)
                # 出错后等待更长时间再继续，避免快速重试导致资源耗尽
                time.sleep(60)
    
    def _setup_schedules(self):
        """设置定时任务"""
        # 每天上午9点检查订阅到期提醒（7天前）
        schedule.every().day.at("09:00").do(self._check_subscription_expiry_7_days)
        
        # 每天上午9点检查订阅到期提醒（3天前）
        schedule.every().day.at("09:00").do(self._check_subscription_expiry_3_days)
        
        # 每天上午9点检查订阅到期提醒（1天前）
        schedule.every().day.at("09:00").do(self._check_subscription_expiry_1_day)
        
        # 每天上午10点检查已过期的订阅
        schedule.every().day.at("10:00").do(self._check_expired_subscriptions)
        
        # 注意：邮件队列由EmailQueueProcessor持续处理，不需要定时任务
        # 移除每小时处理邮件队列的任务，避免重复处理和资源冲突
        
        logger.info("定时任务已设置完成")
    
    def _check_subscription_expiry_7_days(self):
        """检查7天后到期的订阅"""
        # 使用锁防止并发执行
        if not self._execution_lock.acquire(blocking=False):
            logger.warning("订阅到期提醒任务正在执行中，跳过本次执行")
            return
        
        try:
            db = SessionLocal()
            notification_service = NotificationService(db)
            sent_count = notification_service.send_subscription_expiry_reminder(7)
            logger.info(f"发送7天到期提醒: {sent_count} 封邮件")
        except Exception as e:
            logger.error(f"检查7天到期订阅失败: {e}", exc_info=True)
        finally:
            if 'db' in locals():
                db.close()
            self._execution_lock.release()
    
    def _check_subscription_expiry_3_days(self):
        """检查3天后到期的订阅"""
        # 使用锁防止并发执行
        if not self._execution_lock.acquire(blocking=False):
            logger.warning("订阅到期提醒任务正在执行中，跳过本次执行")
            return
        
        try:
            db = SessionLocal()
            notification_service = NotificationService(db)
            sent_count = notification_service.send_subscription_expiry_reminder(3)
            logger.info(f"发送3天到期提醒: {sent_count} 封邮件")
        except Exception as e:
            logger.error(f"检查3天到期订阅失败: {e}", exc_info=True)
        finally:
            if 'db' in locals():
                db.close()
            self._execution_lock.release()
    
    def _check_subscription_expiry_1_day(self):
        """检查1天后到期的订阅"""
        # 使用锁防止并发执行
        if not self._execution_lock.acquire(blocking=False):
            logger.warning("订阅到期提醒任务正在执行中，跳过本次执行")
            return
        
        try:
            db = SessionLocal()
            notification_service = NotificationService(db)
            sent_count = notification_service.send_subscription_expiry_reminder(1)
            logger.info(f"发送1天到期提醒: {sent_count} 封邮件")
        except Exception as e:
            logger.error(f"检查1天到期订阅失败: {e}", exc_info=True)
        finally:
            if 'db' in locals():
                db.close()
            self._execution_lock.release()
    
    def _check_expired_subscriptions(self):
        """检查已过期的订阅"""
        # 使用锁防止并发执行
        if not self._execution_lock.acquire(blocking=False):
            logger.warning("过期订阅检查任务正在执行中，跳过本次执行")
            return
        
        try:
            db = SessionLocal()
            # 处理过期订阅
            subscription_service = SubscriptionService(db)
            expired_count = subscription_service.check_expired_subscriptions()
            logger.info(f"处理过期订阅: {expired_count} 个")
            
            # 发送过期通知
            notification_service = NotificationService(db)
            sent_count = notification_service.send_subscription_expired_notification()
            logger.info(f"发送过期通知: {sent_count} 封邮件")
            
        except Exception as e:
            logger.error(f"检查过期订阅失败: {e}", exc_info=True)
        finally:
            if 'db' in locals():
                db.close()
            self._execution_lock.release()
    
    # 已移除_process_email_queue方法
    # 邮件队列由EmailQueueProcessor持续处理，不需要定时任务


# 全局调度器实例
notification_scheduler = NotificationScheduler()


def start_notification_scheduler():
    """启动通知调度器"""
    notification_scheduler.start()


def stop_notification_scheduler():
    """停止通知调度器"""
    notification_scheduler.stop()


# 手动执行任务的函数（用于测试）
def run_subscription_expiry_check(days: int = 7):
    """手动执行订阅到期检查"""
    db = next(get_db())
    try:
        notification_service = NotificationService(db)
        sent_count = notification_service.send_subscription_expiry_reminder(days)
        logger.info(f"手动发送{days}天到期提醒: {sent_count} 封邮件")
        return sent_count
    except Exception as e:
        logger.error(f"手动执行订阅到期检查失败: {e}", exc_info=True)
        return 0
    finally:
        db.close()


def run_expired_subscription_check():
    """手动执行过期订阅检查"""
    db = next(get_db())
    try:
        notification_service = NotificationService(db)
        sent_count = notification_service.send_subscription_expired_notification()
        logger.info(f"手动发送过期通知: {sent_count} 封邮件")
        return sent_count
    except Exception as e:
        logger.error(f"手动执行过期订阅检查失败: {e}", exc_info=True)
        return 0
    finally:
        db.close()


def get_notification_stats():
    """获取通知统计信息"""
    db = next(get_db())
    try:
        notification_service = NotificationService(db)
        stats = notification_service.get_notification_stats()
        return stats
    except Exception as e:
        logger.error(f"获取通知统计失败: {e}", exc_info=True)
        return {}
    finally:
        db.close()
