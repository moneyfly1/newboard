#!/usr/bin/env python3

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.user import User
from app.utils.security import get_password_hash

def reset_admin_password(username="admin", new_password="admin123"):
    db = SessionLocal()
    
    try:
        admin = db.query(User).filter(
            User.username == username,
            User.is_admin == True
        ).first()
        
        if not admin:
            print(f"❌ 未找到管理员账户: {username}")
            print("\n💡 使用以下命令创建管理员:")
            print("   python3 create_admin.py admin admin@example.com your_password")
            return False
        
        admin.hashed_password = get_password_hash(new_password)
        admin.is_active = True
        admin.is_verified = True
        
        db.commit()
        db.refresh(admin)
        
        print("✅ 密码重置成功！")
        print(f"   用户名: {username}")
        print(f"   新密码: {new_password}")
        print("\n⚠️  请立即使用新密码登录！")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ 重置密码失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        username, new_password = sys.argv[1], sys.argv[2]
    elif len(sys.argv) >= 2:
        username, new_password = sys.argv[1], "admin123"
        print("⚠️  使用默认新密码")
    else:
        username, new_password = "admin", "admin123"
        print("⚠️  使用默认配置")
    
    reset_admin_password(username, new_password)

