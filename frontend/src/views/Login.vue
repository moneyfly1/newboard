<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <h1>CBoard Modern</h1>
        <p>现代化订阅管理系统</p>
      </div>
      
      <form class="login-form" @submit.prevent="handleLogin">
        <div class="form-item">
          <input
            v-model="loginForm.username"
            type="text"
            placeholder="用户名或邮箱"
            class="login-input"
            autocomplete="username"
            name="username"
            id="username"
            required
          />
        </div>
        
        <div class="form-item">
          <input
            v-model="loginForm.password"
            type="password"
            placeholder="密码"
            class="login-input"
            autocomplete="current-password"
            name="password"
            id="password"
            required
            @keyup.enter="handleLogin"
          />
        </div>
        
        <div class="form-item">
          <button
            type="submit"
            :disabled="loading"
            class="login-button"
          >
            {{ loading ? '登录中...' : '登录' }}
          </button>
        </div>
      </form>
      
      <div class="form-item">
        <button
          type="button"
          class="debug-button"
          @click="checkState"
        >
          检查状态
        </button>
      </div>
      
      <div class="login-actions">
        <el-link type="primary" @click="$router.push('/register')">
          注册账户
        </el-link>
        <el-link type="primary" @click="$router.push('/forgot-password')">
          忘记密码？
        </el-link>
      </div>
    </div>
    
    <!-- 忘记密码对话框 -->
    <el-dialog
      v-model="showForgotPassword"
      title="忘记密码"
      width="400px"
    >
      <el-form
        ref="forgotForm"
        :model="forgotForm"
        :rules="forgotRules"
      >
        <el-form-item prop="email">
                  <el-input
          v-model="forgotForm.email"
          placeholder="请输入邮箱地址"
          type="email"
        />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showForgotPassword = false">取消</el-button>
        <el-button 
          type="primary" 
          :loading="forgotLoading"
          @click="handleForgotPassword"
        >
          发送重置邮件
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, nextTick, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/store/auth'

export default {
  name: 'Login',
  setup() {
    const router = useRouter()
    const route = useRoute()
    const authStore = useAuthStore()
    
    const loginForm = reactive({
      username: '',
      password: ''
    })
    
    // 从URL参数中获取用户名（注册成功后跳转）
    onMounted(() => {
      if (route.query.username) {
        loginForm.username = route.query.username
        // 如果是从注册页面跳转过来的，显示提示
        if (route.query.registered === 'true') {
          ElMessage.success('注册成功！请输入密码登录')
        }
      }
    })
    
    const forgotForm = reactive({
      email: ''
    })
    
    const loading = ref(false)
    const forgotLoading = ref(false)
    const showForgotPassword = ref(false)
    
    const loginRules = {
      username: [
        { required: true, message: '请输入用户名或邮箱', trigger: 'blur' }
      ],
      password: [
        { required: true, message: '请输入密码', trigger: 'blur' },
        { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
      ]
    }
    
    const forgotRules = {
      email: [
        { required: true, message: '请输入邮箱地址', trigger: 'blur' },
        { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
      ]
    }
    
    const handleLogin = async () => {
      loading.value = true

      try {
        const result = await authStore.login(loginForm)

        if (result.success) {
          ElMessage.success('登录成功')

          // 确保用户信息已经更新后再跳转
          await nextTick()

          // 根据用户权限跳转到不同页面
          if (authStore.isAdmin) {
            await router.push('/admin/dashboard')
          } else {
            await router.push('/dashboard')
          }
        } else {
          ElMessage.error(result.message)
        }
      } catch (error) {
        ElMessage.error('登录失败，请重试')
      } finally {
        loading.value = false
      }
    }
    
    const handleForgotPassword = async () => {
      forgotLoading.value = true
      
      try {
        const result = await authStore.forgotPassword(forgotForm.email)
        if (result.success) {
          ElMessage.success(result.message)
          showForgotPassword.value = false
          forgotForm.email = ''
        } else {
          ElMessage.error(result.message)
        }
      } catch (error) {
        ElMessage.error('发送失败，请重试')
      } finally {
        forgotLoading.value = false
      }
    }

    const checkState = () => {
      if (process.env.NODE_ENV === 'development') {
        const authStore = useAuthStore()
        const state = authStore.getCurrentState()
        console.log('当前认证状态:', state)
      }
    }
    
    return {
      loginForm,
      forgotForm,
      loading,
      forgotLoading,
      showForgotPassword,
      loginRules,
      forgotRules,
      handleLogin,
      handleForgotPassword,
      checkState
    }
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-box {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  padding: 40px;
  width: 100%;
  max-width: 400px;
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.login-header h1 {
  color: #1677ff;
  font-size: 28px;
  margin-bottom: 8px;
  font-weight: 600;
}

.login-header :is(p) {
  color: #666;
  font-size: 14px;
  margin: 0;
}

.login-form {
  margin-top: 20px;
}

.form-item {
  margin-bottom: 20px;
}

.login-input {
  width: 100%;
  height: 44px;
  padding: 0 16px;
  border: 1px solid #dcdfe6;
  border-radius: 0; /* 移除圆角，设置为长方形 */
  font-size: 16px;
  outline: none;
  transition: border-color 0.3s;
  box-shadow: none !important;
  background-color: #ffffff !important;
}

/* 移除Element Plus输入框的阴影效果 */
:deep(.el-input__wrapper) {
  border-radius: 0 !important;
  box-shadow: none !important;
  border: 1px solid #dcdfe6 !important;
  background-color: #ffffff !important;
}

:deep(.el-input__inner) {
  border-radius: 0 !important;
  border: none !important;
  box-shadow: none !important;
  background-color: transparent !important;
}

:deep(.el-input__wrapper:hover) {
  border-color: #c0c4cc !important;
  box-shadow: none !important;
  background-color: #ffffff !important;
}

:deep(.el-input__wrapper.is-focus) {
  border-color: #1677ff !important;
  box-shadow: none !important;
  background-color: #ffffff !important;
}

/* 确保聚焦时背景颜色不变 */
:deep(.el-input__wrapper.is-focus:hover) {
  background-color: #ffffff !important;
}

.login-input:focus {
  border-color: #1677ff;
  box-shadow: none !important;
  background-color: #ffffff !important;
}

.login-input::placeholder {
  color: #a8abb2;
}

.login-button {
  width: 100%;
  height: 44px;
  font-size: 16px;
  font-weight: 500;
  background: #1677ff;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.login-button:hover:not(:disabled) {
  background: #0958d9;
}

.login-button:disabled {
  background: #a8abb2;
  cursor: not-allowed;
}

.debug-button {
  width: 100%;
  height: 44px;
  font-size: 16px;
  font-weight: 500;
  background: #409eff; /* A different color for debugging */
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.debug-button:hover:not(:disabled) {
  background: #3a8ee6;
}

.debug-button:disabled {
  background: #a8abb2;
  cursor: not-allowed;
}

.login-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
  font-size: 14px;
}

@media (max-width: 480px) {
  .login-box {
    padding: 30px 20px;
  }
  
  .login-header h1 {
    font-size: 24px;
  }
}
</style> 