"""维护模式中间件"""
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from sqlalchemy import text

logger = logging.getLogger(__name__)


async def maintenance_middleware(request: Request, call_next):
    """
    维护模式中间件
    检查系统是否处于维护模式，如果是，则返回维护页面
    """
    # 排除管理员接口和维护状态检查接口
    path = request.url.path
    
    # 允许访问的路径
    allowed_paths = [
        "/api/v1/admin/system-config",  # 管理员可以查看配置
        "/api/v1/settings/public-settings",  # 公开设置（包含维护状态）
        "/api/v1/auth/login",  # 登录接口（管理员需要登录）
        "/api/v1/auth/register",  # 注册接口
        "/api/v1/auth/send-verification-code",  # 发送验证码接口
        "/api/v1/admin",  # 所有管理员接口
        "/docs",  # API文档
        "/redoc",  # API文档
        "/openapi.json",  # OpenAPI规范
        "/static",  # 静态文件
        "/uploads",  # 上传文件
    ]
    
    # 检查是否是允许的路径
    is_allowed = any(path.startswith(allowed) for allowed in allowed_paths)
    
    if not is_allowed:
        # 检查维护模式
        db = None
        try:
            # 从数据库获取维护模式状态
            db = SessionLocal()
            query = text("SELECT value FROM system_configs WHERE key = 'maintenance_mode' AND type = 'system'")
            result = db.execute(query).first()
            
            if result and result.value.lower() == 'true':
                # 获取维护信息
                message_query = text("SELECT value FROM system_configs WHERE key = 'maintenance_message' AND type = 'system'")
                message_result = db.execute(message_query).first()
                maintenance_message = message_result.value if message_result else "系统维护中，请稍后再试"
                
                # 获取网站名称和Logo
                site_name_query = text("SELECT value FROM system_configs WHERE key = 'site_name' AND type = 'system'")
                site_name_result = db.execute(site_name_query).first()
                site_name = site_name_result.value if site_name_result else "CBoard Modern"
                
                logo_query = text("SELECT value FROM system_configs WHERE key = 'logo_url' AND type = 'system'")
                logo_result = db.execute(logo_query).first()
                logo_url = logo_result.value if logo_result else ""
                
                # 如果是API请求，返回JSON
                if path.startswith("/api/"):
                    return JSONResponse(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        content={
                            "success": False,
                            "message": maintenance_message,
                            "maintenance_mode": True,
                            "site_name": site_name,
                            "logo_url": logo_url
                        }
                    )
                else:
                    # 返回HTML维护页面
                    html_content = f"""
                    <!DOCTYPE html>
                    <html lang="zh-CN">
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>{site_name} - 系统维护中</title>
                        <style>
                            * {{
                                margin: 0;
                                padding: 0;
                                box-sizing: border-box;
                            }}
                            body {{
                                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
                                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                min-height: 100vh;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                padding: 20px;
                            }}
                            .maintenance-container {{
                                background: #ffffff;
                                border-radius: 16px;
                                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                                padding: 60px 40px;
                                max-width: 600px;
                                width: 100%;
                                text-align: center;
                                animation: fadeIn 0.5s ease-in;
                            }}
                            @keyframes fadeIn {{
                                from {{
                                    opacity: 0;
                                    transform: translateY(-20px);
                                }}
                                to {{
                                    opacity: 1;
                                    transform: translateY(0);
                                }}
                            }}
                            .logo {{
                                width: 120px;
                                height: 120px;
                                margin: 0 auto 30px;
                                border-radius: 50%;
                                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                font-size: 48px;
                                color: #ffffff;
                                box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
                            }}
                            .logo img {{
                                width: 100%;
                                height: 100%;
                                object-fit: cover;
                                border-radius: 50%;
                            }}
                            h1 {{
                                font-size: 32px;
                                color: #303133;
                                margin-bottom: 20px;
                                font-weight: 600;
                            }}
                            .message {{
                                font-size: 18px;
                                color: #606266;
                                line-height: 1.8;
                                margin-bottom: 40px;
                                white-space: pre-wrap;
                            }}
                            .icon {{
                                font-size: 80px;
                                color: #e6a23c;
                                margin-bottom: 30px;
                                animation: pulse 2s ease-in-out infinite;
                            }}
                            @keyframes pulse {{
                                0%, 100% {{
                                    transform: scale(1);
                                }}
                                50% {{
                                    transform: scale(1.1);
                                }}
                            }}
                            .footer {{
                                margin-top: 40px;
                                padding-top: 30px;
                                border-top: 1px solid #e4e7ed;
                                color: #909399;
                                font-size: 14px;
                            }}
                            @media (max-width: 768px) {{
                                .maintenance-container {{
                                    padding: 40px 20px;
                                }}
                                h1 {{
                                    font-size: 24px;
                                }}
                                .message {{
                                    font-size: 16px;
                                }}
                                .icon {{
                                    font-size: 60px;
                                }}
                            }}
                        </style>
                    </head>
                    <body>
                        <div class="maintenance-container">
                            <div class="logo">
                                {"<img src='" + logo_url + "' alt='Logo' />" if logo_url else "🔧"}
                            </div>
                            <div class="icon">⚠️</div>
                            <h1>系统维护中</h1>
                            <div class="message">{maintenance_message}</div>
                            <div class="footer">
                                <p>{site_name}</p>
                                <p style="margin-top: 10px;">我们正在努力为您提供更好的服务</p>
                            </div>
                        </div>
                    </body>
                    </html>
                    """
                    return HTMLResponse(content=html_content, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            # 如果检查维护模式失败，继续处理请求
            logger.error(f"检查维护模式失败: {e}", exc_info=True)
            pass
        finally:
            if db:
                db.close()
    
    # 继续处理请求
    response = await call_next(request)
    return response

