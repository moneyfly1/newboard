#!/usr/bin/env python3

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.user import User
from app.utils.security import get_password_hash
from datetime import datetime

def create_admin(username="admin", email="admin@example.com", password="admin123"):
    db = SessionLocal()
    
    try:
        existing_admin = db.query(User).filter(User.is_admin == True).first()
        if existing_admin:
            print(f"❌ 管理员已存在: {existing_admin.username} ({existing_admin.email})")
            return False
        
        if db.query(User).filter(User.username == username).first():
            print(f"❌ 用户名 '{username}' 已存在")
            return False
        
        if db.query(User).filter(User.email == email).first():
            print(f"❌ 邮箱 '{email}' 已存在")
            return False
        
        admin = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            is_active=True,
            is_verified=True,
            is_admin=True,
            created_at=datetime.now()
        )
        
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        print("✅ 管理员账户创建成功！")
        print(f"   用户名: {username}")
        print(f"   邮箱: {email}")
        print(f"   密码: {password}")
        print("\n⚠️  请立即登录并修改密码！")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ 创建管理员失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        username, email, password = sys.argv[1], sys.argv[2], sys.argv[3]
    elif len(sys.argv) >= 3:
        username, email, password = sys.argv[1], sys.argv[2], "admin123"
        print("⚠️  使用默认密码")
    elif len(sys.argv) >= 2:
        username, email, password = sys.argv[1], f"{sys.argv[1]}@example.com", "admin123"
        print("⚠️  使用默认邮箱和密码")
    else:
        username, email, password = "admin", "admin@example.com", "admin123"
        print("⚠️  使用默认配置")
    
    create_admin(username, email, password)

