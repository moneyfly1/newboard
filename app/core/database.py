from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from fastapi import HTTPException
from app.core.config import settings
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

def get_database_url():
    project_root = Path(__file__).parent.parent.parent.resolve()
    if settings.DATABASE_URL:
        if settings.DATABASE_URL.startswith("sqlite:///./"):
            db_name = settings.DATABASE_URL.replace("sqlite:///./", "")
            db_path = project_root / db_name
            logger.info(f"数据库路径已转换为绝对路径: {db_path}")
            return f"sqlite:///{db_path}"
        return settings.DATABASE_URL
    if os.getenv("USE_MYSQL", "false").lower() == "true":
        return f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}?charset=utf8mb4"
    elif os.getenv("USE_POSTGRES", "false").lower() == "true":
        return f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:5432/{settings.POSTGRES_DB}"
    else:
        db_path = project_root / "cboard.db"
        logger.info(f"使用默认数据库路径: {db_path}")
        return f"sqlite:///{db_path}"

database_url = get_database_url()
logger.info(f"使用数据库: {database_url}")

def _create_engine_common(pool_size=10, max_overflow=20, echo=False):
    pool_recycle = 3600 if "mysql" in database_url or "postgresql" in database_url else None
    # 添加连接参数，确保连接稳定
    connect_args = {}
    if "mysql" in database_url:
        connect_args = {
            "connect_timeout": 30,
            "read_timeout": 30,
            "write_timeout": 30,
            "charset": "utf8mb4",
            "autocommit": False
        }
    elif "postgresql" in database_url:
        connect_args = {
            "connect_timeout": 30,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5
        }
    return create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,  # 每次使用前检查连接
        pool_recycle=pool_recycle,
        pool_reset_on_return='commit',  # 返回连接池时重置
        echo=echo,
        connect_args=connect_args if connect_args else None,
        pool_timeout=30  # 获取连接的超时时间
    )

if "sqlite" in database_url:
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True
    )
elif "mysql" in database_url or "postgresql" in database_url:
    engine = _create_engine_common(pool_size=10, max_overflow=20, echo=settings.DEBUG)
else:
    engine = _create_engine_common(pool_size=5, max_overflow=10)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """获取数据库会话，带自动重连机制和健康检查"""
    global engine, SessionLocal
    db = None
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            db = SessionLocal()
            # 测试连接是否有效（使用简单查询）
            try:
                db.execute(text("SELECT 1"))
                db.commit()
            except Exception as test_error:
                try:
                    db.rollback()
                except:
                    pass
                try:
                    db.close()
                except:
                    pass
                db = None
                raise test_error
            
            # 连接成功，返回数据库会话
            try:
                yield db
            except Exception as e:
                # 如果发生错误，尝试回滚
                try:
                    db.rollback()
                except:
                    pass
                raise
            finally:
                # 确保连接总是被关闭
                if db:
                    try:
                        db.close()
                    except Exception as close_error:
                        logger.warning(f"关闭数据库连接时出错: {close_error}")
            return  # 成功返回，退出循环
        except HTTPException:
            # HTTPException 应该直接抛出，不重试
            if db:
                try:
                    db.rollback()
                    db.close()
                except:
                    pass
            raise
        except Exception as e:
            if db:
                try:
                    db.rollback()
                    db.close()
                except:
                    pass
                db = None
            retry_count += 1
            logger.warning(f"数据库连接失败，重试 {retry_count}/{max_retries}: {e}")
            if retry_count >= max_retries:
                logger.error(f"数据库连接失败，已达到最大重试次数: {e}")
                # 尝试重新创建连接池
                try:
                    if "sqlite" in database_url:
                        engine = create_engine(
                            database_url,
                            connect_args={"check_same_thread": False},
                            poolclass=QueuePool,
                            pool_size=5,
                            max_overflow=10,
                            pool_pre_ping=True
                        )
                    else:
                        engine = _create_engine_common(pool_size=10, max_overflow=20, echo=settings.DEBUG)
                    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
                    logger.info("数据库连接池已重新创建")
                except Exception as reconnect_error:
                    logger.error(f"重新创建数据库连接池失败: {reconnect_error}")
                # 抛出 HTTPException，让 FastAPI 处理
                raise HTTPException(status_code=503, detail="数据库连接失败，请稍后重试")
            import time
            time.sleep(0.1 * retry_count)  # 递增延迟

def test_database_connection():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            logger.info("数据库连接验证成功")
            return True
    except Exception as e:
        logger.error(f"数据库连接验证失败: {e}")
        return False

def init_database():
    try:
        from app.models import (
            User, Subscription, Device, Order, Package, EmailQueue,
            EmailTemplate, Notification, Node, PaymentTransaction,
            PaymentConfig, PaymentCallback, SystemConfig, Announcement,
            ThemeConfig, UserActivity, SubscriptionReset, LoginHistory,
            Ticket, TicketReply, TicketAttachment, Coupon, CouponUsage,
            RechargeRecord, LoginAttempt, VerificationAttempt
        )
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表初始化成功")
        with engine.connect() as connection:
            if "sqlite" in database_url:
                query = "SELECT name FROM sqlite_master WHERE type='table'"
            elif "mysql" in database_url:
                query = "SHOW TABLES"
            elif "postgresql" in database_url:
                query = "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            else:
                query = "SELECT name FROM sqlite_master WHERE type='table'"
            result = connection.execute(text(query))
            tables = [row[0] for row in result]
            logger.info(f"已创建的表: {tables}")
            required_tables = ["users", "subscriptions", "devices", "orders", "packages", "user_activities", "subscription_resets", "login_history", "tickets", "ticket_replies", "ticket_attachments", "coupons", "coupon_usages", "recharge_records"]
            missing_tables = [table for table in required_tables if table not in tables]
            if missing_tables:
                logger.warning(f"缺少的表: {missing_tables}")
            else:
                logger.info("所有必需的表都已创建")
        return True
    except Exception as e:
        logger.error(f"数据库表初始化失败: {e}")
        return False
