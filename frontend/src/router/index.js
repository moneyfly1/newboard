import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { useThemeStore } from '@/store/theme'
import { secureStorage } from '@/utils/secureStorage'
const UserLayout = () => import('@/components/layout/UserLayout.vue')
const AdminLayout = () => import('@/components/layout/AdminLayout.vue')

const routes = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresGuest: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { requiresGuest: true }
  },
  {
    path: '/forgot-password',
    name: 'ForgotPassword',
    component: () => import('@/views/ForgotPassword.vue'),
    meta: { requiresGuest: true }
  },
  
  // 用户端路由
  {
    path: '/',
    component: UserLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { 
          title: '仪表盘',
          breadcrumb: [
            { title: '首页', path: '/dashboard' }
          ]
        }
      },
      {
        path: 'subscription',
        name: 'Subscription',
        component: () => import('@/views/Subscription.vue'),
        meta: { 
          title: '订阅管理',
          breadcrumb: [
            { title: '首页', path: '/dashboard' },
            { title: '订阅管理', path: '/subscription' }
          ]
        }
      },
      {
        path: 'devices',
        name: 'Devices',
        component: () => import('@/views/Devices.vue'),
        meta: { 
          title: '设备管理',
          breadcrumb: [
            { title: '首页', path: '/dashboard' },
            { title: '设备管理', path: '/devices' }
          ]
        }
      },
      {
        path: 'packages',
        name: 'Packages',
        component: () => import('@/views/Packages.vue'),
        meta: { 
          title: '套餐购买',
          breadcrumb: [
            { title: '首页', path: '/dashboard' },
            { title: '套餐购买', path: '/packages' }
          ]
        }
      },
      {
        path: 'orders',
        name: 'Orders',
        component: () => import('@/views/Orders.vue'),
        meta: { 
          title: '订单记录',
          breadcrumb: [
            { title: '首页', path: '/dashboard' },
            { title: '订单记录', path: '/orders' }
          ]
        }
      },
      {
        path: 'nodes',
        name: 'Nodes',
        component: () => import('@/views/Nodes.vue'),
        meta: { 
          title: '节点列表',
          breadcrumb: [
            { title: '首页', path: '/dashboard' },
            { title: '节点列表', path: '/nodes' }
          ]
        }
      },
      {
        path: 'help',
        name: 'Help',
        component: () => import('@/views/Help.vue'),
        meta: { 
          title: '帮助中心',
          breadcrumb: [
            { title: '首页', path: '/dashboard' },
            { title: '帮助中心', path: '/help' }
          ]
        }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/Profile.vue'),
        meta: { 
          title: '个人资料',
          breadcrumb: [
            { title: '首页', path: '/dashboard' },
            { title: '个人资料', path: '/profile' }
          ]
        }
      },
      {
        path: 'login-history',
        name: 'LoginHistory',
        component: () => import('@/views/LoginHistory.vue'),
        meta: { 
          title: '登录历史',
          breadcrumb: [
            { title: '首页', path: '/dashboard' },
            { title: '个人资料', path: '/profile' },
            { title: '登录历史', path: '/login-history' }
          ]
        }
      },
      {
        path: 'tickets',
        name: 'Tickets',
        component: () => import('@/views/Tickets.vue'),
        meta: { 
          title: '工单中心',
          breadcrumb: [
            { title: '首页', path: '/dashboard' },
            { title: '工单中心', path: '/tickets' }
          ]
        }
      },
      {
        path: 'settings',
        name: 'UserSettings',
        component: () => import('@/views/UserSettings.vue'),
        meta: { 
          title: '用户设置',
          breadcrumb: [
            { title: '首页', path: '/dashboard' },
            { title: '用户设置', path: '/settings' }
          ]
        }
      },
      {
        path: 'tutorials',
        name: 'SoftwareTutorials',
        component: () => import('@/views/SoftwareTutorials.vue'),
        meta: { 
          title: '软件教程',
          breadcrumb: [
            { title: '首页', path: '/dashboard' },
            { title: '软件教程', path: '/tutorials' }
          ]
        }
      }
    ]
  },
  
  // 管理端路由
  {
    path: '/admin',
    component: AdminLayout,
    meta: { requiresAuth: true, requiresAdmin: true },
    children: [
      { path: '', redirect: '/admin/dashboard' },
      { path: 'dashboard', name: 'AdminDashboard', component: () => import('@/views/admin/Dashboard.vue'), meta: { title: '管理仪表盘', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }] } },
      { path: 'users', name: 'AdminUsers', component: () => import('@/views/admin/Users.vue'), meta: { title: '用户管理', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '用户管理', path: '/admin/users' }] } },
      { path: 'abnormal-users', name: 'AdminAbnormalUsers', component: () => import('@/views/admin/AbnormalUsers.vue'), meta: { title: '异常用户监控', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '异常用户监控', path: '/admin/abnormal-users' }] } },
      { path: 'config-update', name: 'AdminConfigUpdate', component: () => import('@/views/admin/ConfigUpdate.vue'), meta: { title: '配置更新', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '配置更新', path: '/admin/config-update' }] } },
      { path: 'subscriptions', name: 'AdminSubscriptions', component: () => import('@/views/admin/Subscriptions.vue'), meta: { title: '订阅管理', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '订阅管理', path: '/admin/subscriptions' }] } },
      { path: 'orders', name: 'AdminOrders', component: () => import('@/views/admin/Orders.vue'), meta: { title: '订单管理', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '订单管理', path: '/admin/orders' }] } },
      { path: 'packages', name: 'AdminPackages', component: () => import('@/views/admin/Packages.vue'), meta: { title: '套餐管理', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '套餐管理', path: '/admin/packages' }] } },
      { path: 'payment-config', name: 'AdminPaymentConfig', component: () => import('@/views/admin/PaymentConfig.vue'), meta: { title: '支付配置', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '支付配置', path: '/admin/payment-config' }] } },
      { path: 'settings', name: 'AdminSettings', component: () => import('@/views/admin/Settings.vue'), meta: { title: '系统设置', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '系统设置', path: '/admin/settings' }] } },
      { path: 'notifications', name: 'AdminNotifications', component: () => import('@/views/admin/Notifications.vue'), meta: { title: '通知管理', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '通知管理', path: '/admin/notifications' }] } },
      { path: 'config', name: 'AdminConfig', component: () => import('@/views/admin/Config.vue'), meta: { title: '配置管理', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '配置管理', path: '/admin/config' }] } },
      { path: 'statistics', name: 'AdminStatistics', component: () => import('@/views/admin/Statistics.vue'), meta: { title: '数据统计', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '数据统计', path: '/admin/statistics' }] } },
      { path: 'email-queue', name: 'AdminEmailQueue', component: () => import('@/views/admin/EmailQueue.vue'), meta: { title: '邮件队列管理', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '邮件队列管理', path: '/admin/email-queue' }] } },
              { path: 'email-detail/:id', name: 'AdminEmailDetail', component: () => import('@/views/admin/EmailDetail.vue'), meta: { title: '邮件详情', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '邮件队列管理', path: '/admin/email-queue' }, { title: '邮件详情', path: '/admin/email-detail' }] } },
        { path: 'profile', name: 'AdminProfile', component: () => import('@/views/admin/Profile.vue'), meta: { title: '个人资料', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '个人资料', path: '/admin/profile' }] } },
        { path: 'system-logs', name: 'AdminSystemLogs', component: () => import('@/views/admin/SystemLogs.vue'), meta: { title: '系统日志', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '系统日志', path: '/admin/system-logs' }] } },
        { path: 'coupons', name: 'AdminCoupons', component: () => import('@/views/admin/Coupons.vue'), meta: { title: '优惠券管理', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '优惠券管理', path: '/admin/coupons' }] } },
        { path: 'tickets', name: 'AdminTickets', component: () => import('@/views/admin/Tickets.vue'), meta: { title: '工单管理', breadcrumb: [{ title: '管理后台', path: '/admin/dashboard' }, { title: '工单管理', path: '/admin/tickets' }] } }
    ]
  },
  
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 导航守卫
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  
  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - CBoard`
  }
  
  // 检查URL参数中是否有sessionKey（用于管理员以用户身份登录）
  if (to.query.sessionKey) {
    try {
      const sessionKey = to.query.sessionKey
      const loginData = sessionStorage.getItem(sessionKey)
      
      if (loginData) {
        const loginDataObj = JSON.parse(loginData)
        const { token: userToken, user: userData, timestamp: dataTimestamp } = loginDataObj
        
        // 检查数据是否过期（5分钟内有效）
        if (Date.now() - dataTimestamp > 5 * 60 * 1000) {
          sessionStorage.removeItem(sessionKey)
          // 使用动态导入避免阻塞
          import('element-plus').then(({ ElMessage }) => {
            ElMessage.error('登录信息已过期，请重新操作')
          })
          next('/login')
          return
        }
        
        // 清除临时sessionKey
        sessionStorage.removeItem(sessionKey)
        
        // 确保用户数据中的 is_admin 为 false（管理员以用户身份登录时，用户不是管理员）
        const finalUserData = {
          ...userData,
          is_admin: false
        }
        
        // 使用sessionStorage保存用户token和用户信息（不覆盖localStorage中的管理员token）
        secureStorage.set('user_token', userToken, true, 24 * 60 * 60 * 1000)
        secureStorage.set('user_data', finalUserData, true, 24 * 60 * 60 * 1000)
        
        // 设置authStore中的用户token和用户信息（使用sessionStorage）
        authStore.setAuth(userToken, finalUserData, true)
        
        const themeStore = useThemeStore()
        themeStore.loadUserTheme().catch(() => {})
        
        // 如果当前路径是管理员路径，重定向到用户仪表盘
        if (to.path.startsWith('/admin')) {
          next('/dashboard')
          return
        }
        
        // 清除URL参数
        const newQuery = { ...to.query }
        delete newQuery.sessionKey
        next({ path: to.path, query: newQuery, replace: true })
        return
      }
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.error('Failed to parse user login data:', error)
      }
    }
  }
  
  // 兼容旧的URL参数方式（token和user）
  if (to.query.token && to.query.user) {
    try {
      const userToken = to.query.token
      const userData = JSON.parse(decodeURIComponent(to.query.user))
      
      // 使用sessionStorage保存用户token和用户信息
      secureStorage.set('user_token', userToken, true, 24 * 60 * 60 * 1000)
      secureStorage.set('user_data', userData, true, 24 * 60 * 60 * 1000)
      
      // 设置authStore中的用户token和用户信息
      authStore.setAuth(userToken, userData, true)
      
      const themeStore = useThemeStore()
      themeStore.loadUserTheme().catch(() => {})
      
      // 清除URL参数，避免暴露token
      const newQuery = { ...to.query }
      delete newQuery.token
      delete newQuery.user
      next({ path: to.path, query: newQuery, replace: true })
      return
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.error('Failed to parse user token from URL:', error)
      }
    }
  }
  
  if (to.path.startsWith('/admin')) {
    const adminToken = secureStorage.get('admin_token') || secureStorage.get('token')
    const adminUserRaw = secureStorage.get('admin_user') || secureStorage.get('user')
    
    if (adminToken && adminUserRaw) {
      try {
        // 如果已经是对象，直接使用；如果是字符串，则解析
        const adminUserData = typeof adminUserRaw === 'string' ? JSON.parse(adminUserRaw) : adminUserRaw
        // 如果当前不是管理员身份，或者token不匹配，恢复管理员身份
        if (!authStore.isAdmin || authStore.token !== adminToken) {
          // 管理员路由使用localStorage
          authStore.setAuth(adminToken, adminUserData, false)
          
          const themeStore = useThemeStore()
          themeStore.loadUserTheme().catch(() => {})
        }
      } catch (error) {
        if (process.env.NODE_ENV === 'development') {
          console.error('Failed to restore admin auth:', error)
        }
      }
    }
  }
  
  // 页面加载时，根据路由类型恢复认证状态
  // 如果是管理员路由，使用localStorage；如果是用户路由，优先使用sessionStorage
  // 注意：如果已经通过 sessionKey 设置了用户信息，则不再恢复认证状态（避免覆盖）
  if (!authStore.isAuthenticated) {
    let token = null
    let userData = null
    
    if (to.path.startsWith('/admin')) {
      token = secureStorage.get('admin_token') || secureStorage.get('token')
      const adminUserStr = secureStorage.get('admin_user') || secureStorage.get('user')
      if (adminUserStr) {
        try {
          userData = JSON.parse(adminUserStr)
        } catch (e) {
          // 忽略解析错误
        }
      }
    } else {
      token = secureStorage.get('user_token') || secureStorage.get('token')
      const userDataStr = secureStorage.get('user_data') || secureStorage.get('user')
      if (userDataStr) {
        try {
          userData = typeof userDataStr === 'string' ? JSON.parse(userDataStr) : userDataStr
        } catch (e) {
          // 忽略解析错误
        }
      }
    }
    
    if (token && userData) {
      try {
        // 恢复认证状态
        const useSessionStorage = !to.path.startsWith('/admin')
        authStore.setAuth(token, userData, useSessionStorage)
        
        const themeStore = useThemeStore()
        themeStore.loadUserTheme().catch(() => {})
      } catch (error) {
        if (to.path.startsWith('/admin')) {
          secureStorage.remove('admin_token')
          secureStorage.remove('admin_user')
        } else {
          secureStorage.remove('user_token')
          secureStorage.remove('user_data')
        }
        secureStorage.remove('token')
        secureStorage.remove('refresh_token')
        secureStorage.remove('user')
      }
    }
  }
  
  // 需要认证的页面
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
    return
  }
  
  // 需要管理员权限的页面
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    // 如果不是管理员，重定向到普通用户仪表盘
    next('/dashboard')
    return
  }
  
  // 已登录用户不能访问登录/注册页面
  if (to.meta.requiresGuest && authStore.isAuthenticated) {
    // 根据用户权限重定向
    if (authStore.isAdmin) {
      next('/admin/dashboard')
    } else {
      next('/dashboard')
    }
    return
  }
  
  // 如果用户访问根路径，根据权限重定向
  if (to.path === '/') {
    if (authStore.isAdmin) {
      next('/admin/dashboard')
    } else {
      next('/dashboard')
    }
    return
  }
  
  next()
})

export default router 