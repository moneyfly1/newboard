import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'

import App from './App.vue'
import router from './router'
import { useSettingsStore } from './store/settings'
import { useAuthStore } from './store/auth'
import { useThemeStore } from './store/theme'

// 导入全局样式
import './styles/global.scss'
import './styles/mobile-buttons.scss'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus, {
  locale: zhCn,
})

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.config.errorHandler = (err, vm, info) => {
  if (process.env.NODE_ENV === 'development') {
    console.error('Vue error:', err, info)
  }
}

// 全局属性
app.config.globalProperties.$settings = null
app.config.globalProperties.$auth = null

// 初始化应用
async function initializeApp() {
  try {
    // 设置全局属性
    app.config.globalProperties.$auth = useAuthStore()
    
    // 先挂载应用
    app.mount('#app')
    
    // 异步加载设置（不阻塞应用启动）
    try {
      const settingsStore = useSettingsStore()
      await settingsStore.loadSettings()
      app.config.globalProperties.$settings = settingsStore
    } catch (settingsError) {
      if (process.env.NODE_ENV === 'development') {
        console.error('Settings load error:', settingsError)
      }
    }
    
    // 初始化主题系统
    try {
      const settingsStore = useSettingsStore()
      const themeStore = useThemeStore()
      
      // 等待设置加载完成
      await settingsStore.loadSettings()
      
      if (settingsStore.defaultTheme) {
        if (!settingsStore.allowUserTheme) {
          themeStore.applyTheme(settingsStore.defaultTheme)
          themeStore.currentTheme = settingsStore.defaultTheme
          if (typeof window !== 'undefined') {
            localStorage.setItem('user-theme', settingsStore.defaultTheme)
          }
        } else {
          const userTheme = typeof window !== 'undefined' ? localStorage.getItem('user-theme') : null
          if (userTheme && settingsStore.availableThemes && settingsStore.availableThemes.includes(userTheme)) {
            themeStore.applyTheme(userTheme)
            themeStore.currentTheme = userTheme
          } else {
            themeStore.applyTheme(settingsStore.defaultTheme)
            themeStore.currentTheme = settingsStore.defaultTheme
            if (typeof window !== 'undefined') {
              localStorage.setItem('user-theme', settingsStore.defaultTheme)
            }
          }
        }
      } else {
        themeStore.initTheme()
        await themeStore.loadUserTheme()
      }
    } catch (themeError) {
      if (process.env.NODE_ENV === 'development') {
        console.error('Theme initialization error:', themeError)
      }
      const themeStore = useThemeStore()
      themeStore.applyTheme('light')
    }
  } catch (error) {
    if (process.env.NODE_ENV === 'development') {
      console.error('App initialization error:', error)
    }
    app.mount('#app')
  }
}

// 启动应用
initializeApp() 