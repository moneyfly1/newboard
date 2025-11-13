<template>
  <div class="admin-payment-config">
    <el-card>
      <template #header>
        <div class="header-content">
          <span>支付配置管理</span>
          <div class="header-actions desktop-only">
            <el-button type="success" @click="exportConfigs">
              <el-icon><Download /></el-icon>
              导出配置
            </el-button>
            <el-button type="warning" @click="showBulkOperationsDialog = true">
              <el-icon><Operation /></el-icon>
              批量操作
            </el-button>
            <el-button type="info" @click="showStatisticsDialog = true">
              <el-icon><DataAnalysis /></el-icon>
              配置统计
            </el-button>
            <el-button type="primary" @click="showAddDialog = true">
              <el-icon><Plus /></el-icon>
              添加支付配置
            </el-button>
          </div>
          <div class="header-actions mobile-only">
            <el-button type="primary" @click="showAddDialog = true" size="small">
              <el-icon><Plus /></el-icon>
              添加
            </el-button>
            <el-dropdown @command="handleMobileAction" trigger="click">
              <el-button type="default" size="small">
                <el-icon><Operation /></el-icon>
                更多
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="export">
                    <el-icon><Download /></el-icon>
                    导出配置
                  </el-dropdown-item>
                  <el-dropdown-item command="bulk">
                    <el-icon><Operation /></el-icon>
                    批量操作
                  </el-dropdown-item>
                  <el-dropdown-item command="statistics">
                    <el-icon><DataAnalysis /></el-icon>
                    配置统计
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </template>
      <div class="table-wrapper desktop-only">
        <el-table :data="paymentConfigs" style="width: 100%" v-loading="loading" :empty-text="paymentConfigs.length === 0 ? '暂无支付配置，请点击右上角【添加支付配置】按钮添加' : '暂无数据'">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="pay_type" label="支付类型" width="120">
            <template #default="scope">
              <el-tag :type="getTypeTagType(scope.row.pay_type)">
                {{ getTypeText(scope.row.pay_type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="app_id" label="应用ID/商户ID" min-width="200">
            <template #default="scope">
              <span v-if="scope.row.app_id">{{ scope.row.app_id }}</span>
              <span v-else-if="scope.row.config_json && scope.row.config_json.yipay_pid">
                {{ scope.row.config_json.yipay_pid }} ({{ getTypeText(scope.row.pay_type) }})
              </span>
              <span v-else class="text-muted">未配置</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120" align="center">
            <template #default="scope">
              <el-switch
                v-model="scope.row.status"
                :active-value="1"
                :inactive-value="0"
                @change="(newValue) => toggleStatus(scope.row, newValue)"
              />
              <span style="margin-left: 8px; font-size: 12px; color: #909399;">
                {{ scope.row.status === 1 ? '已启用' : '已禁用' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180" />
          <el-table-column label="操作" width="180" align="center">
            <template #default="scope">
              <el-button size="small" type="primary" @click="editConfig(scope.row)">
                编辑
              </el-button>
              <el-button size="small" type="danger" @click="deleteConfig(scope.row)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 移动端卡片式列表 -->
      <div class="mobile-card-list mobile-only" v-if="paymentConfigs.length > 0">
        <div 
          v-for="config in paymentConfigs" 
          :key="config.id"
          class="mobile-card"
        >
          <div class="card-row">
            <span class="label">ID</span>
            <span class="value">#{{ config.id }}</span>
          </div>
          <div class="card-row">
            <span class="label">支付类型</span>
            <span class="value">
              <el-tag :type="getTypeTagType(config.pay_type)">
                {{ getTypeText(config.pay_type) }}
              </el-tag>
            </span>
          </div>
          <div class="card-row">
            <span class="label">应用ID/商户ID</span>
            <span class="value">
              <span v-if="config.app_id">{{ config.app_id }}</span>
              <span v-else-if="config.config_json && config.config_json.yipay_pid">
                {{ config.config_json.yipay_pid }}
              </span>
              <span v-else class="text-muted">未配置</span>
            </span>
          </div>
          <div class="card-row">
            <span class="label">状态</span>
            <span class="value">
              <el-switch
                v-model="config.status"
                :active-value="1"
                :inactive-value="0"
                @change="(newValue) => toggleStatus(config, newValue)"
              />
              <span style="margin-left: 8px; font-size: 14px; color: #909399;">
                {{ config.status === 1 ? '已启用' : '已禁用' }}
              </span>
            </span>
          </div>
          <div class="card-row">
            <span class="label">创建时间</span>
            <span class="value">{{ config.created_at || '-' }}</span>
          </div>
          <div class="card-actions">
            <el-button 
              size="small" 
              type="primary" 
              @click="editConfig(config)"
            >
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button 
              size="small" 
              type="danger" 
              @click="deleteConfig(config)"
            >
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </div>
        </div>
      </div>

      <!-- 移动端空状态 -->
      <div class="mobile-card-list mobile-only" v-if="paymentConfigs.length === 0 && !loading">
        <div class="empty-state">
          <el-empty description="暂无支付配置，请点击右上角【添加】按钮添加" :image-size="80" />
        </div>
      </div>
    </el-card>
    <el-dialog
      v-model="showAddDialog"
      :title="editingConfig ? '编辑支付配置' : '添加支付配置'"
      width="600px"
      :class="isMobile ? 'mobile-dialog' : ''"
    >
      <el-form :model="configForm" label-width="120px">
        <el-form-item label="支付类型">
          <el-select v-model="configForm.pay_type" placeholder="选择支付类型">
            <el-option label="支付宝" value="alipay" />
            <el-option label="易支付-支付宝" value="yipay_alipay" />
            <el-option label="易支付-微信" value="yipay_wxpay" />
            <el-option label="微信支付" value="wechat" />
            <el-option label="PayPal" value="paypal" />
          </el-select>
        </el-form-item>

        <el-form-item label="应用ID" v-if="configForm.pay_type === 'alipay' || configForm.pay_type === 'wechat'">
          <el-input v-model="configForm.app_id" placeholder="请输入应用ID" />
        </el-form-item>
        <el-form-item label="商户ID" v-if="configForm.pay_type === 'yipay_alipay' || configForm.pay_type === 'yipay_wxpay'">
          <el-input v-model="configForm.yipay_pid" placeholder="请输入易支付商户ID" />
          <div class="form-tip">在易支付商户后台->个人资料->API信息中查看（易支付-支付宝和易支付-微信使用相同的商户ID）</div>
        </el-form-item>

        <el-form-item label="商户私钥" v-if="configForm.pay_type === 'yipay_alipay' || configForm.pay_type === 'yipay_wxpay'">
          <el-input
            v-model="configForm.yipay_private_key"
            type="textarea"
            :rows="4"
            placeholder="请输入易支付商户私钥"
          />
          <div class="form-tip">在易支付商户后台->个人资料->API信息中点击"生成商户RSA密钥对"生成（V2接口使用RSA签名，易支付-支付宝和易支付-微信使用相同的私钥）</div>
        </el-form-item>

        <el-form-item label="平台公钥" v-if="configForm.pay_type === 'yipay_alipay' || configForm.pay_type === 'yipay_wxpay'">
          <el-input
            v-model="configForm.yipay_public_key"
            type="textarea"
            :rows="4"
            placeholder="请输入易支付平台公钥"
          />
          <div class="form-tip">在易支付商户后台->个人资料->API信息中查看（用于验签，易支付-支付宝和易支付-微信使用相同的公钥）</div>
        </el-form-item>

        <el-form-item label="网关地址" v-if="configForm.pay_type === 'yipay_alipay' || configForm.pay_type === 'yipay_wxpay'">
          <el-input v-model="configForm.yipay_gateway" placeholder="请输入易支付网关地址" />
          <div class="form-tip">默认: https://pay.yi-zhifu.cn/（系统会自动拼接V2接口路径 /api/pay/create）</div>
        </el-form-item>
        <el-form-item label="支付宝公钥" v-if="configForm.pay_type === 'alipay'">
          <el-input
            v-model="configForm.alipay_public_key"
            type="textarea"
            :rows="4"
            placeholder="请输入支付宝公钥"
          />
        </el-form-item>

        <el-form-item label="商户私钥" v-if="configForm.pay_type === 'alipay'">
          <el-input
            v-model="configForm.merchant_private_key"
            type="textarea"
            :rows="4"
            placeholder="请输入商户私钥"
          />
        </el-form-item>

        <el-form-item label="支付宝网关" v-if="configForm.pay_type === 'alipay'">
          <el-input v-model="configForm.alipay_gateway" placeholder="请输入支付宝网关地址" />
          <div class="form-tip">默认: https://openapi.alipay.com/gateway.do (生产环境) 或 https://openapi.alipaydev.com/gateway.do (沙箱环境)</div>
        </el-form-item>
        <el-form-item label="商户号" v-if="configForm.pay_type === 'wechat'">
          <el-input v-model="configForm.wechat_mch_id" placeholder="请输入微信商户号" />
        </el-form-item>

        <el-form-item label="API密钥" v-if="configForm.pay_type === 'wechat'">
          <el-input v-model="configForm.wechat_api_key" placeholder="请输入微信API密钥" />
        </el-form-item>
        <el-form-item label="同步回调地址">
          <el-input v-model="configForm.return_url" placeholder="请输入同步回调地址" />
          <div class="form-tip">支付完成后跳转的地址</div>
        </el-form-item>

        <el-form-item label="异步回调地址">
          <el-input v-model="configForm.notify_url" placeholder="请输入异步回调地址" />
          <div class="form-tip">支付完成后服务器通知的地址</div>
        </el-form-item>

        <el-form-item label="状态">
          <el-select v-model="configForm.status" placeholder="选择状态">
            <el-option label="启用" :value="1" />
            <el-option label="禁用" :value="0" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer-buttons">
          <el-button @click="showAddDialog = false" class="mobile-action-btn">取消</el-button>
          <el-button type="primary" @click="saveConfig" :loading="saving" class="mobile-action-btn">
            {{ editingConfig ? '更新' : '创建' }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Operation, Plus, Edit, Delete, DataAnalysis } from '@element-plus/icons-vue'
import { paymentAPI } from '@/utils/api'

export default {
  name: 'AdminPaymentConfig',
  components: { Download, Operation, Plus, Edit, Delete, DataAnalysis },
  setup() {
    const loading = ref(false)
    const saving = ref(false)
    const paymentConfigs = ref([])
    const showAddDialog = ref(false)
    const showBulkOperationsDialog = ref(false)
    const showStatisticsDialog = ref(false)
    const editingConfig = ref(null)
    const isMobile = ref(false)

    const checkMobile = () => {
      isMobile.value = window.innerWidth <= 768
    }

    const configForm = reactive({
      pay_type: '',
      app_id: '',
      merchant_private_key: '',
      alipay_public_key: '',
      alipay_gateway: 'https://openapi.alipay.com/gateway.do',
      // 微信支付配置
      wechat_mch_id: '',
      wechat_api_key: '',
      // 易支付配置
      yipay_type: 'alipay',  // 支付类型：alipay 或 wxpay
      yipay_pid: '',
      yipay_private_key: '',
      yipay_public_key: '',
      yipay_gateway: 'https://pay.yi-zhifu.cn/api/pay/create',
      yipay_md5_key: '',
      // PayPal配置
      paypal_client_id: '',
      paypal_secret: '',
      // Stripe配置
      stripe_publishable_key: '',
      stripe_secret_key: '',
      return_url: '',
      notify_url: '',
      status: 1,
      sort_order: 0
    })

    const loadPaymentConfigs = async () => {
      loading.value = true
      try {
        // 使用管理员API获取支付配置列表
        const response = await paymentAPI.getPaymentConfigs({
          page: 1,
          size: 100  // 获取更多配置
        })
        // 处理响应数据
        if (response && response.data) {
          // 处理标准响应格式 { success: true, data: { items: [...], total: ... } }
          if (response.data.success && response.data.data) {
            if (response.data.data.items && Array.isArray(response.data.data.items)) {
              paymentConfigs.value = response.data.data.items
            } else if (Array.isArray(response.data.data)) {
              paymentConfigs.value = response.data.data
            } else {
              paymentConfigs.value = []
            }
          } 
          // 处理直接返回 items 的格式 { items: [...], total: ... }
          else if (response.data.items && Array.isArray(response.data.items)) {
            paymentConfigs.value = response.data.items
          } 
          // 处理直接返回数组的格式 [...]
          else if (Array.isArray(response.data)) {
            paymentConfigs.value = response.data
          } else {
            paymentConfigs.value = []
          }
        } else {
          paymentConfigs.value = []
        }
        
        // 检查是否有易支付配置
        const yipayConfig = paymentConfigs.value.find(c => c.pay_type === 'yipay_alipay' || c.pay_type === 'yipay_wxpay')
      } catch (error) {
        ElMessage.error('加载支付配置列表失败: ' + (error.response?.data?.detail || error.message))
        paymentConfigs.value = []
      } finally {
        loading.value = false
      }
    }

    const saveConfig = async () => {
      saving.value = true
      try {
        // 构建请求数据
        const requestData = {
          pay_type: configForm.pay_type,
          status: configForm.status,
          return_url: configForm.return_url,
          notify_url: configForm.notify_url,
          sort_order: configForm.sort_order || 0
        }

        // 根据支付类型添加特定配置
        if (configForm.pay_type === 'alipay') {
          requestData.app_id = configForm.app_id
          requestData.merchant_private_key = configForm.merchant_private_key
          requestData.alipay_public_key = configForm.alipay_public_key
          requestData.alipay_gateway = configForm.alipay_gateway || 'https://openapi.alipay.com/gateway.do'
        } else if (configForm.pay_type === 'wechat') {
          requestData.app_id = configForm.app_id
          requestData.wechat_app_id = configForm.app_id
          requestData.wechat_mch_id = configForm.wechat_mch_id
          requestData.wechat_api_key = configForm.wechat_api_key
        } else if (configForm.pay_type === 'yipay_alipay' || configForm.pay_type === 'yipay_wxpay') {
          // 易支付配置保存到config_json
          // 根据 pay_type 确定 yipay_type（调用值）
          const yipay_type = configForm.pay_type === 'yipay_alipay' ? 'alipay' : 'wxpay'
          requestData.config_json = {
            yipay_type: yipay_type,  // 调用值：alipay 或 wxpay
            yipay_pid: configForm.yipay_pid,
            yipay_private_key: configForm.yipay_private_key,
            yipay_public_key: configForm.yipay_public_key,
            yipay_gateway: configForm.yipay_gateway || 'https://pay.yi-zhifu.cn/',
            yipay_md5_key: configForm.yipay_md5_key || ''
          }
        } else if (configForm.pay_type === 'paypal') {
          requestData.paypal_client_id = configForm.paypal_client_id
          requestData.paypal_secret = configForm.paypal_secret
        } else if (configForm.pay_type === 'stripe') {
          requestData.stripe_publishable_key = configForm.stripe_publishable_key
          requestData.stripe_secret_key = configForm.stripe_secret_key
        }

        if (editingConfig.value) {
          await paymentAPI.updatePaymentConfig(editingConfig.value.id, requestData)
          ElMessage.success('支付配置更新成功')
        } else {
          await paymentAPI.createPaymentConfig(requestData)
          ElMessage.success('支付配置创建成功')
        }

        showAddDialog.value = false
        resetConfigForm()
        loadPaymentConfigs()
      } catch (error) {
        ElMessage.error('操作失败: ' + (error.response?.data?.detail || error.message))
      } finally {
        saving.value = false
      }
    }

    const editConfig = (config) => {
      editingConfig.value = config
      // 从config中提取配置信息
      const configData = config.config_json || {}
      Object.assign(configForm, {
        pay_type: config.pay_type || '',
        app_id: config.app_id || configData.app_id || '',
        merchant_private_key: config.merchant_private_key || configData.merchant_private_key || '',
        alipay_public_key: config.alipay_public_key || configData.alipay_public_key || '',
        alipay_gateway: config.alipay_gateway || configData.alipay_gateway || 'https://openapi.alipay.com/gateway.do',
        // 微信支付配置
        wechat_mch_id: config.wechat_mch_id || configData.mch_id || '',
        wechat_api_key: config.wechat_api_key || configData.api_key || '',
        // 易支付配置
        yipay_type: configData.yipay_type || 'alipay',  // 支付类型
        yipay_pid: configData.yipay_pid || '',
        yipay_private_key: configData.yipay_private_key || '',
        yipay_public_key: configData.yipay_public_key || '',
        yipay_gateway: configData.yipay_gateway || 'https://pay.yi-zhifu.cn/api/pay/create',
        yipay_md5_key: configData.yipay_md5_key || '',
        // PayPal配置
        paypal_client_id: config.paypal_client_id || configData.client_id || '',
        paypal_secret: config.paypal_secret || configData.secret || '',
        // Stripe配置
        stripe_publishable_key: config.stripe_publishable_key || configData.publishable_key || '',
        stripe_secret_key: config.stripe_secret_key || configData.secret_key || '',
        return_url: config.return_url || '',
        notify_url: config.notify_url || '',
        status: config.status !== undefined ? config.status : 1,
        sort_order: config.sort_order || 0
      })
      showAddDialog.value = true
    }

    const deleteConfig = async (config) => {
      try {
        await ElMessageBox.confirm(
          `确定要删除支付配置 "${config.pay_type}" 吗？`,
          '确认删除',
          { type: 'warning' }
        )
        await paymentAPI.deletePaymentConfig(config.id)
        ElMessage.success('支付配置删除成功')
        loadPaymentConfigs()
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('删除失败')
        }
      }
    }

    const toggleStatus = async (config, newValue) => {
      // newValue 是 switch 组件传递的新状态值（1 或 0）
      // 如果 newValue 未传递，则从 config.status 获取（已经被 switch 更新了）
      const newStatus = newValue !== undefined ? newValue : config.status
      const oldStatus = newStatus === 1 ? 0 : 1
      
      try {
        // 使用管理员API更新支付配置状态
        const response = await paymentAPI.updatePaymentConfig(config.id, { status: newStatus })
        
        // 如果响应成功，使用返回的数据更新状态
        if (response.data && response.data.status !== undefined) {
          config.status = response.data.status
        } else {
          // 如果响应没有返回状态，使用请求的状态
          config.status = newStatus
        }
        
        ElMessage.success(`支付配置${newStatus === 1 ? '启用' : '禁用'}成功`)
        // 重新加载配置列表以确保数据同步
        await loadPaymentConfigs()
      } catch (error) {
        // 恢复原状态
        config.status = oldStatus
        ElMessage.error('状态更新失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
      }
    }

    const resetConfigForm = () => {
      Object.assign(configForm, {
        pay_type: '',
        app_id: '',
        merchant_private_key: '',
        alipay_public_key: '',
        alipay_gateway: 'https://openapi.alipay.com/gateway.do',
        // 微信支付配置
        wechat_mch_id: '',
        wechat_api_key: '',
        // 易支付配置
        yipay_type: 'alipay',  // 支付类型
        yipay_pid: '',
        yipay_private_key: '',
        yipay_public_key: '',
        yipay_gateway: 'https://pay.yi-zhifu.cn/api/pay/create',
        yipay_md5_key: '',
        // PayPal配置
        paypal_client_id: '',
        paypal_secret: '',
        // Stripe配置
        stripe_publishable_key: '',
        stripe_secret_key: '',
        return_url: '',
        notify_url: '',
        status: 1,
        sort_order: 0
      })
      editingConfig.value = null
    }

    const getTypeText = (type) => {
      const typeMap = {
        'alipay': '支付宝',
        'yipay': '易支付',
        'yipay_alipay': '易支付-支付宝',
        'yipay_wxpay': '易支付-微信',
        'wechat': '微信支付',
        'paypal': 'PayPal'
      }
      return typeMap[type] || type
    }

    const getTypeTagType = (type) => {
      const typeMap = {
        'alipay': 'success',
        'yipay': 'warning',
        'yipay_alipay': 'warning',
        'yipay_wxpay': 'warning',
        'wechat': 'primary',
        'paypal': 'warning'
      }
      return typeMap[type] || 'info'
    }

    const exportConfigs = () => {
      ElMessage.info('导出功能开发中')
    }

    const handleMobileAction = (command) => {
      switch (command) {
        case 'export':
          exportConfigs()
          break
        case 'bulk':
          showBulkOperationsDialog.value = true
          break
        case 'statistics':
          showStatisticsDialog.value = true
          break
      }
    }

    onMounted(() => {
      checkMobile()
      window.addEventListener('resize', checkMobile)
      loadPaymentConfigs()
    })

    onUnmounted(() => {
      window.removeEventListener('resize', checkMobile)
    })

    return {
      loading,
      saving,
      paymentConfigs,
      showAddDialog,
      showBulkOperationsDialog,
      showStatisticsDialog,
      editingConfig,
      configForm,
      loadPaymentConfigs,
      saveConfig,
      editConfig,
      deleteConfig,
      toggleStatus,
      resetConfigForm,
      getTypeText,
      getTypeTagType,
      exportConfigs,
      handleMobileAction,
      isMobile
    }
  }
}
</script>

<style scoped>
.admin-payment-config {
  padding: 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.text-muted {
  color: #909399;
  font-style: italic;
}

:deep(.el-table .el-table__row:hover) {
  background-color: #f5f7fa;
}

/* 移除所有输入框的圆角和阴影效果，设置为简单长方形 */
:deep(.el-input__wrapper) {
  border-radius: 0 !important;
  box-shadow: none !important;
  border: 1px solid #dcdfe6 !important;
  background-color: #ffffff !important;
}

:deep(.el-select .el-input__wrapper) {
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
}

:deep(.el-input__wrapper.is-focus) {
  border-color: #1677ff !important;
  box-shadow: none !important;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.5;
}

/* 桌面端/移动端显示控制 */
.desktop-only {
  @media (max-width: 768px) {
    display: none !important;
  }
}

.mobile-only {
  display: none;
  
  @media (max-width: 768px) {
    display: block;
  }
  
  &.mobile-card-list {
    @media (max-width: 768px) {
      display: flex;
      flex-direction: column;
    }
  }
  
  &.header-actions {
    @media (max-width: 768px) {
      display: flex;
      gap: 8px;
    }
  }
}

/* 移动端样式 */
@media (max-width: 768px) {
  .admin-payment-config {
    padding: 10px;
  }

  .header-content {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .header-actions {
    width: 100%;
    display: flex;
    flex-direction: row;
    gap: 8px;
    
    .el-button {
      flex: 1;
      height: 40px;
      font-size: 14px;
      font-weight: 500;
    }
  }

  /* 移动端卡片列表 */
  .mobile-card-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .mobile-card {
    background: #fff;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    padding: 16px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  }

  .card-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid #f0f0f0;
    
    &:last-of-type {
      border-bottom: none;
    }
    
    .label {
      font-weight: 600;
      color: #606266;
      font-size: 14px;
      min-width: 100px;
    }
    
    .value {
      flex: 1;
      text-align: right;
      color: #303133;
      font-size: 14px;
      word-break: break-all;
    }
  }

  .card-actions {
    display: flex;
    gap: 12px;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid #f0f0f0;
    
    .el-button {
      flex: 1;
      height: 44px;
      font-size: 16px;
      font-weight: 500;
      
      :deep(.el-icon) {
        margin-right: 6px;
        font-size: 16px;
      }
    }
  }

  .empty-state {
    padding: 40px 20px;
    text-align: center;
  }

  /* 移动端对话框 */
  .mobile-dialog {
    :deep(.el-dialog) {
      width: 95% !important;
      margin: 0 auto;
      max-height: 90vh;
    }

    :deep(.el-dialog__body) {
      max-height: calc(90vh - 120px);
      overflow-y: auto;
      padding: 15px;
    }

    :deep(.el-form-item) {
      margin-bottom: 18px;
    }

    :deep(.el-form-item__label) {
      width: 100% !important;
      text-align: left;
      margin-bottom: 8px;
      padding: 0;
      font-weight: 600;
    }

    :deep(.el-form-item__content) {
      margin-left: 0 !important;
    }

    .dialog-footer-buttons {
      display: flex;
      flex-direction: column;
      gap: 12px;
      width: 100%;
      
      .mobile-action-btn,
      .el-button {
        width: 100% !important;
        height: 44px !important;
        font-size: 16px !important;
        margin: 0 !important;
      }
    }
  }
}
</style>