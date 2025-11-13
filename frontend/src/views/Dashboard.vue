<template>
  <div class="list-container dashboard-container">
    <!-- 欢迎横幅 -->
    <div class="welcome-banner">
      <div class="banner-content">
        <div class="welcome-text">
          <h1 class="welcome-title">欢迎回来，{{ userInfo.username }}！</h1>
          <p class="welcome-subtitle">享受高速稳定的网络服务体验</p>
        </div>
        <div class="welcome-icon">
          <i class="fas fa-rocket"></i>
        </div>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">
          <i class="fas fa-crown"></i>
        </div>
        <div class="stat-content">
          <h3 class="stat-title">{{ userInfo.membership || '普通会员' }}</h3>
          <p class="stat-subtitle">到期时间：{{ formatDate(userInfo.expire_time) }}</p>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon">
          <i class="fas fa-mobile-alt"></i>
        </div>
        <div class="stat-content">
          <h3 class="stat-title">{{ subscriptionInfo.currentDevices || 0 }}/{{ subscriptionInfo.maxDevices || 0 }}</h3>
          <p class="stat-subtitle">设备使用</p>
        </div>
      </div>

      <div class="stat-card balance-card">
        <div class="stat-icon">
          <i class="fas fa-wallet"></i>
        </div>
        <div class="stat-content">
          <h3 class="stat-title">¥ {{ userInfo.balance || '0.00' }}</h3>
          <p class="stat-subtitle">账户余额</p>
          <el-button 
            type="primary" 
            class="recharge-btn"
            @click="showRechargeDialog"
          >
            <i class="fas fa-plus"></i>
            充值
          </el-button>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon">
          <i class="fas fa-tachometer-alt"></i>
        </div>
        <div class="stat-content">
          <h3 class="stat-title">不限</h3>
          <p class="stat-subtitle">宽带速率</p>
        </div>
      </div>

      <div class="stat-card remaining-time-card">
        <div class="stat-content">
          <div class="remaining-time-main">
            <h3 class="remaining-time-title">用户剩余时间</h3>
            <div class="remaining-time-value">
              <span class="time-number">{{ subscriptionInfo.remainingDays || 0 }}</span>
              <span class="time-unit">天</span>
            </div>
            <p class="expiry-date">到期时间：{{ formatDate(subscriptionInfo.expiryDate) || '未设置' }}</p>
          </div>
          <el-button 
            type="primary" 
            class="renew-btn"
            @click="goToPackages"
          >
            <i class="fas fa-sync-alt"></i>
            续费
          </el-button>
        </div>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="main-content">
      <!-- 左侧内容 -->
      <div class="left-content">
        <!-- 公告卡片 -->
        <div class="card announcement-card">
          <div class="card-header">
            <h3 class="card-title">
              <i class="fas fa-bullhorn"></i>
              最新公告
            </h3>
          </div>
          <div class="card-body">
            <div v-if="announcements.length > 0" class="announcement-list">
              <div 
                v-for="announcement in announcements.slice(0, 3)" 
                :key="announcement.id"
                class="announcement-item"
                @click="showAnnouncementDetail(announcement)"
              >
                <div class="announcement-content">
                  <h4 class="announcement-title">{{ announcement.title }}</h4>
                  <p class="announcement-preview">{{ announcement.content.substring(0, 100) }}...</p>
                  <span class="announcement-time">{{ formatDate(announcement.created_at) }}</span>
                </div>
                <div class="announcement-arrow">
                  <i class="fas fa-chevron-right"></i>
                </div>
              </div>
            </div>
            <div v-else class="no-announcements">
              <i class="fas fa-inbox"></i>
              <p>暂无公告</p>
            </div>
          </div>
        </div>

        <!-- 使用教程卡片 -->
        <div class="card tutorial-card">
          <div class="card-header">
            <h3 class="card-title">
              <i class="fas fa-graduation-cap"></i>
              使用教程
            </h3>
          </div>
          <div class="card-body">
            <div class="tutorial-tabs">
              <div 
                v-for="platform in platforms" 
                :key="platform.name"
                class="tutorial-tab"
                :class="{ active: activePlatform === platform.name }"
                @click="activePlatform = platform.name"
              >
                <i :class="platform.icon"></i>
                <span>{{ platform.name }}</span>
              </div>
            </div>
            
            <div class="tutorial-content">
              <div 
                v-for="platform in platforms" 
                :key="platform.name"
                v-show="activePlatform === platform.name"
                class="tutorial-platform"
              >
                <div 
                  v-for="app in platform.apps" 
                  :key="app.name"
                  class="tutorial-app"
                >
                  <div class="app-info">
                    <div class="app-details">
                      <h4 class="app-name">{{ app.name }}</h4>
                      <p class="app-version">{{ app.version }}</p>
                    </div>
                  </div>
                  <div class="app-actions">
                    <el-button type="primary" size="small" @click="downloadApp(app.downloadKey)">
                      立即下载
                    </el-button>
                    <el-button type="default" size="small" @click="openTutorial(app.tutorialUrl)">
                      安装教程
                    </el-button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧内容 -->
      <div class="right-content">
        <!-- 订阅地址卡片 -->
        <div class="card subscription-card">
          <div class="card-header">
            <h3 class="card-title">
              <i class="fas fa-link"></i>
              订阅地址
            </h3>
          </div>
          <div class="card-body">
            <!-- Clash系列软件 -->
            <div class="software-category">
              <h4 class="category-title">
                <i class="fas fa-bolt"></i>
                Clash系列软件
              </h4>
              <div class="subscription-buttons">
                <div class="subscription-group">
                  <el-dropdown @command="handleClashCommand" trigger="click">
                    <el-button type="primary" class="clash-btn">
                      <i class="fas fa-bolt"></i>
                      Clash
                      <i class="fas fa-chevron-down"></i>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="copy-clash">复制订阅</el-dropdown-item>
                        <el-dropdown-item command="import-clash">一键导入</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>

                <div class="subscription-group">
                  <el-dropdown @command="handleFlashCommand" trigger="click">
                    <el-button type="primary" class="flash-btn">
                      <i class="fas fa-flash"></i>
                      Flash
                      <i class="fas fa-chevron-down"></i>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="copy-flash">复制订阅</el-dropdown-item>
                        <el-dropdown-item command="import-flash">一键导入</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>

                <div class="subscription-group">
                  <el-dropdown @command="handleMohomoCommand" trigger="click">
                    <el-button type="primary" class="mohomo-btn">
                      <i class="fas fa-cube"></i>
                      Mohomo Part
                      <i class="fas fa-chevron-down"></i>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="copy-mohomo">复制订阅</el-dropdown-item>
                        <el-dropdown-item command="import-mohomo">一键导入</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>

                <div class="subscription-group">
                  <el-dropdown @command="handleSparkleCommand" trigger="click">
                    <el-button type="primary" class="sparkle-btn">
                      <i class="fas fa-sparkles"></i>
                      Sparkle
                      <i class="fas fa-chevron-down"></i>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="copy-sparkle">复制订阅</el-dropdown-item>
                        <el-dropdown-item command="import-sparkle">一键导入</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </div>
            </div>

            <!-- V2Ray系列软件 -->
            <div class="software-category">
              <h4 class="category-title">
                <i class="fas fa-shield-alt"></i>
                V2Ray系列软件
              </h4>
              <div class="subscription-buttons">
                <div class="subscription-group">
                  <el-button type="info" class="v2ray-btn" @click="copyV2raySubscription">
                    <i class="fas fa-shield-alt"></i>
                    复制 V2Ray 订阅
                  </el-button>
                </div>

                <div class="subscription-group">
                  <el-button type="info" class="hiddify-btn" @click="copyHiddifySubscription">
                    <i class="fas fa-eye"></i>
                    复制 Hiddify Next 订阅
                  </el-button>
                </div>
              </div>
            </div>

            <!-- Shadowrocket -->
            <div class="software-category">
              <h4 class="category-title">
                <i class="fas fa-rocket"></i>
                iOS软件
              </h4>
              <div class="subscription-buttons">
                <div class="subscription-group">
                  <el-dropdown @command="handleShadowrocketCommand" trigger="click">
                    <el-button type="success" class="shadowrocket-btn">
                      <i class="fas fa-rocket"></i>
                      Shadowrocket
                      <i class="fas fa-chevron-down"></i>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="copy-shadowrocket">复制订阅</el-dropdown-item>
                        <el-dropdown-item command="import-shadowrocket">一键导入</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </div>
            </div>

            <!-- 订阅地址显示区域 -->
            <div class="subscription-urls-section">
              <h4 class="section-title">
                <i class="fas fa-link"></i>
                订阅地址
              </h4>
              <div class="url-display">
                <div class="url-item">
                  <label>Clash订阅地址：</label>
                  <div class="url-input-group">
                    <el-input 
                      :value="userInfo.clashUrl" 
                      readonly 
                      size="small"
                      class="url-input"
                    >
                      <template #append>
                        <el-button @click="copyClashSubscription" size="small">
                          <i class="fas fa-copy"></i>
                        </el-button>
                      </template>
                    </el-input>
                  </div>
                </div>
                <div class="url-item">
                  <label>通用订阅地址：</label>
                  <div class="url-input-group">
                    <el-input 
                      :value="userInfo.mobileUrl" 
                      readonly 
                      size="small"
                      class="url-input"
                    >
                      <template #append>
                        <el-button @click="copyUniversalSubscription" size="small">
                          <i class="fas fa-copy"></i>
                        </el-button>
                      </template>
                    </el-input>
                  </div>
                </div>
              </div>
            </div>

            <!-- 二维码区域 -->
            <div class="qr-code-section">
              <h4 class="section-title">
                <i class="fas fa-qrcode"></i>
                二维码
              </h4>
              <div class="qr-code-container">
                <div class="qr-code">
                  <img :src="qrCodeUrl" alt="订阅二维码" v-if="qrCodeUrl">
                  <div v-else class="qr-placeholder">
                    <i class="fas fa-qrcode"></i>
                    <p>二维码生成中...</p>
                  </div>
                </div>
                <p class="qr-tip">扫描二维码即可在Shadowrocket中添加订阅</p>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>

    <!-- 公告详情对话框 -->
    <el-dialog
      v-model="announcementDialogVisible"
      :title="selectedAnnouncement?.title"
      width="60%"
      :before-close="closeAnnouncementDialog"
    >
      <div v-if="selectedAnnouncement" class="announcement-detail">
        <div class="announcement-meta">
          <span class="announcement-time">{{ formatDate(selectedAnnouncement.created_at) }}</span>
        </div>
        <div class="announcement-content" v-html="selectedAnnouncement.content"></div>
      </div>
    </el-dialog>

    <!-- 充值对话框 -->
    <el-dialog
      v-model="rechargeDialogVisible"
      title="账户充值"
      width="500px"
      class="recharge-dialog"
    >
      <el-form :model="rechargeForm" :rules="rechargeRules" ref="rechargeFormRef" label-width="100px">
        <el-form-item label="充值金额" prop="amount">
          <el-input-number
            v-model="rechargeForm.amount"
            :min="20"
            :step="1"
            :precision="2"
            placeholder="请输入充值金额"
            style="width: 100%"
          >
            <template #prepend>¥</template>
          </el-input-number>
          <div class="amount-tips">
            <p>最低充值金额20元，可自定义金额</p>
            <div class="quick-amounts">
              <el-button 
                v-for="amount in quickAmounts" 
                :key="amount"
                size="small"
                :type="rechargeForm.amount === amount ? 'primary' : 'default'"
                @click="selectQuickAmount(amount)"
              >
                ¥{{ amount }}
              </el-button>
            </div>
          </div>
        </el-form-item>
      </el-form>
      
      <!-- 支付二维码 -->
      <div v-if="rechargeQRCode" class="recharge-qr-section">
        <h4>请使用支付宝扫描二维码完成支付</h4>
        <div class="qr-code-wrapper">
          <img :src="rechargeQRCode" alt="支付二维码" class="qr-code-img" />
        </div>
        <p class="qr-tip">支付完成后，余额将自动到账</p>
      </div>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="rechargeDialogVisible = false">取消</el-button>
          <el-button 
            type="primary" 
            @click="createRecharge" 
            :loading="rechargeLoading"
            :disabled="!!rechargeQRCode"
          >
            {{ rechargeQRCode ? '支付中...' : '确认充值' }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { userAPI, subscriptionAPI, softwareConfigAPI, rechargeAPI } from '@/utils/api'

const router = useRouter()

// 响应式数据
const userInfo = ref({
  username: '用户',
  email: '',
  membership: '普通会员',
  expire_time: null,
  expiryDate: '未设置',
  remaining_days: 0,
  online_devices: 0,
  total_devices: 0,
  balance: '0.00',
  speed_limit: '不限速',
  subscription_url: '',
  subscription_status: 'inactive',
  clashUrl: '',
  v2rayUrl: '',
  mobileUrl: '',
  qrcodeUrl: ''
})

const subscriptionInfo = ref({
  currentDevices: 0,
  maxDevices: 0,
  remainingDays: 0,
  expiryDate: '未设置',
  status: 'inactive'
})

const announcements = ref([])
const announcementDialogVisible = ref(false)
const selectedAnnouncement = ref(null)

// 充值相关
const rechargeDialogVisible = ref(false)
const rechargeForm = ref({
  amount: 20
})
const rechargeRules = {
  amount: [
    { required: true, message: '请输入充值金额', trigger: 'blur' },
    { type: 'number', min: 20, message: '充值金额不能少于20元', trigger: 'blur' }
  ]
}
const rechargeFormRef = ref()
const rechargeLoading = ref(false)
const rechargeQRCode = ref('')
const quickAmounts = [20, 50, 100, 200, 500, 1000]
const softwareConfig = ref({
  // Windows软件
  clash_windows_url: '',
  v2rayn_url: '',
  mihomo_windows_url: '',
  sparkle_windows_url: '',
  hiddify_windows_url: '',
  flash_windows_url: '',
  
  // Android软件
  clash_android_url: '',
  v2rayng_url: '',
  hiddify_android_url: '',
  
  // macOS软件
  flash_macos_url: '',
  mihomo_macos_url: '',
  sparkle_macos_url: '',
  
  // iOS软件
  shadowrocket_url: ''
})
const activePlatform = ref('Windows')
const showQRCode = ref(false)

// 平台配置
const platforms = ref([
  {
    name: 'Windows',
    icon: 'fab fa-windows',
    apps: [
      {
        name: 'Clash for Windows',
        version: 'Latest',
        downloadKey: 'clash_windows_url',
        tutorialUrl: '/help#clash-windows'
      },
      {
        name: 'V2rayN',
        version: 'Latest',
        downloadKey: 'v2rayn_url',
        tutorialUrl: '/help#v2rayn'
      },
      {
        name: 'Mihomo Part',
        version: 'Latest',
        downloadKey: 'mihomo_windows_url',
        tutorialUrl: '/help#mihomo-windows'
      },
      {
        name: 'Sparkle',
        version: 'Latest',
        downloadKey: 'sparkle_windows_url',
        tutorialUrl: '/help#sparkle-windows'
      },
      {
        name: 'Hiddify',
        version: 'Latest',
        downloadKey: 'hiddify_windows_url',
        tutorialUrl: '/help#hiddify-windows'
      },
      {
        name: 'Flash',
        version: 'Latest',
        downloadKey: 'flash_windows_url',
        tutorialUrl: '/help#flash-windows'
      }
    ]
  },
  {
    name: 'Android',
    icon: 'fab fa-android',
    apps: [
      {
        name: 'Clash Meta',
        version: 'Latest',
        downloadKey: 'clash_android_url',
        tutorialUrl: '/help#clash-meta'
      },
      {
        name: 'V2rayNG',
        version: 'Latest',
        downloadKey: 'v2rayng_url',
        tutorialUrl: '/help#v2rayng'
      },
      {
        name: 'Hiddify',
        version: 'Latest',
        downloadKey: 'hiddify_android_url',
        tutorialUrl: '/help#hiddify-android'
      }
    ]
  },
  {
    name: 'macOS',
    icon: 'fab fa-apple',
    apps: [
      {
        name: 'Flash',
        version: 'Latest',
        downloadKey: 'flash_macos_url',
        tutorialUrl: '/help#flash-macos'
      },
      {
        name: 'Mihomo Part',
        version: 'Latest',
        downloadKey: 'mihomo_macos_url',
        tutorialUrl: '/help#mihomo-macos'
      },
      {
        name: 'Sparkle',
        version: 'Latest',
        downloadKey: 'sparkle_macos_url',
        tutorialUrl: '/help#sparkle-macos'
      }
    ]
  },
  {
    name: 'iOS',
    icon: 'fab fa-apple',
    apps: [
      {
        name: 'Shadowrocket',
        version: 'Latest',
        downloadKey: 'shadowrocket_url',
        tutorialUrl: '/help#shadowrocket'
      }
    ]
  }
])

// 计算属性
const qrCodeUrl = computed(() => {
  if (userInfo.value.qrcodeUrl) {
    // 使用后台提供的二维码URL
    return `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(userInfo.value.qrcodeUrl)}&ecc=M&margin=10`
  } else if (userInfo.value.mobileUrl) {
    // 降级方案：使用通用订阅地址生成二维码
    return `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(userInfo.value.mobileUrl)}&ecc=M&margin=10`
  }
  return ''
})

// 方法
const formatDate = (dateString) => {
  if (!dateString) return '未知'
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN')
}

const loadUserInfo = async () => {
  try {
    // 获取用户仪表盘信息（现在包含订阅地址）
    const dashboardResponse = await userAPI.getUserInfo()
    if (dashboardResponse.data && dashboardResponse.data.success) {
      userInfo.value = dashboardResponse.data.data
      } else {
      throw new Error('用户信息加载失败')
    }
  } catch (error) {
    // 降级方案：尝试从订阅API获取订阅地址
    try {
      const subscriptionResponse = await subscriptionAPI.getUserSubscription()
      if (subscriptionResponse.data && subscriptionResponse.data.success) {
        const subscriptionData = subscriptionResponse.data.data
        // 设置基本的用户信息
        userInfo.value = {
          username: '用户',
          email: '',
          membership: '普通会员',
          expire_time: null,
          expiryDate: '未设置',
          remaining_days: 0,
          online_devices: 0,
          total_devices: 0,
          balance: '0.00',
          subscription_url: subscriptionData.subscription_url || '',
          subscription_status: 'inactive',
          // 使用订阅API的地址
          clashUrl: subscriptionData.clashUrl || '',
          v2rayUrl: subscriptionData.v2rayUrl || '',
          mobileUrl: subscriptionData.mobileUrl || '',
          qrcodeUrl: subscriptionData.qrcodeUrl || ''
        }
        ElMessage.warning('部分信息加载失败，但订阅地址可用')
      } else {
        throw new Error('订阅API也返回空数据')
      }
    } catch (fallbackError) {
      ElMessage.error('加载用户信息失败，请刷新页面重试')
    }
  }
}

// 获取订阅信息
const loadSubscriptionInfo = async () => {
  try {
    const response = await subscriptionAPI.getUserSubscription()
    if (response.data && response.data.success) {
      subscriptionInfo.value = response.data.data
      } else {
      // 用户可能没有订阅，设置默认值
      subscriptionInfo.value = {
        currentDevices: 0,
        maxDevices: 0,
        remainingDays: 0,
        expiryDate: '未设置',
        status: 'inactive'
      }
    }
  } catch (error) {
    // 用户可能没有订阅，设置默认值
    subscriptionInfo.value = {
      currentDevices: 0,
      maxDevices: 0,
      remainingDays: 0,
      expiryDate: '未设置',
      status: 'inactive'
    }
  }
}

const loadAnnouncements = async () => {
  try {
    const response = await userAPI.getAnnouncements()
    if (response.data && response.data.success) {
      announcements.value = response.data.data
      // 检查是否需要弹窗显示重要公告
      checkForImportantAnnouncements()
    } else {
      }
  } catch (error) {
    }
}

// 充值相关方法
const showRechargeDialog = () => {
  rechargeDialogVisible.value = true
  rechargeForm.value.amount = 20
  rechargeQRCode.value = ''
}

const selectQuickAmount = (amount) => {
  rechargeForm.value.amount = amount
}

const createRecharge = async () => {
  try {
    await rechargeFormRef.value.validate()
    
    if (rechargeForm.value.amount < 20) {
      ElMessage.error('充值金额不能少于20元')
      return
    }
    
    rechargeLoading.value = true
    
    const response = await rechargeAPI.createRecharge(rechargeForm.value.amount, 'alipay')
    
    if (response.data && response.data.success !== false) {
      const data = response.data.data
      
      // 检查是否有支付错误
      if (data.payment_error) {
        ElMessage.warning(data.payment_error || '支付链接生成失败')
        return
      }
      
      // 获取支付URL
      const paymentUrl = data.payment_qr_code || data.payment_url
      
      if (!paymentUrl) {
        ElMessage.error('支付链接生成失败，请稍后重试')
        return
      }
      
      // 使用qrcode库将支付URL生成为二维码图片（与订单支付相同的方式）
      try {
        const QRCode = await import('qrcode')
        // 将支付URL生成为base64格式的二维码图片
        const qrCodeDataURL = await QRCode.toDataURL(paymentUrl, {
          width: 256,
          margin: 2,
          color: {
            dark: '#000000',
            light: '#FFFFFF'
          }
        })
        rechargeQRCode.value = qrCodeDataURL
        ElMessage.success('充值订单创建成功，请扫描二维码完成支付')
        
        // 开始轮询检查支付状态
        checkRechargeStatus(data.recharge_id)
      } catch (qrError) {
        // 如果二维码生成失败，直接使用URL
        rechargeQRCode.value = paymentUrl
        ElMessage.success('充值订单创建成功，请扫描二维码完成支付')
        checkRechargeStatus(data.recharge_id)
      }
    } else {
      ElMessage.error(response.data?.message || '创建充值订单失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '创建充值订单失败')
  } finally {
    rechargeLoading.value = false
  }
}

let rechargeStatusInterval = null
const checkRechargeStatus = (rechargeId) => {
  if (rechargeStatusInterval) {
    clearInterval(rechargeStatusInterval)
  }
  
  rechargeStatusInterval = setInterval(async () => {
    try {
      const response = await rechargeAPI.getRechargeDetail(rechargeId)
      if (response.data && response.data.success) {
        const recharge = response.data.data
        if (recharge.status === 'paid') {
          clearInterval(rechargeStatusInterval)
          rechargeStatusInterval = null
          ElMessage.success('充值成功！余额已到账')
          rechargeQRCode.value = ''
          rechargeDialogVisible.value = false
          // 刷新用户信息
          await loadUserInfo()
        } else if (recharge.status === 'cancelled' || recharge.status === 'failed') {
          clearInterval(rechargeStatusInterval)
          rechargeStatusInterval = null
          ElMessage.warning('充值订单已取消或失败')
          rechargeQRCode.value = ''
        }
      }
    } catch (error) {
      }
  }, 3000) // 每3秒检查一次
  
  // 30秒后停止检查
  setTimeout(() => {
    if (rechargeStatusInterval) {
      clearInterval(rechargeStatusInterval)
      rechargeStatusInterval = null
    }
  }, 30000)
}

// 检查重要公告并弹窗显示
const checkForImportantAnnouncements = () => {
  if (announcements.value.length === 0) return
  
  // 获取最新的公告
  const latestAnnouncement = announcements.value[0]
  
  // 检查是否是需要弹窗显示的类型（活动通知、更新通知、维护通知）
  const importantTypes = ['activity', 'update', 'maintenance']
  if (!importantTypes.includes(latestAnnouncement.type)) return
  
  // 检查用户是否已经看过这个公告（使用localStorage）
  const lastSeenAnnouncementId = localStorage.getItem('lastSeenAnnouncementId')
  if (lastSeenAnnouncementId === latestAnnouncement.id.toString()) return
  
  // 延迟显示弹窗，让页面先加载完成
  setTimeout(() => {
    showAnnouncementPopup(latestAnnouncement)
  }, 1000)
}

// 显示公告弹窗
const showAnnouncementPopup = (announcement) => {
  selectedAnnouncement.value = announcement
  announcementDialogVisible.value = true
  
  // 记录用户已经看过这个公告
  localStorage.setItem('lastSeenAnnouncementId', announcement.id.toString())
}

const loadSoftwareConfig = async () => {
  try {
    const response = await softwareConfigAPI.getSoftwareConfig()
    if (response.data && response.data.success) {
      // 后端返回的是ResponseBase格式，数据在response.data.data中
      softwareConfig.value = response.data.data
    }
  } catch (error) {
    }
}

const downloadApp = (appName) => {
  let downloadUrl = ''
  
  switch (appName) {
    case 'clash_windows_url':
      downloadUrl = softwareConfig.value.clash_windows_url
      break
    case 'v2rayn_url':
      downloadUrl = softwareConfig.value.v2rayn_url
      break
    case 'mihomo_windows_url':
      downloadUrl = softwareConfig.value.mihomo_windows_url
      break
    case 'sparkle_windows_url':
      downloadUrl = softwareConfig.value.sparkle_windows_url
      break
    case 'hiddify_windows_url':
      downloadUrl = softwareConfig.value.hiddify_windows_url
      break
    case 'flash_windows_url':
      downloadUrl = softwareConfig.value.flash_windows_url
      break
    case 'clash_android_url':
      downloadUrl = softwareConfig.value.clash_android_url
      break
    case 'v2rayng_url':
      downloadUrl = softwareConfig.value.v2rayng_url
      break
    case 'hiddify_android_url':
      downloadUrl = softwareConfig.value.hiddify_android_url
      break
    case 'flash_macos_url':
      downloadUrl = softwareConfig.value.flash_macos_url
      break
    case 'mihomo_macos_url':
      downloadUrl = softwareConfig.value.mihomo_macos_url
      break
    case 'sparkle_macos_url':
      downloadUrl = softwareConfig.value.sparkle_macos_url
      break
    case 'shadowrocket_url':
      downloadUrl = softwareConfig.value.shadowrocket_url
      break
    default:
      ElMessage.error('下载链接未配置')
      return
  }
  
  if (downloadUrl) {
    window.open(downloadUrl, '_blank')
  } else {
    ElMessage.error('下载链接未配置，请联系管理员')
  }
}

const openTutorial = (url) => {
  // 跳转到软件教程页面
  router.push('/help')
}

// 跳转到套餐页面
const goToPackages = () => {
  router.push('/packages')
}

const loadDevices = async () => {
  try {
    const response = await userAPI.getUserDevices()
    devices.value = response.data
  } catch (error) {
    }
}

const handleClashCommand = (command) => {
  if (command === 'copy-clash') {
    copyClashSubscription()
  } else if (command === 'import-clash') {
    importClashSubscription()
  }
}

const handleFlashCommand = (command) => {
  if (command === 'copy-flash') {
    copyFlashSubscription()
  } else if (command === 'import-flash') {
    importFlashSubscription()
  }
}

const handleMohomoCommand = (command) => {
  if (command === 'copy-mohomo') {
    copyMohomoSubscription()
  } else if (command === 'import-mohomo') {
    importMohomoSubscription()
  }
}

const handleSparkleCommand = (command) => {
  if (command === 'copy-sparkle') {
    copySparkleSubscription()
  } else if (command === 'import-sparkle') {
    importSparkleSubscription()
  }
}

const handleShadowrocketCommand = (command) => {
  if (command === 'copy-shadowrocket') {
    copyShadowrocketSubscription()
  } else if (command === 'import-shadowrocket') {
    importShadowrocketSubscription()
  }
}

const copyClashSubscription = () => {
  if (!userInfo.value.clashUrl) {
    ElMessage.error('Clash 订阅地址不可用，请刷新页面重试')
    return
  }
  
  try {
    // 添加到期时间参数
    let url = userInfo.value.clashUrl
    if (userInfo.value.expiryDate && userInfo.value.expiryDate !== '未设置') {
      const urlObj = new URL(url)
      const expiryDate = new Date(userInfo.value.expiryDate)
      const expiryDateStr = expiryDate.toISOString().split('T')[0] // YYYY-MM-DD格式
      urlObj.searchParams.set('expiry', expiryDateStr)
      url = urlObj.toString()
    }
    
    copyToClipboard(url, 'Clash 订阅地址已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败，请手动复制订阅地址')
  }
}

const copyShadowrocketSubscription = () => {
  if (!userInfo.value.mobileUrl) {
    ElMessage.error('Shadowrocket 订阅地址不可用，请刷新页面重试')
    return
  }
  
  try {
    // 添加到期时间参数
    let url = userInfo.value.mobileUrl
    if (userInfo.value.expiryDate && userInfo.value.expiryDate !== '未设置') {
      const urlObj = new URL(url)
      const expiryDate = new Date(userInfo.value.expiryDate)
      const expiryDateStr = expiryDate.toISOString().split('T')[0] // YYYY-MM-DD格式
      urlObj.searchParams.set('expiry', expiryDateStr)
      url = urlObj.toString()
    }
    
    copyToClipboard(url, 'Shadowrocket 订阅地址已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败，请手动复制订阅地址')
  }
}

const copyV2raySubscription = () => {
  if (!userInfo.value.v2rayUrl) {
    ElMessage.error('V2Ray 订阅地址不可用')
    return
  }
  
  // 添加到期时间参数
  let url = userInfo.value.v2rayUrl
  if (userInfo.value.expiryDate && userInfo.value.expiryDate !== '未设置') {
    const urlObj = new URL(url)
    const expiryDate = new Date(userInfo.value.expiryDate)
    const expiryDateStr = expiryDate.toISOString().split('T')[0] // YYYY-MM-DD格式
    urlObj.searchParams.set('expiry', expiryDateStr)
    url = urlObj.toString()
  }
  
  copyToClipboard(url, 'V2Ray 订阅地址已复制到剪贴板')
}

const copyUniversalSubscription = () => {
  if (!userInfo.value.mobileUrl) {
    ElMessage.error('通用订阅地址不可用')
    return
  }
  
  // 添加到期时间参数
  let url = userInfo.value.mobileUrl
  if (userInfo.value.expiryDate && userInfo.value.expiryDate !== '未设置') {
    const urlObj = new URL(url)
    const expiryDate = new Date(userInfo.value.expiryDate)
    const expiryDateStr = expiryDate.toISOString().split('T')[0] // YYYY-MM-DD格式
    urlObj.searchParams.set('expiry', expiryDateStr)
    url = urlObj.toString()
  }
  
  copyToClipboard(url, '通用订阅地址已复制到剪贴板')
}

// Flash相关方法
const copyFlashSubscription = () => {
  if (!userInfo.value.clashUrl) {
    ElMessage.error('Flash 订阅地址不可用，请刷新页面重试')
    return
  }
  
  try {
    let url = userInfo.value.clashUrl
    if (userInfo.value.expiryDate && userInfo.value.expiryDate !== '未设置') {
      const urlObj = new URL(url)
      const expiryDate = new Date(userInfo.value.expiryDate)
      const expiryDateStr = expiryDate.toISOString().split('T')[0]
      urlObj.searchParams.set('expiry', expiryDateStr)
      url = urlObj.toString()
    }
    
    copyToClipboard(url, 'Flash 订阅地址已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败，请手动复制订阅地址')
  }
}

const importFlashSubscription = () => {
  if (!userInfo.value.clashUrl) {
    ElMessage.error('Flash 订阅地址不可用，请刷新页面重试')
    return
  }
  
  try {
    // 添加到期时间参数到URL
    let url = userInfo.value.clashUrl
    let name = '' // 用于clash://install-config的name参数
    
    if (userInfo.value.expiryDate && userInfo.value.expiryDate !== '未设置') {
      const urlObj = new URL(url)
      const expiryDate = new Date(userInfo.value.expiryDate)
      const expiryDateStr = expiryDate.toISOString().split('T')[0] // YYYY-MM-DD格式
      urlObj.searchParams.set('expiry', expiryDateStr)
      url = urlObj.toString()
      
      // 格式化到期时间用于name参数，参考格式：到期时间YYYY-MM-DD_到期
      const year = expiryDate.getFullYear()
      const month = String(expiryDate.getMonth() + 1).padStart(2, '0')
      const day = String(expiryDate.getDate()).padStart(2, '0')
      name = `到期时间${year}-${month}-${day}_到期`
    }
    
    // 参考原有的一键导入实现，传入name参数
    oneclickImport('flash', url, name)
    ElMessage.success('正在打开 Flash 客户端...')
  } catch (error) {
    ElMessage.error('一键导入失败，请手动复制订阅地址')
  }
}

// Mohomo Part相关方法
const copyMohomoSubscription = () => {
  if (!userInfo.value.clashUrl) {
    ElMessage.error('Mohomo Part 订阅地址不可用，请刷新页面重试')
    return
  }
  
  try {
    let url = userInfo.value.clashUrl
    if (userInfo.value.expiryDate && userInfo.value.expiryDate !== '未设置') {
      const urlObj = new URL(url)
      const expiryDate = new Date(userInfo.value.expiryDate)
      const expiryDateStr = expiryDate.toISOString().split('T')[0]
      urlObj.searchParams.set('expiry', expiryDateStr)
      url = urlObj.toString()
    }
    
    copyToClipboard(url, 'Mohomo Part 订阅地址已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败，请手动复制订阅地址')
  }
}

const importMohomoSubscription = () => {
  if (!userInfo.value.clashUrl) {
    ElMessage.error('Mohomo Part 订阅地址不可用，请刷新页面重试')
    return
  }
  
  try {
    // 添加到期时间参数到URL
    let url = userInfo.value.clashUrl
    let name = '' // 用于clash://install-config的name参数
    
    if (userInfo.value.expiryDate && userInfo.value.expiryDate !== '未设置') {
      const urlObj = new URL(url)
      const expiryDate = new Date(userInfo.value.expiryDate)
      const expiryDateStr = expiryDate.toISOString().split('T')[0] // YYYY-MM-DD格式
      urlObj.searchParams.set('expiry', expiryDateStr)
      url = urlObj.toString()
      
      // 格式化到期时间用于name参数，参考格式：到期时间YYYY-MM-DD_到期
      const year = expiryDate.getFullYear()
      const month = String(expiryDate.getMonth() + 1).padStart(2, '0')
      const day = String(expiryDate.getDate()).padStart(2, '0')
      name = `到期时间${year}-${month}-${day}_到期`
    }
    
    // 参考原有的一键导入实现，传入name参数
    oneclickImport('mohomo', url, name)
    ElMessage.success('正在打开 Mohomo Part 客户端...')
  } catch (error) {
    ElMessage.error('一键导入失败，请手动复制订阅地址')
  }
}

// Sparkle相关方法
const copySparkleSubscription = () => {
  if (!userInfo.value.clashUrl) {
    ElMessage.error('Sparkle 订阅地址不可用，请刷新页面重试')
    return
  }
  
  try {
    let url = userInfo.value.clashUrl
    if (userInfo.value.expiryDate && userInfo.value.expiryDate !== '未设置') {
      const urlObj = new URL(url)
      const expiryDate = new Date(userInfo.value.expiryDate)
      const expiryDateStr = expiryDate.toISOString().split('T')[0]
      urlObj.searchParams.set('expiry', expiryDateStr)
      url = urlObj.toString()
    }
    
    copyToClipboard(url, 'Sparkle 订阅地址已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败，请手动复制订阅地址')
  }
}

const importSparkleSubscription = () => {
  if (!userInfo.value.clashUrl) {
    ElMessage.error('Sparkle 订阅地址不可用，请刷新页面重试')
    return
  }
  
  try {
    // 添加到期时间参数到URL
    let url = userInfo.value.clashUrl
    let name = '' // 用于clash://install-config的name参数
    
    if (userInfo.value.expiryDate && userInfo.value.expiryDate !== '未设置') {
      const urlObj = new URL(url)
      const expiryDate = new Date(userInfo.value.expiryDate)
      const expiryDateStr = expiryDate.toISOString().split('T')[0] // YYYY-MM-DD格式
      urlObj.searchParams.set('expiry', expiryDateStr)
      url = urlObj.toString()
      
      // 格式化到期时间用于name参数，参考格式：到期时间YYYY-MM-DD_到期
      const year = expiryDate.getFullYear()
      const month = String(expiryDate.getMonth() + 1).padStart(2, '0')
      const day = String(expiryDate.getDate()).padStart(2, '0')
      name = `到期时间${year}-${month}-${day}_到期`
    }
    
    // 参考原有的一键导入实现，传入name参数
    oneclickImport('sparkle', url, name)
    ElMessage.success('正在打开 Sparkle 客户端...')
  } catch (error) {
    ElMessage.error('一键导入失败，请手动复制订阅地址')
  }
}

// Hiddify Next相关方法
const copyHiddifySubscription = () => {
  if (!userInfo.value.mobileUrl) {
    ElMessage.error('Hiddify Next 订阅地址不可用')
    return
  }
  
  // 添加到期时间参数
  let url = userInfo.value.mobileUrl
  if (userInfo.value.expiryDate && userInfo.value.expiryDate !== '未设置') {
    const urlObj = new URL(url)
    const expiryDate = new Date(userInfo.value.expiryDate)
    const expiryDateStr = expiryDate.toISOString().split('T')[0] // YYYY-MM-DD格式
    urlObj.searchParams.set('expiry', expiryDateStr)
    url = urlObj.toString()
  }
  
  copyToClipboard(url, 'Hiddify Next 订阅地址已复制到剪贴板')
}

const copyToClipboard = async (text, message) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success(message)
  } catch (error) {
    // 降级方案
    const textArea = document.createElement('textarea')
    textArea.value = text
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
    ElMessage.success(message)
  }
}

const importClashSubscription = () => {
  if (!userInfo.value.clashUrl) {
    ElMessage.error('Clash 订阅地址不可用，请刷新页面重试')
    return
  }
  
  try {
    // 添加到期时间参数到URL
    let url = userInfo.value.clashUrl
    let name = '' // 用于clash://install-config的name参数
    
    if (userInfo.value.expiryDate && userInfo.value.expiryDate !== '未设置') {
      const urlObj = new URL(url)
      const expiryDate = new Date(userInfo.value.expiryDate)
      const expiryDateStr = expiryDate.toISOString().split('T')[0] // YYYY-MM-DD格式
      urlObj.searchParams.set('expiry', expiryDateStr)
      url = urlObj.toString()
      
      // 格式化到期时间用于name参数，参考格式：到期时间YYYY-MM-DD_到期
      const year = expiryDate.getFullYear()
      const month = String(expiryDate.getMonth() + 1).padStart(2, '0')
      const day = String(expiryDate.getDate()).padStart(2, '0')
      name = `到期时间${year}-${month}-${day}_到期`
    }
    
    // 参考原有的一键导入实现，传入name参数
    oneclickImport('clashx', url, name)
    ElMessage.success('正在打开 Clash 客户端...')
  } catch (error) {
    ElMessage.error('一键导入失败，请手动复制订阅地址')
  }
}

const importShadowrocketSubscription = () => {
  if (!userInfo.value.mobileUrl) {
    ElMessage.error('Shadowrocket 订阅地址不可用，请刷新页面重试')
    return
  }
  
  try {
    // 添加到期时间参数
    let url = userInfo.value.mobileUrl
    let expiryName = ''
    
    if (userInfo.value.expiryDate && userInfo.value.expiryDate !== '未设置') {
      const urlObj = new URL(url)
      const expiryDate = new Date(userInfo.value.expiryDate)
      const expiryDateStr = expiryDate.toISOString().split('T')[0] // YYYY-MM-DD格式
      urlObj.searchParams.set('expiry', expiryDateStr)
      url = urlObj.toString()
      
      // 格式化到期时间作为订阅名称：到期时间 YYYY-MM-DD
      const year = expiryDate.getFullYear()
      const month = String(expiryDate.getMonth() + 1).padStart(2, '0')
      const day = String(expiryDate.getDate()).padStart(2, '0')
      expiryName = `到期时间${year}-${month}-${day}`
    }
    
    // 参考原有的一键导入实现，传递有效期名称
    oneclickImport('shadowrocket', url, expiryName)
    ElMessage.success('正在打开 Shadowrocket 客户端...')
  } catch (error) {
    ElMessage.error('一键导入失败，请手动复制订阅地址')
  }
}

const showAnnouncementDetail = (announcement) => {
  selectedAnnouncement.value = announcement
  announcementDialogVisible.value = true
}

const closeAnnouncementDialog = () => {
  announcementDialogVisible.value = false
  selectedAnnouncement.value = null
}

const refreshDevices = () => {
  loadDevices()
  ElMessage.success('设备列表已刷新')
}

const getDeviceIcon = (osName) => {
  const iconMap = {
    'Windows': 'fab fa-windows',
    'Android': 'fab fa-android',
    'iOS': 'fab fa-apple',
    'macOS': 'fab fa-apple',
    'Linux': 'fab fa-linux'
  }
  return iconMap[osName] || 'fas fa-mobile-alt'
}

// 一键导入功能实现（参考原有实现）
const oneclickImport = (client, url, name = '') => {
  try {
    switch (client) {
      case 'clashx':
      case 'clash':
        // Clash for Windows/macOS/Android
        // 参考格式：clash://install-config?url=...&name=到期时间_到期
        if (name) {
          window.open(`clash://install-config?url=${encodeURIComponent(url)}&name=${encodeURIComponent(name)}`, '_blank')
        } else {
          window.open(`clash://install-config?url=${encodeURIComponent(url)}`, '_blank')
        }
        break
      case 'flash':
        // Flash (Clash系列)
        if (name) {
          window.open(`clash://install-config?url=${encodeURIComponent(url)}&name=${encodeURIComponent(name)}`, '_blank')
        } else {
          window.open(`clash://install-config?url=${encodeURIComponent(url)}`, '_blank')
        }
        break
      case 'mohomo':
        // Mohomo Part (Clash系列)
        if (name) {
          window.open(`clash://install-config?url=${encodeURIComponent(url)}&name=${encodeURIComponent(name)}`, '_blank')
        } else {
          window.open(`clash://install-config?url=${encodeURIComponent(url)}`, '_blank')
        }
        break
      case 'sparkle':
        // Sparkle (Clash系列)
        if (name) {
          window.open(`clash://install-config?url=${encodeURIComponent(url)}&name=${encodeURIComponent(name)}`, '_blank')
        } else {
          window.open(`clash://install-config?url=${encodeURIComponent(url)}`, '_blank')
        }
        break
      case 'shadowrocket':
        // Shadowrocket (iOS)
        // Shadowrocket URL 格式: shadowrocket://add/sub://<base64_url>#<name>
        // name 部分会显示为订阅名称，可以包含有效期信息
        let shadowrocketUrl = `shadowrocket://add/sub://${btoa(url)}`
        if (name) {
          // 如果有名称（有效期），添加到 URL 的 hash 部分
          shadowrocketUrl += `#${encodeURIComponent(name)}`
        }
        window.open(shadowrocketUrl, '_blank')
        break
      case 'ssr':
        // SSR客户端
        window.open(`ssr://${btoa(url)}`, '_blank')
        break
      case 'quantumult':
        // Quantumult
        window.open(`quantumult://resource?url=${encodeURIComponent(url)}`, '_blank')
        break
      case 'quantumult_v2':
        // Quantumult X
        window.open(`quantumult-x://resource?url=${encodeURIComponent(url)}`, '_blank')
        break
      case 'v2rayng':
        // V2rayNG
        window.open(`v2rayng://install-config?url=${encodeURIComponent(url)}`, '_blank')
        break
      case 'hiddify':
        // Hiddify Next (Android)
        window.open(`hiddify://install-config?url=${encodeURIComponent(url)}`, '_blank')
        break
      default:
        // 尝试通用方式
        window.open(url, '_blank')
    }
  } catch (error) {
    ElMessage.error('一键导入失败，请手动复制订阅地址')
  }
}

// 生命周期
onMounted(() => {
  loadUserInfo()
  loadSubscriptionInfo()
  loadAnnouncements()
  loadSoftwareConfig()
})

onUnmounted(() => {
  if (rechargeStatusInterval) {
    clearInterval(rechargeStatusInterval)
    rechargeStatusInterval = null
  }
})
</script>

<style scoped>
.dashboard-container {
  padding: 0;
  max-width: none;
  margin: 0;
  width: 100%;
}

/* 欢迎横幅 */
.welcome-banner {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  padding: 40px;
  margin-bottom: 30px;
  color: white;
  position: relative;
  overflow: hidden;
}

.welcome-banner::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
  animation: float 6s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0px) rotate(0deg); }
  50% { transform: translateY(-20px) rotate(180deg); }
}

.banner-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: relative;
  z-index: 1;
}

.welcome-title {
  font-size: 2.5rem;
  font-weight: 700;
  margin: 0 0 10px 0;
}

.welcome-subtitle {
  font-size: 1.1rem;
  opacity: 0.9;
  margin: 0;
}

.welcome-icon {
  font-size: 4rem;
  opacity: 0.3;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.stat-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
  border: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
  font-size: 24px;
  color: white;
}

.stat-card:nth-child(1) .stat-icon { background: linear-gradient(135deg, #667eea, #764ba2); }
.stat-card:nth-child(2) .stat-icon { background: linear-gradient(135deg, #f093fb, #f5576c); }
.stat-card:nth-child(3) .stat-icon { background: linear-gradient(135deg, #4facfe, #00f2fe); }
.stat-card:nth-child(4) .stat-icon { background: linear-gradient(135deg, #43e97b, #38f9d7); }

.stat-title {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 4px 0;
  color: #1f2937;
}

.stat-subtitle {
  font-size: 0.875rem;
  color: #6b7280;
  margin: 0;
}

.expiry-subtitle {
  word-break: break-word;
  line-height: 1.4;
  
  @media (max-width: 768px) {
    font-size: 0.75rem;
    line-height: 1.3;
  }
  
  @media (max-width: 480px) {
    font-size: 0.6875rem;
    line-height: 1.4;
  }
}

/* 余额卡片样式 */
.balance-card {
  .recharge-btn {
    margin-top: 10px;
    width: 100%;
    padding: 10px 20px;
    font-weight: 600;
    border-radius: 8px;
    font-size: 0.875rem;
    
    :is(i) {
      margin-right: 6px;
    }
    
    @media (max-width: 768px) {
      padding: 8px 14px;
      font-size: 0.8125rem;
      
      :is(i) {
        margin-right: 4px;
        font-size: 12px;
      }
    }
    
    @media (max-width: 480px) {
      padding: 12px 16px;
      font-size: 0.875rem;
      border-radius: 10px;
      
      :is(i) {
        margin-right: 6px;
        font-size: 14px;
      }
    }
  }
}

/* 剩余时间卡片样式 */
.remaining-time-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  overflow: hidden;
  
  .stat-content {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    flex: 1;
    min-width: 0;
    gap: 10px;
    box-sizing: border-box;
  }
  
  .remaining-time-main {
    flex: 1;
    min-width: 0;
    overflow: hidden;
  }
  
  .remaining-time-title {
    font-size: 0.875rem;
    color: #6b7280;
    margin: 0 0 8px 0;
    font-weight: 500;
  }
  
  .remaining-time-value {
    display: flex;
    align-items: baseline;
    gap: 4px;
  }
  
  .time-number {
    font-size: 2.5rem;
    font-weight: 700;
    color: #1f2937;
    line-height: 1;
  }
  
  .time-unit {
    font-size: 1.25rem;
    font-weight: 600;
    color: #6b7280;
  }
  
  .expiry-date {
    font-size: 0.8125rem;
    color: #9ca3af;
    margin: 8px 0 0 0;
    font-weight: 400;
    line-height: 1.4;
  }
  
  .renew-btn {
    margin-left: 12px;
    padding: 8px 16px;
    font-weight: 600;
    border-radius: 8px;
    white-space: nowrap;
    font-size: 0.8125rem;
    flex-shrink: 0;
    box-sizing: border-box;
    max-width: fit-content;
    height: auto;
    
    :is(i) {
      margin-right: 4px;
      font-size: 12px;
    }
  }
  
  @media (max-width: 768px) {
    padding: 16px 12px;
    
    .stat-content {
      flex-direction: row;
      align-items: center;
      gap: 12px;
    }
    
    .remaining-time-title {
      font-size: 0.75rem;
      margin-bottom: 6px;
      line-height: 1.2;
    }
    
    .time-number {
      font-size: 1.75rem;
    }
    
    .time-unit {
      font-size: 0.875rem;
    }
    
    .expiry-date {
      font-size: 0.75rem;
      margin-top: 6px;
      line-height: 1.3;
      word-break: break-word;
    }
    
    .renew-btn {
      margin-left: 0;
      padding: 6px 12px;
      font-size: 0.75rem;
      flex-shrink: 0;
      box-sizing: border-box;
      max-width: fit-content;
      height: auto;
      
      :is(i) {
        margin-right: 3px;
        font-size: 11px;
      }
    }
  }
  
  @media (max-width: 480px) {
    padding: 14px 12px;
    
    .stat-content {
      flex-direction: column;
      align-items: center;
      gap: 10px;
    }
    
    .remaining-time-main {
      width: 100%;
      text-align: center;
    }
    
    .remaining-time-title {
      font-size: 0.8125rem;
      margin-bottom: 8px;
    }
    
    .remaining-time-value {
      justify-content: center;
    }
    
    .time-number {
      font-size: 2rem;
    }
    
    .time-unit {
      font-size: 1rem;
    }
    
    .expiry-date {
      font-size: 0.6875rem;
      margin-top: 8px;
      line-height: 1.4;
      word-break: break-word;
      color: #6b7280;
      text-align: center;
    }
    
    .renew-btn {
      margin-left: 0;
      width: auto;
      padding: 8px 16px;
      font-size: 0.8125rem;
      border-radius: 8px;
      box-sizing: border-box;
      max-width: fit-content;
      align-self: center;
      
      :is(i) {
        margin-right: 4px;
        font-size: 12px;
      }
    }
  }
}

/* 充值对话框样式 */
.recharge-dialog {
  :deep(.el-dialog__body) {
    padding: 20px;
  }
  
  :deep(.el-dialog) {
    @media (max-width: 768px) {
      width: 90% !important;
      margin: 5vh auto !important;
    }
  }
  
  :deep(.el-form-item__label) {
    @media (max-width: 768px) {
      font-size: 14px;
      padding-bottom: 8px;
    }
  }
  
  .amount-tips {
    margin-top: 10px;
    font-size: 12px;
    color: #909399;
    
    @media (max-width: 768px) {
      font-size: 11px;
    }
    
    :is(p) {
      margin-bottom: 10px;
      
      @media (max-width: 768px) {
        margin-bottom: 8px;
      }
    }
    
    .quick-amounts {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
      
      @media (max-width: 768px) {
        gap: 6px;
        margin-top: 8px;
      }
      
      .el-button {
        margin: 0;
        
        @media (max-width: 768px) {
          padding: 8px 12px;
          font-size: 12px;
          flex: 1 1 calc(33.333% - 4px);
          min-width: calc(33.333% - 4px);
        }
      }
    }
  }
  
  .recharge-qr-section {
    margin-top: 20px;
    text-align: center;
    padding: 20px;
    background: #f5f7fa;
    border-radius: 8px;
    
    @media (max-width: 768px) {
      margin-top: 15px;
      padding: 15px;
    }
    
    :is(h4) {
      margin-bottom: 15px;
      color: #303133;
      font-size: 16px;
      
      @media (max-width: 768px) {
        font-size: 14px;
        margin-bottom: 12px;
      }
    }
    
    .qr-code-wrapper {
      display: flex;
      justify-content: center;
      margin: 20px 0;
      
      @media (max-width: 768px) {
        margin: 15px 0;
      }
      
      .qr-code-img {
        max-width: 250px;
        max-height: 250px;
        border: 1px solid #dcdfe6;
        border-radius: 4px;
        padding: 10px;
        background: white;
        
        @media (max-width: 768px) {
          max-width: 200px;
          max-height: 200px;
          padding: 8px;
        }
      }
    }
    
    .qr-tip {
      color: #909399;
      font-size: 12px;
      margin-top: 10px;
      
      @media (max-width: 768px) {
        font-size: 11px;
        margin-top: 8px;
      }
    }
  }
  
  :deep(.el-dialog__footer) {
    @media (max-width: 768px) {
      padding: 15px 20px;
      
      .el-button {
        flex: 1;
        margin: 0 5px;
      }
    }
  }
}

/* 主要内容区域 */
.main-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 30px;
}

/* 卡片通用样式 */
.card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
  border: 1px solid #e5e7eb;
  margin-bottom: 20px;
}

.card-header {
  padding: 20px 24px 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0;
  color: #1f2937;
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-body {
  padding: 20px 24px 24px;
}

/* 公告卡片 */
.announcement-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.announcement-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: 12px;
}

.announcement-item:hover {
  border-color: #3b82f6;
  background-color: #f8fafc;
}

.announcement-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 4px 0;
  color: #1f2937;
}

.announcement-preview {
  font-size: 0.875rem;
  color: #6b7280;
  margin: 0 0 8px 0;
  line-height: 1.4;
}

.announcement-time {
  font-size: 0.75rem;
  color: #9ca3af;
}

.announcement-arrow {
  color: #9ca3af;
}

.no-announcements {
  text-align: center;
  padding: 40px 20px;
  color: #9ca3af;
}

.no-announcements :is(i) {
  font-size: 3rem;
  margin-bottom: 16px;
  display: block;
}

/* 教程卡片 */
.tutorial-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.tutorial-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 0.875rem;
  font-weight: 500;
}

.tutorial-tab:hover {
  border-color: #3b82f6;
  background-color: #f8fafc;
}

.tutorial-tab.active {
  border-color: #3b82f6;
  background-color: #3b82f6;
  color: white;
}

.tutorial-app {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-bottom: 12px;
}

.app-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-name {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 4px 0;
  color: #1f2937;
}

.app-version {
  font-size: 0.875rem;
  color: #6b7280;
  margin: 0;
}

.app-actions {
  display: flex;
  gap: 8px;
}

/* 订阅卡片 */
.subscription-buttons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 20px;
  
  @media (max-width: 768px) {
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 16px;
  }
  
  @media (max-width: 480px) {
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
}

.subscription-group {
  display: flex;
  
  @media (max-width: 768px) {
    width: 100%;
  }
}

.clash-btn {
  background: linear-gradient(135deg, #667eea, #764ba2);
  border: none;
  width: 100%;
}

.shadowrocket-btn {
  background: linear-gradient(135deg, #f093fb, #f5576c);
  border: none;
  width: 100%;
}

.v2ray-btn {
  background: linear-gradient(135deg, #4facfe, #00f2fe);
  border: none;
  width: 100%;
}

.universal-btn {
  background: linear-gradient(135deg, #43e97b, #38f9d7);
  border: none;
  width: 100%;
}

.qr-code-section {
  text-align: center;
  padding-top: 20px;
  border-top: 1px solid #e5e7eb;
}

.qr-code-container {
  margin-top: 16px;
}

/* 软件分类标题 */
.software-category {
  margin-bottom: 24px;
}

.category-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid #f0f0f0;
}

.category-title i {
  color: #667eea;
}

/* 订阅地址显示区域 */
.subscription-urls-section {
  margin-bottom: 24px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid #f0f0f0;
}

.section-title i {
  color: #667eea;
}

.url-display {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.url-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.url-item label {
  font-weight: 500;
  color: #555;
  font-size: 14px;
}

.url-input-group {
  display: flex;
  gap: 8px;
}

.url-input {
  flex: 1;
}

/* 二维码区域 */
.qr-code-section {
  margin-bottom: 24px;
}

.qr-code-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 12px;
  border: 2px dashed #e0e0e0;
}

.qr-code {
  width: 200px;
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.qr-code img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 8px;
}

.qr-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #999;
}

.qr-placeholder :is(i) {
  font-size: 48px;
}

.qr-tip {
  font-size: 14px;
  color: #666;
  text-align: center;
  margin: 0;
}

/* 新按钮样式 */
.flash-btn {
  background: linear-gradient(135deg, #ff6b6b, #ee5a24);
  border: none;
  width: 100%;
  border-radius: 12px;
  padding: 14px 20px;
  font-weight: 600;
  transition: all 0.3s ease;
  
  @media (max-width: 768px) {
    padding: 16px 20px;
    font-size: 15px;
    border-radius: 16px;
    box-shadow: 0 4px 12px rgba(255, 107, 107, 0.3);
    
    &:active {
      transform: scale(0.98);
    }
  }
}

.mohomo-btn {
  background: linear-gradient(135deg, #4834d4, #686de0);
  border: none;
  width: 100%;
  border-radius: 12px;
  padding: 14px 20px;
  font-weight: 600;
  transition: all 0.3s ease;
  
  @media (max-width: 768px) {
    padding: 16px 20px;
    font-size: 15px;
    border-radius: 16px;
    box-shadow: 0 4px 12px rgba(72, 52, 212, 0.3);
    
    &:active {
      transform: scale(0.98);
    }
  }
}

.sparkle-btn {
  background: linear-gradient(135deg, #feca57, #ff9ff3);
  border: none;
  width: 100%;
  border-radius: 12px;
  padding: 14px 20px;
  font-weight: 600;
  transition: all 0.3s ease;
  
  @media (max-width: 768px) {
    padding: 16px 20px;
    font-size: 15px;
    border-radius: 16px;
    box-shadow: 0 4px 12px rgba(254, 202, 87, 0.3);
    
    &:active {
      transform: scale(0.98);
    }
  }
}

.hiddify-btn {
  background: linear-gradient(135deg, #a8edea, #fed6e3);
  border: none;
  width: 100%;
  color: #333;
  border-radius: 12px;
  padding: 14px 20px;
  font-weight: 600;
  transition: all 0.3s ease;
  
  @media (max-width: 768px) {
    padding: 16px 20px;
    font-size: 15px;
    border-radius: 16px;
    box-shadow: 0 4px 12px rgba(168, 237, 234, 0.3);
    
    &:active {
      transform: scale(0.98);
    }
  }
}

.qr-code img {
  width: 200px;
  height: 200px;
  border-radius: 8px;
}

.qr-tip {
  font-size: 0.875rem;
  color: #6b7280;
  margin: 12px 0 0 0;
}

/* 设备卡片 */
.device-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.device-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-bottom: 12px;
}

.device-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.device-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 18px;
}

.device-name {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 4px 0;
  color: #1f2937;
}

.device-os, .device-ip {
  font-size: 0.875rem;
  color: #6b7280;
  margin: 0;
}

.no-devices {
  text-align: center;
  padding: 40px 20px;
  color: #9ca3af;
}

.no-devices i {
  font-size: 3rem;
  margin-bottom: 16px;
  display: block;
}

/* 公告详情对话框 */
.announcement-detail {
  max-height: 60vh;
  overflow-y: auto;
}

.announcement-meta {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e5e7eb;
}

.announcement-content {
  line-height: 1.6;
  color: #374151;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .dashboard-container {
    padding: 0;
  }
  
  .welcome-banner {
    margin: 0 -12px 12px -12px;
    border-radius: 0;
    padding: 16px 12px;
    
    .banner-content {
      flex-direction: column;
      text-align: center;
      gap: 12px;
      
      .welcome-text {
        .welcome-title {
          font-size: 1.5rem;
          margin-bottom: 8px;
        }
        
        .welcome-subtitle {
          font-size: 0.875rem;
        }
      }
      
      .welcome-icon {
        font-size: 2rem;
      }
    }
  }
  
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    margin-bottom: 16px;
    
    .stat-card {
      padding: 14px 12px;
      
      .stat-icon {
        width: 44px;
        height: 44px;
        font-size: 20px;
        margin-right: 12px;
      }
      
      .stat-content {
        flex: 1;
        min-width: 0;
        
        .stat-title {
          font-size: 1.125rem;
          margin-bottom: 4px;
          word-break: break-word;
        }
        
        .stat-subtitle {
          font-size: 0.75rem;
          line-height: 1.3;
          word-break: break-word;
        }
      }
    }
    
    /* 剩余时间卡片在移动端的特殊处理 */
    .remaining-time-card {
      grid-column: 1 / -1; /* 占据整行 */
      
      .stat-content {
        flex-direction: row;
        align-items: center;
      }
    }
  }
  
  .main-content {
    grid-template-columns: 1fr;
    gap: 12px;
    
    .left-content,
    .right-content {
      width: 100%;
    }
  }
  
  .card {
    margin-bottom: 12px;
    
    .card-header {
      padding: 12px 16px;
      
      .card-title {
        font-size: 1rem;
        
        :is(i) {
          font-size: 16px;
          margin-right: 6px;
        }
      }
    }
    
    .card-body {
      padding: 16px;
    }
  }
  
  .announcement-item {
    padding: 12px;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
    
    .announcement-content {
      flex: 1;
      width: 100%;
      
      .announcement-title {
        font-size: 0.9375rem;
        margin-bottom: 6px;
      }
      
      .announcement-preview {
        font-size: 0.8125rem;
        line-height: 1.4;
        margin-bottom: 6px;
      }
      
      .announcement-time {
        font-size: 0.6875rem;
      }
    }
    
    .announcement-arrow {
      align-self: flex-end;
    }
  }
  
  .tutorial-tabs {
    gap: 6px;
    margin-bottom: 16px;
    
    .tutorial-tab {
      padding: 10px 12px;
      font-size: 0.8125rem;
      flex: 1;
      min-width: 0;
      justify-content: center;
      
      :is(i) {
        font-size: 14px;
      }
    }
  }
  
  .subscription-buttons {
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 20px;
    
    .el-button {
      padding: 14px 12px;
      font-size: 14px;
      border-radius: 16px;
      font-weight: 600;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      
      &:active {
        transform: scale(0.98);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      }
      
      :is(i) {
        font-size: 14px;
        margin-right: 4px;
      }
    }
  }
  
  .software-category {
    margin-bottom: 24px;
    
    .category-title {
      font-size: 15px;
      margin-bottom: 14px;
      padding-bottom: 10px;
    }
  }
  
  .url-input-group {
    flex-direction: column;
    
    .el-button {
      width: 100%;
      margin-top: 8px;
    }
  }
  
  .qr-code-container {
    padding: 16px;
    
    .qr-code {
      width: 160px;
      height: 160px;
    }
    
    .qr-tip {
      font-size: 0.8125rem;
      margin-top: 12px;
    }
  }
  
  .device-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
    padding: 14px;
    
    .device-info {
      width: 100%;
    }
    
    .device-actions {
      width: 100%;
      
      .el-button {
        width: 100%;
        margin-bottom: 8px;
        
        &:last-child {
          margin-bottom: 0;
        }
      }
    }
  }
}

@media (max-width: 480px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
  
  .welcome-title {
    font-size: 1.25rem;
  }
  
  .welcome-subtitle {
    font-size: 0.8125rem;
  }
  
  .stat-card {
    padding: 12px;
    
    .stat-icon {
      width: 40px;
      height: 40px;
      font-size: 18px;
    }
    
    .stat-content {
      .stat-title {
        font-size: 1rem;
      }
      
      .stat-subtitle {
        font-size: 0.6875rem;
      }
    }
  }
  
  .card-body {
    padding: 12px;
  }
  
  .announcement-item {
    padding: 10px;
  }
  
  .subscription-buttons {
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    
    .el-button {
      padding: 12px 10px;
      font-size: 13px;
      border-radius: 14px;
      
      :is(i) {
        font-size: 12px;
        margin-right: 3px;
      }
    }
  }
  
  .qr-code-container {
    .qr-code {
      width: 140px;
      height: 140px;
    }
  }
}
</style>
