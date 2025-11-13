"""增强邮件模板服务"""
import logging
import urllib.parse

from app.core.domain_config import get_domain_config
from app.utils.timezone import format_beijing_time, get_beijing_time

logger = logging.getLogger(__name__)


class EmailTemplateEnhanced:
    """增强邮件模板类"""
    @staticmethod
    def _get_base_url(request=None, db=None) -> str:
        domain_config = get_domain_config()
        return domain_config.get_email_base_url(request, db)

    @staticmethod
    def _get_safe_base_url(data=None, request=None, db=None) -> str:
        base_url = data.get('base_url') if data else None
        if not base_url or 'localhost' in base_url or '127.0.0.1' in base_url:
            base_url = EmailTemplateEnhanced._get_base_url(request, db)
        return base_url

    @staticmethod
    def _format_time(time_value, default='未知'):
        if isinstance(time_value, str):
            return time_value if time_value not in ['未知', '从未登录'] else default
        return format_beijing_time(time_value) if time_value else default

    @staticmethod
    def _get_subscription_data(subscription_id, request=None, db=None):
        if not db:
            return None
        try:
            from app.services.email_api_client import EmailAPIClient
            api_client = EmailAPIClient(request, db)
            return api_client.get_complete_subscription_data(subscription_id)
        except Exception as e:
            logger.error(f"获取订阅数据失败: {e}", exc_info=True)
            return None

    @staticmethod
    def _get_user_data(user_id, request=None, db=None):
        if not db:
            return None
        try:
            from app.services.email_api_client import EmailAPIClient
            api_client = EmailAPIClient(request, db)
            return api_client.get_complete_user_data(user_id)
        except Exception as e:
            logger.error(f"获取用户数据失败: {e}", exc_info=True)
            return None

    @staticmethod
    def _get_order_data(order_id, request=None, db=None):
        if not db:
            return None
        try:
            from app.services.email_api_client import EmailAPIClient
            api_client = EmailAPIClient(request, db)
            return api_client.get_order_info(order_id)
        except Exception as e:
            logger.error(f"获取订单数据失败: {e}", exc_info=True)
            return None

    @staticmethod
    def _render_url_list(v2ray_url, clash_url, ssr_url=''):
        urls = []
        if v2ray_url or ssr_url:
            urls.append(f'''<div class="url-item">
                        <strong>🔗 通用配置地址（推荐）：</strong>
                        <p style="margin: 5px 0; color: #666; font-size: 12px;">适用于大部分客户端，包括手机和电脑</p>
                        <code class="url-code">{v2ray_url or ssr_url}</code>
                    </div>''')
        if clash_url:
            urls.append(f'''<div class="url-item">
                        <strong>⚡ 移动端专用地址：</strong>
                        <p style="margin: 5px 0; color: #666; font-size: 12px;">专为移动设备优化，支持规则分流</p>
                        <code class="url-code">{clash_url}</code>
                    </div>''')
        return '<div class="url-list">' + ''.join(urls) + '</div>' if urls else ''

    @staticmethod
    def _render_client_tags():
        clients = ['Clash', 'V2rayN', 'Shadowrocket', 'Quantumult X', 'Surge', 'Sparkle', 'Mihomo']
        return ''.join([f'<span style="background: #667eea; color: white; padding: 5px 10px; border-radius: 15px; font-size: 12px;">{c}</span>' for c in clients])

    @staticmethod
    def _render_qr_code(url):
        if not url:
            return ''
        qr_url = urllib.parse.quote(url, safe='')
        return f'''<div style="margin-top: 20px; text-align: center;">
                    <p><strong>📱 扫码快速配置</strong></p>
                    <p style="color: #666; font-size: 14px; margin-bottom: 10px;">使用相机扫描下方二维码即可快速添加配置</p>
                    <img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={qr_url}" style="border: 1px solid #ddd; border-radius: 8px; max-width: 200px;" alt="配置二维码">
                </div>'''

    @staticmethod
    def get_base_template(title: str, content: str, footer_text: str = '') -> str:
        from app.utils.timezone import get_beijing_time
        current_year = get_beijing_time().year
        site_name = "网络服务"
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{margin: 0; padding: 0; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; background-color: #f4f4f4; color: #333;}}
        .email-container {{max-width: 600px; margin: 0 auto; background-color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.1);}}
        .header {{background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 20px; text-align: center;}}
        .header h1 {{margin: 0; font-size: 28px; font-weight: 300;}}
        .header .subtitle {{margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;}}
        .content {{padding: 40px 30px;}}
        .content h2 {{color: #333; font-size: 24px; margin-bottom: 20px; font-weight: 400;}}
        .content p {{line-height: 1.6; margin-bottom: 16px; color: #555;}}
        .info-box {{background-color: #f8f9fa; border-left: 4px solid #667eea; padding: 20px; margin: 20px 0; border-radius: 4px;}}
        .info-table {{width: 100%; border-collapse: collapse; margin: 20px 0;}}
        .info-table th, .info-table td {{padding: 12px; text-align: left; border-bottom: 1px solid #e9ecef;}}
        .info-table th {{background-color: #f8f9fa; font-weight: 600; color: #495057; width: 30%;}}
        .btn {{display: inline-block; padding: 12px 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; border-radius: 25px; font-weight: 500; margin: 20px 0; transition: all 0.3s ease;}}
        .btn:hover {{transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);}}
        .warning-box {{background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px; padding: 15px; margin: 20px 0; color: #856404;}}
        .success-box {{background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 4px; padding: 15px; margin: 20px 0; color: #155724;}}
        .footer {{background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e9ecef;}}
        .footer p {{margin: 5px 0; color: #6c757d; font-size: 14px;}}
        .url-list {{margin: 15px 0;}}
        .url-item {{background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 6px; padding: 15px; margin: 10px 0; border-left: 4px solid #667eea;}}
        .url-item strong {{color: #333; font-size: 14px; display: block; margin-bottom: 8px;}}
        .url-code {{background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 4px; padding: 10px; margin: 5px 0; word-break: break-all; font-family: 'Courier New', monospace; font-size: 12px; color: #495057; display: block; line-height: 1.4;}}
        @media only screen and (max-width: 600px) {{
            .email-container {{width: 100% !important;}}
            .content {{padding: 20px !important;}}
            .header {{padding: 20px !important;}}
            .header h1 {{font-size: 24px !important;}}
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>{site_name}</h1>
            <p class="subtitle">{title}</p>
        </div>
        <div class="content">{content}</div>
        <div class="footer">
            <p><strong>{site_name}</strong></p>
            <p>{footer_text or '感谢您选择我们的服务'}</p>
            <p style="font-size: 12px; color: #999;">此邮件由系统自动发送，请勿直接回复</p>
            <p style="font-size: 12px; color: #999;">© {current_year} {site_name}. All rights reserved.</p>
        </div>
    </div>
</body>
</html>'''

    @staticmethod
    def get_subscription_template(subscription_id: int, request=None, db=None) -> str:
        subscription_data = EmailTemplateEnhanced._get_subscription_data(subscription_id, request, db)
        if not subscription_data:
            return "订阅信息不存在"
        title = "服务配置信息"
        username = subscription_data.get('username', '用户')
        v2ray_url = subscription_data.get('v2ray_url', '')
        clash_url = subscription_data.get('clash_url', '')
        user_email = subscription_data.get('email', '')
        user_id = subscription_data.get('user_id', '')
        is_verified = subscription_data.get('is_verified', False)
        created_at = EmailTemplateEnhanced._format_time(subscription_data.get('created_at'), '未知')
        last_login = EmailTemplateEnhanced._format_time(subscription_data.get('last_login'), '从未登录')
        remaining_days = subscription_data.get('remaining_days', 0)
        max_devices = subscription_data.get('max_devices', subscription_data.get('device_limit', 3))
        base_url = EmailTemplateEnhanced._get_safe_base_url(subscription_data, request, db)
        url_list = EmailTemplateEnhanced._render_url_list(v2ray_url, clash_url)
        qr_code = EmailTemplateEnhanced._render_qr_code(v2ray_url)
        client_tags = EmailTemplateEnhanced._render_client_tags()
        content = f'''<h2>您的服务配置信息</h2>
            <p>亲爱的 {username}，</p>
            <p>您的服务配置已生成完成，请查收以下信息：</p>
            <table class="info-table">
                <tr><th>用户账号</th><td>{username}</td></tr>
                <tr><th>用户ID</th><td>{user_id}</td></tr>
                <tr><th>用户邮箱</th><td>{user_email}</td></tr>
                <tr><th>邮箱验证状态</th><td style="color: {'#27ae60' if is_verified else '#e74c3c'};">{'已验证' if is_verified else '未验证'}</td></tr>
                <tr><th>注册时间</th><td>{created_at}</td></tr>
                <tr><th>最后登录</th><td>{last_login}</td></tr>
                <tr><th>客户剩余时长</th><td style="color: {'#e74c3c' if remaining_days <= 7 else '#27ae60'}; font-weight: bold;">{remaining_days} 天</td></tr>
                <tr><th>允许最大设备数</th><td style="color: #27ae60; font-weight: bold;">{max_devices} 台设备</td></tr>
            </table>
            <h3>📱 配置地址</h3>
            <div class="success-box">{url_list}{qr_code}</div>
            <h3>📖 使用说明</h3>
            <div class="info-box">
                <p><strong>客户端配置步骤：</strong></p>
                <ol>
                    <li><strong>复制配置地址</strong>：点击上方配置地址进行复制</li>
                    <li><strong>添加配置</strong>：在您的客户端中添加配置</li>
                    <li><strong>更新配置</strong>：点击更新获取最新配置</li>
                    <li><strong>开始使用</strong>：选择节点并连接即可</li>
                </ol>
            </div>
            <h3>🔧 支持的客户端</h3>
            <div style="display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0;">{client_tags}</div>
            <div class="warning-box">
                <p><strong>⚠️ 安全提醒：</strong></p>
                <ul>
                    <li>请妥善保管您的配置地址，切勿分享给他人</li>
                    <li>如发现地址泄露，请及时联系客服重置</li>
                    <li>建议定期更换配置地址以确保安全</li>
                    <li>服务到期前会收到续费提醒邮件</li>
                </ul>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{base_url}/" class="btn">查看我的服务</a>
            </div>
            <p style="text-align: center; color: #666; font-size: 14px;">如有任何问题，请随时联系我们的客服团队</p>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '享受高速稳定的网络服务')

    @staticmethod
    def get_verification_code_template(username: str, verification_code: str) -> str:
        title = "注册验证码"
        content = f'''<h2>📧 您的注册验证码</h2>
            <p>亲爱的用户 <strong>{username}</strong>，</p>
            <p>感谢您注册我们的服务！请使用以下验证码完成注册：</p>
            <div style="text-align: center; margin: 30px 0;">
                <div style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px 40px; border-radius: 8px; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);">
                    <div style="font-size: 32px; font-weight: bold; color: #ffffff; letter-spacing: 8px; font-family: 'Courier New', monospace;">{verification_code}</div>
                </div>
            </div>
            <div class="info-box">
                <p><strong>📋 使用说明：</strong></p>
                <ul>
                    <li>此验证码有效期为 <strong>10分钟</strong></li>
                    <li>请在注册页面输入此验证码完成注册</li>
                    <li>验证码仅限本次使用，使用后自动失效</li>
                    <li>如果验证码过期，请重新获取</li>
                </ul>
            </div>
            <div class="warning-box">
                <p><strong>⚠️ 安全提示：</strong></p>
                <p>请勿将验证码告知他人。如果这不是您本人的操作，请忽略此邮件。您的账户安全对我们非常重要。</p>
            </div>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '完成注册，开启您的专属网络体验')

    @staticmethod
    def get_password_reset_verification_code_template(username: str, verification_code: str) -> str:
        title = "密码重置验证码"
        content = f'''<h2>🔐 您的密码重置验证码</h2>
            <p>亲爱的用户 <strong>{username}</strong>，</p>
            <p>您正在重置账户密码，请使用以下验证码完成重置：</p>
            <div style="text-align: center; margin: 30px 0;">
                <div style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px 40px; border-radius: 8px; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);">
                    <div style="font-size: 32px; font-weight: bold; color: #ffffff; letter-spacing: 8px; font-family: 'Courier New', monospace;">{verification_code}</div>
                </div>
            </div>
            <div class="info-box">
                <p><strong>📋 使用说明：</strong></p>
                <ul>
                    <li>此验证码有效期为 <strong>10分钟</strong></li>
                    <li>请在密码重置页面输入此验证码和新密码完成重置</li>
                    <li>验证码仅限本次使用，使用后自动失效</li>
                    <li>如果验证码过期，请重新获取</li>
                </ul>
            </div>
            <div class="warning-box">
                <p><strong>⚠️ 安全提示：</strong></p>
                <p>请勿将验证码告知他人。如果这不是您本人的操作，请立即忽略此邮件并联系客服。您的账户安全对我们非常重要。</p>
            </div>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '安全重置您的账户密码')

    @staticmethod
    def get_order_confirmation_template(username: str, order_data: dict) -> str:
        title = "订单确认"
        base_url = EmailTemplateEnhanced._get_safe_base_url(order_data)
        pay_url = f"{base_url}/payment/order/{order_data.get('order_no', '')}"
        content = f'''<h2>✅ 订单确认</h2>
            <p>亲爱的用户 <strong>{username}</strong>，</p>
            <p>感谢您的购买！您的订单已成功创建，详情如下：</p>
            <div class="info-box">
                <h3>📋 订单详情</h3>
                <table class="info-table">
                    <tr><th>订单号</th><td><strong>{order_data.get('order_no', 'N/A')}</strong></td></tr>
                    <tr><th>套餐名称</th><td>{order_data.get('package_name', 'N/A')}</td></tr>
                    <tr><th>套餐时长</th><td>{order_data.get('package_duration', 'N/A')} 天</td></tr>
                    <tr><th>订单金额</th><td style="color: #e74c3c; font-weight: bold; font-size: 18px;">¥{order_data.get('amount', '0.00')}</td></tr>
                    <tr><th>支付方式</th><td>{order_data.get('payment_method', 'N/A')}</td></tr>
                    <tr><th>下单时间</th><td>{format_beijing_time(order_data.get('created_at')) or 'N/A'}</td></tr>
                    <tr><th>订单状态</th><td><span style="color: #ffc107; font-weight: bold;">待支付</span></td></tr>
                </table>
            </div>
            <div class="warning-box">
                <p><strong>⏰ 重要提醒：</strong></p>
                <ul>
                    <li>请尽快完成支付，订单将在24小时后自动取消</li>
                    <li>支付成功后，服务将自动激活，无需额外操作</li>
                    <li>支付完成后，您将收到包含订阅地址的确认邮件</li>
                    <li>如有任何疑问，请及时联系客服</li>
                </ul>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{pay_url}" class="btn">立即支付</a>
            </div>
            <p style="text-align: center; color: #666; font-size: 14px;">感谢您选择我们的服务！</p>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '开启您的专属网络体验')

    @staticmethod
    def get_account_deletion_template(username: str, deletion_data: dict) -> str:
        title = "账号删除确认"
        content = f'''<h2>账号删除确认</h2>
            <p>亲爱的用户 <strong>{username}</strong>，</p>
            <p>您的账号删除请求已收到，我们对此表示遗憾。</p>
            <div class="info-box">
                <table class="info-table">
                    <tr><th>删除原因</th><td>{deletion_data.get('reason', '用户主动删除')}</td></tr>
                    <tr><th>删除时间</th><td>{deletion_data.get('deletion_date', 'N/A')}</td></tr>
                    <tr><th>数据保留期</th><td>{deletion_data.get('data_retention_period', '30天')}</td></tr>
                </table>
            </div>
            <div class="warning-box">
                <p><strong>重要提醒：</strong></p>
                <ul>
                    <li>您的账号将在数据保留期结束后永久删除</li>
                    <li>删除后无法恢复，请谨慎操作</li>
                    <li>如有疑问，请在保留期内联系客服</li>
                </ul>
            </div>
            <p>感谢您曾经选择我们的服务！</p>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '开启您的专属网络体验')

    @staticmethod
    def get_renewal_confirmation_template(username: str, renewal_data: dict) -> str:
        title = "续费成功"
        base_url = renewal_data.get('base_url') or EmailTemplateEnhanced._get_base_url(None, None)
        content = f'''<h2>🎉 续费成功！</h2>
            <p>亲爱的用户 <strong>{username}</strong>，</p>
            <p>恭喜！您的服务续费已成功完成，服务时间已自动延长。</p>
            <div class="success-box">
                <h3>✅ 续费详情</h3>
                <table class="info-table">
                    <tr><th>套餐名称</th><td><strong>{renewal_data.get('package_name', 'N/A')}</strong></td></tr>
                    <tr><th>原到期时间</th><td style="color: #999; text-decoration: line-through;">{renewal_data.get('old_expiry_date', 'N/A')}</td></tr>
                    <tr><th>新到期时间</th><td style="color: #27ae60; font-weight: bold; font-size: 16px;">{renewal_data.get('new_expiry_date', 'N/A')}</td></tr>
                    <tr><th>续费金额</th><td style="color: #e74c3c; font-weight: bold;">¥{renewal_data.get('amount', '0.00')}</td></tr>
                    <tr><th>续费时间</th><td>{renewal_data.get('renewal_date', 'N/A')}</td></tr>
                </table>
            </div>
            <div class="info-box">
                <p><strong>📋 服务说明：</strong></p>
                <ul>
                    <li>✅ 您的服务已成功续费，可立即继续使用</li>
                    <li>✅ 订阅配置地址保持不变，无需重新配置</li>
                    <li>✅ 所有客户端配置将继续正常工作</li>
                    <li>💡 建议定期更新订阅配置以获取最新节点信息</li>
                </ul>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{base_url}/dashboard" class="btn">查看订阅详情</a>
            </div>
            <p style="text-align: center; color: #666; font-size: 14px;">感谢您的续费，祝您使用愉快！</p>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '开启您的专属网络体验')

    @staticmethod
    def get_password_reset_template(username: str, reset_link: str, request=None, db=None) -> str:
        title = "密码重置"
        base_url = EmailTemplateEnhanced._get_base_url(request, db)
        login_url = f"{base_url}/login"
        content = f'''<h2>您的密码重置请求</h2>
            <p>亲爱的 {username}，</p>
            <p>我们收到了您的密码重置请求。如果这不是您本人的操作，请忽略此邮件。</p>
            <div class="info-box">
                <h3>📋 重置信息</h3>
                <table class="info-table">
                    <tr><th>用户账号</th><td><strong>{username}</strong></td></tr>
                    <tr><th>重置链接有效期</th><td style="color: #ffc107; font-weight: bold;">1小时</td></tr>
                    <tr><th>链接使用次数</th><td>仅可使用一次</td></tr>
                </table>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_link}" class="btn">重置密码</a>
            </div>
            <div class="warning-box">
                <h3>⚠️ 安全提醒</h3>
                <ul>
                    <li>此重置链接仅在1小时内有效</li>
                    <li>链接仅可使用一次，使用后自动失效</li>
                    <li>如果链接失效，请重新申请密码重置</li>
                    <li>如果按钮无法点击，请复制以下链接到浏览器中打开：</li>
                </ul>
                <div style="margin-top: 15px; padding: 10px; background: #f8f9fa; border-radius: 4px; word-break: break-all;">
                    <code style="color: #667eea; font-size: 12px;">{reset_link}</code>
                </div>
            </div>
            <div class="info-box">
                <p><strong>💡 密码安全建议：</strong></p>
                <ul>
                    <li>建议设置强密码，包含字母、数字和特殊字符</li>
                    <li>密码长度建议在8-50个字符之间</li>
                    <li>不要使用过于简单的密码，如"123456"、"password"等</li>
                    <li>定期更换密码以确保账户安全</li>
                </ul>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{login_url}" class="btn">返回登录</a>
            </div>
            <p style="text-align: center; color: #666; font-size: 14px;">如果您没有请求重置密码，请忽略此邮件</p>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '保护您的账户安全')

    @staticmethod
    def get_password_reset_direct_template(username: str, reset_url: str, request=None, db=None) -> tuple:
        text_content = f"""您好 {username}，

我们收到了您的密码重置请求。

请点击以下链接重置您的密码：
{reset_url}

如果您没有请求重置密码，请忽略此邮件。

此链接将在1小时后失效。

祝好，
CBoard Modern 团队
"""
        html_content = EmailTemplateEnhanced.get_password_reset_template(username, reset_url, request, db)
        return text_content, html_content

    @staticmethod
    def get_password_changed_template(username: str, change_time: str, request=None, db=None) -> str:
        title = "密码修改成功"
        base_url = EmailTemplateEnhanced._get_base_url(request, db)
        login_url = f"{base_url}/login"
        content = f'''<h2>您的密码已修改</h2>
            <p>亲爱的 {username}，</p>
            <p>您的账户密码已成功修改。如果这不是您本人的操作，请立即联系客服。</p>
            <div class="info-box">
                <h3>📋 修改信息</h3>
                <table class="info-table">
                    <tr><th>用户账号</th><td><strong>{username}</strong></td></tr>
                    <tr><th>修改时间</th><td>{change_time}</td></tr>
                    <tr><th>修改状态</th><td style="color: #27ae60; font-weight: bold;">✅ 修改成功</td></tr>
                </table>
            </div>
            <div class="warning-box">
                <h3>⚠️ 安全提醒</h3>
                <ul>
                    <li>如果这不是您本人的操作，请立即登录账户修改密码</li>
                    <li>建议定期更换密码以确保账户安全</li>
                    <li>不要使用过于简单的密码，如"123456"、"password"等</li>
                    <li>如发现账户异常，请及时联系客服</li>
                </ul>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{login_url}" class="btn">立即登录</a>
            </div>
            <div class="info-box">
                <p><strong>💡 温馨提示：</strong></p>
                <ul>
                    <li>新密码已立即生效，请使用新密码登录</li>
                    <li>建议设置强密码，包含字母、数字和特殊字符</li>
                    <li>妥善保管您的账户信息，不要泄露给他人</li>
                </ul>
            </div>
            <p style="text-align: center; color: #666; font-size: 14px;">如有任何问题，请随时联系我们的客服团队</p>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '保护您的账户安全')

    @staticmethod
    def get_expiration_template(subscription_id: int, is_expired: bool = False, request=None, db=None) -> str:
        title = "订阅已到期" if is_expired else "订阅即将到期"
        subscription_data = EmailTemplateEnhanced._get_subscription_data(subscription_id, request, db)
        if not subscription_data:
            return "订阅信息不存在"
        base_url = EmailTemplateEnhanced._get_safe_base_url(subscription_data, request, db)
        username = subscription_data.get('username', '用户')
        expire_date = subscription_data.get('expire_time', '未知')
        package_name = subscription_data.get('package_name', '未知套餐')
        device_limit = subscription_data.get('device_limit', 3)
        current_devices = subscription_data.get('current_devices', 0)
        remaining_days = subscription_data.get('remaining_days', 0)
        if is_expired:
            content = f'''<h2>⚠️ 服务已到期</h2>
                <p>亲爱的用户 <strong>{username}</strong>，</p>
                <p>您的服务已于 <strong style="color: #e74c3c;">{expire_date}</strong> 到期。</p>
                <div class="warning-box">
                    <p><strong>服务已暂停：</strong></p>
                    <ul>
                        <li>您的配置地址已停止更新</li>
                        <li>无法获取最新的节点配置</li>
                        <li>请及时续费以恢复服务</li>
                    </ul>
                </div>'''
        else:
            content = f'''<h2>服务即将到期</h2>
                <p>亲爱的用户 <strong>{username}</strong>，</p>
                <p>您的服务将于 <strong style="color: #ffc107;">{expire_date}</strong> 到期。</p>
                <div class="warning-box">
                    <p><strong>温馨提醒：</strong></p>
                    <ul>
                        <li>为避免服务中断，请提前续费</li>
                        <li>到期后配置地址将停止更新</li>
                        <li>续费后服务将自动恢复</li>
                    </ul>
                </div>'''
        content += f'''<div class="info-box">
                <h3>📋 订阅详情</h3>
                <table class="info-table">
                    <tr><th>用户账号</th><td><strong>{username}</strong></td></tr>
                    <tr><th>套餐名称</th><td>{package_name}</td></tr>
                    <tr><th>到期时间</th><td style="color: #e74c3c; font-weight: bold; font-size: 16px;">{expire_date}</td></tr>
                    {f'<tr><th>剩余天数</th><td style="color: #ffc107; font-weight: bold;">{remaining_days} 天</td></tr>' if not is_expired and remaining_days > 0 else ''}
                    <tr><th>设备限制</th><td>{device_limit} 台设备</td></tr>
                    <tr><th>当前设备</th><td>{current_devices} / {device_limit}</td></tr>
                </table>
            </div>
            {f'''<div class="warning-box">
                <p><strong>⚠️ 服务状态：</strong></p>
                <ul>
                    <li>订阅地址已停止更新，无法获取最新节点</li>
                    <li>现有配置可能暂时可用，但建议尽快续费</li>
                    <li>续费后服务将立即恢复</li>
                </ul>
            </div>''' if is_expired else ''}
            <div style="text-align: center; margin: 30px 0;">
                <a href="{base_url}/dashboard" class="btn">{'立即续费' if is_expired else '查看订阅详情'}</a>
            </div>
            <div class="info-box">
                <p><strong>💡 续费说明：</strong></p>
                <ul>
                    <li>续费后，订阅地址将立即恢复更新</li>
                    <li>所有客户端配置无需修改，可直接使用</li>
                    <li>支持多种支付方式，支付成功后自动激活</li>
                </ul>
            </div>
            <p style="text-align: center; color: #666; font-size: 14px;">如有任何问题，请随时联系我们的客服团队</p>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '我们期待继续为您服务')

    @staticmethod
    def get_subscription_reset_template(subscription_id: int, reset_time: str, reset_reason: str, request=None, db=None) -> str:
        title = "订阅重置通知"
        subscription_data = EmailTemplateEnhanced._get_subscription_data(subscription_id, request, db)
        if not subscription_data:
            return "订阅信息不存在"
        base_url = EmailTemplateEnhanced._get_safe_base_url(subscription_data, request, db)
        username = subscription_data.get('username', '用户')
        v2ray_url = subscription_data.get('v2ray_url', '')
        clash_url = subscription_data.get('clash_url', '')
        ssr_url = subscription_data.get('ssr_url', '')
        expire_time = subscription_data.get('expire_time', '永久')
        url_list = EmailTemplateEnhanced._render_url_list(v2ray_url, clash_url, ssr_url)
        qr_code = EmailTemplateEnhanced._render_qr_code(v2ray_url or ssr_url)
        content = f'''<h2>🔄 您的订阅已重置</h2>
            <p>亲爱的 {username}，</p>
            <p>您的订阅地址已被重置，请使用新的订阅地址更新您的客户端配置。</p>
            <div class="info-box">
                <h3>📋 重置信息</h3>
                <table class="info-table">
                    <tr><th>重置时间</th><td><strong>{reset_time}</strong></td></tr>
                    <tr><th>重置原因</th><td>{reset_reason}</td></tr>
                    <tr><th>订阅状态</th><td style="color: #27ae60; font-weight: bold;">✅ 已激活</td></tr>
                    <tr><th>到期时间</th><td>{expire_time}</td></tr>
                </table>
            </div>
            <div class="success-box">
                <h3>🔗 新的订阅地址</h3>{url_list}{qr_code}
            </div>
            <div class="warning-box">
                <h3>⚠️ 重要提醒</h3>
                <ul style="line-height: 2;">
                    <li><strong>立即更新</strong>：请立即更新您的客户端配置，使用新的订阅地址</li>
                    <li><strong>旧地址失效</strong>：旧的订阅地址已失效，将无法使用</li>
                    <li><strong>妥善保管</strong>：请妥善保管新的订阅地址，不要分享给他人</li>
                    <li><strong>设备清理</strong>：所有设备记录已清空，需要重新连接</li>
                    <li><strong>如有疑问</strong>：如有任何疑问，请及时联系客服</li>
                </ul>
            </div>
            <div class="info-box">
                <h3>📖 更新步骤</h3>
                <ol style="line-height: 2;">
                    <li>复制上方新的订阅地址</li>
                    <li>在客户端中删除旧的订阅配置</li>
                    <li>添加新的订阅配置</li>
                    <li>更新并测试连接</li>
                </ol>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{base_url}/dashboard" class="btn">查看订阅详情</a>
            </div>
            <p style="text-align: center; color: #666; font-size: 14px;">如有任何问题，请随时联系我们的客服团队</p>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '请及时更新您的客户端配置')

    @staticmethod
    def get_payment_success_template(order_id: int, request=None, db=None) -> str:
        title = "支付成功通知"
        order_data = EmailTemplateEnhanced._get_order_data(order_id, request, db)
        if not order_data:
            return "订单信息不存在"
        base_url = EmailTemplateEnhanced._get_safe_base_url(order_data, request, db)
        username = order_data.get('username', '用户')
        amount = order_data.get('amount', 0.0)
        package_name = order_data.get('package_name', '未知套餐')
        order_no = order_data.get('order_no', '')
        payment_method = order_data.get('payment_method_name', '未知')
        from app.utils.timezone import get_beijing_time_str
        payment_time = get_beijing_time_str('%Y-%m-%d %H:%M:%S')
        subscription_url = order_data.get('subscription_url', '')
        v2ray_url = f"{base_url}/api/v1/subscriptions/ssr/{subscription_url}" if subscription_url else ""
        clash_url = f"{base_url}/api/v1/subscriptions/clash/{subscription_url}" if subscription_url else ""
        url_list = EmailTemplateEnhanced._render_url_list(v2ray_url, clash_url) if subscription_url else ''
        content = f'''<h2>🎉 支付成功！</h2>
            <p>亲爱的 {username}，</p>
            <p>您的支付已成功处理，感谢您的购买！</p>
            <div class="success-box">
                <h3>✅ 支付确认</h3>
                <table class="info-table">
                    <tr><th>订单号</th><td><strong>{order_no or order_id}</strong></td></tr>
                    <tr><th>套餐名称</th><td><strong>{package_name}</strong></td></tr>
                    <tr><th>支付金额</th><td style="color: #27ae60; font-weight: bold; font-size: 18px;">¥{amount}</td></tr>
                    <tr><th>支付方式</th><td>{payment_method}</td></tr>
                    <tr><th>支付时间</th><td>{payment_time}</td></tr>
                    <tr><th>订单状态</th><td style="color: #27ae60; font-weight: bold;">✅ 已支付</td></tr>
                </table>
            </div>
            <div class="info-box">
                <p><strong>✨ 服务已激活：</strong></p>
                <ul>
                    <li>✅ 您的订阅已自动激活</li>
                    <li>✅ 配置地址已生成并可用</li>
                    <li>✅ 可以立即开始使用服务</li>
                    <li>💡 您可以查看订阅详情获取配置地址</li>
                </ul>
            </div>
            {f'<div class="success-box"><h3>🔗 您的订阅地址</h3>{url_list}</div>' if subscription_url else ''}
            <div style="text-align: center; margin: 30px 0;">
                <a href="{base_url}/dashboard" class="btn">查看订阅详情</a>
            </div>
            <div class="info-box">
                <p><strong>📖 接下来：</strong></p>
                <ol style="line-height: 2;">
                    <li>访问订阅详情页面获取完整配置信息</li>
                    <li>复制配置地址到您的客户端</li>
                    <li>开始享受高速稳定的网络服务</li>
                </ol>
            </div>
            <p style="text-align: center; color: #666; font-size: 14px;">如有任何问题，请随时联系我们的客服团队</p>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '感谢您的信任')

    @staticmethod
    def get_broadcast_notification_template(title: str, content: str, request=None, db=None) -> str:
        return EmailTemplateEnhanced.get_base_template(
            title=title,
            content=f'''<div class="content">
                <h2>{title}</h2>
                <div style="line-height: 1.8; color: #555;">{content.replace(chr(10), '<br>')}</div>
            </div>''',
            footer_text="此邮件由系统自动发送，请勿回复。"
        )

    @staticmethod
    def get_announcement_email_template(title: str, content: str, request=None, db=None) -> str:
        return EmailTemplateEnhanced.get_broadcast_notification_template(title, content, request, db)

    @staticmethod
    def get_announcement_template(title: str, content: str, request=None, db=None) -> str:
        base_url = EmailTemplateEnhanced._get_base_url(request, db)
        site_name = "网络服务"
        email_content = f'''<h2>{title}</h2>
            <div class="info-box">
                <div style="line-height: 1.8;">{content}</div>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{base_url}/dashboard" class="btn">查看详情</a>
            </div>
            <p style="text-align: center; color: #666; font-size: 14px;">此邮件来自 {site_name}</p>'''
        return EmailTemplateEnhanced.get_base_template(title, email_content, '感谢您的关注')

    @staticmethod
    def get_welcome_template(user_id: int, password: str = None, request=None, db=None) -> str:
        title = "欢迎加入我们！"
        user_data = EmailTemplateEnhanced._get_user_data(user_id, request, db)
        if not user_data:
            return "用户信息不存在"
        base_url = EmailTemplateEnhanced._get_safe_base_url(user_data, request, db)
        username = user_data.get('username', '用户')
        email = user_data.get('email', '')
        created_at = EmailTemplateEnhanced._format_time(user_data.get('created_at'), '未知')
        is_verified = user_data.get('is_verified', False)
        login_url = f"{base_url}/login"
        packages_url = f"{base_url}/packages"
        subscription_url = user_data.get('subscription_url', '')
        v2ray_url = user_data.get('v2ray_url', '')
        clash_url = user_data.get('clash_url', '')
        ssr_url = user_data.get('ssr_url', '')
        device_limit = user_data.get('device_limit', 0)
        current_devices = user_data.get('current_devices', 0)
        expire_time = user_data.get('expire_time', '')
        remaining_days = user_data.get('remaining_days', 0)
        package_name = user_data.get('package_name', '')
        is_active = user_data.get('is_active', False)
        has_active_subscription = subscription_url and is_active and (not expire_time or remaining_days > 0)
        if expire_time and expire_time not in ['永久', '未知']:
            try:
                expire_time_formatted = format_beijing_time(expire_time) if isinstance(expire_time, str) else format_beijing_time(expire_time)
            except:
                expire_time_formatted = str(expire_time) if expire_time else '永久'
        else:
            expire_time_formatted = '永久' if not expire_time or expire_time == '永久' else '未设置'
        url_list = EmailTemplateEnhanced._render_url_list(v2ray_url, clash_url, ssr_url) if has_active_subscription else ''
        content = f'''<h2>您的账户注册成功</h2>
            <p>亲爱的 {username}，</p>
            <p>欢迎加入我们的网络服务平台！您的账户已成功创建，现在可以开始使用我们的服务了。</p>
            <div class="info-box">
                <h3>📋 账户信息</h3>
                <table class="info-table">
                    <tr><th>用户账号</th><td><strong>{username}</strong></td></tr>
                    <tr><th>注册邮箱</th><td>{email}</td></tr>
                    {f'<tr><th>登录密码</th><td style="color: #667eea; font-weight: bold; font-size: 16px;">{password}</td></tr>' if password else ''}
                    <tr><th>邮箱验证状态</th><td style="color: {'#27ae60' if is_verified else '#e74c3c'};">{'已验证' if is_verified else '未验证'}</td></tr>
                    <tr><th>注册时间</th><td>{created_at}</td></tr>
                </table>
            </div>
            <div class="success-box">
                <h3>🔗 登录信息</h3>
                <table class="info-table">
                    <tr><th>登录地址</th><td><a href="{login_url}" style="color: #667eea; text-decoration: none;">{login_url}</a></td></tr>
                    <tr><th>用户账号</th><td><strong>{username}</strong></td></tr>
                    {f'<tr><th>登录密码</th><td style="color: #667eea; font-weight: bold; font-size: 16px;">{password}</td></tr>' if password else ''}
                </table>
            </div>
            {f'''<div class="success-box">
                <h3>📡 订阅信息</h3>
                <table class="info-table">
                    {f'<tr><th>套餐名称</th><td><strong>{package_name}</strong></td></tr>' if package_name else ''}
                    <tr><th>到期时间</th><td style="color: {'#e74c3c' if remaining_days <= 7 and remaining_days > 0 else '#27ae60'}; font-weight: bold;">{expire_time_formatted}</td></tr>
                    {f'<tr><th>剩余时长</th><td style="color: {'#e74c3c' if remaining_days <= 7 else '#27ae60'}; font-weight: bold;">{remaining_days} 天</td></tr>' if remaining_days > 0 else ''}
                    <tr><th>允许最大设备数</th><td style="color: #27ae60; font-weight: bold;">{device_limit} 台设备</td></tr>
                    <tr><th>当前使用设备</th><td>{current_devices} / {device_limit}</td></tr>
                </table>
            </div>
            <div class="success-box">
                <h3>🔗 配置地址</h3>{url_list}
            </div>''' if has_active_subscription else f'''<div class="warning-box" style="background-color: #fff3cd; border-left-color: #ffc107;">
                <h3>💡 温馨提示</h3>
                <p><strong>您还没有购买服务套餐，请先购买套餐后才能使用服务。</strong></p>
                <p>购买套餐后，您将获得：</p>
                <ul>
                    <li>专属订阅配置地址</li>
                    <li>高速稳定的网络服务</li>
                    <li>多设备同时使用</li>
                    <li>24小时客服支持</li>
                </ul>
                <div style="text-align: center; margin: 20px 0;">
                    <a href="{packages_url}" class="btn" style="background-color: #ffc107; color: #000;">立即购买套餐</a>
                </div>
            </div>'''}
            <div class="warning-box">
                <h3>⚠️ 重要提示</h3>
                <ul>
                    <li>请妥善保管您的登录密码，建议您登录后及时修改密码</li>
                    <li>为了账户安全，建议设置强密码，包含字母、数字和特殊字符</li>
                    <li>不要将密码泄露给他人，避免账户被盗用</li>
                    {f'<li>您的邮箱尚未验证，请尽快验证邮箱以确保账户安全</li>' if not is_verified else ''}
                    {f'<li>请妥善保管您的配置地址，切勿分享给他人</li><li>如发现地址泄露，请及时联系客服重置</li>' if has_active_subscription else ''}
                </ul>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{login_url}" class="btn">立即登录</a>
                {f'<a href="{packages_url}" class="btn" style="margin-left: 10px; background-color: #27ae60;">购买套餐</a>' if not has_active_subscription else ''}
            </div>
            <div class="info-box">
                <p><strong>🚀 开始使用流程：</strong></p>
                <ol style="line-height: 2;">
                    <li><strong>登录系统</strong>：使用上方提供的账号和密码登录</li>
                    {f'<li><strong>配置客户端</strong>：将配置地址导入到您的客户端</li><li><strong>享受服务</strong>：连接节点，开始使用高速稳定的网络服务</li>' if has_active_subscription else '<li><strong>选择套餐</strong>：浏览并选择适合您的服务套餐</li><li><strong>完成支付</strong>：支付成功后获取您的订阅配置地址</li><li><strong>配置客户端</strong>：将配置地址导入到您的客户端</li><li><strong>享受服务</strong>：连接节点，开始使用高速稳定的网络服务</li>'}
                </ol>
            </div>
            <p style="text-align: center; color: #666; font-size: 14px;">如有任何问题，请随时联系我们的客服团队</p>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '期待为您提供优质服务')

    @staticmethod
    def get_subscription_created_template(subscription_id: int, request=None, db=None) -> str:
        title = "订阅创建成功"
        subscription_data = EmailTemplateEnhanced._get_subscription_data(subscription_id, request, db)
        if not subscription_data:
            return "订阅信息不存在"
        base_url = EmailTemplateEnhanced._get_safe_base_url(subscription_data, request, db)
        username = subscription_data.get('username', '用户')
        v2ray_url = subscription_data.get('v2ray_url', '')
        clash_url = subscription_data.get('clash_url', '')
        ssr_url = subscription_data.get('ssr_url', '')
        expire_time = subscription_data.get('expire_time', '永久')
        package_name = subscription_data.get('package_name', '未知套餐')
        device_limit = subscription_data.get('device_limit', 3)
        current_devices = subscription_data.get('current_devices', 0)
        remaining_days = subscription_data.get('remaining_days', 0)
        url_list = EmailTemplateEnhanced._render_url_list(v2ray_url, clash_url, ssr_url)
        qr_code = EmailTemplateEnhanced._render_qr_code(v2ray_url or ssr_url)
        client_tags = EmailTemplateEnhanced._render_client_tags()
        content = f'''<h2>🎉 订阅创建成功！</h2>
            <p>亲爱的 {username}，</p>
            <p>您的订阅已成功创建，现在可以开始使用我们的服务了！</p>
            <div class="info-box">
                <h3>📋 订阅信息</h3>
                <table class="info-table">
                    <tr><th>套餐名称</th><td><strong>{package_name}</strong></td></tr>
                    <tr><th>到期时间</th><td style="color: {'#e74c3c' if remaining_days <= 7 else '#27ae60'}; font-weight: bold;">{expire_time}</td></tr>
                    <tr><th>剩余时长</th><td style="color: {'#e74c3c' if remaining_days <= 7 else '#27ae60'}; font-weight: bold;">{remaining_days} 天</td></tr>
                    <tr><th>设备限制</th><td style="color: #27ae60; font-weight: bold;">{device_limit} 台设备</td></tr>
                    <tr><th>当前设备</th><td>{current_devices} / {device_limit}</td></tr>
                </table>
            </div>
            <div class="success-box">
                <h3>🔗 配置地址</h3>{url_list}{qr_code}
            </div>
            <div class="info-box">
                <h3>📱 使用说明</h3>
                <ol style="line-height: 2;">
                    <li><strong>复制配置地址</strong>：点击上方配置地址进行复制</li>
                    <li><strong>添加配置</strong>：在您的客户端中添加订阅配置</li>
                    <li><strong>更新配置</strong>：定期更新获取最新节点信息</li>
                    <li><strong>开始使用</strong>：选择节点并连接即可享受服务</li>
                </ol>
            </div>
            <h3>🔧 支持的客户端</h3>
            <div style="display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0;">{client_tags}</div>
            <div class="warning-box">
                <p><strong>⚠️ 安全提醒：</strong></p>
                <ul>
                    <li>请妥善保管您的配置地址，切勿分享给他人</li>
                    <li>如发现地址泄露，请及时联系客服重置</li>
                    <li>建议定期更换配置地址以确保安全</li>
                    <li>服务到期前会收到续费提醒邮件</li>
                </ul>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{base_url}/dashboard" class="btn">查看订阅详情</a>
            </div>
            <p style="text-align: center; color: #666; font-size: 14px;">如有任何问题，请随时联系我们的客服团队</p>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '祝您使用愉快')

    @staticmethod
    def get_account_deletion_warning_template(username: str, email: str, last_login, request=None, db=None) -> str:
        title = "账号删除提醒"
        base_url = EmailTemplateEnhanced._get_base_url(request, db)
        login_url = f"{base_url}/login"
        last_login_str = format_beijing_time(last_login) if last_login else '从未登录'
        content = f'''<h2>⚠️ 账号删除提醒</h2>
            <p>亲爱的 {username}，</p>
            <p>我们注意到您的账号已经<strong>30天未登录</strong>，且<strong>没有有效的付费套餐</strong>。</p>
            <div class="warning-box">
                <h3>📋 账号状态</h3>
                <table class="info-table">
                    <tr><th>用户账号</th><td><strong>{username}</strong></td></tr>
                    <tr><th>注册邮箱</th><td>{email}</td></tr>
                    <tr><th>最后登录</th><td>{last_login_str}</td></tr>
                    <tr><th>订阅状态</th><td style="color: #e74c3c; font-weight: bold;">无有效套餐</td></tr>
                </table>
            </div>
            <div class="warning-box">
                <h3>⚠️ 重要通知</h3>
                <p>根据我们的账号管理政策，您的账号将在<strong style="color: #e74c3c;">7天后</strong>被自动删除。</p>
                <p>如果您希望保留账号，请：</p>
                <ol style="line-height: 2;">
                    <li>立即登录账号（<a href="{login_url}">点击登录</a>）</li>
                    <li>购买并激活有效的服务套餐</li>
                    <li>账号将自动保留</li>
                </ol>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{login_url}" class="btn">立即登录</a>
            </div>
            <div class="info-box">
                <p><strong>💡 温馨提示：</strong></p>
                <ul>
                    <li>账号删除后，所有数据将无法恢复</li>
                    <li>包括订阅记录、订单记录、设备记录等</li>
                    <li>如有任何疑问，请及时联系客服</li>
                </ul>
            </div>
            <p style="text-align: center; color: #666; font-size: 14px;">如有任何问题，请随时联系我们的客服团队</p>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '请及时登录以保留您的账号')

    @staticmethod
    def get_subscription_template_fallback(username: str, subscription_data: dict, request=None, db=None) -> str:
        title = "服务配置信息"
        base_url = EmailTemplateEnhanced._get_base_url(request, db)
        v2ray_url = subscription_data.get('v2ray_url', subscription_data.get('subscription_url', ''))
        clash_url = subscription_data.get('clash_url', '')
        device_limit = subscription_data.get('device_limit', 3)
        expire_time = subscription_data.get('expire_time', '永久')
        url_list = EmailTemplateEnhanced._render_url_list(v2ray_url, clash_url) if (v2ray_url or clash_url) else f'''<div class="url-item"><strong>订阅标识：</strong><code class="url-code">{subscription_data.get("subscription_url", "")}</code></div>'''
        content = f'''<h2>您的服务配置信息</h2>
            <p>亲爱的 {username}，</p>
            <p>您的服务配置已生成完成，请查收以下信息：</p>
            <div class="info-box">
                <h3>📋 账户信息</h3>
                <table class="info-table">
                    <tr><th>用户账号</th><td><strong>{username}</strong></td></tr>
                    <tr><th>设备限制</th><td>{device_limit} 台设备</td></tr>
                    <tr><th>服务期限</th><td>{expire_time}</td></tr>
                </table>
            </div>
            <div class="success-box">
                <h3>🔗 配置地址</h3>
                <div class="url-list">{url_list}</div>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{base_url}/dashboard" class="btn">查看订阅详情</a>
            </div>
            <p style="text-align: center; color: #666; font-size: 14px;">如有任何问题，请随时联系我们的客服团队</p>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '感谢您选择我们的服务')

    @staticmethod
    def get_subscription_reset_template_fallback(username: str, new_subscription_url: str, reset_time: str, reset_reason: str, request=None, db=None) -> str:
        title = "订阅重置通知"
        base_url = EmailTemplateEnhanced._get_base_url(request, db)
        content = f'''<h2>🔄 您的订阅已重置</h2>
            <p>亲爱的 {username}，</p>
            <p>您的订阅地址已被重置，请使用新的订阅地址更新您的客户端配置。</p>
            <div class="info-box">
                <h3>📋 重置信息</h3>
                <table class="info-table">
                    <tr><th>重置时间</th><td><strong>{reset_time}</strong></td></tr>
                    <tr><th>重置原因</th><td>{reset_reason}</td></tr>
                    <tr><th>订阅状态</th><td style="color: #27ae60; font-weight: bold;">✅ 已激活</td></tr>
                </table>
            </div>
            <div class="success-box">
                <h3>🔗 新的订阅地址</h3>
                <div class="url-list">
                    <div class="url-item">
                        <strong>🔗 订阅标识：</strong>
                        <code class="url-code">{new_subscription_url}</code>
                    </div>
                </div>
            </div>
            <div class="warning-box">
                <h3>⚠️ 重要提醒</h3>
                <ul style="line-height: 2;">
                    <li><strong>立即更新</strong>：请立即更新您的客户端配置，使用新的订阅地址</li>
                    <li><strong>旧地址失效</strong>：旧的订阅地址已失效，将无法使用</li>
                    <li><strong>妥善保管</strong>：请妥善保管新的订阅地址，不要分享给他人</li>
                    <li><strong>设备清理</strong>：所有设备记录已清空，需要重新连接</li>
                    <li><strong>如有疑问</strong>：如有任何疑问，请及时联系客服</li>
                </ul>
            </div>
            <div class="info-box">
                <h3>📖 更新步骤</h3>
                <ol style="line-height: 2;">
                    <li>复制上方新的订阅地址</li>
                    <li>在客户端中删除旧的订阅配置</li>
                    <li>添加新的订阅配置</li>
                    <li>更新并测试连接</li>
                </ol>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{base_url}/dashboard" class="btn">查看订阅详情</a>
            </div>
            <p style="text-align: center; color: #666; font-size: 14px;">如有任何问题，请随时联系我们的客服团队</p>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '请及时更新您的客户端配置')

    @staticmethod
    def get_payment_success_template_fallback(username: str, payment_data: dict, request=None, db=None) -> str:
        from app.utils.timezone import get_beijing_time_str
        title = "支付成功通知"
        base_url = EmailTemplateEnhanced._get_base_url(request, db)
        order_no = payment_data.get('order_no', 'N/A')
        package_name = payment_data.get('package_name', '未知套餐')
        amount = payment_data.get('amount', '0.00')
        payment_method = payment_data.get('payment_method', '未知')
        payment_time = format_beijing_time(payment_data.get('paid_at')) if payment_data.get('paid_at') else get_beijing_time_str('%Y-%m-%d %H:%M:%S')
        transaction_id = payment_data.get('transaction_id', '')
        content = f'''<h2>🎉 支付成功！</h2>
            <p>亲爱的 {username}，</p>
            <p>您的支付已成功处理，感谢您的购买！</p>
            <div class="success-box">
                <h3>✅ 支付确认</h3>
                <table class="info-table">
                    <tr><th>订单号</th><td><strong>{order_no}</strong></td></tr>
                    <tr><th>套餐名称</th><td><strong>{package_name}</strong></td></tr>
                    <tr><th>支付金额</th><td style="color: #27ae60; font-weight: bold; font-size: 18px;">¥{amount}</td></tr>
                    <tr><th>支付方式</th><td>{payment_method}</td></tr>
                    <tr><th>支付时间</th><td>{payment_time}</td></tr>
                    {f'<tr><th>交易ID</th><td>{transaction_id}</td></tr>' if transaction_id else ''}
                    <tr><th>订单状态</th><td style="color: #27ae60; font-weight: bold;">✅ 已支付</td></tr>
                </table>
            </div>
            <div class="info-box">
                <p><strong>✨ 服务已激活：</strong></p>
                <ul>
                    <li>✅ 您的订阅已自动激活</li>
                    <li>✅ 配置地址已生成并可用</li>
                    <li>✅ 可以立即开始使用服务</li>
                    <li>💡 您可以查看订阅详情获取配置地址</li>
                </ul>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{base_url}/dashboard" class="btn">查看订阅详情</a>
            </div>
            <div class="info-box">
                <p><strong>📖 接下来：</strong></p>
                <ol style="line-height: 2;">
                    <li>访问订阅详情页面获取完整配置信息</li>
                    <li>复制配置地址到您的客户端</li>
                    <li>开始享受高速稳定的网络服务</li>
                </ol>
            </div>
            <p style="text-align: center; color: #666; font-size: 14px;">如有任何问题，请随时联系我们的客服团队</p>'''
        return EmailTemplateEnhanced.get_base_template(title, content, '感谢您的信任')
