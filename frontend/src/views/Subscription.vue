<template>
  <div class="list-container subscription-container">
    <el-card class="subscription-card">
      <template #header>
        <div class="card-header">
          <h2>订阅管理</h2>
          <p>管理您的订阅信息和订阅地址</p>
        </div>
      </template>

      <!-- 订阅状态 -->
      <div class="subscription-status" v-if="subscription">
        <el-row :gutter="20">
          <el-col :span="6">
            <div class="status-item">
              <div class="status-label">账号状态</div>
              <div class="status-value">
                <el-tag :type="getStatusType(subscription)">
                  {{ getStatusText(subscription) }}
                </el-tag>
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="status-item">
              <div class="status-label">到期时间</div>
              <div class="status-value">{{ formatDate(subscription.expire_time) }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="status-item">
              <div class="status-label">到期天数</div>
              <div class="status-value">{{ getRemainingDays(subscription) }} 天</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="status-item">
              <div class="status-label">设备使用</div>
              <div class="status-value">{{ subscription.currentDevices || 0 }}/{{ subscription.maxDevices || 0 }}</div>
            </div>
          </el-col>
        </el-row>
      </div>

      <!-- 订阅地址 -->
      <div class="subscription-urls" v-if="subscription && (subscription.subscription_id || subscription.clash_url)">
        <h3>订阅地址</h3>
        <div class="url-list">
          <div class="url-item">
            <div class="url-label">Clash订阅地址：</div>
            <div class="url-content">
              <el-input
                v-model="subscription.clash_url"
                readonly
                size="large"
              >
                <template #append>
                  <el-button @click="copyUrl(subscription.clash_url)">
                    <i class="el-icon-document-copy"></i>
                    复制
                  </el-button>
                </template>
              </el-input>
            </div>
          </div>
          
          <div class="url-item">
            <div class="url-label">通用订阅地址：</div>
            <div class="url-content">
              <el-input
                v-model="subscription.universal_url"
                readonly
                size="large"
              >
                <template #append>
                  <el-button @click="copyUrl(subscription.universal_url)">
                    <i class="el-icon-document-copy"></i>
                    复制
                  </el-button>
                </template>
              </el-input>
            </div>
          </div>
        </div>

        <div class="qr-code-section">
          <h4>二维码</h4>
          <div class="qr-codes">
            <div class="qr-item">
              <canvas id="clash-qrcode"></canvas>
              <p>Clash订阅</p>
            </div>
            <div class="qr-item">
              <canvas id="universal-qrcode"></canvas>
              <p>通用订阅</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 无订阅状态提示 -->
      <div class="no-subscription" v-else>
        <el-empty description="您还没有订阅">
          <el-button type="primary" @click="$router.push('/packages')">
            立即订阅
          </el-button>
        </el-empty>
      </div>

      <!-- 操作按钮 -->
      <div class="subscription-actions" v-if="subscription && (subscription.subscription_id || subscription.clash_url)">
        <el-button
          type="primary"
          class="action-btn reset-btn"
          @click="resetSubscription"
          :loading="resetLoading"
        >
          重置订阅地址
        </el-button>
        
        <el-button
          type="success"
          class="action-btn email-btn"
          @click="sendSubscriptionToEmail"
          :loading="sendEmailLoading"
        >
          发送到邮箱
        </el-button>
        
        <el-button
          type="warning"
          class="action-btn renew-btn"
          @click="$router.push('/packages')"
          v-if="!isSubscriptionActive(subscription)"
        >
          续费订阅
        </el-button>
      </div>

      <!-- 续费提示 -->
      <div class="renewal-prompt" v-if="subscription && !isSubscriptionActive(subscription)">
        <el-alert
          title="订阅已过期"
          type="warning"
          :description="`您的订阅已于 ${formatDate(subscription.expire_time)} 过期，请及时续费以继续使用服务。`"
          show-icon
          :closable="false"
        >
          <template #default>
            <div class="renewal-actions">
              <el-button type="primary" @click="$router.push('/packages')">
                立即续费
              </el-button>
            </div>
          </template>
        </el-alert>
      </div>
    </el-card>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import QRCode from 'qrcode'
import { subscriptionAPI, userAPI } from '@/utils/api'
import { formatDateTime } from '@/utils/date'
import '@/styles/list-common.scss'

export default {
  name: 'Subscription',
  setup() {
    const subscription = ref(null)
    const resetLoading = ref(false)
    const sendEmailLoading = ref(false)

    // 获取订阅信息
    const fetchSubscription = async () => {
      try {
        // 优先使用订阅API获取设备信息
        let subscriptionResponse
        try {
          subscriptionResponse = await subscriptionAPI.getUserSubscription()
          } catch (subscriptionError) {
          subscriptionResponse = null
        }
        
        // 获取用户仪表盘信息（用于订阅地址）
        let userResponse
        try {
          userResponse = await userAPI.getUserInfo()
          } catch (userError) {
          userResponse = null
        }
        
        // 优先使用订阅API的数据，用户API作为补充
        if (subscriptionResponse && subscriptionResponse.data && subscriptionResponse.data.success) {
          const subscriptionData = subscriptionResponse.data.data
          // 使用订阅API的数据作为主要数据源
          subscription.value = {
            subscription_id: subscriptionData.subscription_id,
            expire_time: subscriptionData.expire_time || subscriptionData.expiryDate,
            status: subscriptionData.status,
            currentDevices: subscriptionData.currentDevices || 0,
            maxDevices: subscriptionData.maxDevices || 0,
            clash_url: subscriptionData.clashUrl || '',
            universal_url: subscriptionData.mobileUrl || '',
            qrcode_url: subscriptionData.qrcodeUrl || ''
          }
          
          // 如果用户API有订阅地址信息，优先使用用户API的地址
          if (userResponse && userResponse.data && userResponse.data.success) {
            const userData = userResponse.data.data
            if (userData.clashUrl) {
              subscription.value.clash_url = userData.clashUrl
            }
            if (userData.mobileUrl) {
              subscription.value.universal_url = userData.mobileUrl
            }
            if (userData.qrcodeUrl) {
              subscription.value.qrcode_url = userData.qrcodeUrl
            }
          }
        } else if (userResponse && userResponse.data && userResponse.data.success) {
          // 降级方案：使用用户API的数据
          const userData = userResponse.data.data
          subscription.value = {
            subscription_id: userData.subscription_url,
            expire_time: userData.expire_time,
            status: userData.subscription_status,
            currentDevices: userData.online_devices || 0,
            maxDevices: userData.total_devices || 0,
            clash_url: userData.clashUrl || '',
            universal_url: userData.mobileUrl || userData.v2rayUrl || '',
            qrcode_url: userData.qrcodeUrl || ''
          }
        } else {
          ElMessage.error('获取订阅信息失败：无法连接到服务器')
          return
        }
        
        // 延迟生成二维码，确保DOM元素已渲染
        setTimeout(() => {
          generateQRCodes()
        }, 100)
        
      } catch (error) {
        ElMessage.error(`获取订阅信息失败: ${error.message || '未知错误'}`)
      }
    }

    // 生成二维码
    const generateQRCodes = async () => {
      if (!subscription.value) return

      try {
        // 生成Clash二维码
        const clashElement = document.getElementById('clash-qrcode')
        if (clashElement && subscription.value.clash_url) {
          await QRCode.toCanvas(clashElement, subscription.value.clash_url, {
            width: 150,
            margin: 2
          })
        }

        // 生成通用订阅二维码
        const universalElement = document.getElementById('universal-qrcode')
        if (universalElement && subscription.value.universal_url) {
          await QRCode.toCanvas(universalElement, subscription.value.universal_url, {
            width: 150,
            margin: 2
          })
        }
      } catch (error) {
        }
    }

    // 复制链接
    const copyUrl = async (url) => {
      try {
        await navigator.clipboard.writeText(url)
        ElMessage.success('链接已复制到剪贴板')
      } catch (error) {
        ElMessage.error('复制失败')
      }
    }

    // 重置订阅地址
    const resetSubscription = async () => {
      try {
        await ElMessageBox.confirm(
          '重置订阅地址将清空所有设备记录，确定要继续吗？',
          '确认重置',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )

        resetLoading.value = true
        await subscriptionAPI.resetSubscription()
        
        ElMessage.success('订阅地址已重置')
        await fetchSubscription()
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('重置失败')
          }
      } finally {
        resetLoading.value = false
      }
    }

    // 发送订阅地址到邮箱
    const sendSubscriptionToEmail = async () => {
      try {
        sendEmailLoading.value = true
        await subscriptionAPI.sendSubscriptionEmail()
        ElMessage.success('订阅地址已发送到您的邮箱')
      } catch (error) {
        ElMessage.error('发送失败，请稍后重试')
        } finally {
        sendEmailLoading.value = false
      }
    }

    // 格式化日期 - 使用北京时间
    const formatDate = (dateString) => {
      if (!dateString) return '未设置'
      // 使用统一的北京时间格式化函数
      return formatDateTime(dateString, 'YYYY-MM-DD HH:mm')
    }

    // 获取剩余天数
    const getRemainingDays = (subscription) => {
      if (!subscription || !subscription.expire_time) return 0
      const now = new Date()
      const expireDate = new Date(subscription.expire_time)
      const diffTime = expireDate - now
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
      return diffDays > 0 ? diffDays : 0
    }

    // 获取状态类型
    const getStatusType = (subscription) => {
      if (!subscription) return 'info'
      
      // 优先根据到期时间判断，确保有效期内用户显示为正常
      if (subscription.expire_time) {
        const now = new Date()
        const expireDate = new Date(subscription.expire_time)
        if (expireDate > now) {
          return 'success'  // 有效期内显示为正常
        } else {
          return 'danger'   // 已过期显示为危险
        }
      }
      
      // 如果后端直接返回了状态，作为备用判断
      if (subscription.status) {
        switch (subscription.status) {
          case 'active':
            return 'success'
          case 'expired':
            return 'danger'
          case 'inactive':
            return 'info'
          default:
            return 'info'
        }
      }
      
      return 'info'
    }

    // 获取状态文本
    const getStatusText = (subscription) => {
      if (!subscription) return '未激活'
      
      // 优先根据到期时间判断，确保有效期内用户显示为正常
      if (subscription.expire_time) {
        const now = new Date()
        const expireDate = new Date(subscription.expire_time)
        if (expireDate > now) {
          return '正常'  // 有效期内显示为正常
        } else {
          return '已过期'  // 已过期显示为已过期
        }
      }
      
      // 如果后端直接返回了状态，作为备用判断
      if (subscription.status) {
        switch (subscription.status) {
          case 'active':
            return '正常'
          case 'expired':
            return '已过期'
          case 'inactive':
            return '未激活'
          default:
            return '未激活'
        }
      }
      
      return '未激活'
    }

    // 检查订阅是否激活
    const isSubscriptionActive = (subscription) => {
      if (!subscription) return false
      
      // 如果后端直接返回了状态，优先使用
      if (subscription.status) {
        return subscription.status === 'active'
      }
      
      // 否则根据到期时间判断
      if (!subscription.expire_time) return false
      const now = new Date()
      const expireDate = new Date(subscription.expire_time)
      return expireDate > now
    }

    onMounted(() => {
      fetchSubscription()
    })

    return {
      subscription,
      resetLoading,
      sendEmailLoading,
      copyUrl,
      resetSubscription,
      sendSubscriptionToEmail,
      formatDate,
      getRemainingDays,
      getStatusType,
      getStatusText,
      isSubscriptionActive
    }
  }
}
</script>

<style scoped>
.subscription-container {
  padding: 0;
  max-width: none;
  margin: 0;
  width: 100%;
}

.subscription-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 15px;
}

.card-header h2 {
  margin: 0;
  color: #333;
  font-size: 1.5rem;
}

.card-header :is(p) {
  margin: 0;
  color: #666;
  font-size: 0.9rem;
}

.subscription-status {
  margin-bottom: 30px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
}

.status-item {
  text-align: left;
}

.status-label {
  color: #666;
  font-size: 0.9rem;
  margin-bottom: 8px;
}

.status-value {
  color: #333;
  font-size: 1.1rem;
  font-weight: 600;
}

.subscription-urls {
  margin-bottom: 30px;
}

.subscription-urls h3 {
  color: #333;
  margin-bottom: 20px;
  font-size: 1.2rem;
}

.url-list {
  margin-bottom: 30px;
}

.url-item {
  display: flex;
  align-items: center;
  margin-bottom: 15px;
  gap: 15px;
}

.url-label {
  min-width: 120px;
  color: #666;
  font-weight: 500;
}

.url-content {
  flex: 1;
}

.qr-code-section {
  text-align: center;
}

.qr-code-section h4 {
  color: #333;
  margin-bottom: 20px;
  font-size: 1.1rem;
}

.qr-codes {
  display: flex;
  justify-content: center;
  gap: 40px;
}

.qr-item {
  text-align: center;
}

.qr-item :is(p) {
  margin-top: 10px;
  color: #666;
  font-size: 0.9rem;
}

.subscription-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  
  .action-btn {
    padding: 12px 24px;
    font-weight: 600;
    font-size: 0.9375rem;
    border-radius: 8px;
    white-space: nowrap;
    min-width: 120px;
    box-sizing: border-box;
    
    :is(i) {
      margin-right: 6px;
    }
  }
  
  @media (max-width: 768px) {
    gap: 10px;
    margin-bottom: 16px;
    
    .action-btn {
      padding: 10px 20px;
      font-size: 0.875rem;
      min-width: 100px;
    }
  }
  
  @media (max-width: 480px) {
    flex-direction: column;
    gap: 10px;
    
    .action-btn {
      width: 100%;
      padding: 12px 16px;
      font-size: 0.875rem;
      min-width: auto;
    }
  }
}

.renewal-prompt {
  margin-top: 20px;
}

.renewal-actions {
  margin-top: 15px;
  text-align: center;
}

.no-subscription {
  text-align: center;
  padding: 40px 20px;
}

@media (max-width: 768px) {
  .subscription-container {
    padding: 0;
  }
  
  .subscription-card {
    border-radius: 0;
    margin: 0 -12px;
    box-shadow: none;
    border-left: none;
    border-right: none;
    
    :deep(.el-card__header) {
      padding: 16px;
      
      .card-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 8px;
        
        :is(h2) {
          font-size: 1.25rem;
          margin: 0;
        }
        
        :is(p) {
          font-size: 0.875rem;
          margin: 0;
        }
      }
    }
    
    :deep(.el-card__body) {
      padding: 16px;
    }
  }
  
  .subscription-status {
    margin-bottom: 20px;
    padding: 16px 12px;
    
    :deep(.el-row) {
      margin-left: 0 !important;
      margin-right: 0 !important;
      
      .el-col {
        padding: 0 4px !important;
        margin-bottom: 12px;
        
        .status-item {
          padding: 12px 8px;
          text-align: center;
          
          .status-label {
            font-size: 0.75rem;
            margin-bottom: 6px;
          }
          
          .status-value {
            font-size: 0.9375rem;
            word-break: break-word;
          }
        }
      }
    }
  }
  
  .subscription-urls {
    margin-bottom: 24px;
    
    :is(h3) {
      font-size: 1.125rem;
      margin-bottom: 16px;
    }
    
    .url-list {
      margin-bottom: 24px;
      
      .url-item {
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
        margin-bottom: 20px;
        
        .url-label {
          font-size: 0.875rem;
          font-weight: 500;
          min-width: auto;
          width: 100%;
        }
        
        .url-content {
          width: 100%;
          
          :deep(.el-input) {
            .el-input__inner {
              font-size: 0.8125rem;
              padding-right: 80px;
            }
            
            .el-input-group__append {
              .el-button {
                padding: 0 12px;
                font-size: 0.8125rem;
                
                :is(i) {
                  font-size: 14px;
                }
              }
            }
          }
        }
      }
    }
    
    .qr-code-section {
      margin-top: 24px;
      padding-top: 20px;
      border-top: 1px solid #e5e7eb;
      
      :is(h4) {
        font-size: 1rem;
        margin-bottom: 16px;
      }
      
      .qr-codes {
        flex-direction: column;
        gap: 24px;
        align-items: center;
        
        .qr-item {
          :is(canvas) {
            max-width: 180px;
            width: 100%;
            height: auto;
          }
          
          :is(p) {
            margin-top: 12px;
            font-size: 0.875rem;
          }
        }
      }
    }
  }
  
  .subscription-actions {
    flex-direction: column;
    gap: 10px;
    margin-bottom: 20px;
    
    .action-btn {
      width: 100%;
      margin: 0;
      padding: 12px 16px;
      font-size: 0.875rem;
      box-sizing: border-box;
    }
  }
  
  .renewal-prompt {
    margin-top: 20px;
    padding: 16px;
    background: #fff7e6;
    border-radius: 8px;
    font-size: 0.875rem;
  }
  
  .renewal-actions {
    margin-top: 16px;
    
    .el-button {
      width: 100%;
      padding: 12px 16px;
    }
  }
  
  .no-subscription {
    padding: 60px 20px;
    
    :is(i) {
      font-size: 4rem;
      margin-bottom: 20px;
    }
    
    :is(p) {
      font-size: 1rem;
    }
  }
}

@media (max-width: 480px) {
  .subscription-status {
    :deep(.el-row) {
      .el-col {
        width: 100% !important;
        margin-bottom: 10px;
        
        .status-item {
          padding: 10px;
        }
      }
    }
  }
  
  .qr-code-section {
    .qr-codes {
      .qr-item {
        :is(canvas) {
          max-width: 160px;
        }
      }
    }
  }
}
</style> 