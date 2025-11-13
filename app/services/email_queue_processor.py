"""邮件队列处理服务"""
import logging
import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.email import EmailQueue
from app.services.email import EmailService

logger = logging.getLogger(__name__)


class EmailQueueProcessor:
    """邮件队列处理器类"""

    def __init__(self):
        self.is_running = False
        self.processing_thread = None
        self.batch_size = 5
        self.processing_interval = 10
        self.max_retries = 3
        self.retry_delays = [60, 300, 1800]
        self._stop_event = threading.Event()
        self._auto_restart = True
        self._restart_timer = None
        self._max_memory_usage = 100 * 1024 * 1024
        self._connection_timeout = 30
        self._max_processing_time = 300
        self._health_check_interval = 60
        self._last_health_check = time.time()
        self._consecutive_health_check_failures = 0
        self._max_health_check_failures = 3
        self._restart_count = 0
        self._max_restart_count = 5
        self._last_restart_time = 0

    def start_processing(self, force: bool = False):
        if self.is_running:
            logger.warning("邮件队列处理器已在运行")
            return
        if not force:
            current_time = time.time()
            if self._restart_count >= self._max_restart_count:
                if current_time - self._last_restart_time < 3600:
                    logger.error(f"邮件队列处理器重启次数过多（{self._restart_count}次），停止自动重启。请手动检查系统状态。")
                    logger.info("尝试重置重启计数并继续启动...")
                    self._restart_count = 0
                    self._last_restart_time = 0
                else:
                    self._restart_count = 0
            self._restart_count += 1
            self._last_restart_time = time.time()
        else:
            self._restart_count = 0
            self._last_restart_time = 0
        self.is_running = True
        self._stop_event.clear()
        self._auto_restart = True
        self._consecutive_health_check_failures = 0
        if self.processing_thread and self.processing_thread.is_alive():
            try:
                self._stop_event.set()
                self.processing_thread.join(timeout=2)
            except Exception:
                pass
        try:
            self.processing_thread = threading.Thread(target=self._process_queue_loop, daemon=True, name="EmailQueueProcessor")
            self.processing_thread.start()
            logger.info(f"邮件队列处理器已启动（重启次数: {self._restart_count if not force else 0}/{self._max_restart_count}，强制: {force}）")
            logger.debug(f"邮件队列处理器线程已启动: {self.processing_thread.name}, 运行状态: {self.is_running}, 线程存活: {self.processing_thread.is_alive()}")
        except Exception as e:
            logger.error(f"启动邮件队列处理器线程失败: {e}", exc_info=True)
            self.is_running = False
            raise
        try:
            self._start_health_check()
        except Exception as e:
            logger.warning(f"启动健康检查失败: {e}")

    def stop_processing(self):
        if not self.is_running:
            return
        self.is_running = False
        self._auto_restart = False
        self._stop_event.set()
        if self._restart_timer:
            self._restart_timer.cancel()
            self._restart_timer = None
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=10)
            if self.processing_thread.is_alive():
                logger.warning("邮件队列处理器强制停止")
        logger.info("邮件队列处理器已停止")

    def _process_queue_loop(self):
        while self.is_running and not self._stop_event.is_set():
            try:
                health_ok = self._health_check()
                if not health_ok:
                    self._consecutive_health_check_failures += 1
                    logger.warning(f"健康检查失败（连续失败 {self._consecutive_health_check_failures}/{self._max_health_check_failures} 次）")
                    if self._consecutive_health_check_failures >= self._max_health_check_failures:
                        logger.error("健康检查连续失败次数过多，停止处理")
                        break
                else:
                    self._consecutive_health_check_failures = 0
                self._process_batch()
                if self._stop_event.wait(self.processing_interval):
                    break
            except Exception as e:
                logger.error(f"邮件队列处理错误: {e}")
                logger.error(traceback.format_exc())
                if self._stop_event.wait(30):
                    break
        self.is_running = False
        if self._auto_restart and not self._stop_event.is_set():
            logger.warning("邮件队列处理器意外停止，将在10秒后自动重启")
            self._schedule_restart(10)

    def _process_batch(self):
        db = SessionLocal()
        try:
            pending_emails = self._get_pending_emails(db)
            if not pending_emails:
                return
            logger.info(f"处理 {len(pending_emails)} 封待发送邮件")
            for email_queue in pending_emails:
                if self._stop_event.is_set():
                    break
                try:
                    self._process_single_email(db, email_queue)
                except Exception as e:
                    logger.error(f"处理邮件 {email_queue.id} 失败: {e}")
                    logger.error(traceback.format_exc())
                    self._handle_email_failure(db, email_queue, str(e))
            if not self._stop_event.is_set():
                self._cleanup_processed_emails(db)
        except Exception as e:
            logger.error(f"批处理邮件失败: {e}")
            logger.error(traceback.format_exc())
        finally:
            db.close()

    def _get_pending_emails(self, db: Session) -> List[EmailQueue]:
        try:
            return db.query(EmailQueue).filter(
                EmailQueue.status == 'pending'
            ).order_by(EmailQueue.created_at).limit(self.batch_size).all()
        except Exception as e:
            logger.error(f"获取待发送邮件失败: {e}")
            return []

    def _process_single_email(self, db: Session, email_queue: EmailQueue):
        try:
            db.refresh(email_queue)
            if email_queue.status != 'pending':
                logger.info(f"邮件 {email_queue.id} 状态已变更为 {email_queue.status}，跳过处理")
                return
            email_service = EmailService(db)
            if email_queue.retry_count >= self.max_retries:
                email_queue.status = 'failed'
                email_queue.error_message = f"重试{self.max_retries}次后仍然失败"
                db.commit()
                logger.warning(f"邮件 {email_queue.id} 重试次数超限，标记为失败")
                return
            success = email_service.send_email(email_queue)
            if success:
                email_queue.status = 'sent'
                email_queue.sent_at = datetime.now()
                email_queue.retry_count = 0
                db.commit()
                logger.info(f"邮件 {email_queue.id} 发送成功")
            else:
                self._schedule_retry(db, email_queue)
        except Exception as e:
            logger.error(f"发送邮件 {email_queue.id} 异常: {e}")
            logger.error(traceback.format_exc())
            self._schedule_retry(db, email_queue, str(e))

    def _schedule_retry(self, db: Session, email_queue: EmailQueue, error: str = None):
        try:
            email_queue.retry_count += 1
            email_queue.status = 'pending'
            email_queue.error_message = error or "发送失败，等待重试"
            if email_queue.retry_count <= len(self.retry_delays):
                delay = self.retry_delays[email_queue.retry_count - 1]
            db.commit()
            logger.info(f"邮件 {email_queue.id} 安排重试，第 {email_queue.retry_count} 次")
        except Exception as e:
            logger.error(f"安排重试失败: {e}")
            db.rollback()

    def _handle_email_failure(self, db: Session, email_queue: EmailQueue, error: str):
        try:
            email_queue.status = 'failed'
            email_queue.error_message = error
            db.commit()
            logger.error(f"邮件 {email_queue.id} 发送失败: {error}")
        except Exception as e:
            logger.error(f"处理邮件失败状态失败: {e}")
            db.rollback()

    def _cleanup_processed_emails(self, db: Session):
        try:
            cutoff_date = datetime.now() - timedelta(days=30)
            deleted_count = db.query(EmailQueue).filter(
                and_(
                    EmailQueue.created_at < cutoff_date,
                    EmailQueue.status.in_(['sent', 'failed'])
                )
            ).delete()
            if deleted_count > 0:
                db.commit()
                logger.info(f"清理了 {deleted_count} 封已处理邮件")
        except Exception as e:
            logger.error(f"清理邮件失败: {e}")
            db.rollback()

    def _with_db(self, func):
        db = SessionLocal()
        try:
            return func(db)
        finally:
            db.close()

    def get_queue_stats(self) -> Dict[str, Any]:
        def _get_stats(db):
            total = db.query(EmailQueue).count()
            pending = db.query(EmailQueue).filter(EmailQueue.status == 'pending').count()
            sent = db.query(EmailQueue).filter(EmailQueue.status == 'sent').count()
            failed = db.query(EmailQueue).filter(EmailQueue.status == 'failed').count()
            type_stats = db.query(
                EmailQueue.email_type,
                func.count(EmailQueue.id)
            ).group_by(EmailQueue.email_type).all()
            retry_stats = db.query(
                EmailQueue.retry_count,
                func.count(EmailQueue.id)
            ).group_by(EmailQueue.retry_count).all()
            avg_retry_count = 0
            if total > 0:
                total_retries = sum(count * retry_count for retry_count, count in retry_stats)
                avg_retry_count = round(total_retries / total, 2)
            return {
                "total": total,
                "pending": pending,
                "sent": sent,
                "failed": failed,
                "type_distribution": dict(type_stats),
                "retry_distribution": dict(retry_stats),
                "avg_retry_count": avg_retry_count,
                "processor_status": "running" if self.is_running else "stopped"
            }
        try:
            return self._with_db(_get_stats)
        except Exception as e:
            logger.error(f"获取队列统计失败: {e}")
            return {
                "total": 0,
                "pending": 0,
                "sent": 0,
                "failed": 0,
                "type_distribution": {},
                "retry_distribution": {},
                "avg_retry_count": 0,
                "processor_status": "error"
            }

    def retry_failed_emails(self, email_ids: Optional[List[int]] = None) -> Dict[str, int]:
        def _retry(db):
            if email_ids:
                failed_emails = db.query(EmailQueue).filter(
                    and_(
                        EmailQueue.id.in_(email_ids),
                        EmailQueue.status == 'failed'
                    )
                ).all()
            else:
                failed_emails = db.query(EmailQueue).filter(EmailQueue.status == 'failed').all()
            retry_count = 0
            for email in failed_emails:
                email.status = 'pending'
                email.retry_count = 0
                email.error_message = "手动重试"
                retry_count += 1
            db.commit()
            logger.info(f"手动重试了 {retry_count} 封失败邮件")
            return {"retried": retry_count, "total_failed": len(failed_emails)}
        try:
            return self._with_db(_retry)
        except Exception as e:
            logger.error(f"重试失败邮件时出错: {e}")
            return {"retried": 0, "error": str(e)}

    def pause_processing(self, duration_minutes: int = 0):
        if duration_minutes > 0:
            logger.info(f"暂停邮件处理 {duration_minutes} 分钟")
            self.is_running = False
            threading.Timer(duration_minutes * 60, self.start_processing).start()
        else:
            logger.info("暂停邮件处理")
            self.is_running = False

    def resume_processing(self):
        if not self.is_running:
            self.start_processing()
        else:
            logger.info("邮件处理器已在运行")

    def is_healthy(self) -> bool:
        try:
            if not self.processing_thread or not self.processing_thread.is_alive():
                return False
            def _check(db):
                failed_count = db.query(EmailQueue).filter(EmailQueue.status == 'failed').count()
                total_count = db.query(EmailQueue).count()
                return not (total_count > 0 and (failed_count / total_count) > 0.5)
            return self._with_db(_check)
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return False

    def get_email_queue(self, page: int = 1, size: int = 20, status: str = None) -> List[EmailQueue]:
        def _get(db):
            query = db.query(EmailQueue)
            if status:
                query = query.filter(EmailQueue.status == status)
            offset = (page - 1) * size
            return query.order_by(EmailQueue.created_at.desc()).offset(offset).limit(size).all()
        return self._with_db(_get)

    def get_email_queue_count(self, status: str = None) -> int:
        def _count(db):
            query = db.query(EmailQueue)
            if status:
                query = query.filter(EmailQueue.status == status)
            return query.count()
        return self._with_db(_count)

    def get_email_by_id(self, email_id: int) -> Optional[EmailQueue]:
        def _get(db):
            return db.query(EmailQueue).filter(EmailQueue.id == email_id).first()
        return self._with_db(_get)

    def retry_email(self, email_id: int) -> bool:
        def _retry(db):
            email = db.query(EmailQueue).filter(EmailQueue.id == email_id).first()
            if not email:
                return False
            email.status = 'pending'
            email.retry_count += 1
            email.error_message = None
            db.commit()
            email_service = EmailService(db)
            success = email_service.send_email(email)
            if success:
                email.status = 'sent'
                email.sent_at = datetime.now()
            else:
                email.status = 'failed'
                email.error_message = '重试发送失败'
            db.commit()
            return success
        try:
            return self._with_db(_retry)
        except Exception as e:
            logger.error(f"重试邮件失败: {e}")
            return False

    def delete_email_from_queue(self, email_id: int) -> bool:
        def _delete(db):
            email = db.query(EmailQueue).filter(EmailQueue.id == email_id).first()
            if not email:
                return False
            db.delete(email)
            db.commit()
            return True
        try:
            return self._with_db(_delete)
        except Exception as e:
            logger.error(f"删除邮件失败: {e}")
            return False

    def clear_email_queue(self, status: str = None) -> bool:
        def _clear(db):
            query = db.query(EmailQueue)
            if status:
                query = query.filter(EmailQueue.status == status)
            deleted_count = query.delete()
            db.commit()
            logger.info(f"清空邮件队列成功，删除了 {deleted_count} 条记录")
            return True
        try:
            return self._with_db(_clear)
        except Exception as e:
            logger.error(f"清空邮件队列失败: {e}")
            return False

    def _cancel_timer(self):
        if self._restart_timer:
            try:
                self._restart_timer.cancel()
            except:
                pass

    def _start_health_check(self):
        def health_check():
            if self._stop_event.is_set() or not self._auto_restart:
                return
            if not self.is_running or not self.processing_thread or not self.processing_thread.is_alive():
                if self._restart_timer and self._restart_timer.is_alive():
                    return
                logger.warning("检测到邮件队列处理器异常，准备重启")
                self._schedule_restart(5)
            else:
                self._restart_timer = threading.Timer(30, health_check)
                self._restart_timer.start()
        self._cancel_timer()
        self._restart_timer = threading.Timer(30, health_check)
        self._restart_timer.start()

    def _schedule_restart(self, delay_seconds: int = 10):
        self._cancel_timer()
        def restart():
            if self._auto_restart and not self._stop_event.is_set():
                self.is_running = False
                if self.processing_thread and self.processing_thread.is_alive():
                    self.processing_thread.join(timeout=5)
                if self._restart_count >= self._max_restart_count:
                    current_time = time.time()
                    if current_time - self._last_restart_time < 3600:
                        logger.error(f"邮件队列处理器已达到最大重启次数（{self._max_restart_count}次），停止自动重启。请检查系统状态。")
                        self._auto_restart = False
                        return
                    else:
                        self._restart_count = 0
                logger.info("自动重启邮件队列处理器")
                self.start_processing()
        self._restart_timer = threading.Timer(delay_seconds, restart)
        self._restart_timer.start()

    def force_restart(self):
        logger.info("强制重启邮件队列处理器")
        self.stop_processing()
        self._auto_restart = True
        self.start_processing()

    def _health_check(self):
        try:
            current_time = time.time()
            if current_time - self._last_health_check > self._health_check_interval:
                self._last_health_check = current_time
                if not self._check_memory_usage():
                    return False
                if not self._check_database_connection():
                    return False
            return True
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return False

    def _check_memory_usage(self):
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            if memory_info.rss > self._max_memory_usage:
                logger.warning(f"内存使用过高: {memory_info.rss / 1024 / 1024:.2f}MB")
                return False
            return True
        except ImportError:
            return True
        except Exception as e:
            logger.error(f"内存检查失败: {e}")
            return True

    def _check_database_connection(self):
        try:
            from sqlalchemy import text
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db.close()
            return True
        except Exception as e:
            logger.error(f"数据库连接检查失败: {e}")
            return False

email_queue_processor = EmailQueueProcessor()

def get_email_queue_processor() -> EmailQueueProcessor:
    return email_queue_processor
