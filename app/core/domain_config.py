import os
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

class DomainConfig:
    def __init__(self):
        self._domain_cache = {}
        self._ssl_enabled_cache = {}
    def _normalize_domain(self, domain: str) -> Optional[str]:
        if not domain:
            return None
        domain = domain.strip()
        if domain.startswith('http://'):
            domain = domain[7:]
        elif domain.startswith('https://'):
            domain = domain[8:]
        domain = domain.rstrip('/')
        return domain if domain else None
    def _get_scheme(self, request=None, db: Optional[Session] = None) -> str:
        return 'https' if self.is_ssl_enabled(request, db) else 'http'
    def _get_configured_base_url(self, db: Optional[Session] = None, exclude_localhost: bool = False) -> Optional[str]:
        try:
            from app.core.config import settings
            if hasattr(settings, 'BASE_URL') and settings.BASE_URL:
                base_url = settings.BASE_URL.rstrip('/')
                if not exclude_localhost or ('localhost' not in base_url and '127.0.0.1' not in base_url):
                    return base_url
        except Exception:
            pass
        domain = os.getenv('DOMAIN_NAME') or os.getenv('DOMAIN')
        domain = self._normalize_domain(domain)
        if domain:
            return f"{self._get_scheme(None, db)}://{domain}"
        if db:
            try:
                result = db.execute(text("SELECT value FROM system_configs WHERE key = 'domain_name'")).first()
                if result and result[0]:
                    domain = self._normalize_domain(result[0])
                    if domain:
                        return f"{self._get_scheme(None, db)}://{domain}"
            except Exception:
                pass
        return None
    def get_base_url(self, request=None, db: Optional[Session] = None) -> str:
        base_url = self._get_configured_base_url(db, exclude_localhost=False)
        if base_url:
            return base_url
        if request:
            host = request.headers.get('host', '')
            if host:
                return f"{self._get_scheme(request, db)}://{host}"
        return "http://localhost:8000"
    def get_frontend_url(self, request=None, db: Optional[Session] = None) -> str:
        base_url = self.get_base_url(request, db)
        frontend_domain = os.getenv('FRONTEND_DOMAIN')
        if frontend_domain:
            return f"{self._get_scheme(request, db)}://{frontend_domain}"
        return base_url
    def is_ssl_enabled(self, request=None, db: Optional[Session] = None) -> bool:
        if request:
            if request.headers.get('x-forwarded-proto') == 'https' or request.headers.get('x-forwarded-ssl') == 'on' or (hasattr(request, 'url') and str(request.url).startswith('https')):
                return True
        ssl_enabled = os.getenv('SSL_ENABLED', '').lower()
        if ssl_enabled in ['true', '1', 'yes', 'on']:
            return True
        if db:
            try:
                result = db.execute(text("SELECT value FROM system_configs WHERE key = 'ssl_enabled'")).first()
                if result:
                    return result[0].lower() in ['true', '1', 'yes', 'on']
            except Exception:
                pass
        return False
    def get_payment_callback_urls(self, request=None, db: Optional[Session] = None) -> Dict[str, str]:
        base_url = self.get_base_url(request, db)
        return {
            'notify_url': f"{base_url}/api/v1/payment/alipay/notify",
            'return_url': f"{base_url}/payment/success",
            'cancel_url': f"{base_url}/payment/cancel"
        }
    def get_subscription_urls(self, subscription_key: str, request=None, db: Optional[Session] = None) -> Dict[str, str]:
        base_url = self.get_base_url(request, db)
        return {
            'v2ray_url': f"{base_url}/api/v1/subscriptions/v2ray/{subscription_key}",
            'clash_url': f"{base_url}/api/v1/subscriptions/clash/{subscription_key}",
            'ssr_url': f"{base_url}/api/v1/subscriptions/ssr/{subscription_key}"
        }
    def get_email_base_url(self, request=None, db: Optional[Session] = None) -> str:
        base_url = self._get_configured_base_url(db, exclude_localhost=True)
        if base_url:
            return base_url
        if request:
            base_url = self.get_base_url(request, db)
            if 'localhost' not in base_url and '127.0.0.1' not in base_url:
                return base_url
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("未配置域名，邮件中使用localhost:8000。")
        logger.info("请在 .env 文件中设置以下任一变量：")
        logger.info("   - DOMAIN_NAME=yourdomain.com")
        logger.info("   - DOMAIN=yourdomain.com")
        logger.info("   - BASE_URL=https://yourdomain.com")
        return "http://localhost:8000"
    def update_domain_config(self, domain_name: str, ssl_enabled: bool, db: Session):
        try:
            from datetime import datetime
            now = datetime.now()
            db.execute(text("""
                INSERT OR REPLACE INTO system_configs (key, value, type, created_at, updated_at)
                VALUES ('domain_name', :domain_name, 'system', :now, :now)
            """), {'domain_name': domain_name, 'now': now})
            db.execute(text("""
                INSERT OR REPLACE INTO system_configs (key, value, type, created_at, updated_at)
                VALUES ('ssl_enabled', :ssl_enabled, 'system', :now, :now)
            """), {'ssl_enabled': str(ssl_enabled).lower(), 'now': now})
            db.commit()
            self._domain_cache.clear()
            self._ssl_enabled_cache.clear()
        except Exception as e:
            db.rollback()
            raise e
    def get_domain_info(self, request=None, db: Optional[Session] = None) -> Dict[str, Any]:
        return {
            'base_url': self.get_base_url(request, db),
            'frontend_url': self.get_frontend_url(request, db),
            'ssl_enabled': self.is_ssl_enabled(request, db),
            'domain_name': self._extract_domain_name(self.get_base_url(request, db)),
            'payment_urls': self.get_payment_callback_urls(request, db),
            'email_base_url': self.get_email_base_url(request, db)
        }
    def _extract_domain_name(self, url: str) -> str:
        if '://' in url:
            return url.split('://')[1].split('/')[0]
        return url

domain_config = DomainConfig()

def get_domain_config() -> DomainConfig:
    return domain_config
