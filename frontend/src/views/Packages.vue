<template>
  <div class="list-container packages-container">

    <!-- 加载状态 -->
    <div v-if="isLoading" class="loading-container">
      <el-icon class="is-loading"><Loading /></el-icon>
      <p>正在加载套餐列表...</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="errorMessage" class="error-container">
      <el-alert
        :title="errorMessage"
        type="error"
        :closable="false"
        show-icon
      />
      <el-button @click="loadPackages" type="primary" style="margin-top: 10px;">
        重试加载
      </el-button>
    </div>

    <!-- 套餐列表 -->
    <div v-else-if="packages.length > 0" class="packages-grid">
      <el-card 
        v-for="pkg in packages" 
        :key="pkg.id" 
        class="package-card"
        :class="{ 'popular': pkg.is_popular, 'recommended': pkg.is_recommended }"
      >
        <div class="package-header">
          <h3 class="package-name">{{ pkg.name }}</h3>
          <div v-if="pkg.is_popular" class="popular-badge">热门</div>
          <div v-if="pkg.is_recommended" class="recommended-badge">推荐</div>
        </div>
        
        <div class="package-price">
          <span class="currency">¥</span>
          <span class="amount">{{ pkg.price }}</span>
          <span class="period">/{{ pkg.duration_days }}天</span>
        </div>
        
        <div class="package-features">
          <ul>
            <li v-for="feature in pkg.features" :key="feature">
              <i class="el-icon-check"></i>
              {{ feature }}
            </li>
          </ul>
        </div>
        
        <div class="package-description">
          <p>{{ pkg.description }}</p>
        </div>
        
        <div class="package-actions">
          <el-button 
            type="primary" 
            size="large" 
            @click.stop.prevent="selectPackage(pkg)"
            :loading="isProcessing"
            :disabled="isProcessing || !pkg || !pkg.id"
            style="width: 100%"
          >
            {{ isProcessing ? '处理中...' : '立即购买' }}
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-container">
      <el-empty description="暂无可用套餐" />
    </div>

    <!-- 购买确认对话框 -->
    <el-dialog
      v-model="purchaseDialogVisible"
      title="确认购买"
      :width="isMobile ? '90%' : '500px'"
      :close-on-click-modal="false"
      class="purchase-dialog"
    >
      <div class="purchase-confirm">
        <div class="package-summary">
          <h4>套餐信息</h4>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="套餐名称">{{ selectedPackage?.name }}</el-descriptions-item>
            <el-descriptions-item label="有效期">{{ selectedPackage?.duration_days }}天</el-descriptions-item>
            <el-descriptions-item label="设备限制">{{ selectedPackage?.device_limit }}个</el-descriptions-item>
            <el-descriptions-item label="流量限制">
              {{ selectedPackage?.bandwidth_limit ? selectedPackage.bandwidth_limit + 'GB' : '无限制' }}
            </el-descriptions-item>
            <el-descriptions-item label="原价">
              <span>¥{{ selectedPackage?.price }}</span>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- 优惠券输入 -->
        <div class="coupon-section" style="margin-top: 20px; padding: 15px; background: #f5f7fa; border-radius: 4px">
          <h4 style="margin-bottom: 10px">优惠券（可选）</h4>
          <div class="coupon-input-group">
            <el-input
              v-model="couponCode"
              placeholder="输入优惠券码"
              class="coupon-input"
              :disabled="validatingCoupon || isProcessing"
              @input="handleCouponInput"
              @focus="handleCouponFocus"
            />
            <div class="coupon-buttons">
              <el-button
                @click="validateCoupon"
                :loading="validatingCoupon"
                :disabled="!couponCode || isProcessing"
                size="default"
              >
                验证
              </el-button>
              <el-button
                v-if="couponCode"
                @click="clearCoupon"
                :disabled="isProcessing"
                size="default"
              >
                清除
              </el-button>
            </div>
          </div>
          <div v-if="couponInfo" style="margin-top: 10px">
            <el-alert
              :title="couponInfo.message"
              :type="couponInfo.valid ? 'success' : 'error'"
              :closable="false"
              show-icon
            />
            <div v-if="couponInfo.valid && couponInfo.discount_amount" style="margin-top: 10px; color: #67c23a; font-weight: bold">
              优惠金额：¥{{ couponInfo.discount_amount.toFixed(2) }}
            </div>
          </div>
        </div>

        <!-- 价格汇总 -->
        <div class="price-summary" style="margin-top: 20px; padding: 15px; background: #f0f9ff; border-radius: 4px">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="原价">
              <span>¥{{ selectedPackage?.price }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="优惠金额" v-if="couponInfo && couponInfo.valid && couponInfo.discount_amount">
              <span style="color: #67c23a">-¥{{ couponInfo.discount_amount.toFixed(2) }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="实付金额">
              <span class="amount" style="font-size: 20px; color: #f56c6c; font-weight: bold">
                ¥{{ finalAmount.toFixed(2) }}
              </span>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- 支付方式选择 -->
        <div class="payment-method-section" style="margin-top: 20px; padding: 15px; background: #fff; border-radius: 4px; border: 1px solid #e4e7ed">
          <h4 style="margin-bottom: 15px">支付方式</h4>
          
          <!-- 账户余额显示 -->
          <div class="balance-info" style="margin-bottom: 15px; padding: 10px; background: #f5f7fa; border-radius: 4px">
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: 600">账户余额：</span>
              <span style="font-size: 18px; color: #409eff; font-weight: 700">¥{{ userBalance.toFixed(2) }}</span>
            </div>
          </div>

          <!-- 支付方式选择 -->
          <el-radio-group v-model="paymentMethod" @change="handlePaymentMethodChange" style="width: 100%">
            <el-radio label="balance" :disabled="userBalance <= 0" style="width: 100%; margin-bottom: 10px; padding: 10px; border: 1px solid #e4e7ed; border-radius: 4px">
              <div style="display: flex; justify-content: space-between; align-items: center; width: 100%">
                <span>
                  <el-icon style="margin-right: 5px"><Wallet /></el-icon>
                  余额支付
                </span>
                <span v-if="userBalance >= finalAmount" style="color: #67c23a; font-weight: 600">（余额充足）</span>
                <span v-else style="color: #f56c6c; font-weight: 600">
                  （余额不足，还需 ¥{{ (finalAmount - userBalance).toFixed(2) }}）
                </span>
              </div>
            </el-radio>
            <!-- 动态加载的支付方式 -->
            <el-radio 
              v-for="method in availablePaymentMethods" 
              :key="method.key"
              :label="method.key" 
              style="width: 100%; margin-bottom: 10px; padding: 10px; border: 1px solid #e4e7ed; border-radius: 4px"
            >
              <div style="display: flex; justify-content: space-between; align-items: center; width: 100%">
                <span>
                  <el-icon style="margin-right: 5px"><CreditCard /></el-icon>
                  {{ method.name || method.key }}
                </span>
              </div>
            </el-radio>
            <!-- 兼容旧版本：如果没有加载到支付方式，显示默认的支付宝 -->
            <el-radio 
              v-if="availablePaymentMethods.length === 0"
              label="alipay" 
              style="width: 100%; margin-bottom: 10px; padding: 10px; border: 1px solid #e4e7ed; border-radius: 4px"
            >
              <div style="display: flex; justify-content: space-between; align-items: center; width: 100%">
                <span>
                  <el-icon style="margin-right: 5px"><CreditCard /></el-icon>
                  支付宝支付
                </span>
              </div>
            </el-radio>
            <el-radio 
              v-if="userBalance > 0 && userBalance < finalAmount" 
              label="mixed" 
              style="width: 100%; padding: 10px; border: 1px solid #e4e7ed; border-radius: 4px"
            >
              <div style="display: flex; justify-content: space-between; align-items: center; width: 100%">
                <span>
                  <el-icon style="margin-right: 5px"><Money /></el-icon>
                  余额+支付宝合并支付
                </span>
                <span style="color: #409eff; font-weight: 600">
                  （余额 ¥{{ userBalance.toFixed(2) }} + 支付宝 ¥{{ (finalAmount - userBalance).toFixed(2) }}）
                </span>
              </div>
            </el-radio>
          </el-radio-group>

          <!-- 支付说明 -->
          <div v-if="paymentMethod === 'balance' && userBalance >= finalAmount" style="margin-top: 10px; padding: 10px; background: #e1f3d8; border-radius: 4px">
            <el-alert
              title="将使用余额全额支付"
              type="success"
              :closable="false"
              show-icon
            />
          </div>
          <div v-else-if="paymentMethod === 'mixed'" style="margin-top: 10px; padding: 10px; background: #ecf5ff; border-radius: 4px">
            <el-alert
              :title="`将使用余额 ¥${userBalance.toFixed(2)} 和支付宝 ¥${(finalAmount - userBalance).toFixed(2)} 合并支付`"
              type="info"
              :closable="false"
              show-icon
            />
          </div>
        </div>
        
        <div class="purchase-actions" style="margin-top: 20px">
          <el-button @click="purchaseDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmPurchase" :loading="isProcessing">
            确认购买
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- 支付二维码对话框 -->
    <el-dialog
      v-model="paymentQRVisible"
      title="扫码支付"
      width="500px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <div class="payment-qr-container">
        <div class="order-info">
          <h3>订单信息</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="订单号">{{ currentOrder?.order_no || orderInfo.orderNo }}</el-descriptions-item>
            <el-descriptions-item label="套餐名称">{{ currentOrder?.package_name || orderInfo.packageName }}</el-descriptions-item>
            <el-descriptions-item label="支付金额">
              <span class="amount">¥{{ currentOrder?.amount || orderInfo.amount }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="支付方式">
              <el-tag type="primary">支付宝</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </div>
        
        <div class="qr-code-wrapper">
          <div v-if="paymentQRCode" class="qr-code">
            <img 
              :src="paymentQRCode.startsWith('data:') ? paymentQRCode : (paymentQRCode + '?t=' + Date.now())" 
              alt="支付二维码" 
              title="支付宝二维码"
              @error="onImageError"
              @load="onImageLoad"
            />
          </div>
          <div v-else class="qr-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <p>正在生成二维码...</p>
          </div>
        </div>
        
        <div class="payment-tips">
          <el-alert
            title="支付提示"
            type="info"
            :closable="false"
            show-icon
          >
            <template #default>
              <p>1. 请使用支付宝扫描上方二维码</p>
              <p>2. 确认订单信息无误后完成支付</p>
              <p>3. 支付完成后请勿关闭此窗口，系统将自动检测支付状态</p>
            </template>
          </el-alert>
        </div>
        
        <div class="payment-actions">
          <el-button 
            @click="checkPaymentStatus" 
            :loading="isCheckingPayment"
            type="primary"
          >
            检查支付状态
          </el-button>
          <el-button @click="paymentQRVisible = false">
            关闭
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- 购买成功提示 -->
    <el-dialog
      v-model="successDialogVisible"
      title="购买成功"
      width="400px"
      :close-on-click-modal="false"
    >
      <div class="success-message">
        <el-icon class="success-icon"><CircleCheckFilled /></el-icon>
        <h3>恭喜！购买成功</h3>
        <p>您的订阅已激活，可以正常使用了。</p>
        <div class="success-actions">
          <el-button type="primary" @click="goToSubscription">查看订阅</el-button>
          <el-button @click="successDialogVisible = false">关闭</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleCheckFilled, Loading, Wallet, CreditCard, Money } from '@element-plus/icons-vue'
import { useApi, couponAPI, userAPI } from '@/utils/api'

export default {
  name: 'Packages',
  components: {
    CircleCheckFilled,
    Loading,
    Wallet,
    CreditCard,
    Money
  },
  setup() {
    const router = useRouter()
    const api = useApi()
    
    // 响应式数据
    const packages = ref([])
    const isLoading = ref(false)
    const errorMessage = ref('')
    const isProcessing = ref(false)
    const purchaseDialogVisible = ref(false)
    const paymentQRVisible = ref(false)
    const successDialogVisible = ref(false)
    const selectedPackage = ref(null)
    const currentOrder = ref(null)
    const paymentQRCode = ref('')
    const isCheckingPayment = ref(false)
    let paymentStatusCheckInterval = null
    
    // 优惠券相关
    const couponCode = ref('')
    const validatingCoupon = ref(false)
    const couponInfo = ref(null)
    
    // 支付方式相关
    const paymentMethod = ref('alipay')  // 'balance', 'alipay', 'yipay', 'mixed'
    const availablePaymentMethods = ref([])  // 可用的支付方式列表
    const userBalance = ref(0)
    
    // 确保 isMobile 在初始化时就有值
    const windowWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1920)
    
    // 检测是否为移动端
    const isMobile = computed(() => {
      return windowWidth.value <= 768
    })
    
    // 监听窗口大小变化
    const handleResize = () => {
      if (typeof window !== 'undefined') {
        windowWidth.value = window.innerWidth
      }
    }
    
    // 优惠券输入处理函数
    const handleCouponInput = (value) => {
      couponCode.value = value
    }
    
    const handleCouponFocus = () => {
      // 确保输入框可以聚焦
    }
    
    // 验证优惠券
    const validateCoupon = async () => {
      if (!couponCode.value || !couponCode.value.trim()) {
        ElMessage.warning('请输入优惠券码')
        return
      }
      
      if (!selectedPackage.value) {
        ElMessage.warning('请先选择套餐')
        return
      }
      
      validatingCoupon.value = true
      try {
        const response = await couponAPI.validateCoupon({
          code: couponCode.value.trim(),
          package_id: selectedPackage.value.id,
          amount: parseFloat(selectedPackage.value.price) || 0
        })
        
        if (response.data && response.data.success) {
          couponInfo.value = {
            valid: true,
            message: '优惠券验证成功',
            discount_amount: response.data.data?.discount_amount || 0
          }
          ElMessage.success('优惠券验证成功')
        } else {
          couponInfo.value = {
            valid: false,
            message: response.data?.message || '优惠券验证失败'
          }
          ElMessage.error(response.data?.message || '优惠券验证失败')
        }
        } catch (error) {
        const errorMsg = error.response?.data?.message || error.message || '验证优惠券失败'
        couponInfo.value = {
          valid: false,
          message: errorMsg
        }
        ElMessage.error(errorMsg)
      } finally {
        validatingCoupon.value = false
      }
    }
    
    // 清除优惠券
    const clearCoupon = () => {
      couponCode.value = ''
      couponInfo.value = null
    }
    
    const orderInfo = reactive({
      orderNo: '',
      packageName: '',
      amount: 0,
      duration: 0,
      paymentUrl: ''
    })
    
    // 计算最终金额
    const finalAmount = computed(() => {
      if (!selectedPackage.value) return 0
      const originalPrice = parseFloat(selectedPackage.value.price) || 0
      const discount = (couponInfo.value && couponInfo.value.valid && couponInfo.value.discount_amount) 
        ? couponInfo.value.discount_amount 
        : 0
      return Math.max(0, originalPrice - discount)
    })
    
    // 获取套餐列表
    const loadPackages = async () => {
      try {
        isLoading.value = true
        errorMessage.value = ''
        
        const response = await api.get('/packages/')
        
        // 处理响应数据结构：ResponseBase { success: true, data: { packages: [...] }, message: "..." }
        let packagesList = []
        if (response && response.data) {
          // axios 响应结构：response.data 是后端返回的 JSON
          const responseData = response.data
          
          // 优先检查标准格式：{ success: true, data: { packages: [...] } }
          if (responseData.data && responseData.data.packages && Array.isArray(responseData.data.packages)) {
            packagesList = responseData.data.packages
          } 
          // 如果 data 直接是数组（不常见但兼容）
          else if (Array.isArray(responseData.data)) {
            packagesList = responseData.data
          } 
          // 如果 packages 在顶层（不常见但兼容）
          else if (responseData.packages && Array.isArray(responseData.packages)) {
            packagesList = responseData.packages
          } 
          // 如果响应直接是数组（不常见但兼容）
          else if (Array.isArray(responseData)) {
            packagesList = responseData
          } 
          // 如果 data 是对象但没有 packages 字段，尝试将其作为单个套餐
          else if (responseData.data && typeof responseData.data === 'object' && !Array.isArray(responseData.data)) {
            // 检查是否是单个套餐对象
            if (responseData.data.id || responseData.data.name) {
              packagesList = [responseData.data]
            }
          }
        }
        
        if (packagesList && Array.isArray(packagesList) && packagesList.length > 0) {
          packages.value = packagesList.map(pkg => ({
            ...pkg,
            features: [
              `有效期 ${pkg.duration_days} 天`,
              `支持 ${pkg.device_limit} 个设备`,
              pkg.bandwidth_limit ? `流量限制 ${pkg.bandwidth_limit}GB` : '无流量限制',
              '7×24小时技术支持',
              '高速稳定节点'
            ],
            is_popular: pkg.sort_order === 2,
            is_recommended: pkg.sort_order === 3
          }))
          errorMessage.value = '' // 清除错误信息
        } else {
          // 套餐列表为空，显示空状态而不是错误
          packages.value = []
          errorMessage.value = '' // 不显示错误，而是显示空状态
        }
      } catch (error) {
        if (error.response?.status === 404) {
          errorMessage.value = '套餐服务暂时不可用'
        } else if (error.response?.status === 500) {
          errorMessage.value = '服务器内部错误'
        } else if (error.code === 'ECONNREFUSED') {
          errorMessage.value = '无法连接到服务器'
        } else {
          const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || '加载套餐列表失败，请重试'
          errorMessage.value = errorMsg
        }
        packages.value = [] // 确保清空套餐列表
      } finally {
        isLoading.value = false
      }
    }
    
    // 获取用户余额
    const loadUserBalance = async () => {
      try {
        const response = await userAPI.getUserInfo()
        if (response.data && response.data.success && response.data.data) {
          userBalance.value = parseFloat(response.data.data.balance || 0)
        }
      } catch (error) {
        userBalance.value = 0
      }
    }
    
    // 获取可用的支付方式列表
    const loadPaymentMethods = async () => {
      try {
        const response = await api.get('/payment/methods')
        if (response && response.data) {
          // 处理不同的响应格式
          let methods = []
          if (response.data.success && response.data.data) {
            methods = Array.isArray(response.data.data) ? response.data.data : []
          } else if (Array.isArray(response.data)) {
            methods = response.data
          } else if (response.data.data && Array.isArray(response.data.data)) {
            methods = response.data.data
          }
          
          availablePaymentMethods.value = methods
        }
      } catch (error) {
        // 如果获取失败，使用默认的支付方式
        availablePaymentMethods.value = [
          { key: 'alipay', name: '支付宝' },
          { key: 'yipay', name: '易支付' }
        ]
      }
    }
    
    // 支付方式变更处理
    const handlePaymentMethodChange = (value) => {
      // 支付方式变更处理
    }
    
    // 选择套餐
    const selectPackage = async (pkg) => {
      try {
        if (!pkg) {
          ElMessage.error('套餐信息错误，请刷新页面重试')
          return
        }
        
        if (!pkg.id) {
          ElMessage.error('套餐ID缺失，请刷新页面重试')
          return
        }
        
        selectedPackage.value = pkg
        
        // 加载用户余额
        await loadUserBalance()
        
        // 加载支付方式列表
        await loadPaymentMethods()
        
        // 根据余额自动选择支付方式
        const finalPrice = finalAmount.value
        if (userBalance.value >= finalPrice) {
          paymentMethod.value = 'balance'
        } else if (userBalance.value > 0) {
          paymentMethod.value = 'mixed'
        } else {
          // 优先选择易支付，如果没有则选择支付宝
          const hasYipay = availablePaymentMethods.value.some(m => m.key === 'yipay')
          paymentMethod.value = hasYipay ? 'yipay' : (availablePaymentMethods.value[0]?.key || 'alipay')
        }
        
        purchaseDialogVisible.value = true
      } catch (error) {
        ElMessage.error('选择套餐失败: ' + error.message)
      }
    }
    
    // 确认购买
    const confirmPurchase = async () => {
      try {
        isProcessing.value = true
        
        // 创建订单
        const orderData = {
          package_id: selectedPackage.value.id,
          payment_method: paymentMethod.value === 'balance' ? 'balance' : paymentMethod.value,
          amount: finalAmount.value, // 使用最终金额（已扣除优惠券）
          currency: 'CNY'
        }
        
        // 如果优惠券已验证，添加到订单数据中
        if (couponInfo.value && couponInfo.value.valid && couponCode.value) {
          orderData.coupon_code = couponCode.value.trim()
        }
        
        // 处理余额支付
        if (paymentMethod.value === 'balance') {
          // 纯余额支付
          orderData.use_balance = true
          orderData.balance_amount = finalAmount.value
        } else if (paymentMethod.value === 'mixed') {
          // 余额+支付宝合并支付
          orderData.use_balance = true
          orderData.balance_amount = userBalance.value
          // 实际需要支付宝支付的金额
          orderData.amount = finalAmount.value - userBalance.value
        }
        
        // 创建订单可能需要较长时间（支付链接生成），优化超时设置
        // 减少超时时间，快速反馈给用户
        const response = await api.post('/orders/create', orderData, {
          timeout: 25000  // 25秒超时，与后端20秒读取超时+5秒缓冲匹配
        }).catch(error => {
          if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
            throw new Error('请求超时，支付宝服务响应较慢，请稍后重试或前往订单页面查看')
          } else if (error.response) {
            // 服务器返回了错误响应
            const errorMsg = error.response.data?.message || error.response.data?.detail || '创建订单失败'
            throw new Error(errorMsg)
          } else {
            // 网络错误或其他错误
            throw new Error('网络连接失败，请检查网络连接后重试')
          }
        })
        
        // 处理响应数据结构：ResponseBase { data: {...}, message: "...", success: true/false }
        let order = null
        if (response.data) {
          // 如果响应有 success 字段，检查它
          if (response.data.success !== false) {
            // success 为 true 或 undefined，尝试获取 data
            order = response.data.data || response.data
          } else {
            // success 为 false，表示失败
            throw new Error(response.data.message || '创建订单失败')
          }
        } else {
          throw new Error('订单创建响应格式错误')
        }
        
        if (!order) {
          throw new Error('订单创建失败：未返回订单数据')
        }
        
        // 设置订单信息
        orderInfo.orderNo = order.order_no
        orderInfo.packageName = selectedPackage.value.name
        orderInfo.amount = order.amount
        orderInfo.duration = selectedPackage.value.duration_days
        
        // 检查订单状态
        if (order.status === 'paid') {
          // 余额支付成功，直接显示成功提示
          purchaseDialogVisible.value = false
          ElMessage.success('购买成功！订单已支付')
          
          // 更新用户余额
          if (order.remaining_balance !== undefined) {
            userBalance.value = order.remaining_balance
          }
          
          // 显示成功对话框
          successDialogVisible.value = true
          
          // 刷新套餐列表（可选）
          await loadPackages()
        } else if (order.payment_url || order.payment_qr_code) {
          // 支付URL生成成功，直接显示支付二维码（类似Orders.vue的处理方式）
          purchaseDialogVisible.value = false
          
          // 设置订单信息用于显示
          orderInfo.orderNo = order.order_no
          orderInfo.packageName = selectedPackage.value.name
          orderInfo.amount = order.amount
          orderInfo.duration = selectedPackage.value.duration_days
          orderInfo.paymentUrl = order.payment_url || order.payment_qr_code
          
          // 显示支付二维码对话框
          showPaymentQRCode(order)
        } else {
          // 支付URL生成失败，显示提示信息并提供重试选项
          const errorMsg = order.payment_error || order.note || '支付链接生成失败，可能是网络问题或支付宝配置问题'
          
          // 显示错误提示，并提供跳转到订单页面的选项
          ElMessageBox.confirm(
            `${errorMsg}。订单已创建成功（订单号：${order.order_no}），您可以：\n\n1. 前往订单页面重新生成支付链接\n2. 稍后重试`,
            '支付链接生成失败',
            {
              confirmButtonText: '前往订单页面',
              cancelButtonText: '稍后重试',
              type: 'warning',
              distinguishCancelAndClose: true
            }
          ).then(() => {
            // 用户点击"前往订单页面"
            router.push('/orders')
          }).catch(() => {
            // 用户点击"稍后重试"或关闭对话框
          })
          
          // 关闭购买确认对话框
          purchaseDialogVisible.value = false
        }
        
      } catch (error) {
        const errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message || '创建订单失败，请重试'
        ElMessage.error(errorMessage)
      } finally {
        isProcessing.value = false
      }
    }
    
    // 显示支付二维码
    const showPaymentQRCode = async (order) => {
      // 尝试多种方式获取支付URL
      const paymentUrl = order.payment_url || order.payment_qr_code || orderInfo.paymentUrl
      
      if (!paymentUrl) {
        ElMessage.error('支付链接生成失败，请重试或前往订单页面重新生成')
        return
      }
      
      // 设置当前订单信息
      currentOrder.value = {
        order_no: order.order_no || orderInfo.orderNo,
        amount: order.amount || orderInfo.amount,
        package_name: orderInfo.packageName,
        payment_method_name: order.payment_method_name || 'alipay',
        payment_method: order.payment_method || 'alipay'
      }
      
      // 支付宝支付：使用qrcode库将支付宝URL生成为二维码图片
      const paymentMethod = order.payment_method_name || order.payment_method || 'alipay'
      
      if (paymentMethod === 'alipay') {
        // 支付宝返回的是URL（如 https://qr.alipay.com/xxx），需要在前端生成二维码图片
        if (paymentUrl.startsWith('http://') || paymentUrl.startsWith('https://')) {
          try {
            // 动态导入qrcode库
            const QRCode = await import('qrcode')
            // 将支付宝URL生成为base64格式的二维码图片
            const qrCodeDataURL = await QRCode.toDataURL(paymentUrl, {
              width: 256,
              margin: 2,
              color: {
                dark: '#000000',
                light: '#FFFFFF'
              },
              errorCorrectionLevel: 'M'
            })
            paymentQRCode.value = qrCodeDataURL
          } catch (error) {
            ElMessage.error('生成二维码失败，请刷新页面重试')
            return
          }
        } else {
          ElMessage.error('支付宝二维码格式错误，请联系管理员检查配置')
          return
        }
      } else {
        // 非支付宝支付方式，使用qrcode库生成二维码
        if (paymentUrl.startsWith('http://') || paymentUrl.startsWith('https://')) {
          try {
            const QRCode = await import('qrcode')
            const qrCodeDataURL = await QRCode.toDataURL(paymentUrl, {
              width: 256,
              margin: 2,
              color: {
                dark: '#000000',
                light: '#FFFFFF'
              },
              errorCorrectionLevel: 'M'
            })
            paymentQRCode.value = qrCodeDataURL
          } catch (error) {
            ElMessage.error('生成二维码失败，请刷新页面重试')
            return
          }
        } else {
          // 直接是字符串，也使用qrcode库生成
          try {
            const QRCode = await import('qrcode')
            const qrCodeDataURL = await QRCode.toDataURL(paymentUrl, {
              width: 256,
              margin: 2,
              color: {
                dark: '#000000',
                light: '#FFFFFF'
              },
              errorCorrectionLevel: 'M'
            })
            paymentQRCode.value = qrCodeDataURL
          } catch (error) {
            ElMessage.error('生成二维码失败，请刷新页面重试')
            return
          }
        }
      }
      
      // 显示二维码对话框
      paymentQRVisible.value = true
      
      // 等待一下确保对话框已渲染
      await new Promise(resolve => setTimeout(resolve, 100))
      
      // 开始检查支付状态
      startPaymentStatusCheck()
    }
    
    // 开始检查支付状态
    const startPaymentStatusCheck = () => {
      // 清除之前的检查
      if (paymentStatusCheckInterval) {
        clearInterval(paymentStatusCheckInterval)
      }
      
      // 每3秒检查一次支付状态
      paymentStatusCheckInterval = setInterval(async () => {
        await checkPaymentStatus()
      }, 3000)
      
      // 30分钟后停止检查
      setTimeout(() => {
        if (paymentStatusCheckInterval) {
          clearInterval(paymentStatusCheckInterval)
          paymentStatusCheckInterval = null
        }
      }, 30 * 60 * 1000)
    }
    
    // 检查支付状态
    const checkPaymentStatus = async () => {
      if (!currentOrder.value || !currentOrder.value.order_no) return
      
      try {
        isCheckingPayment.value = true
        
        // 检查订单状态（设置较短的超时时间，避免阻塞）
        const response = await api.get(`/orders/${currentOrder.value.order_no}/status`, {
          timeout: 10000  // 10秒超时
        })
        const orderData = response.data.data
        
        if (orderData.status === 'paid') {
          // 支付成功
          if (paymentStatusCheckInterval) {
            clearInterval(paymentStatusCheckInterval)
            paymentStatusCheckInterval = null
          }
          
          paymentQRVisible.value = false
          successDialogVisible.value = true
          
          ElMessage.success('支付成功！您的订阅已激活')
          
          // 刷新用户信息（包括订阅信息）
          try {
            // 可以在这里调用API刷新用户订阅信息
            // 例如：await refreshUserInfo()
          } catch (refreshError) {
            // 刷新失败，静默处理
          }
          
          // 3秒后自动关闭成功对话框并刷新页面数据
          setTimeout(() => {
            successDialogVisible.value = false
            // 可以在这里刷新套餐列表或其他数据
            loadPackages()
          }, 3000)
        } else if (orderData.status === 'cancelled') {
          // 订单已取消
          if (paymentStatusCheckInterval) {
            clearInterval(paymentStatusCheckInterval)
            paymentStatusCheckInterval = null
          }
          
          paymentQRVisible.value = false
          ElMessage.info('订单已取消')
        }
        // 如果状态是pending，继续等待
        
      } catch (error) {
        // 如果是超时错误，不中断轮询
        if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
          // 超时，继续轮询
        } else {
          // 其他错误，静默处理，继续轮询
        }
      } finally {
        isCheckingPayment.value = false
      }
    }
    
    // 图片加载成功
    const onImageLoad = () => {
      // 图片加载成功
    }
    
    // 图片加载失败
    const onImageError = async (event) => {
      // 如果二维码是base64格式还加载失败，说明有问题
      // 重新尝试生成二维码
      if (paymentQRCode.value && paymentQRCode.value.startsWith('data:')) {
        ElMessage.warning('二维码显示异常，正在重新生成...')
        
        // 从订单信息中重新获取支付URL并生成二维码
        const paymentUrl = orderInfo.paymentUrl || currentOrder.value?.payment_url
        if (paymentUrl) {
          try {
            const QRCode = await import('qrcode')
            const qrCodeDataURL = await QRCode.toDataURL(paymentUrl, {
              width: 256,
              margin: 2,
              color: {
                dark: '#000000',
                light: '#FFFFFF'
              },
              errorCorrectionLevel: 'M'
            })
            paymentQRCode.value = qrCodeDataURL
            event.target.src = qrCodeDataURL
          } catch (error) {
            ElMessage.error('二维码生成失败，请刷新页面重试')
          }
        } else {
          ElMessage.error('无法获取支付链接，请刷新页面重试')
        }
      } else {
        ElMessage.error('二维码加载失败，请刷新页面重试')
      }
    }
    
    // 跳转到订阅页面
    const goToSubscription = () => {
      successDialogVisible.value = false
      router.push('/subscription')
    }

    // 支付成功回调（已弃用，保留用于兼容）
    const onPaymentSuccess = () => {
      // 已弃用
    }
    
    // 支付取消回调（已弃用，保留用于兼容）
    const onPaymentCancel = () => {
      // 已弃用
    }
    
    // 支付错误回调（已弃用，保留用于兼容）
    const onPaymentError = (error) => {
      // 已弃用
    }
    
    // 生命周期
    onMounted(() => {
      loadPackages()
      // 初始化窗口大小
      if (typeof window !== 'undefined') {
        windowWidth.value = window.innerWidth
        window.addEventListener('resize', handleResize)
      }
    })
    
    onUnmounted(() => {
      // 清理定时器
      if (paymentStatusCheckInterval) {
        clearInterval(paymentStatusCheckInterval)
        paymentStatusCheckInterval = null
      }
      // 清理窗口大小监听
      if (typeof window !== 'undefined') {
        window.removeEventListener('resize', handleResize)
      }
    })
    
    return {
      packages,
      isLoading,
      errorMessage,
      isProcessing,
      purchaseDialogVisible,
      paymentQRVisible,
      successDialogVisible,
      paymentQRCode,
      currentOrder,
      isCheckingPayment,
      showPaymentQRCode,
      checkPaymentStatus,
      onImageLoad,
      onImageError,
      selectedPackage,
      orderInfo,
      loadPackages,
      selectPackage,
      confirmPurchase,
      onPaymentSuccess,
      onPaymentCancel,
      onPaymentError,
      goToSubscription,
      // 优惠券相关
      couponCode,
      validatingCoupon,
      couponInfo,
      finalAmount,
      handleCouponInput,
      handleCouponFocus,
      // 支付方式相关
      paymentMethod,
      availablePaymentMethods,
      loadPaymentMethods,
      userBalance,
      handlePaymentMethodChange,
      loadUserBalance,
      // 移动端检测
      isMobile,
      validateCoupon,
      clearCoupon
    }
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/list-common.scss';

// 页面头部已移除，统一风格

.packages-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 30px;
  margin-top: 20px;
}

.package-card {
  position: relative;
  text-align: center;
  transition: all 0.3s ease;
  border: 2px solid transparent;
}

.package-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.package-card.popular {
  border-color: #409EFF;
}

.package-card.recommended {
  border-color: #67C23A;
}

.package-header {
  position: relative;
  margin-bottom: 20px;
}

.package-name {
  margin: 0;
  color: #303133;
  font-size: 20px;
  font-weight: bold;
}

.popular-badge,
.recommended-badge {
  position: absolute;
  top: -10px;
  right: -10px;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
  color: white;
}

.popular-badge {
  background: #409EFF;
}

.recommended-badge {
  background: #67C23A;
}

.package-price {
  margin-bottom: 30px;
}

.currency {
  font-size: 18px;
  color: #909399;
  vertical-align: top;
}

.amount {
  font-size: 36px;
  font-weight: bold;
  color: #409EFF;
  margin: 0 5px;
}

.period {
  font-size: 16px;
  color: #909399;
}

.package-features {
  margin-bottom: 30px;
  text-align: left;
}

.package-features :is(ul) {
  list-style: none;
  padding: 0;
  margin: 0;
}

.package-features :is(li) {
  padding: 8px 0;
  color: #606266;
  display: flex;
  align-items: center;
}

.package-features :is(li) :is(i) {
  color: #67C23A;
  margin-right: 10px;
  font-size: 16px;
}

.package-actions {
  margin-bottom: 20px;
}

.package-actions .el-button {
  cursor: pointer;
  position: relative;
  z-index: 1;
}

.package-actions .el-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

/* 购买确认对话框 */
.purchase-confirm {
  padding: 20px 0;
}

.package-summary :is(h4) {
  margin-bottom: 15px;
  color: #303133;
}

.amount {
  color: #f56c6c;
  font-weight: bold;
}

.purchase-actions {
  text-align: center;
  margin-top: 20px;
}

.purchase-actions .el-button {
  margin: 0 10px;
}

/* 成功提示对话框 */
.success-message {
  text-align: center;
  padding: 20px 0;
}

.success-icon {
  font-size: 48px;
  color: #67C23A;
  margin-bottom: 15px;
}

.success-message h3 {
  margin: 15px 0;
  color: #303133;
}

.success-message :is(p) {
  margin-bottom: 20px;
  color: #606266;
}

.success-actions {
  margin-top: 20px;
}

.success-actions .el-button {
  margin: 0 10px;
}

/* 套餐描述样式 */
.package-description {
  margin: 15px 0;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 6px;
  border-left: 3px solid #409EFF;
}

.package-description :is(p) {
  margin: 0;
  color: #606266;
  font-size: 14px;
  line-height: 1.5;
}

/* 手机端对话框优化 */
.purchase-dialog {
  :deep(.el-dialog) {
    margin: 5vh auto !important;
    max-height: 90vh;
    overflow-y: auto;
  }
  
  :deep(.el-dialog__body) {
    padding: 15px !important;
    max-height: calc(90vh - 120px);
    overflow-y: auto;
  }
}

/* 优惠券输入组布局优化 */
.coupon-input-group {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  flex-wrap: nowrap;
}

.coupon-input {
  flex: 1;
  min-width: 0;
}

.coupon-buttons {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* 响应式设计 */
@media (max-width: 768px) {
  // 页面头部已移除，统一风格
  
  /* 手机端对话框 */
  .purchase-dialog {
    :deep(.el-dialog) {
      width: 90% !important;
      margin: 5vh auto !important;
    }
  }
  
  /* 手机端优惠券输入布局 */
  .coupon-input-group {
    flex-direction: column;
    gap: 12px;
  }
  
  .coupon-input {
    width: 100%;
  }
  
  .coupon-buttons {
    width: 100%;
    display: flex;
    gap: 10px;
  }
  
  .coupon-buttons .el-button {
    flex: 1;
    min-height: 44px; /* 增加按钮高度便于点击 */
    font-size: 16px; /* 增加字体大小 */
  }
  
  /* 手机端购买按钮优化 */
  .purchase-actions {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  
  .purchase-actions .el-button {
    width: 100%;
    min-height: 44px;
    font-size: 16px;
    margin: 0 !important;
  }
  
  /* 手机端描述列表优化 */
  .purchase-confirm :deep(.el-descriptions) {
    font-size: 14px;
  }
  
  .purchase-confirm :deep(.el-descriptions__label) {
    width: 35% !important;
  }
  
  .purchase-confirm :deep(.el-descriptions__content) {
    width: 65% !important;
  }
  
  .packages-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  
  .package-card {
    margin: 0;
    border-radius: 12px;
    
    :deep(.el-card__body) {
      padding: 20px 16px;
    }
    
    .package-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 16px;
      
      .package-name {
        font-size: 1.25rem;
        margin: 0;
      }
      
      .popular-badge,
      .recommended-badge {
        font-size: 0.75rem;
        padding: 4px 10px;
      }
    }
    
    .package-price {
      margin-bottom: 20px;
      
      .currency {
        font-size: 1.25rem;
      }
      
      .amount {
        font-size: 2rem;
      }
      
      .period {
        font-size: 1rem;
      }
    }
    
    .package-features {
      margin-bottom: 20px;
      
      :is(ul) {
        :is(li) {
          padding: 8px 0;
          font-size: 0.875rem;
          
          :is(i) {
            font-size: 14px;
            margin-right: 8px;
          }
        }
      }
    }
    
    .package-description {
      margin-bottom: 20px;
      
      :is(p) {
        font-size: 0.875rem;
        line-height: 1.6;
      }
    }
    
    .package-button {
      width: 100%;
      padding: 14px;
      font-size: 1rem;
    }
  }
}

@media (max-width: 480px) {
  .package-card {
    .package-price {
      .amount {
        font-size: 1.75rem;
      }
    }
  }
}

/* 修复输入框嵌套问题 - 移除内部边框和嵌套效果 */
:deep(.el-input__wrapper) {
  border-radius: 0 !important;
  box-shadow: none !important;
  border: 1px solid #dcdfe6 !important;
  background-color: #ffffff !important;
  pointer-events: auto !important;
}

:deep(.el-input__inner) {
  border-radius: 0 !important;
  border: none !important;
  box-shadow: none !important;
  background-color: transparent !important;
  pointer-events: auto !important;
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

:deep(.el-input__wrapper.is-focus:hover) {
  background-color: #ffffff !important;
}

/* 确保输入框内部所有子元素背景透明 */
:deep(.el-input__wrapper > *) {
  background-color: transparent !important;
  background: transparent !important;
}

/* 移除 textarea 的嵌套边框 */
:deep(.el-textarea__inner) {
  border-radius: 0 !important;
  border: 1px solid #dcdfe6 !important;
  box-shadow: none !important;
  background-color: #ffffff !important;
}

:deep(.el-textarea__inner:hover) {
  border-color: #c0c4cc !important;
}

:deep(.el-textarea__inner:focus) {
  border-color: #1677ff !important;
  box-shadow: none !important;
}

/* 专门修复优惠券输入框 - 确保可以正常输入 */
.coupon-section {
  position: relative;
  z-index: 1;
}

.coupon-section :deep(.el-input) {
  pointer-events: auto !important;
  position: relative;
  z-index: 10 !important;
}

.coupon-section :deep(.el-input__wrapper) {
  pointer-events: auto !important;
  cursor: text !important;
  position: relative;
  z-index: 10 !important;
}

.coupon-section :deep(.el-input__inner) {
  pointer-events: auto !important;
  cursor: text !important;
  position: relative;
  z-index: 10 !important;
  -webkit-user-select: text !important;
  user-select: text !important;
  -webkit-tap-highlight-color: transparent !important;
}

.coupon-section :deep(.el-input:not(.is-disabled)) {
  pointer-events: auto !important;
}

.coupon-section :deep(.el-input:not(.is-disabled) .el-input__wrapper) {
  pointer-events: auto !important;
  cursor: text !important;
}

.coupon-section :deep(.el-input:not(.is-disabled) .el-input__inner) {
  pointer-events: auto !important;
  cursor: text !important;
  -webkit-user-select: text !important;
  user-select: text !important;
}

.coupon-section :deep(.el-input.is-disabled) {
  pointer-events: none !important;
}

.coupon-section :deep(.el-input.is-disabled .el-input__wrapper) {
  pointer-events: none !important;
  cursor: not-allowed !important;
}

.coupon-section :deep(.el-input.is-disabled .el-input__inner) {
  pointer-events: none !important;
  cursor: not-allowed !important;
}

/* 确保优惠券输入框在对话框中的层级正确 */
.purchase-confirm .coupon-section {
  position: relative;
  z-index: 1;
}

.purchase-confirm .coupon-section .el-input {
  position: relative;
  z-index: 2;
}

/* 移除可能阻止输入的事件 */
.coupon-input {
  pointer-events: auto !important;
}

.coupon-input :deep(*) {
  pointer-events: auto !important;
}

.coupon-input :deep(.el-input__wrapper) {
  pointer-events: auto !important;
}

.coupon-input :deep(.el-input__inner) {
  pointer-events: auto !important;
}
</style> 