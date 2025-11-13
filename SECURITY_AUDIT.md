# 安全审计报告

## 审计日期
2025-01-07

## 审计范围
管理员后台地址分离后的安全性评估

## 1. 后端API权限控制 ✅

### 1.1 管理员API权限验证
- **状态**: ✅ 安全
- **检查结果**: 所有管理员API都使用 `Depends(get_current_admin_user)`
- **验证机制**: 
  - `get_current_admin_user` 首先调用 `get_current_user` 验证token
  - 然后检查 `current_user.is_admin` 是否为 `True`
  - 如果不是管理员，返回 `403 Forbidden`
- **受保护的API**:
  - `/admin/*` - 所有管理员路由
  - `/payment-config/*` (除 `/active` 外)
  - `/software-config/*`
  - `/config/admin/*`
  - `/notifications/admin/*`
  - `/tickets/admin/*`
  - `/coupons/admin/*`
  - `/announcements/admin/*`

### 1.2 敏感信息API
- **节点信息API** (`/nodes/`):
  - ✅ 使用 `_extract_public_node_data` 过滤敏感信息
  - ✅ 不返回 `server`, `port`, `password` 等敏感字段
  - ✅ 只返回公开信息：id, name, region, type, status, load, speed, uptime, latency, description
  - ⚠️ 需要用户认证 (`get_current_user`)，但这是合理的（用户需要选择节点）

- **支付配置API** (`/payment-config/active`):
  - ✅ 返回 `PaymentConfigPublic` 模型
  - ✅ 不包含敏感信息：app_id, merchant_private_key, alipay_public_key 等
  - ✅ 只返回公开信息：id, pay_type, pay_name, status, sort_order
  - ⚠️ 无权限验证，但这是合理的（用户需要看到可用的支付方式）

- **软件配置API** (`/software-config/`):
  - ✅ 需要 `get_current_admin_user` 权限验证
  - ✅ 只有管理员可以访问

- **系统配置API** (`/config/admin/*`):
  - ✅ 需要 `get_current_admin_user` 权限验证
  - ✅ 只有管理员可以访问

## 2. 前端路由守卫 ✅

### 2.1 路由权限检查
- **状态**: ✅ 安全
- **实现**: `router.beforeEach` 导航守卫
- **检查项**:
  - `requiresAuth`: 检查用户是否已登录
  - `requiresAdmin`: 检查用户是否为管理员
  - `requiresGuest`: 已登录用户不能访问登录/注册页面

### 2.2 管理员路由保护
- ✅ 所有 `/admin/*` 路由都有 `meta: { requiresAuth: true, requiresAdmin: true }`
- ✅ 非管理员用户访问管理员路由会被重定向到 `/dashboard`
- ✅ 未登录用户访问管理员路由会被重定向到 `/admin/login`

## 3. API拦截器安全 ✅

### 3.1 Token识别逻辑
- **状态**: ✅ 安全
- **实现**: 根据API路径和当前页面路径智能识别
- **逻辑**:
  1. 检查API路径是否以 `/admin` 开头
  2. 检查API路径是否包含 `/admin/`
  3. 检查API路径是否匹配管理员路径列表
  4. **新增**: 如果在管理员后台（`/admin` 路径下），`/users/` 开头的API也使用 `admin_token`

### 3.2 Token验证
- ✅ 管理员API使用 `admin_token`
- ✅ 用户API使用 `user_token`
- ✅ 如果token不存在，API调用会失败（401 Unauthorized）
- ✅ 后端会验证token并检查用户权限

## 4. 潜在安全风险分析

### 4.1 用户直接调用管理员API
- **风险**: 用户可能尝试直接调用管理员API
- **防护**: ✅ 已防护
  - 后端 `get_current_admin_user` 会检查 `is_admin` 属性
  - 即使用户使用 `user_token` 调用管理员API，后端会返回 `403 Forbidden`
  - 前端API拦截器会使用正确的token，但即使使用错误的token，后端也会拒绝

### 4.2 敏感信息泄露
- **节点信息**: ✅ 已过滤敏感信息
- **支付配置**: ✅ 公开API只返回非敏感信息
- **系统配置**: ✅ 需要管理员权限
- **软件配置**: ✅ 需要管理员权限

### 4.3 前端路由绕过
- **风险**: 用户可能直接访问管理员路由URL
- **防护**: ✅ 已防护
  - 路由守卫会检查 `requiresAdmin`
  - 非管理员会被重定向到用户仪表盘
  - 即使绕过前端，后端API也会拒绝请求

## 5. 安全建议

### 5.1 已实施的安全措施 ✅
1. ✅ 所有管理员API都有权限验证
2. ✅ 敏感信息已过滤
3. ✅ 前端路由守卫已实施
4. ✅ API拦截器正确识别管理员API
5. ✅ Token分离（admin_token vs user_token）

### 5.2 建议的额外安全措施
1. ⚠️ 考虑添加API访问频率限制（Rate Limiting）
2. ⚠️ 考虑添加IP白名单（可选，用于管理员后台）
3. ⚠️ 考虑添加操作日志记录（部分已实施）
4. ⚠️ 定期审查和更新依赖包

## 6. 结论

### 总体安全评级: ✅ 安全

**关键发现**:
1. ✅ 后端API权限控制完善，所有管理员API都有正确的权限验证
2. ✅ 敏感信息（节点配置、支付密钥等）不会泄露给普通用户
3. ✅ 前端路由守卫和API拦截器正确工作
4. ✅ 即使用户尝试绕过前端直接调用API，后端也会拒绝

**不存在以下漏洞**:
- ❌ 用户无法获取管理员配置信息
- ❌ 用户无法获取节点敏感信息（server, port, password等）
- ❌ 用户无法访问管理员功能
- ❌ 用户无法绕过权限检查

**系统是安全的**，管理员后台地址分离后，安全机制仍然有效。

