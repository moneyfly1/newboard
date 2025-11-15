#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_PATH="$SCRIPT_DIR"
BACKEND_PORT=8000

show_menu() {
    clear
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║         CBoard 管理工具 v2.0              ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}【安装与配置】${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}1.${NC} 安装系统"
    echo -e "${GREEN}2.${NC} 配置域名和Nginx"
    echo -e "${GREEN}3.${NC} 修复常见错误"
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}【服务管理】${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}4.${NC} 启动服务"
    echo -e "${GREEN}5.${NC} 停止服务"
    echo -e "${GREEN}6.${NC} 重启服务"
    echo -e "${GREEN}7.${NC} 查看服务状态"
    echo -e "${GREEN}8.${NC} 查看服务日志"
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}【管理员管理】${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}9.${NC} 重设管理员密码"
    echo -e "${GREEN}10.${NC} 查看管理员账号"
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}0.${NC} 退出"
    echo ""
}

get_admin_info() {
    ADMIN_USERNAME="admin"
    ADMIN_EMAIL=""
    ADMIN_PASSWORD=""
    
    while [ -z "$ADMIN_EMAIL" ]; do
        read -p "请输入管理员邮箱: " ADMIN_EMAIL
        if [ -z "$ADMIN_EMAIL" ]; then
            echo -e "${RED}❌ 管理员邮箱不能为空${NC}"
        elif [[ ! "$ADMIN_EMAIL" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
            echo -e "${RED}❌ 邮箱格式不正确${NC}"
            ADMIN_EMAIL=""
        fi
    done
    
    while [ -z "$ADMIN_PASSWORD" ]; do
        read -s -p "请输入管理员密码 (至少8位): " ADMIN_PASSWORD
        echo
        if [ ${#ADMIN_PASSWORD} -lt 8 ]; then
            echo -e "${RED}❌ 密码长度至少8位${NC}"
            ADMIN_PASSWORD=""
        fi
    done
}

install_redis() {
    echo -e "${YELLOW}📦 检查 Redis 服务...${NC}"
    
    if command -v redis-cli &> /dev/null; then
        if redis-cli ping &> /dev/null; then
            echo -e "${GREEN}✅ Redis 已安装并运行${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️ Redis 已安装但未运行，正在启动...${NC}"
            if systemctl start redis-server 2>/dev/null || systemctl start redis 2>/dev/null; then
                sleep 2
                if redis-cli ping &> /dev/null; then
                    echo -e "${GREEN}✅ Redis 启动成功${NC}"
                    return 0
                fi
            fi
        fi
    fi
    
    echo -e "${YELLOW}📦 安装 Redis...${NC}"
    
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        case $ID in
            ubuntu|debian)
                apt update -qq
                apt install -y redis-server
                systemctl enable redis-server
                systemctl start redis-server
                ;;
            centos|rhel|fedora)
                if ! command -v redis-server &> /dev/null; then
                    # 尝试安装 EPEL 仓库
                    if ! rpm -qa | grep -q epel-release; then
                        echo -e "${YELLOW}   安装 EPEL 仓库...${NC}"
                        yum install -y epel-release || dnf install -y epel-release || true
                    fi
                    # 安装 Redis
                    yum install -y redis || dnf install -y redis || true
                fi
                # 启用并启动 Redis
                if systemctl list-unit-files | grep -q redis; then
                    systemctl enable redis 2>/dev/null || systemctl enable redis-server 2>/dev/null || true
                    systemctl start redis 2>/dev/null || systemctl start redis-server 2>/dev/null || true
                fi
                ;;
            *)
                echo -e "${YELLOW}⚠️ 未识别的系统，请手动安装 Redis${NC}"
                return 1
                ;;
        esac
    else
        echo -e "${YELLOW}⚠️ 无法检测系统类型，请手动安装 Redis${NC}"
        return 1
    fi
    
    sleep 3
    if redis-cli ping &> /dev/null; then
        echo -e "${GREEN}✅ Redis 安装并启动成功${NC}"
        echo -e "${BLUE}💡 提示：Redis 已自动配置为开机自启${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️ Redis 安装失败，将使用内存缓存${NC}"
        echo -e "${YELLOW}💡 提示：您可以稍后手动安装 Redis 以获得更好的性能${NC}"
        return 1
    fi
}

install_system() {
    echo -e "${BLUE}🚀 开始安装系统...${NC}\n"
    
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}❌ 请使用root用户运行此脚本${NC}"
        return 1
    fi
    
    get_admin_info
    echo -e "${GREEN}✅ 管理员信息已收集${NC}\n"
    
    cd "$PROJECT_PATH"
    
    install_redis
    echo ""
    
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python3 未安装${NC}"
        return 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✅ Python版本: $PYTHON_VERSION${NC}"
    
    if ! python3 -m venv --help &> /dev/null; then
        echo -e "${YELLOW}📦 安装 python3-venv...${NC}"
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
        
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            case $ID in
                ubuntu|debian)
                    apt update -qq
                    apt install -y python${PYTHON_MAJOR}.${PYTHON_MINOR}-venv || apt install -y python3-venv
                    ;;
                centos|rhel|fedora)
                    yum install -y python3-pip python3-devel || dnf install -y python3-pip python3-devel
                    # CentOS/RHEL 通常 venv 已包含在 python3 中
                    ;;
                *)
                    echo -e "${YELLOW}⚠️ 未识别的系统，尝试通用安装...${NC}"
                    apt update -qq && apt install -y python3-venv 2>/dev/null || yum install -y python3-pip 2>/dev/null || true
                    ;;
            esac
        else
            echo -e "${YELLOW}⚠️ 无法检测系统类型，尝试通用安装...${NC}"
            apt update -qq && apt install -y python3-venv 2>/dev/null || yum install -y python3-pip 2>/dev/null || true
        fi
    fi
    
    if [ ! -f "requirements.txt" ]; then
        echo -e "${RED}❌ 错误：未找到 requirements.txt 文件${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}🐍 创建Python虚拟环境...${NC}"
    if [ ! -d "venv" ]; then
        if ! python3 -m venv venv 2>/dev/null; then
            echo -e "${RED}❌ 虚拟环境创建失败，请检查 python3-venv 是否已安装${NC}"
            return 1
        fi
        echo -e "${GREEN}✅ 虚拟环境创建成功${NC}"
    fi
    
    echo -e "${YELLOW}📦 安装Python依赖...${NC}"
    source venv/bin/activate
    
    # 升级 pip，最多重试3次
    for i in {1..3}; do
        if pip install --upgrade pip -q 2>/dev/null; then
            break
        elif [ $i -eq 3 ]; then
            echo -e "${YELLOW}⚠️ pip 升级失败，继续使用当前版本...${NC}"
        else
            sleep 2
        fi
    done
    
    # 安装依赖，最多重试2次
    if ! pip install -r requirements.txt; then
        echo -e "${YELLOW}⚠️ 依赖安装失败，尝试重试...${NC}"
        sleep 3
        if ! pip install -r requirements.txt; then
            echo -e "${RED}❌ Python依赖安装失败，请检查网络连接和 requirements.txt 文件${NC}"
            deactivate
            return 1
        fi
    fi
    echo -e "${GREEN}✅ Python依赖安装完成${NC}"
    
    echo -e "${YELLOW}🔍 验证 Redis 连接...${NC}"
    if python3 -c "from app.core.cache import redis_cache; exit(0 if redis_cache.is_connected() else 1)" 2>/dev/null; then
        echo -e "${GREEN}✅ Redis 连接成功${NC}"
    else
        echo -e "${YELLOW}⚠️ Redis 连接失败，将使用内存缓存（不影响运行）${NC}"
    fi
    
    mkdir -p static logs uploads/avatars
    echo -e "${GREEN}✅ 创建必要目录${NC}"
    
    echo -e "${YELLOW}🗄️ 初始化数据库...${NC}"
    python3 -c "from app.core.database import init_database; init_database()" 2>/dev/null || echo -e "${YELLOW}⚠️ 数据库可能已存在${NC}"
    
    echo -e "${YELLOW}👤 创建管理员账户...${NC}"
    if [ ! -f "create_admin.py" ]; then
        echo -e "${RED}❌ 错误：未找到 create_admin.py 文件${NC}"
        deactivate
        return 1
    fi
    
    if ! python3 create_admin.py "$ADMIN_USERNAME" "$ADMIN_EMAIL" "$ADMIN_PASSWORD" 2>/dev/null; then
        echo -e "${YELLOW}⚠️ 管理员账户创建失败，可能已存在${NC}"
        echo -e "${BLUE}💡 提示：如果账户已存在，可以使用菜单选项 2 重设密码${NC}"
    else
        echo -e "${GREEN}✅ 管理员账户创建成功${NC}"
    fi
    deactivate
    
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js 未安装${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Node.js版本: $(node --version)${NC}"
    
    if [ ! -d "frontend" ]; then
        echo -e "${RED}❌ 错误：未找到 frontend 目录${NC}"
        return 1
    fi
    
    if [ ! -f "frontend/package.json" ]; then
        echo -e "${RED}❌ 错误：未找到 frontend/package.json 文件${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}📦 安装前端依赖...${NC}"
    cd frontend
    npm config set registry https://registry.npmmirror.com
    
    # npm install 最多重试2次
    if ! npm install --silent; then
        echo -e "${YELLOW}⚠️ 依赖安装失败，尝试重试...${NC}"
        sleep 3
        if ! npm install --silent; then
            echo -e "${RED}❌ 前端依赖安装失败，请检查网络连接${NC}"
            cd "$PROJECT_PATH"
            return 1
        fi
    fi
    
    echo -e "${YELLOW}🏗️ 构建前端项目...${NC}"
    export NODE_OPTIONS="--max-old-space-size=4096"
    if ! npm run build; then
        echo -e "${RED}❌ 前端构建失败，请检查错误信息${NC}"
        cd "$PROJECT_PATH"
        return 1
    fi
    echo -e "${GREEN}✅ 前端构建完成${NC}"
    
    cd "$PROJECT_PATH"
    
    if [ ! -f "$PROJECT_PATH/main.py" ]; then
        echo -e "${RED}❌ 错误：根目录必须存在 main.py 文件${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}📝 创建systemd服务...${NC}"
    cat > /etc/systemd/system/cboard.service << EOF
[Unit]
Description=CBoard Backend Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_PATH
Environment=PATH=$PROJECT_PATH/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$PROJECT_PATH
ExecStart=$PROJECT_PATH/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port $BACKEND_PORT --workers 2
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable cboard
    echo -e "${GREEN}✅ systemd服务创建完成${NC}"
    
    echo -e "${YELLOW}🔧 准备启动服务...${NC}"
    systemctl stop cboard 2>/dev/null || true
    systemctl stop xboard 2>/dev/null || true
    
    # 检查并释放端口 8000
    if command -v lsof &> /dev/null; then
        PID=$(lsof -ti:8000 2>/dev/null)
        if [ -n "$PID" ]; then
            echo -e "${YELLOW}   发现端口 8000 被占用 (PID: $PID)，正在释放...${NC}"
            kill -9 $PID 2>/dev/null || true
            sleep 2
        fi
    elif command -v fuser &> /dev/null; then
        if fuser 8000/tcp &>/dev/null; then
            echo -e "${YELLOW}   发现端口 8000 被占用，正在释放...${NC}"
            fuser -k 8000/tcp 2>/dev/null || true
            sleep 2
        fi
    elif command -v netstat &> /dev/null; then
        PID=$(netstat -tlnp 2>/dev/null | grep ':8000 ' | awk '{print $7}' | cut -d'/' -f1 | head -1)
        if [ -n "$PID" ] && [ "$PID" != "-" ]; then
            echo -e "${YELLOW}   发现端口 8000 被占用 (PID: $PID)，正在释放...${NC}"
            kill -9 $PID 2>/dev/null || true
            sleep 2
        fi
    fi
    
    echo -e "${YELLOW}🚀 启动服务...${NC}"
    systemctl start cboard
    sleep 5
    
    if systemctl is-active --quiet cboard; then
        echo -e "${GREEN}✅ 服务启动成功${NC}"
    else
        echo -e "${RED}❌ 服务启动失败${NC}"
        echo -e "${YELLOW}📋 查看错误日志：${NC}"
        journalctl -u cboard -n 30 --no-pager | tail -20
        echo ""
        echo -e "${YELLOW}💡 常见问题排查：${NC}"
        echo -e "   1. 检查 Python 依赖是否完整: pip list"
        echo -e "   2. 检查数据库文件权限: ls -l cboard.db"
        echo -e "   3. 检查端口是否被占用: netstat -tlnp | grep 8000"
        echo -e "   4. 查看完整日志: journalctl -u cboard -n 50"
        return 1
    fi
    
    if [ -f ".env" ]; then
        DOMAIN=$(grep "^DOMAIN=" .env 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'" | xargs)
        [ -z "$DOMAIN" ] && DOMAIN=$(grep "^DOMAIN_NAME=" .env 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'" | xargs)
    fi
    
    [ -z "$DOMAIN" ] && DOMAIN=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
    [ -z "$DOMAIN" ] && DOMAIN="localhost"
    
    if [[ "$DOMAIN" =~ ^https?:// ]]; then
        BASE_URL="$DOMAIN"
    elif [ -f ".env" ] && grep -q "^HTTPS=" .env; then
        BASE_URL="https://$DOMAIN"
    else
        BASE_URL="http://$DOMAIN"
    fi
    
    echo ""
    echo -e "${GREEN}🎉 安装完成！${NC}"
    echo "=================================="
    echo ""
    echo -e "${BLUE}📋 登录信息：${NC}"
    echo -e "   管理员用户名: ${GREEN}$ADMIN_USERNAME${NC}"
    echo -e "   管理员邮箱: ${GREEN}$ADMIN_EMAIL${NC}"
    echo -e "   管理员密码: ${GREEN}${ADMIN_PASSWORD:0:2}******${NC}"
    echo ""
    echo -e "${BLUE}🌐 访问地址：${NC}"
    echo -e "   前端界面: ${GREEN}$BASE_URL${NC}"
    echo -e "   管理后台: ${GREEN}$BASE_URL/admin${NC}"
    echo -e "   API文档: ${GREEN}$BASE_URL/api/docs${NC}"
    echo ""
    echo -e "${YELLOW}⚠️ 请立即登录并修改默认密码！${NC}"
    echo ""
    
    read -p "按回车键继续..."
}

reset_admin_password() {
    echo -e "${BLUE}🔑 重设管理员密码${NC}\n"
    
    cd "$PROJECT_PATH"
    
    if [ ! -d "venv" ]; then
        echo -e "${RED}❌ 虚拟环境不存在，请先安装系统${NC}"
        read -p "按回车键继续..."
        return 1
    fi
    
    source venv/bin/activate
    
    read -p "请输入管理员用户名 (默认: admin): " ADMIN_USERNAME
    ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
    NEW_PASSWORD=""
    
    while [ -z "$NEW_PASSWORD" ]; do
        read -s -p "请输入新密码 (至少8位): " NEW_PASSWORD
        echo
        if [ ${#NEW_PASSWORD} -lt 8 ]; then
            echo -e "${RED}❌ 密码长度至少8位${NC}"
            NEW_PASSWORD=""
        fi
    done
    
    echo ""
    python3 reset_admin_password.py "$ADMIN_USERNAME" "$NEW_PASSWORD"
    
    deactivate
    
    echo ""
    read -p "按回车键继续..."
}

view_admin_account() {
    echo -e "${BLUE}👤 查看管理员账号${NC}\n"
    
    cd "$PROJECT_PATH"
    
    if [ ! -d "venv" ]; then
        echo -e "${RED}❌ 虚拟环境不存在，请先安装系统${NC}"
        read -p "按回车键继续..."
        return 1
    fi
    
    source venv/bin/activate
    python3 check_admin.py
    deactivate
    
    echo ""
    read -p "按回车键继续..."
}

configure_domain_nginx() {
    echo -e "${BLUE}🌐 配置域名和Nginx${NC}\n"
    
    # 临时禁用错误退出，允许某些命令失败
    set +e
    
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}❌ 请使用root用户运行此脚本${NC}"
        set -e
        read -p "按回车键继续..."
        return 1
    fi
    
    cd "$PROJECT_PATH"
    
    # 获取域名
    DOMAIN=""
    read -p "请输入域名 (例如: example.com): " DOMAIN
    if [ -z "$DOMAIN" ]; then
        echo -e "${RED}❌ 域名不能为空${NC}"
        set -e
        read -p "按回车键继续..."
        return 1
    fi
    
    # 移除协议前缀
    DOMAIN=$(echo "$DOMAIN" | sed 's|^https\?://||' | sed 's|/$||')
    
    # 询问是否使用HTTPS
    USE_HTTPS=""
    read -p "是否使用HTTPS? (y/n, 默认: y): " USE_HTTPS
    USE_HTTPS=${USE_HTTPS:-y}
    
    BASE_URL=""
    SSL_ENABLED=""
    PROTOCOL=""
    
    if [[ "$USE_HTTPS" =~ ^[Yy]$ ]]; then
        BASE_URL="https://$DOMAIN"
        SSL_ENABLED="true"
        PROTOCOL="https"
    else
        BASE_URL="http://$DOMAIN"
        SSL_ENABLED="false"
        PROTOCOL="http"
    fi
    
    # 配置 .env 文件
    echo -e "${YELLOW}📝 配置 .env 文件...${NC}"
    if [ ! -f ".env" ]; then
        touch .env
    fi
    
    # 更新或添加域名配置
    if grep -q "^DOMAIN=" .env; then
        sed -i "s|^DOMAIN=.*|DOMAIN=$DOMAIN|" .env
    else
        echo "DOMAIN=$DOMAIN" >> .env
    fi
    
    if grep -q "^DOMAIN_NAME=" .env; then
        sed -i "s|^DOMAIN_NAME=.*|DOMAIN_NAME=$DOMAIN|" .env
    else
        echo "DOMAIN_NAME=$DOMAIN" >> .env
    fi
    
    if grep -q "^BASE_URL=" .env; then
        sed -i "s|^BASE_URL=.*|BASE_URL=$BASE_URL|" .env
    else
        echo "BASE_URL=$BASE_URL" >> .env
    fi
    
    if grep -q "^SSL_ENABLED=" .env; then
        sed -i "s|^SSL_ENABLED=.*|SSL_ENABLED=$SSL_ENABLED|" .env
    else
        echo "SSL_ENABLED=$SSL_ENABLED" >> .env
    fi
    
    # 生成SECRET_KEY（如果不存在）
    if ! grep -q "^SECRET_KEY=" .env; then
        SECRET_KEY=$(openssl rand -hex 32)
        echo "SECRET_KEY=$SECRET_KEY" >> .env
    fi
    
    # 配置CORS
    if grep -q "^BACKEND_CORS_ORIGINS=" .env; then
        sed -i "s|^BACKEND_CORS_ORIGINS=.*|BACKEND_CORS_ORIGINS=[\"$BASE_URL\"]|" .env
    else
        echo "BACKEND_CORS_ORIGINS=[\"$BASE_URL\"]" >> .env
    fi
    
    echo -e "${GREEN}✅ .env 文件配置完成${NC}"
    
    # 检测是否使用宝塔面板
    IS_BT=false
    if [ -d "/www/server/panel" ] || [ -f "/www/server/panel/BT-Panel" ]; then
        IS_BT=true
        echo -e "${GREEN}✅ 检测到宝塔面板${NC}"
    fi
    
    # 生成Nginx配置
    echo -e "${YELLOW}📝 生成Nginx配置文件...${NC}"
    
    # 确定SSL证书路径
    if [ "$IS_BT" = true ]; then
        SSL_CERT="/www/server/panel/vhost/cert/$DOMAIN/fullchain.pem"
        SSL_KEY="/www/server/panel/vhost/cert/$DOMAIN/privkey.pem"
        NGINX_CONF="/www/server/panel/vhost/nginx/${DOMAIN}.conf"
        LOG_DIR="/www/wwwlogs"
    else
        SSL_CERT="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
        SSL_KEY="/etc/letsencrypt/live/$DOMAIN/privkey.pem"
        NGINX_CONF="/etc/nginx/sites-available/$DOMAIN.conf"
        LOG_DIR="/var/log/nginx"
    fi
    
    # 确定前端目录
    FRONTEND_DIR="$PROJECT_PATH/frontend/dist"
    
    # 生成Nginx配置内容
    NGINX_CONFIG="server {
    listen 80;
"
    
    if [ "$USE_HTTPS" = "true" ]; then
        NGINX_CONFIG="$NGINX_CONFIG    listen 443 ssl http2;
    server_name $DOMAIN;
    
    # SSL证书配置
    ssl_certificate $SSL_CERT;
    ssl_certificate_key $SSL_KEY;
    
    # SSL配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE:ECDH:AES:HIGH:!NULL:!aNULL:!MD5:!ADH:!RC4;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
"
    else
        NGINX_CONFIG="$NGINX_CONFIG    server_name $DOMAIN;
"
    fi
    
    NGINX_CONFIG="$NGINX_CONFIG    
    # 前端静态文件目录
    root $FRONTEND_DIR;
    index index.html;
    
    # ⚠️ 关键：API反向代理（必须在伪静态之前！）
    location /api/ {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # 支付宝回调需要较长的超时时间
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # 禁用缓冲，确保POST数据不丢失（支付宝回调是POST请求）
        proxy_buffering off;
        proxy_request_buffering off;
        
        # 支持POST请求
        proxy_http_version 1.1;
    }
    
    # ⚠️ 支付回调特殊配置（更具体的匹配，会优先于 /api/）
    location /api/v1/payment/notify/ {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # 支付宝回调特殊配置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # 禁用缓冲
        proxy_buffering off;
        proxy_request_buffering off;
        
        # 支持POST请求
        proxy_http_version 1.1;
        
        # 记录日志（用于调试）
        access_log $LOG_DIR/alipay_notify.log;
        error_log $LOG_DIR/alipay_notify_error.log;
    }
    
    # 兼容路由：/notify（如果支付宝配置的是这个地址）
    location = /notify {
        proxy_pass http://127.0.0.1:$BACKEND_PORT/notify;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_request_buffering off;
        
        access_log $LOG_DIR/alipay_notify.log;
    }
    
    # 前端SPA路由（伪静态，必须在最后）
    location / {
        try_files \$uri \$uri/ /index.html;
    }
    
    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)\$ {
        expires 30d;
        add_header Cache-Control \"public, immutable\";
    }
    
    # 禁止访问隐藏文件
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
"
    
    # 保存配置文件到项目目录
    CONFIG_FILE="$PROJECT_PATH/${DOMAIN}.conf"
    echo "$NGINX_CONFIG" > "$CONFIG_FILE"
    echo -e "${GREEN}✅ Nginx配置文件已保存到: $CONFIG_FILE${NC}"
    
    # 如果使用宝塔面板，提供安装说明
    if [ "$IS_BT" = true ]; then
        echo ""
        echo -e "${YELLOW}📋 宝塔面板配置步骤：${NC}"
        echo -e "   1. 登录宝塔面板"
        echo -e "   2. 网站 → 添加站点 → 域名: ${GREEN}$DOMAIN${NC}"
        echo -e "   3. 网站 → $DOMAIN → 设置 → 配置文件"
        echo -e "   4. 将以下配置文件内容复制到宝塔配置中："
        echo -e "      ${GREEN}$CONFIG_FILE${NC}"
        echo -e "   5. 如果使用HTTPS，请在宝塔面板中申请SSL证书"
        echo -e "   6. 保存并重载配置"
    else
        # 标准Nginx安装
        if command -v nginx &> /dev/null; then
            echo -e "${YELLOW}📝 安装Nginx配置...${NC}"
            
            # 复制到sites-available
            cp "$CONFIG_FILE" "$NGINX_CONF"
            
            # 创建软链接到sites-enabled
            if [ -d "/etc/nginx/sites-enabled" ]; then
                ln -sf "$NGINX_CONF" "/etc/nginx/sites-enabled/$DOMAIN.conf"
            fi
            
            # 测试配置
            if nginx -t 2>/dev/null; then
                echo -e "${GREEN}✅ Nginx配置测试通过${NC}"
                
                # 询问是否重载Nginx
                read -p "是否立即重载Nginx配置? (y/n, 默认: y): " RELOAD_NGINX
                RELOAD_NGINX=${RELOAD_NGINX:-y}
                
                if [[ "$RELOAD_NGINX" =~ ^[Yy]$ ]]; then
                    systemctl reload nginx 2>/dev/null || service nginx reload 2>/dev/null
                    echo -e "${GREEN}✅ Nginx配置已重载${NC}"
                fi
            else
                echo -e "${RED}❌ Nginx配置测试失败，请检查配置文件${NC}"
            fi
        else
            echo -e "${YELLOW}⚠️ Nginx未安装，配置文件已保存到: $CONFIG_FILE${NC}"
            echo -e "${YELLOW}   请手动安装Nginx后，将配置文件复制到 /etc/nginx/sites-available/${NC}"
        fi
    fi
    
    # 如果使用HTTPS，询问是否申请SSL证书
    if [ "$USE_HTTPS" = "true" ] && [ "$IS_BT" != true ]; then
        if command -v certbot &> /dev/null; then
            read -p "是否使用Certbot申请SSL证书? (y/n, 默认: n): " USE_CERTBOT
            USE_CERTBOT=${USE_CERTBOT:-n}
            
            if [[ "$USE_CERTBOT" =~ ^[Yy]$ ]]; then
                read -p "请输入邮箱地址（用于证书到期提醒）: " CERT_EMAIL
                if [ -n "$CERT_EMAIL" ]; then
                    echo -e "${YELLOW}📜 申请SSL证书...${NC}"
                    certbot --nginx -d "$DOMAIN" --email "$CERT_EMAIL" --agree-tos --non-interactive 2>/dev/null || {
                        echo -e "${YELLOW}⚠️ 自动申请失败，请手动运行: certbot --nginx -d $DOMAIN${NC}"
                    }
                fi
            fi
        else
            echo -e "${YELLOW}💡 提示：安装certbot可自动申请SSL证书${NC}"
            echo -e "   Ubuntu/Debian: apt install certbot python3-certbot-nginx"
            echo -e "   CentOS/RHEL: yum install certbot python3-certbot-nginx"
        fi
    fi
    
    echo ""
    echo -e "${GREEN}✅ 域名和Nginx配置完成！${NC}"
    echo -e "${BLUE}📋 配置信息：${NC}"
    echo -e "   域名: ${GREEN}$DOMAIN${NC}"
    echo -e "   访问地址: ${GREEN}$BASE_URL${NC}"
    echo -e "   SSL: ${GREEN}$SSL_ENABLED${NC}"
    echo -e "   配置文件: ${GREEN}$CONFIG_FILE${NC}"
    echo ""
    
    # 恢复错误退出
    set -e
    
    read -p "按回车键继续..."
}

start_service() {
    echo -e "${BLUE}🚀 启动服务${NC}\n"
    
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}❌ 请使用root用户运行此脚本${NC}"
        read -p "按回车键继续..."
        return 1
    fi
    
    if systemctl is-active --quiet cboard; then
        echo -e "${YELLOW}⚠️ 服务已在运行中${NC}"
    else
        systemctl start cboard
        sleep 3
        
        if systemctl is-active --quiet cboard; then
            echo -e "${GREEN}✅ 服务启动成功${NC}"
        else
            echo -e "${RED}❌ 服务启动失败${NC}"
            echo -e "${YELLOW}📋 查看错误日志：${NC}"
            journalctl -u cboard -n 20 --no-pager
        fi
    fi
    
    echo ""
    read -p "按回车键继续..."
}

stop_service() {
    echo -e "${BLUE}🛑 停止服务${NC}\n"
    
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}❌ 请使用root用户运行此脚本${NC}"
        read -p "按回车键继续..."
        return 1
    fi
    
    if ! systemctl is-active --quiet cboard; then
        echo -e "${YELLOW}⚠️ 服务未运行${NC}"
    else
        systemctl stop cboard
        sleep 2
        
        if ! systemctl is-active --quiet cboard; then
            echo -e "${GREEN}✅ 服务已停止${NC}"
        else
            echo -e "${RED}❌ 服务停止失败${NC}"
        fi
    fi
    
    echo ""
    read -p "按回车键继续..."
}

restart_service() {
    echo -e "${BLUE}🔄 重启服务${NC}\n"
    
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}❌ 请使用root用户运行此脚本${NC}"
        read -p "按回车键继续..."
        return 1
    fi
    
    systemctl restart cboard
    sleep 3
    
    if systemctl is-active --quiet cboard; then
        echo -e "${GREEN}✅ 服务重启成功${NC}"
    else
        echo -e "${RED}❌ 服务重启失败${NC}"
        echo -e "${YELLOW}📋 查看错误日志：${NC}"
        journalctl -u cboard -n 20 --no-pager
    fi
    
    echo ""
    read -p "按回车键继续..."
}

check_service_status() {
    echo -e "${BLUE}📊 查看服务状态${NC}\n"
    
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}❌ 请使用root用户运行此脚本${NC}"
        read -p "按回车键继续..."
        return 1
    fi
    
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}【服务状态】${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    if systemctl is-active --quiet cboard; then
        echo -e "   状态: ${GREEN}运行中 ✅${NC}"
    else
        echo -e "   状态: ${RED}已停止 ❌${NC}"
    fi
    
    if systemctl is-enabled --quiet cboard 2>/dev/null; then
        echo -e "   开机自启: ${GREEN}已启用${NC}"
    else
        echo -e "   开机自启: ${YELLOW}未启用${NC}"
    fi
    
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}【进程信息】${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    PID=$(systemctl show -p MainPID --value cboard 2>/dev/null)
    if [ -n "$PID" ] && [ "$PID" != "0" ]; then
        echo -e "   PID: ${GREEN}$PID${NC}"
        if command -v ps &> /dev/null; then
            CPU=$(ps -p $PID -o %cpu --no-headers 2>/dev/null | xargs)
            MEM=$(ps -p $PID -o %mem --no-headers 2>/dev/null | xargs)
            echo -e "   CPU使用率: ${GREEN}${CPU}%${NC}"
            echo -e "   内存使用率: ${GREEN}${MEM}%${NC}"
        fi
    fi
    
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}【端口监听】${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    if command -v netstat &> /dev/null; then
        if netstat -tlnp 2>/dev/null | grep -q ":$BACKEND_PORT "; then
            echo -e "   端口 $BACKEND_PORT: ${GREEN}已监听 ✅${NC}"
        else
            echo -e "   端口 $BACKEND_PORT: ${RED}未监听 ❌${NC}"
        fi
    elif command -v ss &> /dev/null; then
        if ss -tlnp 2>/dev/null | grep -q ":$BACKEND_PORT "; then
            echo -e "   端口 $BACKEND_PORT: ${GREEN}已监听 ✅${NC}"
        else
            echo -e "   端口 $BACKEND_PORT: ${RED}未监听 ❌${NC}"
        fi
    fi
    
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}【最近日志】${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    journalctl -u cboard -n 5 --no-pager --no-hostname 2>/dev/null || echo -e "   ${YELLOW}无法获取日志${NC}"
    
    echo ""
    read -p "按回车键继续..."
}

view_service_logs() {
    echo -e "${BLUE}📋 查看服务日志${NC}\n"
    
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}❌ 请使用root用户运行此脚本${NC}"
        read -p "按回车键继续..."
        return 1
    fi
    
    echo -e "${YELLOW}选择日志查看方式：${NC}"
    echo -e "   ${GREEN}1.${NC} 实时日志（tail -f）"
    echo -e "   ${GREEN}2.${NC} 最近50行"
    echo -e "   ${GREEN}3.${NC} 最近100行"
    echo -e "   ${GREEN}4.${NC} 最近200行"
    echo -e "   ${GREEN}5.${NC} 错误日志"
    echo -e "   ${GREEN}0.${NC} 返回"
    echo ""
    
    read -p "请选择 [0-5]: " log_choice
    
    case $log_choice in
        1)
            echo -e "${YELLOW}按 Ctrl+C 退出实时日志${NC}\n"
            journalctl -u cboard -f
            ;;
        2)
            journalctl -u cboard -n 50 --no-pager
            ;;
        3)
            journalctl -u cboard -n 100 --no-pager
            ;;
        4)
            journalctl -u cboard -n 200 --no-pager
            ;;
        5)
            journalctl -u cboard -p err -n 50 --no-pager
            ;;
        0)
            return 0
            ;;
        *)
            echo -e "${RED}❌ 无效的选择${NC}"
            ;;
    esac
    
    echo ""
    read -p "按回车键继续..."
}

fix_common_errors() {
    echo -e "${BLUE}🔧 修复常见错误${NC}\n"
    
    cd "$PROJECT_PATH"
    
    echo -e "${YELLOW}1. 检查Python虚拟环境...${NC}"
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}   创建虚拟环境...${NC}"
        python3 -m venv venv
        echo -e "${GREEN}   ✅ 虚拟环境创建成功${NC}"
    else
        echo -e "${GREEN}   ✅ 虚拟环境存在${NC}"
    fi
    
    echo -e "${YELLOW}2. 检查Python依赖...${NC}"
    source venv/bin/activate
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    echo -e "${GREEN}   ✅ 依赖检查完成${NC}"
    deactivate
    
    echo -e "${YELLOW}3. 检查必要目录...${NC}"
    mkdir -p static logs uploads/avatars uploads/config uploads/backups
    echo -e "${GREEN}   ✅ 目录检查完成${NC}"
    
    echo -e "${YELLOW}4. 检查数据库...${NC}"
    source venv/bin/activate
    python3 -c "from app.core.database import init_database; init_database()" 2>/dev/null && echo -e "${GREEN}   ✅ 数据库初始化完成${NC}" || echo -e "${YELLOW}   ⚠️ 数据库可能已存在${NC}"
    deactivate
    
    echo -e "${YELLOW}5. 检查systemd服务...${NC}"
    if [ -f "/etc/systemd/system/cboard.service" ]; then
        systemctl daemon-reload
        echo -e "${GREEN}   ✅ 服务配置已重新加载${NC}"
    else
        echo -e "${YELLOW}   ⚠️ systemd服务不存在，请先安装系统${NC}"
    fi
    
    echo -e "${YELLOW}6. 检查端口占用...${NC}"
    if command -v fuser &> /dev/null; then
        if fuser 8000/tcp &>/dev/null; then
            echo -e "${YELLOW}   端口8000被占用，正在释放...${NC}"
            fuser -k 8000/tcp 2>/dev/null || true
            sleep 2
            echo -e "${GREEN}   ✅ 端口已释放${NC}"
        else
            echo -e "${GREEN}   ✅ 端口8000可用${NC}"
        fi
    fi
    
    echo -e "${YELLOW}7. 重启服务...${NC}"
    if systemctl is-enabled cboard &>/dev/null; then
        systemctl restart cboard
        sleep 3
        if systemctl is-active --quiet cboard; then
            echo -e "${GREEN}   ✅ 服务重启成功${NC}"
        else
            echo -e "${RED}   ❌ 服务重启失败，查看日志: journalctl -u cboard -n 50${NC}"
        fi
    else
        echo -e "${YELLOW}   ⚠️ 服务未启用，跳过重启${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}✅ 修复完成！${NC}"
    echo ""
    read -p "按回车键继续..."
}

main() {
    while true; do
        show_menu
        read -p "请选择操作 [0-10]: " choice
        
        case $choice in
            1)
                install_system
                ;;
            2)
                configure_domain_nginx
                ;;
            3)
                fix_common_errors
                ;;
            4)
                start_service
                ;;
            5)
                stop_service
                ;;
            6)
                restart_service
                ;;
            7)
                check_service_status
                ;;
            8)
                view_service_logs
                ;;
            9)
                reset_admin_password
                ;;
            10)
                view_admin_account
                ;;
            0)
                echo -e "${GREEN}👋 再见！${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}❌ 无效的选择，请重新输入${NC}"
                sleep 2
                ;;
        esac
    done
}

main
