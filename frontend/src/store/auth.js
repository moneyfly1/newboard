import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, resetRefreshFailed } from '@/utils/api'
import { useThemeStore } from '@/store/theme'
import { secureStorage } from '@/utils/secureStorage'

export const useAuthStore = defineStore('auth', () => {
  const isAdminPath = () => typeof window !== 'undefined' && window.location.pathname.startsWith('/admin')
  const TOKEN_TTL = 24 * 60 * 60 * 1000
  const REFRESH_TOKEN_TTL = 7 * 24 * 60 * 60 * 1000

  const getInitialToken = () => {
    if (typeof window === 'undefined') return secureStorage.get('token') || ''
    const path = window.location.pathname
    if (path.startsWith('/admin')) {
      return secureStorage.get('admin_token') || secureStorage.get('token') || ''
    }
    return secureStorage.get('user_token') || secureStorage.get('token') || ''
  }

  const getInitialUser = () => {
    try {
      if (typeof window === 'undefined') return secureStorage.get('user')
      const path = window.location.pathname
      if (path.startsWith('/admin')) {
        return secureStorage.get('admin_user') || secureStorage.get('user')
      }
      return secureStorage.get('user_data') || secureStorage.get('user')
    } catch (error) {
      secureStorage.remove('user_data')
      secureStorage.remove('user')
      return null
    }
  }

  const saveToken = (accessToken) => {
    const admin = isAdminPath()
    secureStorage.set('token', accessToken, !admin, TOKEN_TTL)
    if (admin) {
      secureStorage.set('admin_token', accessToken, false, TOKEN_TTL)
    } else {
      secureStorage.set('user_token', accessToken, true, TOKEN_TTL)
    }
  }

  const saveUser = (userData) => {
    const admin = isAdminPath()
    secureStorage.set('user', userData, !admin, TOKEN_TTL)
    if (admin) {
      secureStorage.set('admin_user', userData, false, TOKEN_TTL)
    } else {
      secureStorage.set('user_data', userData, true, TOKEN_TTL)
    }
  }

  const token = ref(getInitialToken())
  const user = ref(getInitialUser())
  const loading = ref(false)
  const isAuthenticated = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.is_admin || false)

  const handleApiError = (error, defaultMessage) => {
    const message = error.response?.data?.detail || error.message || defaultMessage
    return {
      success: false,
      message
    }
  }

  const login = async (credentials) => {
    loading.value = true
    try {
      const response = await api.post('/auth/login-json', {
        username: credentials.username,
        password: credentials.password
      })
      const { access_token, refresh_token, user: userData } = response.data
      token.value = access_token
      user.value = userData
      const admin = isAdminPath()
      secureStorage.set('token', access_token, !admin, TOKEN_TTL)
      secureStorage.set('refresh_token', refresh_token, !admin, REFRESH_TOKEN_TTL)
      secureStorage.set('user', userData, !admin, TOKEN_TTL)
      if (admin) {
        secureStorage.set('admin_token', access_token, false, TOKEN_TTL)
        secureStorage.set('admin_user', userData, false, TOKEN_TTL)
        secureStorage.set('admin_refresh_token', refresh_token, false, REFRESH_TOKEN_TTL)
      } else {
        secureStorage.set('user_token', access_token, true, TOKEN_TTL)
        secureStorage.set('user_data', userData, true, TOKEN_TTL)
        secureStorage.set('user_refresh_token', refresh_token, true, REFRESH_TOKEN_TTL)
      }
      resetRefreshFailed()
      try {
        const themeStore = useThemeStore()
        await themeStore.loadUserTheme()
      } catch (themeError) {
        // 主题加载失败不影响登录流程
      }
      return { success: true }
    } catch (error) {
      return handleApiError(error, '登录失败')
    } finally {
      loading.value = false
    }
  }

  const register = async (userData) => {
    loading.value = true
    try {
      const response = await api.post('/auth/register', userData)
      return { success: true, message: '注册成功', data: response.data }
    } catch (error) {
      return handleApiError(error, '注册失败')
    } finally {
      loading.value = false
    }
  }

  const logout = () => {
    token.value = ''
    user.value = null
    const admin = isAdminPath()
    
    // 清除所有角色的token和用户数据
    if (admin) {
      secureStorage.remove('admin_token')
      secureStorage.remove('admin_user')
      secureStorage.remove('admin_refresh_token')
    } else {
      secureStorage.remove('user_token')
      secureStorage.remove('user_data')
      secureStorage.remove('user_refresh_token')
    }
    
    // 清除通用的token和用户数据（可能被两个角色共享）
    secureStorage.remove('token')
    secureStorage.remove('refresh_token')
    secureStorage.remove('user')
    
    // 重置刷新失败标志
    resetRefreshFailed()
  }

  const refreshToken = async () => {
    const refresh_token = secureStorage.get('refresh_token')
    if (!refresh_token) {
      logout()
      return false
    }
    try {
      const response = await api.post('/auth/refresh', { refresh_token }, { withCredentials: true })
      const { access_token } = response.data
      token.value = access_token
      saveToken(access_token)
      return true
    } catch (error) {
      logout()
      return false
    }
  }

  const forgotPassword = async (email) => {
    loading.value = true
    try {
      await api.post('/auth/forgot-password', { email })
      return { success: true, message: '重置链接已发送到您的邮箱，请查收' }
    } catch (error) {
      return handleApiError(error, '发送失败')
    } finally {
      loading.value = false
    }
  }

  const updateUser = (userData) => {
    user.value = { ...user.value, ...userData }
    saveUser(user.value)
  }

  const changePassword = async (oldPassword, newPassword) => {
    loading.value = true
    try {
      await api.post('/users/change-password', {
        old_password: oldPassword,
        new_password: newPassword
      })
      return { success: true, message: '密码修改成功' }
    } catch (error) {
      return handleApiError(error, '密码修改失败')
    } finally {
      loading.value = false
    }
  }

  const setAuth = (newToken, newUser, useSessionStorage = false) => {
    token.value = newToken
    user.value = newUser
    if (useSessionStorage) {
      secureStorage.set('user_token', newToken, true, TOKEN_TTL)
      secureStorage.set('user_data', newUser, true, TOKEN_TTL)
    } else {
      secureStorage.set('token', newToken, false, TOKEN_TTL)
      secureStorage.set('user', newUser, false, TOKEN_TTL)
      secureStorage.set('admin_token', newToken, false, TOKEN_TTL)
      secureStorage.set('admin_user', newUser, false, TOKEN_TTL)
    }
  }

  const setToken = (newToken) => {
    token.value = newToken
    saveToken(newToken)
  }

  const setUser = (newUser) => {
    user.value = newUser
    saveUser(newUser)
  }

  const getCurrentState = () => ({
    token: token.value,
    user: user.value,
    isAuthenticated: isAuthenticated.value,
    isAdmin: isAdmin.value,
    storedUser: secureStorage.get('user') || secureStorage.get('user_data') || secureStorage.get('admin_user'),
    storedToken: secureStorage.get('token') || secureStorage.get('user_token') || secureStorage.get('admin_token')
  })

  return {
    token,
    user,
    loading,
    isAuthenticated,
    isAdmin,
    login,
    register,
    logout,
    refreshToken,
    forgotPassword,
    updateUser,
    changePassword,
    setAuth,
    setToken,
    setUser,
    getCurrentState
  }
}) 