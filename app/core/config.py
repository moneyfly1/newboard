from typing import List, Union
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings
import os
import warnings
import secrets
from pathlib import Path

class Settings(BaseSettings):
    PROJECT_NAME: str = "CBoard Modern"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ]
    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./cboard.db")
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "cboard_user")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    @validator("MYSQL_PASSWORD", pre=True)
    def validate_mysql_password(cls, v: str) -> str:
        if not v or v == "cboard_password_2024":
            if os.getenv("FORCE_STRONG_PASSWORDS", "false").lower() == "true":
                raise ValueError("MYSQL_PASSWORD必须通过环境变量设置，不能使用默认值")
            warnings.warn("MYSQL_PASSWORD未设置或使用默认值，请立即在环境变量中设置强密码！", UserWarning)
        if v and len(v) < 12:
            warnings.warn("MYSQL_PASSWORD长度不足12位，建议使用更强的密码", UserWarning)
        return v
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "cboard_db")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    @validator("POSTGRES_PASSWORD", pre=True)
    def validate_postgres_password(cls, v: str) -> str:
        if not v or v == "password":
            if os.getenv("FORCE_STRONG_PASSWORDS", "false").lower() == "true":
                raise ValueError("POSTGRES_PASSWORD必须通过环境变量设置，不能使用默认值")
            warnings.warn("POSTGRES_PASSWORD未设置或使用默认值，请立即在环境变量中设置强密码！", UserWarning)
        if v and len(v) < 12:
            warnings.warn("POSTGRES_PASSWORD长度不足12位，建议使用更强的密码", UserWarning)
        return v
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "cboard")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    @validator("SECRET_KEY", pre=True)
    def validate_secret_key(cls, v: str) -> str:
        if not v or v == "your-secret-key-here" or len(v) < 32:
            generated_key = secrets.token_urlsafe(32)
            warnings.warn(
                f"SECRET_KEY未设置或太弱，已自动生成: {generated_key[:20]}... "
                "请立即在环境变量中设置SECRET_KEY！",
                UserWarning
            )
            return generated_key
        return v
    ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_HOURS", "24")) * 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    SMTP_TLS: bool = os.getenv("SMTP_ENCRYPTION", "tls") in ["tls", "ssl"]
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.qq.com")
    SMTP_USER: str = os.getenv("SMTP_USERNAME", "your-email@qq.com")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "your-smtp-password")
    EMAILS_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "your-email@qq.com")
    EMAILS_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "CBoard Modern")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    ALIPAY_APP_ID: str = os.getenv("ALIPAY_APP_ID", "your-alipay-app-id")
    ALIPAY_PRIVATE_KEY: str = os.getenv("ALIPAY_PRIVATE_KEY", "your-private-key")
    ALIPAY_PUBLIC_KEY: str = os.getenv("ALIPAY_PUBLIC_KEY", "alipay-public-key")
    ALIPAY_NOTIFY_URL: str = os.getenv("ALIPAY_NOTIFY_URL", "https://yourdomain.com/api/v1/payment/alipay/notify")
    ALIPAY_RETURN_URL: str = os.getenv("ALIPAY_RETURN_URL", "https://yourdomain.com/api/v1/payment/alipay/return")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))
    SUBSCRIPTION_URL_PREFIX: str = os.getenv("SUBSCRIPTION_URL_PREFIX", "http://localhost:8000/sub")
    DEVICE_LIMIT_DEFAULT: int = int(os.getenv("DEVICE_LIMIT_DEFAULT", "3"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    WORKERS: int = int(os.getenv("WORKERS", "4"))
    BASE_URL: str = os.getenv("BASE_URL", "http://127.0.0.1:8000")
    @property
    def REDIS_URL(self) -> str:
        return os.getenv("REDIS_URL", f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}")
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()
upload_dir = Path(settings.UPLOAD_DIR)
upload_dir.mkdir(exist_ok=True)
