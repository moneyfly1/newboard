# CBoard VPS 部署完整指南

本文档提供在VPS服务器上部署CBoard项目的完整步骤。

## 📋 目录

- [系统要求](#系统要求)
- [方式一：使用安装脚本（推荐）](#方式一使用安装脚本推荐)
- [方式二：手动安装](#方式二手动安装)
- [支付配置](#支付配置)
  - [支付宝配置](#支付宝配置)
  - [常见支付问题](#常见支付问题)
- [Nginx配置（支付回调专用）](#nginx配置支付回调专用)
- [Redis 缓存配置](#redis-缓存配置)
- [常见问题](#常见问题)
- [维护和管理](#维护和管理)
- [安全建议](#安全建议)

---

## 系统要求

### 最低配置
- **操作系统**: Ubuntu 20.04+ / Debian 11+ / CentOS 7+
- **内存**: 2GB RAM（推荐4GB+）
- **磁盘**: 20GB可用空间
- **CPU**: 2核心（推荐4核心+）

### 必需软件
- **Python**: 3.8+（推荐3.9-3.12）
- **Node.js**: 16+（推荐18+）
- **Git**: 用于代码拉取

---

## 方式一：使用安装脚本（推荐）⭐

一键安装脚本提供了交互式菜单，可以完成系统安装、管理员管理、错误修复等操作。

### 前置条件

1. **确保是root用户**
   ```bash
   sudo su -
   ```

2. **确保已安装Python3和Node.js**
   ```bash
   # 检查Python
   python3 --version
   
   # 检查Node.js
   node --version
   ```

### 安装步骤

#### 1. 下载项目代码

```bash
# 方式1：从GitHub克隆
cd /www/wwwroot  # 或其他您希望存放项目的目录
git clone https://github.com/moneyfly1/newboard.git cboard
cd cboard

# 方式2：如果代码已在服务器上
cd /path/to/your/project  # 进入项目目录
```

#### 2. 配置环境变量（重要）

在运行安装脚本之前，请先配置 `.env` 文件：

```bash
# 如果.env文件不存在，复制示例文件
cp env.example .env

# 编辑.env文件
nano .env
```

在 `.env` 文件中配置域名（将 `YOUR_DOMAIN` 替换为您的实际域名）：

```env
# 数据库配置
DATABASE_URL=sqlite:///./cboard.db

# 域名配置（重要！）
DOMAIN_NAME=YOUR_DOMAIN
DOMAIN=YOUR_DOMAIN
BASE_URL=https://YOUR_DOMAIN
SSL_ENABLED=true

# 应用配置
APP_NAME=CBoard
SECRET_KEY=$(openssl rand -hex 32)

# CORS配置
BACKEND_CORS_ORIGINS=["https://YOUR_DOMAIN"]
```

保存文件（nano: `Ctrl+O`, `Enter`, `Ctrl+X`）

#### 3. 运行安装脚本

```bash
# 赋予执行权限
chmod +x install.sh

# 运行安装脚本
./install.sh
```

#### 4. 选择操作

脚本会显示交互式菜单：

```
╔════════════════════════════════════╗
║   CBoard 管理工具
╚════════════════════════════════════╝

1. 安装系统
2. 重设管理员密码
3. 查看管理员账号
4. 修复常见错误
0. 退出
```

**选项说明：**

- **选项1：安装系统** - 完整安装流程
  - 提示输入管理员邮箱和密码（至少8位）
  - 自动检查Python和Node.js环境
  - **自动安装并配置 Redis 缓存服务**（如果未安装）
  - 创建Python虚拟环境并安装依赖
  - 初始化数据库
  - 创建管理员账户
  - 构建前端项目
  - 创建systemd服务并启动

- **选项2：重设管理员密码**
  - 输入管理员用户名（默认：admin）
  - 输入新密码（至少8位）
  - 自动重置密码并激活账户

- **选项3：查看管理员账号**
  - 显示所有管理员账户信息
  - 包括用户名、邮箱、激活状态、创建时间等

- **选项4：修复常见错误**
  - 检查并修复Python虚拟环境
  - 检查并安装Python依赖
  - 创建必要目录
  - 初始化数据库
  - 重新加载systemd服务
  - 释放端口占用
  - 重启服务

#### 5. 首次安装流程

选择 **选项1** 后，按照提示：

1. **输入管理员邮箱**：用于登录管理后台的邮箱地址
2. **输入管理员密码**：至少8位字符（输入时不会显示）

脚本会自动完成以下操作：
- ✅ 检查Python和Node.js环境
- ✅ 安装python3-venv包（如果需要）
- ✅ 创建Python虚拟环境
- ✅ 安装所有Python依赖包
- ✅ 创建必要的目录（static、logs、uploads等）
- ✅ 初始化数据库
- ✅ 创建管理员账户（使用您输入的信息）
- ✅ 安装前端依赖
- ✅ 构建前端项目
- ✅ 创建systemd服务
- ✅ 启动后端服务

#### 6. 安装完成

脚本运行完成后，会显示：
- 📋 **登录信息**：管理员用户名、邮箱、密码（部分隐藏）
- 🌐 **访问地址**：前端界面、管理后台、API文档地址
- 🔧 **管理命令**：启动、停止、重启、查看日志等命令

**重要提示**：
- ⚠️ 请立即登录并修改默认密码
- ⚠️ 域名需要在 `.env` 文件中配置，脚本不会询问域名
- ⚠️ 安装脚本不会配置宝塔面板、Nginx、SSL等，这些需要您手动配置

#### 7. 配置Web服务器（可选）

如果您使用宝塔面板或其他Web服务器，需要手动配置：

**宝塔面板配置步骤**：

1. **创建网站**
   - 宝塔面板 → **网站** → **添加站点**
   - 域名：`YOUR_DOMAIN`（与.env中配置的域名一致）
   - 根目录：`/path/to/project/frontend/dist`
   - PHP版本：**纯静态**
   - 点击 **确定**

2. **配置反向代理**
   - 网站 → `YOUR_DOMAIN` → **设置** → **反向代理**
   - 点击 **添加反向代理**
   - 配置：
     - **代理名称**：`api`
     - **代理目录**：`/api/`
     - **目标URL**：`http://127.0.0.1:8000`
     - **发送域名**：`$host`
     - 点击 **提交**

3. **配置SSL证书**
   - 网站 → `YOUR_DOMAIN` → **设置** → **SSL**
   - 选择 **Let's Encrypt**
   - 填写邮箱地址
   - 如果HTTP验证失败，选择 **DNS验证**
   - 申请成功后，开启 **强制HTTPS**

4. **配置伪静态（SPA路由）**
   - 网站 → `YOUR_DOMAIN` → **设置** → **伪静态**
   - 添加以下规则：
     ```nginx
     location / {
         try_files $uri $uri/ /index.html;
     }
     ```
   - 点击 **保存**

---

## 方式二：手动安装

如果您不使用自动安装脚本，可以按照以下步骤手动部署。

**⚠️ 重要提示**：以下所有命令中的 `/www/wwwroot/baidu.com` 仅为示例路径，请根据您的实际情况替换为您的项目路径。例如：
- 如果您的域名是 `example.com`，路径应该是 `/www/wwwroot/example.com`
- 如果您的项目在其他位置，请替换为实际路径

### 第一步：安装系统依赖

```bash
# 更新包列表
apt update

# 安装Python和基础工具
apt install -y python3 python3-pip python3-dev build-essential git curl wget

# 安装对应版本的python3-venv（重要！）
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
apt install -y python${PYTHON_MAJOR}.${PYTHON_MINOR}-venv
```

### 第二步：安装Node.js

```bash
# 安装Node.js 18.x
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y nodejs

# 验证安装
node --version
npm --version
```

### 第三步：下载项目代码

```bash
# 创建项目目录（⚠️ 请将 /www/wwwroot/baidu.com 替换为您的实际项目路径）
PROJECT_PATH="/www/wwwroot/baidu.com"
mkdir -p $PROJECT_PATH
cd $PROJECT_PATH

# 克隆项目
git clone https://github.com/moneyfly1/newboard.git .
```

**注意**：`/www/wwwroot/baidu.com` 是示例路径，请替换为您的实际项目目录。

### 第四步：配置环境变量

```bash
# ⚠️ 确保已设置 PROJECT_PATH 变量，如果未设置请重新执行：
# PROJECT_PATH="/www/wwwroot/baidu.com"  # 替换为您的实际路径
cd $PROJECT_PATH

# 复制示例配置文件
cp env.example .env

# 编辑.env文件
nano .env
```

在 `.env` 文件中配置以下内容（⚠️ 将 `baidu.com` 和 `YOUR_DOMAIN` 替换为您的实际域名）：

```env
# 数据库配置
DATABASE_URL=sqlite:///./cboard.db

# 域名配置（重要！）
DOMAIN_NAME=YOUR_DOMAIN
DOMAIN=YOUR_DOMAIN
BASE_URL=https://YOUR_DOMAIN
SSL_ENABLED=true

# 应用配置
APP_NAME=CBoard
SECRET_KEY=$(openssl rand -hex 32)

# CORS配置
BACKEND_CORS_ORIGINS=["https://YOUR_DOMAIN"]
```

保存文件（nano: `Ctrl+O`, `Enter`, `Ctrl+X`）

### 第五步：配置Python环境

```bash
# ⚠️ 确保 PROJECT_PATH 变量已设置为您的实际项目路径
cd $PROJECT_PATH

# 创建Python虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 升级pip
pip install --upgrade pip

# 安装Python依赖
pip install -r requirements.txt

# 创建必要的目录
mkdir -p static logs uploads/avatars

# 退出虚拟环境
deactivate
```

### 第六步：初始化数据库

```bash
# ⚠️ 确保 PROJECT_PATH 变量已设置为您的实际项目路径
cd $PROJECT_PATH
source venv/bin/activate

# 初始化数据库
python3 -c "from app.core.database import init_database; init_database()"

# 创建管理员账户
python3 create_admin.py admin your-email@example.com your-password

# 验证管理员账户
python3 check_admin.py

deactivate
```

### 第七步：构建前端

```bash
# ⚠️ 确保 PROJECT_PATH 变量已设置为您的实际项目路径
cd $PROJECT_PATH/frontend

# 配置npm镜像源（可选，加速下载）
npm config set registry https://registry.npmmirror.com

# 安装前端依赖
npm install

# 构建生产版本
export NODE_OPTIONS="--max-old-space-size=4096"
npm run build

# 验证构建结果
ls -la dist/
# 应该能看到 index.html 和 assets/ 目录
```

### 第八步：配置systemd服务

```bash
# ⚠️ 重要：请先设置 PROJECT_PATH 变量为您的实际项目路径
# PROJECT_PATH="/www/wwwroot/baidu.com"  # 替换为您的实际路径
cd $PROJECT_PATH

# 创建systemd服务文件
# ⚠️ 注意：以下命令中的 $PROJECT_PATH 会自动替换为上面设置的变量值
sudo tee /etc/systemd/system/cboard.service > /dev/null << EOF
[Unit]
Description=CBoard Backend Service (FastAPI)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_PATH
Environment=PATH=$PROJECT_PATH/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$PROJECT_PATH
ExecStart=$PROJECT_PATH/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cboard-backend
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

# 重新加载systemd配置
sudo systemctl daemon-reload

# 启用服务（开机自启）
sudo systemctl enable cboard

# 启动服务
sudo systemctl start cboard

# 检查服务状态
sudo systemctl status cboard
```

### 第九步：配置Web服务器

参考[方式一第7步](#7-配置web服务器可选)的Web服务器配置说明。

**⚠️ 注意**：配置Web服务器时，根目录应设置为：`/www/wwwroot/baidu.com/frontend/dist`（请将 `baidu.com` 替换为您的实际域名）

### 第十步：验证部署

```bash
# 1. 检查服务状态
systemctl status cboard

# 2. 测试本地API
curl http://127.0.0.1:8000/health
# 应该返回: {"status":"healthy"}

# 3. 检查端口监听
netstat -tlnp | grep 8000
# 应该能看到8000端口在监听

# 4. 测试域名访问（需要配置DNS和Web服务器）
curl https://YOUR_DOMAIN/api/health
# 应该返回: {"status":"healthy"}
```

---

## 支付配置

### 支付宝配置

#### 1. 在支付宝开放平台配置

**重要提示**：支付宝支付需要配置**应用网关**和**授权回调地址**，否则支付成功后无法收到回调通知，订单状态不会更新。

**配置步骤：**

1. **登录支付宝开放平台**
   - 访问：https://open.alipay.com/
   - 登录您的开发者账号

2. **设置应用网关（最重要！）**
   - 进入 **控制台** → **开发设置**
   - 找到 **"应用网关"** 选项
   - 点击 **"设置"** 按钮
   - 输入回调URL（将 `YOUR_DOMAIN` 替换为您的实际域名）：
     ```
     https://YOUR_DOMAIN/api/v1/payment/notify/alipay
     ```
   - 点击保存

3. **设置授权回调地址**
   - 在 **开发设置** 页面找到 **"授权回调地址"**
   - 点击 **"修改"** 按钮
   - 输入回调URL（与应用网关相同）：
     ```
     https://YOUR_DOMAIN/api/v1/payment/notify/alipay
     ```
   - 点击保存

**重要提示：**
- ✅ 必须是 HTTPS 协议
- ✅ 必须是公网可访问的地址
- ✅ 路径必须完全匹配：`/api/v1/payment/notify/alipay`
- ✅ 确保域名已配置SSL证书

#### 2. 在管理后台配置支付宝密钥

1. **登录管理后台**
   - 访问：`https://YOUR_DOMAIN/admin`
   - 使用管理员账号登录

2. **配置支付方式**
   - 进入 **系统管理** → **支付配置**
   - 找到 **支付宝** 配置项
   - 点击 **编辑** 或 **配置** 按钮
   - 填写以下信息：
     - **应用ID (App ID)**：从支付宝开放平台获取
     - **商户私钥 (Private Key)**：您的RSA私钥
     - **支付宝公钥 (Public Key)**：从支付宝开放平台获取
     - **网关地址**：`https://openapi.alipay.com/gateway.do`（正式环境）
     - **回调URL**：`https://YOUR_DOMAIN/api/v1/payment/notify/alipay`（可选，系统会自动生成）
   - 点击 **保存**

3. **启用支付方式**
   - 在支付配置列表中，找到支付宝配置
   - 点击开关按钮，启用支付宝支付

#### 3. 验证配置

配置完成后，可以通过以下方式验证：

1. **测试回调URL可访问性**
   ```bash
   curl -X POST https://YOUR_DOMAIN/api/v1/payment/notify/alipay \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "test=1"
   ```
   应该返回JSON响应（即使验证失败也会返回）

2. **测试支付流程**
   - 创建一个小额测试订单（如 ¥0.01）
   - 完成支付后，检查：
     - ✅ 订单状态是否更新为"已支付"
     - ✅ 订阅是否已激活
     - ✅ 设备数量是否已更新

3. **查看支付日志**
   ```bash
   # 查看后端日志
   journalctl -u cboard -n 100 | grep -i "alipay\|支付\|notify"
   
   # 查看支付专用日志（如果有）
   tail -f uploads/logs/payment.log
   ```

### 常见支付问题

#### Q1: 支付成功了但订单状态还是"未支付"？

**原因**：支付宝的异步通知没有到达服务器。

**解决方案**：
1. ✅ 检查应用网关是否已设置
2. ✅ 检查回调URL是否正确
3. ✅ 检查服务器防火墙是否允许支付宝访问
4. ✅ 检查SSL证书是否有效
5. ✅ 检查Nginx配置是否正确（见下方Nginx配置章节）

#### Q2: 前端显示"支付状态检查超时"？

**原因**：
- 后端没有收到支付宝回调，订单状态一直是 `pending`
- 前端轮询检查时网络超时

**解决方案**：
- 先修复应用网关配置
- 支付成功后，支付宝会发送回调，订单状态会自动更新
- 前端轮询会检测到状态变化并跳转

#### Q3: 如何查看支付宝回调日志？

**查看日志**：
```bash
# 后端systemd日志
journalctl -u cboard -n 200 | grep -iE "notify|回调|alipay|支付"

# Nginx访问日志（如果配置了）
tail -f /www/wwwlogs/alipay_notify.log

# 支付专用日志
tail -f uploads/logs/payment.log
```

---

## Nginx配置（支付回调专用）

### 重要提示

⚠️ **支付回调配置必须在伪静态之前！** Nginx会按照配置顺序匹配，如果伪静态在前，会拦截支付回调请求。

### 完整Nginx配置示例

以下是完整的Nginx虚拟主机配置（将 `YOUR_DOMAIN` 替换为您的实际域名）：

```nginx
server {
    listen 80;
    listen 443 ssl http2;
    server_name YOUR_DOMAIN;
    
    # SSL证书配置（请根据实际情况修改路径）
    # 如果使用宝塔面板，通常路径是：
    ssl_certificate /www/server/panel/vhost/cert/YOUR_DOMAIN/fullchain.pem;
    ssl_certificate_key /www/server/panel/vhost/cert/YOUR_DOMAIN/privkey.pem;
    
    # SSL配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE:ECDH:AES:HIGH:!NULL:!aNULL:!MD5:!ADH:!RC4;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # 前端静态文件目录（请根据实际情况修改路径）
    root /www/wwwroot/YOUR_DOMAIN/frontend/dist;
    index index.html;
    
    # ⚠️ 关键：API反向代理（必须在伪静态之前！）
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
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
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
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
        access_log /www/wwwlogs/alipay_notify.log;
        error_log /www/wwwlogs/alipay_notify_error.log;
    }
    
    # 兼容路由：/notify（如果支付宝配置的是这个地址）
    location = /notify {
        proxy_pass http://127.0.0.1:8000/notify;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_request_buffering off;
        
        access_log /www/wwwlogs/alipay_notify.log;
    }
    
    # 前端SPA路由（伪静态，必须在最后）
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # 禁止访问隐藏文件
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
```

### 配置说明

#### 1. API反向代理配置

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    # ... 其他配置 ...
}
```

**关键点**：
- ✅ `proxy_pass` 后面**不要带斜杠**（如果location带斜杠）
- ✅ 必须设置 `proxy_buffering off` 和 `proxy_request_buffering off`，确保POST数据不丢失
- ✅ 超时时间设置为60秒，避免支付宝回调超时

#### 2. 支付回调特殊配置

```nginx
location /api/v1/payment/notify/ {
    # ... 配置 ...
}
```

**为什么需要单独配置？**
- 更具体的匹配规则会优先于 `/api/`
- 可以单独设置日志记录，方便调试
- 可以单独设置超时时间

#### 3. 兼容路由

```nginx
location = /notify {
    proxy_pass http://127.0.0.1:8000/notify;
    # ... 配置 ...
}
```

**用途**：如果支付宝配置的是 `/notify` 而不是 `/api/v1/payment/notify/alipay`，这个路由会转发到后端的兼容处理函数。

### 使用宝塔面板配置

如果您使用宝塔面板，可以按以下步骤配置：

1. **登录宝塔面板**
   - 访问宝塔面板地址
   - 使用管理员账号登录

2. **配置反向代理**
   - 网站 → 找到您的域名 → **设置** → **反向代理**
   - 点击 **添加反向代理**
   - 配置：
     - **代理名称**：`api`
     - **代理目录**：`/api/`
     - **目标URL**：`http://127.0.0.1:8000`（⚠️ 不要带斜杠）
     - **发送域名**：`$host`
     - **超时时间**：60秒
   - 点击 **提交**

3. **配置伪静态**
   - 网站 → 您的域名 → **设置** → **伪静态**
   - 添加以下规则：
     ```nginx
     location / {
         try_files $uri $uri/ /index.html;
     }
     ```
   - 点击 **保存**

4. **手动编辑配置文件（推荐）**
   - 网站 → 您的域名 → **设置** → **配置文件**
   - 点击 **编辑** 按钮
   - 将上面的完整配置示例复制进去（记得替换域名和路径）
   - 点击 **保存**
   - 点击 **重载配置**

### 验证Nginx配置

#### 1. 检查配置语法

```bash
nginx -t
```

如果显示 `syntax is ok` 和 `test is successful`，说明配置正确。

#### 2. 测试回调URL

```bash
# 从服务器本地测试
curl -X POST http://127.0.0.1:8000/api/v1/payment/notify/alipay \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "test=1"

# 从外网测试（需要替换为您的实际域名）
curl -X POST https://YOUR_DOMAIN/api/v1/payment/notify/alipay \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "test=1"
```

#### 3. 查看日志

```bash
# 查看支付回调日志（如果配置了）
tail -f /www/wwwlogs/alipay_notify.log

# 查看Nginx访问日志
tail -f /www/wwwlogs/access.log | grep notify

# 查看后端日志
journalctl -u cboard -f | grep -i "notify\|alipay"
```

### 常见Nginx配置问题

#### 问题1：Nginx返回404

**原因**：`proxy_pass` 配置不正确

**解决方案**：
- 确保 `proxy_pass` 后面**不要带斜杠**（如果location带斜杠）
- 例如：`location /api/ { proxy_pass http://127.0.0.1:8000; }`

#### 问题2：Nginx返回502 Bad Gateway

**原因**：后端服务未运行或端口不正确

**解决方案**：
```bash
# 检查后端服务是否运行
systemctl status cboard

# 检查端口是否监听
netstat -tlnp | grep 8000

# 测试后端是否响应
curl http://127.0.0.1:8000/health
```

#### 问题3：回调参数丢失

**原因**：Nginx缓冲导致POST数据丢失

**解决方案**：
```nginx
proxy_buffering off;
proxy_request_buffering off;
```

#### 问题4：回调超时

**原因**：Nginx超时设置太短

**解决方案**：增加超时时间（参考上面的配置）

---

## 常见问题

### 1. Python虚拟环境创建失败

**错误信息**: `The virtual environment was not created successfully because ensurepip is not available`

**解决方案**:
```bash
# 安装对应版本的python3-venv
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
apt install -y python${PYTHON_MAJOR}.${PYTHON_MINOR}-venv

# 重新创建虚拟环境
python3 -m venv venv
```

### 2. 后端服务启动失败

**查看错误日志**:
```bash
journalctl -u cboard -n 50 --no-pager
```

**常见原因**:
- 缺少Python依赖包：运行 `pip install -r requirements.txt`
- 端口被占用：检查并停止占用8000端口的进程
- 数据库文件权限问题：`chmod 664 cboard.db`
- **`main.py` 导入错误**：如果看到 `ImportError: attempted relative import with no known parent package`，说明 `main.py` 使用了相对导入

**修复 `main.py` 导入错误**:
```bash
# 手动修复：确保 main.py 使用绝对导入（from app.xxx 而不是 from .xxx）
cd /www/wwwroot/go.moneyfly.top  # 替换为您的实际路径
# 检查 main.py 是否使用了相对导入
grep "from \\.core.config" main.py
# 如果存在，运行以下命令修复（会自动将相对导入改为绝对导入）
sed -i 's/from \.core\.config/from app.core.config/g' main.py
sed -i 's/from \.api\.api_v1/from app.api.api_v1/g' main.py
sed -i 's/from \.core\.database/from app.core.database/g' main.py
sed -i 's/from \.middleware\.rate_limit/from app.middleware.rate_limit/g' main.py
sed -i 's/from \.models import/from app.models import/g' main.py
sed -i 's/from \.services\.email_queue_processor/from app.services.email_queue_processor/g' main.py
sed -i 's/from \.tasks\.notification_tasks/from app.tasks.notification_tasks/g' main.py
# 重启服务
systemctl restart cboard
```

### 3. 前端页面404错误

**原因**: Nginx未配置SPA路由

**解决方案**: 在宝塔面板中添加伪静态规则：
```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

### 4. API请求返回404或502

**检查反向代理配置**:
```bash
# 查看Nginx配置
cat /www/server/panel/vhost/nginx/YOUR_DOMAIN.conf | grep -A 10 "location /api/"
```

确保配置正确：
- 代理目录：`/api/`
- 目标URL：`http://127.0.0.1:8000`（不要带斜杠）
- 发送域名：`$host`

### 5. SSL证书申请失败

**原因**: DNS解析未生效或CAA记录冲突

**解决方案**:
- 使用DNS验证方式申请证书
- 检查DNS解析是否生效：`nslookup YOUR_DOMAIN`
- 检查并移除CAA记录中的冲突项

### 6. 登录时提示"Not Found"或认证失败

**检查步骤**:
1. 确认后端服务运行：`systemctl status cboard`
2. 检查API是否可达：`curl http://127.0.0.1:8000/health`
3. 检查管理员账户：`python3 check_admin.py`
4. 查看后端日志：`journalctl -u cboard -n 50`

**重置管理员密码**:
```bash
cd $PROJECT_PATH
source venv/bin/activate
python3 reset_admin_password.py admin new-password
deactivate
```

### 7. Node.js版本过低

**错误**: npm构建时提示Node.js版本不兼容

**解决方案**:
```bash
# 安装Node.js 18.x
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y nodejs
```

---

## 维护和管理

### 服务管理

```bash
# 启动服务
systemctl start cboard

# 停止服务
systemctl stop cboard

# 重启服务
systemctl restart cboard

# 查看状态
systemctl status cboard

# 查看实时日志
journalctl -u cboard -f

# 查看最近50行日志
journalctl -u cboard -n 50 --no-pager
```

### 代码更新

```bash
# ⚠️ 请先设置 PROJECT_PATH 变量为您的实际项目路径
# PROJECT_PATH="/www/wwwroot/baidu.com"  # 替换为您的实际路径
cd $PROJECT_PATH

# 拉取最新代码
git pull origin master

# 更新Python依赖（如果有新依赖）
source venv/bin/activate
pip install -r requirements.txt
deactivate

# 更新前端
cd frontend
npm install
npm run build
cd ..

# 重启服务
systemctl restart cboard
```

### 数据库备份

```bash
# ⚠️ 请先设置 PROJECT_PATH 变量为您的实际项目路径
# PROJECT_PATH="/www/wwwroot/baidu.com"  # 替换为您的实际路径
cd $PROJECT_PATH

# 创建备份目录
mkdir -p uploads/backups

# 备份数据库
cp cboard.db uploads/backups/cboard_$(date +%Y%m%d_%H%M%S).db

# 定期备份（添加到crontab）
# 0 2 * * * cp /www/wwwroot/YOUR_DOMAIN/cboard.db /www/wwwroot/YOUR_DOMAIN/uploads/backups/cboard_$(date +\%Y\%m\%d).db
```

### 日志管理

```bash
# 查看应用日志
tail -f logs/app.log

# 查看systemd日志
journalctl -u cboard -f

# 查看Nginx访问日志（如果使用宝塔面板）
tail -f /www/wwwlogs/YOUR_DOMAIN.log

# 查看Nginx错误日志（如果使用宝塔面板）
tail -f /www/wwwlogs/YOUR_DOMAIN.error.log
```

### 性能优化

1. **增加worker数量**（如果服务器资源充足）:
   编辑 `/etc/systemd/system/cboard.service`，将 `--workers 2` 改为 `--workers 4`

2. **启用Nginx缓存**:
   在宝塔面板的网站设置中启用缓存

3. **数据库优化**:
   - 定期清理过期数据
   - 使用更强大的数据库（PostgreSQL/MySQL）替换SQLite

4. **使用 Redis 缓存**（推荐）:
   - 减少应用内存占用约 60-70%
   - 提高缓存性能
   - 详见 [Redis 缓存配置](#redis-缓存配置)

### 故障排查工具

项目提供了几个有用的Python脚本（需要先激活虚拟环境）：

```bash
# ⚠️ 请先设置 PROJECT_PATH 变量为您的实际项目路径
# PROJECT_PATH="/www/wwwroot/baidu.com"  # 替换为您的实际路径
cd $PROJECT_PATH
source venv/bin/activate

# 检查管理员账户
python3 check_admin.py

# 创建管理员账户
python3 create_admin.py username email password

# 重置管理员密码
python3 reset_admin_password.py username new-password

deactivate
```

### 快速诊断命令

```bash
# 1. 检查后端服务状态
systemctl status cboard

# 2. 查看最近50行错误日志
journalctl -u cboard -n 50 --no-pager

# 3. 测试本地API
curl http://127.0.0.1:8000/health

# 4. 检查端口占用
netstat -tlnp | grep 8000

# 5. 测试域名API（需要配置DNS）
curl https://YOUR_DOMAIN/api/health

# 6. 检查Nginx配置（如果使用Nginx）
nginx -t
```

---

## Redis 缓存配置

### 概述

项目已集成 Redis 缓存功能，用于减少内存占用并提高性能。系统会自动检测 Redis 连接状态，如果 Redis 不可用，会自动降级到内存缓存，不影响应用运行。

### 核心优势

- ✅ **减少内存占用**：缓存数据存储在独立的 Redis 进程中，应用内存占用减少约 60-70%
- ✅ **提高性能**：Redis 读写速度快，支持持久化，响应时间更快
- ✅ **自动降级**：Redis 不可用时自动使用内存缓存，不影响功能
- ✅ **可扩展**：支持多实例共享缓存，便于横向扩展

### 安装 Redis

#### 方式一：使用安装脚本（推荐）

安装脚本会自动检测并安装 Redis（如果未安装）：

```bash
./install.sh
# 选择 "1. 安装系统"
```

脚本会自动：
- 检测系统类型（Ubuntu/Debian/CentOS）
- 安装 Redis 服务
- 配置 Redis 开机自启
- 启动 Redis 服务

#### 方式二：手动安装

**Ubuntu/Debian:**
```bash
# 更新包列表
apt update

# 安装 Redis
apt install -y redis-server

# 启动 Redis
systemctl start redis-server

# 设置开机自启
systemctl enable redis-server

# 验证安装
redis-cli ping
# 应该返回: PONG
```

**CentOS/RHEL:**
```bash
# 安装 EPEL 仓库（如果未安装）
yum install -y epel-release

# 安装 Redis
yum install -y redis

# 启动 Redis
systemctl start redis

# 设置开机自启
systemctl enable redis

# 验证安装
redis-cli ping
```

**使用 Docker:**
```bash
docker run -d \
  --name redis \
  -p 6379:6379 \
  --restart unless-stopped \
  redis:latest
```

### 配置 Redis

#### 1. 环境变量配置（可选）

在 `.env` 文件中添加以下配置（如果使用非默认设置）：

```env
# Redis 配置（可选，默认值如下）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=          # 如果设置了密码，填写密码
REDIS_DB=0               # 数据库编号，默认 0
```

或者使用 Redis URL：
```env
REDIS_URL=redis://localhost:6379/0
# 或带密码
REDIS_URL=redis://:password@localhost:6379/0
```

**注意**：如果不配置，系统会使用默认值（localhost:6379，无密码）。

#### 2. 设置 Redis 密码（生产环境推荐）

编辑 Redis 配置文件：

```bash
# Ubuntu/Debian
nano /etc/redis/redis.conf

# CentOS
nano /etc/redis.conf
```

找到并修改以下行：
```conf
# requirepass foobared
```
改为：
```conf
requirepass your_strong_password_here
```

重启 Redis：
```bash
systemctl restart redis-server  # Ubuntu/Debian
systemctl restart redis         # CentOS
```

然后在 `.env` 文件中配置密码：
```env
REDIS_PASSWORD=your_strong_password_here
```

### 验证 Redis 连接

#### 方法 1：启动日志

应用启动时会自动检查 Redis 连接，日志中会显示：
```
Redis 连接成功: localhost:6379/0
```
或
```
Redis 缓存连接失败，将使用内存缓存作为后备
```

#### 方法 2：命令行测试

```bash
# 测试连接（无密码）
redis-cli ping

# 测试连接（有密码）
redis-cli -a your_password ping

# 应该返回: PONG
```

#### 方法 3：Python 测试

```bash
cd /path/to/project
source venv/bin/activate
python3 -c "from app.core.cache import redis_cache; print('Redis 连接:', '成功' if redis_cache.is_connected() else '失败（将使用内存缓存）')"
```

### 已使用 Redis 缓存的服务

1. **节点服务 (NodeService)**
   - 缓存键：`nodes:clash_config`
   - 缓存时间：300 秒（5 分钟）
   - 自动降级：Redis 不可用时使用内存缓存

2. **监控服务 (SystemMonitor)**
   - 缓存键：`monitoring:metrics_history`, `monitoring:latest_metrics`
   - 历史记录：最多 100 条
   - 自动降级：Redis 不可用时使用内存缓存

### 监控和维护

#### 查看 Redis 使用情况

```bash
# 查看内存使用
redis-cli info memory

# 查看统计信息
redis-cli info stats

# 查看所有键
redis-cli KEYS *

# 查看特定模式的键
redis-cli KEYS "nodes:*"
redis-cli KEYS "monitoring:*"
```

#### 清理缓存

```bash
# 清理所有缓存（谨慎使用）
redis-cli FLUSHALL

# 清理当前数据库
redis-cli FLUSHDB

# 删除特定键
redis-cli DEL "nodes:clash_config"
```

#### 查看连接信息

```bash
# 查看客户端连接
redis-cli CLIENT LIST

# 查看配置
redis-cli CONFIG GET "*"
```

### 故障处理

#### Redis 连接失败

如果 Redis 连接失败，系统会自动降级到内存缓存，不会影响应用运行。但会记录警告日志：

```
Redis 连接失败，将使用内存缓存: Connection refused
```

**常见原因和解决方案：**

1. **Redis 服务未启动**
   ```bash
   systemctl status redis-server  # Ubuntu/Debian
   systemctl status redis          # CentOS
   systemctl start redis-server    # 启动服务
   ```

2. **端口被占用**
   ```bash
   netstat -tlnp | grep 6379
   # 检查是否有其他程序占用 6379 端口
   ```

3. **防火墙阻止**
   ```bash
   # 如果 Redis 在远程服务器，检查防火墙规则
   ufw allow 6379/tcp  # Ubuntu
   firewall-cmd --add-port=6379/tcp --permanent  # CentOS
   ```

4. **认证失败**
   - 检查 `.env` 文件中的 `REDIS_PASSWORD` 是否正确
   - 检查 Redis 配置文件中的 `requirepass` 设置

5. **连接超时**
   - 检查网络连接
   - 检查 Redis 配置文件中的 `timeout` 设置

### 生产环境建议

1. **设置密码**：在生产环境中必须设置 Redis 密码
2. **持久化**：启用 Redis 持久化（RDB 或 AOF）
   ```bash
   # 编辑配置文件，确保以下配置已启用
   save 900 1
   save 300 10
   save 60 10000
   appendonly yes
   ```
3. **内存限制**：设置 `maxmemory` 和淘汰策略
   ```conf
   maxmemory 256mb
   maxmemory-policy allkeys-lru
   ```
4. **监控**：使用 Redis 监控工具监控性能
5. **备份**：定期备份 Redis 数据
   ```bash
   # 手动备份
   redis-cli SAVE
   cp /var/lib/redis/dump.rdb /backup/redis_$(date +%Y%m%d).rdb
   ```

### 相关文件

- `app/core/cache.py` - Redis 缓存服务类
- `app/core/config.py` - Redis 配置
- `app/services/node_service.py` - 节点服务（使用 Redis）
- `app/services/monitoring.py` - 监控服务（使用 Redis）
- `main.py` - 应用启动时的 Redis 连接检查

---

## 安全建议

1. **定期更新系统**和依赖包
2. **使用强密码**，并定期更换
3. **配置防火墙**，只开放必要端口
4. **定期备份数据库**
5. **监控日志**，及时发现异常
6. **使用HTTPS**，保护数据传输安全

---

## 技术支持

如遇到问题，请检查：
1. 服务日志：`journalctl -u cboard -n 50`
2. 常见问题章节
3. GitHub Issues

---

**祝您使用愉快！** 🎉
