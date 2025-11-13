<template>
  <div class="list-container devices-container">

    <!-- 设备统计 -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-number">{{ deviceStats.total }}</div>
        <div class="stat-label">总设备数</div>
      </div>
      <div class="stat-card">
        <div class="stat-number">{{ deviceStats.online }}</div>
        <div class="stat-label">在线设备</div>
      </div>
      <div class="stat-card">
        <div class="stat-number">{{ deviceStats.mobile }}</div>
        <div class="stat-label">移动设备</div>
      </div>
      <div class="stat-card">
        <div class="stat-number">{{ deviceStats.desktop }}</div>
        <div class="stat-label">桌面设备</div>
      </div>
    </div>

    <!-- 设备列表 -->
    <el-card class="list-card devices-card">
      <template #header>
        <div class="card-header">
          <span>
            <i class="el-icon-monitor"></i>
            设备列表
          </span>
          <el-button 
            type="primary" 
            size="small" 
            @click="refreshDevices"
            :loading="loading"
          >
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <!-- 桌面端表格 -->
      <div class="table-wrapper">
        <el-table 
          :data="devices" 
          v-loading="loading"
          style="width: 100%"
          stripe
        >
        <el-table-column prop="device_name" label="设备名称" min-width="150">
          <template #default="{ row }">
            <div class="device-name">
              <i :class="getDeviceIcon(row.device_type)"></i>
              <span>{{ row.device_name || '未知设备' }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="device_type" label="设备类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getDeviceTypeColor(row.device_type)">
              {{ getDeviceTypeName(row.device_type) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="ip_address" label="IP地址" width="140">
          <template #default="{ row }">
            <span class="ip-address">{{ row.ip_address }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="last_access" label="最后访问" width="180">
          <template #default="{ row }">
            <span>{{ formatTime(row.last_access) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="user_agent" label="User Agent" min-width="200">
          <template #default="{ row }">
            <el-tooltip :content="row.user_agent" placement="top">
              <span class="user-agent">{{ truncateUserAgent(row.user_agent) }}</span>
            </el-tooltip>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button 
                type="danger" 
                size="small" 
                @click="removeDevice(row.id)"
                :loading="row.removing"
              >
                移除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      </div>

      <!-- 移动端卡片式列表 -->
      <div class="mobile-card-list" v-if="devices.length > 0">
        <div 
          v-for="device in devices" 
          :key="device.id"
          class="mobile-card"
        >
          <div class="card-row">
            <span class="label">设备名称</span>
            <span class="value">
              <i :class="getDeviceIcon(device.device_type)"></i>
              {{ device.device_name || '未知设备' }}
            </span>
          </div>
          <div class="card-row">
            <span class="label">设备类型</span>
            <span class="value">
              <el-tag v-if="device.device_type && device.device_type !== 'unknown'" 
                      :type="getDeviceTypeColor(device.device_type)">
                {{ getDeviceTypeName(device.device_type) }}
              </el-tag>
              <span v-else style="color: #909399; font-size: 12px;">-</span>
            </span>
          </div>
          <div class="card-row">
            <span class="label">IP地址</span>
            <span class="value ip-address">{{ device.ip_address }}</span>
          </div>
          <div class="card-row">
            <span class="label">最后访问</span>
            <span class="value">{{ formatTime(device.last_access) }}</span>
          </div>
          <div class="card-row">
            <span class="label">User Agent</span>
            <span class="value user-agent">{{ truncateUserAgent(device.user_agent) }}</span>
          </div>
          <div class="card-actions">
            <el-button 
              type="danger" 
              size="small" 
              @click="removeDevice(device.id)"
              :loading="device.removing"
            >
              移除
            </el-button>
          </div>
        </div>
      </div>

      <!-- 移动端空状态 -->
      <div class="mobile-card-list" v-if="!loading && devices.length === 0">
        <div class="empty-state">
          <i class="el-icon-monitor"></i>
          <p>暂无设备记录</p>
          <el-button type="primary" @click="refreshDevices" style="margin-top: 1rem;">
            刷新设备列表
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 设备类型统计 -->
    <el-card class="chart-card">
      <template #header>
        <div class="card-header">
          <i class="el-icon-pie-chart"></i>
          设备类型统计
        </div>
      </template>
      
      <div class="chart-container">
        <div class="chart-item" v-for="(count, type) in deviceTypeStats" :key="type">
          <div class="chart-label">{{ getDeviceTypeName(type) }}</div>
          <div class="chart-bar">
            <div 
              class="chart-fill" 
              :style="{ width: getPercentage(count) + '%' }"
            ></div>
          </div>
          <div class="chart-count">{{ count }}</div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { subscriptionAPI } from '@/utils/api'
import { formatDateTime } from '@/utils/date'

export default {
  name: 'Devices',
  components: {
    Refresh
  },
  setup() {
    const loading = ref(false)
    const devices = ref([])

    const deviceStats = reactive({
      total: 0,
      online: 0,
      mobile: 0,
      desktop: 0
    })

    const deviceTypeStats = computed(() => {
      const stats = {}
      devices.value.forEach(device => {
        const type = device.device_type || 'unknown'
        stats[type] = (stats[type] || 0) + 1
      })
      return stats
    })

    // 获取设备列表
    const fetchDevices = async () => {
      loading.value = true
      try {
        const response = await subscriptionAPI.getDevices()
        // 检查响应结构
        if (response && response.data) {
          const responseData = response.data
          
          // 处理多种可能的响应格式
          if (responseData.success !== false && responseData.data) {
            if (responseData.data.devices && Array.isArray(responseData.data.devices)) {
              devices.value = responseData.data.devices
            } else if (Array.isArray(responseData.data)) {
              devices.value = responseData.data
            } else {
              devices.value = []
            }
          } else {
            devices.value = []
            }
        } else {
          devices.value = []
          }
        
        // 计算统计数据
        updateDeviceStats()
      } catch (error) {
        ElMessage.error('获取设备列表失败: ' + (error.response?.data?.message || error.message || '未知错误'))
        devices.value = []
        updateDeviceStats()
      } finally {
        loading.value = false
      }
    }

    // 更新设备统计
    const updateDeviceStats = () => {
      deviceStats.total = devices.value.length
      deviceStats.online = devices.value.filter(d => isOnline(d.last_access)).length
      deviceStats.mobile = devices.value.filter(d => d.device_type === 'mobile').length
      deviceStats.desktop = devices.value.filter(d => d.device_type === 'desktop').length
    }

    // 刷新设备列表
    const refreshDevices = () => {
      fetchDevices()
    }

    // 移除设备
    const removeDevice = async (deviceId) => {
      try {
        await ElMessageBox.confirm(
          '确定要移除这个设备吗？移除后该设备将无法继续使用订阅服务。',
          '确认移除',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )

        // 设置移除状态
        const device = devices.value.find(d => d.id === deviceId)
        if (device) {
          device.removing = true
        }

        await subscriptionAPI.removeDevice(deviceId)
        ElMessage.success('设备移除成功')
        
        // 重新获取设备列表
        await fetchDevices()
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('移除设备失败')
        }
      }
    }

    // 获取设备图标
    const getDeviceIcon = (deviceType) => {
      const icons = {
        mobile: 'el-icon-mobile-phone',
        desktop: 'el-icon-monitor',
        tablet: 'el-icon-tablet',
        tv: 'el-icon-video-camera',
        unknown: 'el-icon-question'
      }
      return icons[deviceType] || icons.unknown
    }

    // 获取设备类型名称
    const getDeviceTypeName = (deviceType) => {
      const names = {
        mobile: '手机',
        desktop: '电脑',
        tablet: '平板',
        server: '服务器',
        unknown: '未知'
      }
      return names[deviceType] || '未知'
    }

    // 获取设备类型颜色
    const getDeviceTypeColor = (deviceType) => {
      const colors = {
        mobile: 'primary',
        desktop: 'success',
        tablet: 'warning',
        server: 'danger',
        unknown: 'info'
      }
      return colors[deviceType] || colors.unknown
    }

    // 格式化时间
    const formatTime = (time) => {
      if (!time) return '未知'
      // 使用北京时间格式化
      return formatDateTime(time, 'YYYY-MM-DD HH:mm:ss')
    }

    // 截断User Agent
    const truncateUserAgent = (ua) => {
      if (!ua) return '未知'
      return ua.length > 50 ? ua.substring(0, 50) + '...' : ua
    }

    // 检查是否在线（24小时内访问过）
    const isOnline = (lastAccess) => {
      if (!lastAccess) return false
      const lastTime = dayjs(lastAccess)
      const now = dayjs()
      return now.diff(lastTime, 'hour') < 24
    }

    // 计算百分比
    const getPercentage = (count) => {
      if (deviceStats.total === 0) return 0
      return Math.round((count / deviceStats.total) * 100)
    }

    onMounted(() => {
      fetchDevices()
    })

    return {
      loading,
      devices,
      deviceStats,
      deviceTypeStats,
      fetchDevices,
      refreshDevices,
      removeDevice,
      getDeviceIcon,
      getDeviceTypeName,
      getDeviceTypeColor,
      formatTime,
      truncateUserAgent,
      getPercentage
    }
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/list-common.scss';

.device-name {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  
  :is(i) {
    font-size: 1.2rem;
    color: var(--primary-color);
  }
}

.ip-address {
  font-family: 'Courier New', monospace;
  color: #666;
  font-size: 0.9rem;
}

.user-agent {
  color: #666;
  font-size: 0.9rem;
}

.chart-card {
  background: var(--card-bg);
  border-radius: var(--border-radius);
  box-shadow: var(--card-shadow);
  margin-bottom: 1.5rem;
}

.chart-container {
  padding: 1rem 0;
  
  @media (max-width: 768px) {
    padding: 0.75rem 0;
  }
}

.chart-item {
  display: flex;
  align-items: center;
  margin-bottom: 1rem;
  gap: 1rem;
  
  @media (max-width: 768px) {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }
}

.chart-label {
  width: 100px;
  font-weight: 500;
  color: #333;
  
  @media (max-width: 768px) {
    width: auto;
    font-size: 0.9rem;
  }
}

.chart-bar {
  flex: 1;
  height: 20px;
  background: #f0f0f0;
  border-radius: 10px;
  overflow: hidden;
  
  @media (max-width: 768px) {
    width: 100%;
    height: 16px;
  }
}

.chart-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
  border-radius: 10px;
  transition: width 0.3s ease;
}

.chart-count {
  width: 60px;
  text-align: right;
  font-weight: 600;
  color: var(--primary-color);
  
  @media (max-width: 768px) {
    width: auto;
    font-size: 0.9rem;
  }
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: #999;
  
  :is(i) {
    font-size: 3rem;
    margin-bottom: 1rem;
    display: block;
  }
  
  :is(p) {
    font-size: 0.9rem;
    margin: 0 0 1rem 0;
  }
}
</style> 