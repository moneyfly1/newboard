import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

try:
    import bcrypt
    pwd_context = CryptContext(
        schemes=["bcrypt"],
        deprecated="auto",
        bcrypt__rounds=12,
        bcrypt__min_rounds=10,
        bcrypt__max_rounds=15,
        bcrypt__ident="2b"
    )
except ImportError:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password or not isinstance(hashed_password, str):
        return False
    if not hashed_password.startswith(('$2a$', '$2b$', '$2y$')):
        return False
    try:
        import bcrypt
        password_bytes = plain_password.encode('utf-8') if isinstance(plain_password, str) else plain_password
        hash_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        try:
            return bcrypt.checkpw(password_bytes, hash_bytes)
        except (ValueError, TypeError):
            return pwd_context.verify(plain_password, hashed_password)
    except ImportError:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"密码验证错误: {e}", exc_info=True)
        return False

def get_password_hash(password: str) -> str:
    try:
        import bcrypt
        password_bytes = password.encode('utf-8') if isinstance(password, str) else password
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    except ImportError:
        hashed = pwd_context.hash(password)
        if not hashed:
            raise ValueError("密码哈希失败")
        return hashed
    except Exception as e:
        logger.error(f"密码哈希错误: {e}", exc_info=True)
        raise ValueError(f"密码哈希失败: {e}")

def validate_password_strength(password: str) -> tuple[bool, str]:
    if len(password) < 12:
        return False, "密码长度至少12位以提高安全性"
    if not any(c.isupper() for c in password):
        return False, "密码必须包含至少一个大写字母"
    if not any(c.islower() for c in password):
        return False, "密码必须包含至少一个小写字母"
    if not any(c.isdigit() for c in password):
        return False, "密码必须包含至少一个数字"
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        return False, "密码必须包含至少一个特殊字符 (!@#$%^&*()_+-=[]{}|;:,.<>?)"
    weak_passwords = ["password", "123456", "123456789", "qwerty", "abc123", "password123", "admin", "root", "user", "test"]
    if password.lower() in weak_passwords:
        return False, "密码过于简单，请使用更复杂的密码"
    return True, "密码强度符合要求"

def is_password_strong_enough(password: str) -> bool:
    return validate_password_strength(password)[0]

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = verify_token(token)
        if payload is None:
            raise credentials_exception
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        if payload.get("type") == "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌不能用于访问")
    except JWTError:
        raise credentials_exception
    try:
        user = db.query(User).filter(User.id == int(user_id)).first() if user_id.isdigit() else None
        if not user:
            user = db.query(User).filter(User.username == user_id).first()
    except (ValueError, TypeError):
        raise credentials_exception
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户账户已停用" if user else "无法验证凭据")
    if payload.get("login_as") and payload.get("admin_id"):
        logger.warning(f"检测到管理员 {payload.get('admin_id')} 以用户 {user.id} 身份登录")
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user

async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足，需要管理员权限")
    return current_user

async def get_current_verified_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先验证邮箱")
    return current_user

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

def create_user_tokens(user: User) -> dict:
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email, "is_admin": user.is_admin}, expires_delta=access_token_expires)
    refresh_token = create_refresh_token(data={"sub": str(user.id), "email": user.email})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

def refresh_access_token(refresh_token: str) -> Optional[str]:
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return create_access_token(data={"sub": user_id, "email": payload.get("email"), "is_admin": payload.get("is_admin")}, expires_delta=access_token_expires)
    except JWTError:
        return None

def get_user_from_token(token: str, db: Session) -> Optional[User]:
    try:
        payload = verify_token(token)
        if payload is None:
            return None
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return db.query(User).filter(User.id == int(user_id)).first()
    except Exception:
        return None

def check_permission(user: User, required_permission: str) -> bool:
    return user.is_admin

def require_permission(permission: str):
    def permission_checker(current_user: User = Depends(get_current_user)):
        if not check_permission(current_user, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"权限不足，需要 {permission} 权限")
        return current_user
    return permission_checker

require_admin = get_current_admin_user
require_verified = get_current_verified_user
require_auth = get_current_user

async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security), db: Session = Depends(get_db)) -> Optional[User]:
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None

class TokenBlacklist:
    def __init__(self):
        self.blacklisted_tokens = set()
    def add_token(self, token: str):
        self.blacklisted_tokens.add(token)
    def is_blacklisted(self, token: str) -> bool:
        return token in self.blacklisted_tokens
    def remove_token(self, token: str):
        self.blacklisted_tokens.discard(token)

token_blacklist = TokenBlacklist()

def blacklist_token(token: str):
    token_blacklist.add_token(token)

def is_token_blacklisted(token: str) -> bool:
    return token_blacklist.is_blacklisted(token)

async def get_current_user_with_blacklist(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    token = credentials.credentials
    if is_token_blacklisted(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌已失效，请重新登录")
    return await get_current_user(credentials, db)

class UserSession:
    def __init__(self):
        self.active_sessions = {}
    def create_session(self, user_id: int, token: str, ip_address: str = None):
        self.active_sessions[user_id] = {
            "token": token,
            "ip_address": ip_address,
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow()
        }
    def update_activity(self, user_id: int):
        if user_id in self.active_sessions:
            self.active_sessions[user_id]["last_activity"] = datetime.utcnow()
    def remove_session(self, user_id: int):
        if user_id in self.active_sessions:
            del self.active_sessions[user_id]
    def get_session(self, user_id: int):
        return self.active_sessions.get(user_id)
    def cleanup_expired_sessions(self, max_idle_minutes: int = 30):
        now = datetime.utcnow()
        expired_users = [user_id for user_id, session_info in self.active_sessions.items() if (now - session_info["last_activity"]).total_seconds() > max_idle_minutes * 60]
        for user_id in expired_users:
            self.remove_session(user_id)

user_sessions = UserSession()

def create_user_session(user_id: int, token: str, ip_address: str = None):
    user_sessions.create_session(user_id, token, ip_address)

def update_user_activity(user_id: int):
    user_sessions.update_activity(user_id)

def remove_user_session(user_id: int):
    session_info = user_sessions.get_session(user_id)
    if session_info:
        blacklist_token(session_info["token"])
    user_sessions.remove_session(user_id)
