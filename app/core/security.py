import secrets
import hashlib
import hmac
import time
import re
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta
from app.core.config import settings

class SecurityManager:
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7
    def generate_csrf_token(self) -> str:
        return secrets.token_urlsafe(32)
    def verify_csrf_token(self, token: str, session_token: str) -> bool:
        return hmac.compare_digest(token, session_token)
    def generate_api_key(self) -> str:
        return f"cboard_{secrets.token_urlsafe(32)}"
    def hash_password(self, password: str) -> str:
        from app.core.auth import get_password_hash
        return get_password_hash(password)
    def verify_password(self, password: str, hashed: str) -> bool:
        from app.core.auth import verify_password
        return verify_password(password, hashed)
    def create_access_token(self, data: Dict[str, Any]) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != token_type:
                return None
            return payload
        except (jwt.ExpiredSignatureError, jwt.JWTError):
            return None
    def is_secure_request(self, request: Request) -> bool:
        if not request.url.scheme == "https" and not settings.DEBUG:
            return False
        required_headers = ["User-Agent", "Accept"]
        return all(request.headers.get(header) for header in required_headers)
    def sanitize_input(self, input_str: str) -> str:
        if not input_str:
            return ""
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '(', ')', '|', '`', '$']
        for char in dangerous_chars:
            input_str = input_str.replace(char, '')
        return input_str.strip()
    def validate_email(self, email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    def validate_password_strength(self, password: str) -> Dict[str, Any]:
        from app.core.auth import validate_password_strength as auth_validate
        is_valid, message = auth_validate(password)
        result = {"valid": is_valid, "score": 0, "issues": []}
        if not is_valid:
            result["issues"].append(message)
        if len(password) < 12:
            result["valid"] = False
            result["issues"].append("密码长度至少12位")
        if not any(c.isupper() for c in password):
            result["score"] += 1
            result["issues"].append("建议包含大写字母")
        if not any(c.islower() for c in password):
            result["score"] += 1
            result["issues"].append("建议包含小写字母")
        if not any(c.isdigit() for c in password):
            result["score"] += 1
            result["issues"].append("建议包含数字")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            result["score"] += 1
            result["issues"].append("建议包含特殊字符")
        weak_passwords = ["password", "123456", "123456789", "qwerty", "abc123", "password123", "admin", "root", "user"]
        if password.lower() in weak_passwords:
            result["valid"] = False
            result["issues"].append("密码过于简单")
        return result

class SecurityHeaders:
    @staticmethod
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response

security_manager = SecurityManager()

async def security_middleware(request: Request, call_next):
    if not security_manager.is_secure_request(request):
        if not settings.DEBUG:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不安全的请求")
    response = await call_next(request)
    response = SecurityHeaders.add_security_headers(response)
    return response
