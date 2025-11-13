<template>
  <div class="list-container email-queue-admin">
    <el-row :gutter="20" class="stats-overview">
      <el-col :span="6">
        <el-card class="stat-card clickable" @click="filterByStatus('')">
          <div class="stat-content">
            <div class="stat-number">{{ statistics.total || 0 }}</div>
            <div class="stat-label">总邮件数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card clickable" @click="filterByStatus('pending')">
          <div class="stat-content">
            <div class="stat-number success">{{ statistics.pending || 0 }}</div>
            <div class="stat-label">待发送</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card clickable" @click="filterByStatus('sent')">
          <div class="stat-content">
            <div class="stat-number warning">{{ statistics.sent || 0 }}</div>
            <div class="stat-label">已发送</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card clickable" @click="filterByStatus('failed')">
          <div class="stat-content">
            <div class="stat-number danger">{{ statistics.failed || 0 }}</div>
            <div class="stat-label">发送失败</div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 移动端搜索和筛选栏 -->
    <div class="mobile-action-bar">
      <div class="mobile-search-section">
        <div class="search-input-wrapper">
          <el-input
            v-model="filterForm.email"
            placeholder="搜索邮箱地址"
            class="mobile-search-input"
            clearable
            @keyup.enter="applyFilter"
          />
          <el-button 
            @click="applyFilter" 
            class="search-button-inside"
            type="default"
            plain
          >
            <el-icon><Search /></el-icon>
          </el-button>
        </div>
      </div>
      <div class="mobile-filter-buttons">
        <el-select 
          v-model="filterForm.status" 
          placeholder="选择状态" 
          clearable
          class="mobile-status-select"
        >
          <el-option label="待发送" value="pending" />
          <el-option label="发送中" value="sending" />
          <el-option label="已发送" value="sent" />
          <el-option label="发送失败" value="failed" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
        <el-button 
          @click="resetFilter" 
          type="default"
          plain
        >
          <el-icon><Refresh /></el-icon>
          重置
        </el-button>
      </div>
    </div>
    
    <el-card class="filter-section desktop-only">
      <el-form :inline="true" :model="filterForm" class="filter-form">
        <el-form-item label="状态">
          <el-select v-model="filterForm.status" placeholder="选择状态" clearable style="width: 180px">
            <el-option label="待发送" value="pending" />
            <el-option label="发送中" value="sending" />
            <el-option label="已发送" value="sent" />
            <el-option label="发送失败" value="failed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="filterForm.email" placeholder="搜索邮箱地址" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="applyFilter">
            <el-icon><Search /></el-icon>
            筛选
          </el-button>
          <el-button @click="resetFilter">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    <el-card class="list-card queue-list">
      <template #header>
        <div class="card-header">
          <span>邮件队列列表</span>
          <div style="display: flex; align-items: center; gap: 10px;">
            <div class="header-info">
              共 {{ pagination.total }} 条记录，第 {{ pagination.page }}/{{ pagination.pages }} 页
            </div>
            <div class="header-actions">
              <el-button @click="refreshQueue" :loading="loading">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
              <el-button type="warning" @click="clearFailedEmails">
                <el-icon><Delete /></el-icon>
                清空失败邮件
              </el-button>
              <el-button type="danger" @click="clearAllEmails">
                <el-icon><Delete /></el-icon>
                清空所有邮件
              </el-button>
            </div>
          </div>
        </div>
      </template>
      <div class="table-wrapper desktop-only">
        <el-table :data="emailList" v-loading="loading" stripe empty-text="暂无数据">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="to_email" label="收件人" min-width="200" />
        <el-table-column prop="subject" label="主题" min-width="250" />
        <el-table-column prop="email_type" label="邮件类型" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="retry_count" label="重试次数" width="100">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.retry_count > 0 }">
              {{ row.retry_count }}/{{ row.max_retries || 3 }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button size="small" @click="viewEmailDetail(row)">
                <el-icon><View /></el-icon>
                详情
              </el-button>
              <el-button 
                v-if="row.status === 'failed'" 
                size="small" 
                type="warning" 
                @click="retryEmail(row)"
              >
                <el-icon><Refresh /></el-icon>
                重试
              </el-button>
              <el-button 
                size="small" 
                type="danger" 
                @click="deleteEmail(row)"
              >
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      </div>
      <div class="mobile-card-list mobile-only" v-if="emailList.length > 0">
        <div 
          v-for="email in emailList" 
          :key="email.id"
          class="mobile-card"
        >
          <div class="card-row">
            <span class="label">ID</span>
            <span class="value">#{{ email.id }}</span>
          </div>
          <div class="card-row">
            <span class="label">收件人</span>
            <span class="value">{{ email.to_email }}</span>
          </div>
          <div class="card-row">
            <span class="label">主题</span>
            <span class="value">{{ email.subject }}</span>
          </div>
          <div class="card-row">
            <span class="label">邮件类型</span>
            <span class="value">{{ email.email_type }}</span>
          </div>
          <div class="card-row">
            <span class="label">状态</span>
            <span class="value">
              <el-tag :type="getStatusTagType(email.status)">
                {{ getStatusText(email.status) }}
              </el-tag>
            </span>
          </div>
          <div class="card-row">
            <span class="label">重试次数</span>
            <span class="value" :class="{ 'text-danger': email.retry_count > 0 }">
              {{ email.retry_count }}/{{ email.max_retries || 3 }}
            </span>
          </div>
          <div class="card-row">
            <span class="label">创建时间</span>
            <span class="value">{{ formatDate(email.created_at) }}</span>
          </div>
          <div class="card-actions">
            <el-button size="small" @click="viewEmailDetail(email)">
              <el-icon><View /></el-icon>
              详情
            </el-button>
            <el-button 
              v-if="email.status === 'failed'" 
              size="small" 
              type="warning" 
              @click="retryEmail(email)"
            >
              <el-icon><Refresh /></el-icon>
              重试
            </el-button>
            <el-button 
              size="small" 
              type="danger" 
              @click="deleteEmail(email)"
            >
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </div>
        </div>
      </div>
      <div class="mobile-card-list mobile-only" v-if="emailList.length === 0 && !loading">
        <div class="empty-state">
          <i class="el-icon-message"></i>
          <p>暂无邮件数据</p>
        </div>
      </div>
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>
    <el-dialog 
      v-model="detailDialogVisible" 
      title="邮件详情" 
      width="70%"
      :close-on-click-modal="false"
      :class="isMobile ? 'mobile-dialog' : ''"
    >
      <div v-if="emailDetail" class="email-detail">
        <el-descriptions :column="isMobile ? 1 : 2" border class="desktop-only">
          <el-descriptions-item label="邮件ID">{{ emailDetail.id }}</el-descriptions-item>
          <el-descriptions-item label="收件人">{{ emailDetail.to_email }}</el-descriptions-item>
          <el-descriptions-item label="主题">{{ emailDetail.subject }}</el-descriptions-item>
          <el-descriptions-item label="邮件类型">{{ emailDetail.email_type }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusTagType(emailDetail.status)">
              {{ getStatusText(emailDetail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="优先级">
            <span>{{ emailDetail.priority || 'N/A' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="重试次数">{{ emailDetail.retry_count }}/{{ emailDetail.max_retries }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(emailDetail.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="发送时间" v-if="emailDetail.sent_at">
            {{ formatDate(emailDetail.sent_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="处理时间" v-if="emailDetail.processing_time">
            {{ emailDetail.processing_time }}ms
          </el-descriptions-item>
        </el-descriptions>
        <div class="mobile-detail-info mobile-only">
          <div class="detail-info-row">
            <span class="detail-label">邮件ID</span>
            <span class="detail-value">#{{ emailDetail.id }}</span>
          </div>
          <div class="detail-info-row">
            <span class="detail-label">收件人</span>
            <span class="detail-value">{{ emailDetail.to_email }}</span>
          </div>
          <div class="detail-info-row">
            <span class="detail-label">主题</span>
            <span class="detail-value">{{ emailDetail.subject }}</span>
          </div>
          <div class="detail-info-row">
            <span class="detail-label">邮件类型</span>
            <span class="detail-value">{{ emailDetail.email_type }}</span>
          </div>
          <div class="detail-info-row">
            <span class="detail-label">状态</span>
            <span class="detail-value">
              <el-tag :type="getStatusTagType(emailDetail.status)">
                {{ getStatusText(emailDetail.status) }}
              </el-tag>
            </span>
          </div>
          <div class="detail-info-row" v-if="emailDetail.priority">
            <span class="detail-label">优先级</span>
            <span class="detail-value">{{ emailDetail.priority }}</span>
          </div>
          <div class="detail-info-row">
            <span class="detail-label">重试次数</span>
            <span class="detail-value">{{ emailDetail.retry_count }}/{{ emailDetail.max_retries }}</span>
          </div>
          <div class="detail-info-row">
            <span class="detail-label">创建时间</span>
            <span class="detail-value">{{ formatDate(emailDetail.created_at) }}</span>
          </div>
          <div class="detail-info-row" v-if="emailDetail.sent_at">
            <span class="detail-label">发送时间</span>
            <span class="detail-value">{{ formatDate(emailDetail.sent_at) }}</span>
          </div>
          <div class="detail-info-row" v-if="emailDetail.processing_time">
            <span class="detail-label">处理时间</span>
            <span class="detail-value">{{ emailDetail.processing_time }}ms</span>
          </div>
        </div>
        <div class="detail-section">
          <h4>邮件内容</h4>
          <div v-if="emailDetail.content_type === 'html'" class="email-content-html">
            <div v-html="emailDetail.content" class="email-html-content"></div>
          </div>
          <div v-else class="email-content-text">
            <el-input
              v-model="emailDetail.content"
              type="textarea"
              :rows="isMobile ? 8 : 10"
              readonly
              class="email-text-content"
            />
          </div>
        </div>
        <div class="detail-section" v-if="emailDetail.template_data">
          <h4>模板数据</h4>
          <el-input
            v-model="emailDetail.template_data"
            type="textarea"
            :rows="isMobile ? 6 : 8"
            readonly
            class="template-data-content"
          />
        </div>
        <div class="detail-section" v-if="emailDetail.error_message">
          <h4>错误信息</h4>
          <el-alert
            :title="emailDetail.error_message"
            type="error"
            :description="emailDetail.error_details || '无详细错误信息'"
            show-icon
            :closable="false"
            class="error-alert"
          />
        </div>
        <div class="detail-section" v-if="emailDetail.smtp_response">
          <h4>SMTP响应</h4>
          <el-input
            v-model="emailDetail.smtp_response"
            type="textarea"
            :rows="isMobile ? 4 : 6"
            readonly
            class="smtp-response-content"
          />
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer-buttons">
          <el-button @click="detailDialogVisible = false" class="mobile-action-btn">关闭</el-button>
          <el-button 
            v-if="emailDetail && emailDetail.status === 'failed'" 
            type="warning" 
            @click="retryEmailFromDetail"
            class="mobile-action-btn"
          >
            重试发送
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, onMounted, computed, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search, View, Delete, HomeFilled } from '@element-plus/icons-vue'
import { adminAPI } from '@/utils/api'
import { formatDateTime } from '@/utils/date'

export default {
  name: 'EmailQueue',
  components: {
    Refresh, Search, View, Delete, HomeFilled
  },
  setup() {
    const loading = ref(false)
    const detailDialogVisible = ref(false)
    const emailDetail = ref(null)
    const isMobile = ref(false)
    
    const checkMobile = () => {
      isMobile.value = window.innerWidth <= 768
    }
    
    const filterForm = reactive({
      status: '',
      email: ''
    })
    
    const pagination = reactive({
      page: 1,
      size: 20,
      total: 0,
      pages: 0
    })
    
    const emailList = ref([])
    const statistics = reactive({
      total: 0,
      pending: 0,
      sent: 0,
      failed: 0
    })

    // 获取邮件队列列表
    const fetchEmailQueue = async () => {
      loading.value = true
      try {
        const params = {
          page: pagination.page,
          size: pagination.size,
          ...filterForm
        }
        
        const response = await adminAPI.getEmailQueue(params)
        if (response && response.data && response.data.success) {
          emailList.value = [...response.data.data.emails]
          pagination.total = response.data.data.total
          pagination.pages = response.data.data.pages
        } else if (response && response.success) {
          emailList.value = [...response.data.emails]
          pagination.total = response.data.total
          pagination.pages = response.data.pages
        } else {
          ElMessage.error(response?.message || response?.data?.message || '获取邮件队列失败')
        }
      } catch (error) {
        ElMessage.error('获取邮件队列失败: ' + (error.response?.data?.message || error.message))
      } finally {
        loading.value = false
      }
    }
    const fetchStatistics = async () => {
      try {
        const response = await adminAPI.getEmailQueueStatistics()
        if (response && response.data && response.data.success) {
          statistics.total = response.data.data.total
          statistics.pending = response.data.data.pending
          statistics.sent = response.data.data.sent
          statistics.failed = response.data.data.failed
        } else if (response && response.success) {
          statistics.total = response.data.total
          statistics.pending = response.data.pending
          statistics.sent = response.data.sent
          statistics.failed = response.data.failed
        }
      } catch (error) {
      }
    }
    const refreshQueue = () => {
      fetchEmailQueue()
      fetchStatistics()
    }
    const applyFilter = () => {
      pagination.page = 1
      fetchEmailQueue()
    }
    const resetFilter = () => {
      Object.assign(filterForm, {
        status: '',
        email: ''
      })
      pagination.page = 1
      fetchEmailQueue()
    }
    const filterByStatus = (status) => {
      filterForm.status = status
      pagination.page = 1
      fetchEmailQueue()
    }
    const viewEmailDetail = async (row) => {
      try {
        const response = await adminAPI.getEmailDetail(row.id)
        if (response && response.data && response.data.success) {
          emailDetail.value = response.data.data
          detailDialogVisible.value = true
        } else if (response && response.success) {
          emailDetail.value = response.data
          detailDialogVisible.value = true
        } else {
          ElMessage.error('获取邮件详情失败: ' + (response?.data?.message || response?.message || '未知错误'))
        }
      } catch (error) {
        ElMessage.error('获取邮件详情失败: ' + error.message)
      }
    }
    const retryEmail = async (row) => {
      try {
        await ElMessageBox.confirm(
          `确定要重试发送邮件到 ${row.to_email} 吗？`,
          '确认重试',
          { type: 'warning' }
        )
        
        const response = await adminAPI.retryEmail(row.id)
        if (response && response.data && response.data.success) {
          ElMessage.success('邮件重试成功')
          refreshQueue()
        } else if (response && response.success) {
          ElMessage.success('邮件重试成功')
          refreshQueue()
        } else {
          ElMessage.error('邮件重试失败: ' + (response?.data?.message || response?.message || '未知错误'))
        }
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('邮件重试失败')
        }
      }
    }
    const retryEmailFromDetail = async () => {
      if (emailDetail.value) {
        await retryEmail(emailDetail.value)
        detailDialogVisible.value = false
      }
    }
    const deleteEmail = async (row) => {
      try {
        await ElMessageBox.confirm(
          `确定要删除发送到 ${row.to_email} 的邮件吗？`,
          '确认删除',
          { type: 'warning' }
        )
        
        const response = await adminAPI.deleteEmailFromQueue(row.id)
        if (response && response.data && response.data.success) {
          ElMessage.success('邮件删除成功')
          refreshQueue()
        } else if (response && response.success) {
          ElMessage.success('邮件删除成功')
          refreshQueue()
        } else {
          ElMessage.error('邮件删除失败: ' + (response?.data?.message || response?.message || '未知错误'))
        }
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('邮件删除失败')
        }
      }
    }
    const clearFailedEmails = async () => {
      try {
        await ElMessageBox.confirm(
          '确定要清空所有失败的邮件吗？',
          '确认清空',
          { type: 'warning' }
        )
        
        const response = await adminAPI.clearEmailQueue('failed')
        if (response && response.data && response.data.success) {
          ElMessage.success('失败邮件清空成功')
          refreshQueue()
        } else if (response && response.success) {
          ElMessage.success('失败邮件清空成功')
          refreshQueue()
        } else {
          ElMessage.error('清空失败邮件失败: ' + (response?.data?.message || response?.message || '未知错误'))
        }
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('清空失败邮件失败')
        }
      }
    }
    const clearAllEmails = async () => {
      try {
        await ElMessageBox.confirm(
          '确定要清空所有邮件吗？此操作不可恢复！',
          '确认清空',
          { type: 'error' }
        )
        
        const response = await adminAPI.clearEmailQueue()
        if (response && response.data && response.data.success) {
          ElMessage.success('所有邮件清空成功')
          refreshQueue()
        } else if (response && response.success) {
          ElMessage.success('所有邮件清空成功')
          refreshQueue()
        } else {
          ElMessage.error('清空所有邮件失败: ' + (response?.data?.message || response?.message || '未知错误'))
        }
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('清空所有邮件失败')
        }
      }
    }
    const handleSizeChange = (size) => {
      pagination.size = size
      pagination.page = 1
      fetchEmailQueue()
    }

    const handleCurrentChange = (page) => {
      pagination.page = page
      fetchEmailQueue()
    }
    const getStatusTagType = (status) => {
      const statusMap = {
        pending: 'warning',
        sending: 'info',
        sent: 'success',
        failed: 'danger',
        cancelled: 'info'
      }
      return statusMap[status] || 'info'
    }

    const getStatusText = (status) => {
      const statusMap = {
        pending: '待发送',
        sending: '发送中',
        sent: '已发送',
        failed: '发送失败',
        cancelled: '已取消'
      }
      return statusMap[status] || status
    }

    const formatDate = (dateString) => {
      if (!dateString) return '-'
      // 使用北京时间格式化
      return formatDateTime(dateString, 'YYYY-MM-DD HH:mm:ss')
    }

    onMounted(() => {
      checkMobile()
      window.addEventListener('resize', checkMobile)
      fetchEmailQueue()
      fetchStatistics()
    })

    onUnmounted(() => {
      window.removeEventListener('resize', checkMobile)
    })

    return {
      loading,
      detailDialogVisible,
      emailDetail,
      filterForm,
      pagination,
      emailList,
      statistics,
      isMobile,
      fetchEmailQueue,
      fetchStatistics,
      refreshQueue,
      applyFilter,
      resetFilter,
      filterByStatus,
      viewEmailDetail,
      retryEmail,
      retryEmailFromDetail,
      deleteEmail,
      clearFailedEmails,
      clearAllEmails,
      handleSizeChange,
      handleCurrentChange,
      getStatusTagType,
      getStatusText,
      formatDate
    }
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/list-common.scss';

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
    margin: 0;
    line-height: 1.5;
  }
}

/* email-queue-admin 使用 list-container 的样式 */

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  color: #333;
  font-size: 1.8rem;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.stats-overview {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
}

.stat-card.clickable {
  cursor: pointer;
  transition: all 0.3s ease;
}

.stat-card.clickable:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.stat-content {
  padding: 20px;
}

.stat-number {
  font-size: 2rem;
  font-weight: bold;
  color: #333;
  margin-bottom: 10px;
}

.stat-number.success {
  color: #67c23a;
}

.stat-number.warning {
  color: #e6a23c;
}

.stat-number.danger {
  color: #f56c6c;
}

.stat-label {
  color: #666;
  font-size: 0.9rem;
}

.filter-section {
  margin-bottom: 20px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 15px;
}

.queue-list {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  
  @media (max-width: 768px) {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }
}

.header-info {
  color: #666;
  font-size: 0.9rem;
}

.pagination-wrapper {
  margin-top: 20px;
  text-align: center;
}

.email-detail {
  max-height: 60vh;
  overflow-y: auto;
}

.detail-section {
  margin-top: 20px;
}

.detail-section h4 {
  margin-bottom: 10px;
  color: #333;
  font-size: 1rem;
}

/* 邮件内容样式 */
.email-html-content {
  border: 1px solid #ddd;
  padding: 15px;
  border-radius: 4px;
  max-height: 400px;
  overflow-y: auto;
  word-break: break-word;
}

.email-text-content,
.template-data-content,
.smtp-response-content {
  width: 100%;
}

.error-alert {
  margin-top: 8px;
}

/* 移动端详情信息 */
.mobile-detail-info {
  display: none;
}

@media (max-width: 768px) {
  .mobile-detail-info {
    display: block;
    margin-bottom: 20px;
  }
  
  .detail-info-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 12px 0;
    border-bottom: 1px solid #f0f0f0;
    
    &:last-child {
      border-bottom: none;
    }
    
    .detail-label {
      font-weight: 600;
      color: #606266;
      font-size: 14px;
      min-width: 100px;
      flex-shrink: 0;
    }
    
    .detail-value {
      flex: 1;
      text-align: right;
      color: #303133;
      font-size: 14px;
      word-break: break-all;
    }
  }
  
  .email-detail {
    max-height: calc(90vh - 200px);
    overflow-y: auto;
  }
  
  .detail-section {
    margin-top: 16px;
    
    h4 {
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 12px;
      color: #303133;
    }
  }
  
  .email-html-content {
    padding: 12px;
    max-height: 300px;
    font-size: 14px;
  }
  
  .email-text-content,
  .template-data-content,
  .smtp-response-content {
    :deep(.el-textarea__inner) {
      font-size: 14px;
      padding: 12px;
    }
  }
  
  .error-alert {
    :deep(.el-alert__title) {
      font-size: 14px;
    }
    
    :deep(.el-alert__description) {
      font-size: 13px;
      margin-top: 8px;
    }
  }
  
  /* 移动端对话框优化 */
  .mobile-dialog {
    :deep(.el-dialog) {
      width: 95% !important;
      margin: 5vh auto !important;
      max-height: 90vh;
      border-radius: 12px;
    }
    
    :deep(.el-dialog__header) {
      padding: 16px 20px;
      border-bottom: 1px solid #f0f0f0;
      
      .el-dialog__title {
        font-size: 18px;
        font-weight: 600;
      }
    }
    
    :deep(.el-dialog__body) {
      padding: 16px;
      max-height: calc(90vh - 140px);
      overflow-y: auto;
    }
    
    :deep(.el-dialog__footer) {
      padding: 16px 20px;
      border-top: 1px solid #f0f0f0;
    }
  }
}

.text-danger {
  color: #f56c6c;
}

.dialog-footer {
  text-align: right;
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
      gap: 12px;
    }
  }
}

/* 移动端卡片列表样式 */
.mobile-card-list {
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
      flex-shrink: 0;
    }
    
    .value {
      flex: 1;
      text-align: right;
      color: #303133;
      font-size: 14px;
      word-break: break-all;
    }
  }
}

@media (max-width: 768px) {
  .email-queue-admin {
    padding: 10px;
  }
  
  .page-header {
    flex-direction: column;
    gap: 15px;
    align-items: flex-start;
  }
  
  .header-actions {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
    
    .el-button {
      width: 100% !important;
      height: 44px !important;
      font-size: 16px !important;
      font-weight: 500 !important;
      margin: 0 !important;
    }
  }
  
  .filter-form {
    flex-direction: column;
    align-items: stretch;
  }
  
  .filter-form .el-form-item {
    margin-bottom: 10px;
    width: 100% !important;
    
    .el-button {
      width: 100% !important;
      height: 44px !important;
      font-size: 16px !important;
      font-weight: 500 !important;
      margin: 0 !important;
    }
    
    /* 按钮组之间的间距 */
    .el-button + .el-button {
      margin-top: 12px !important;
    }
  }
  
  .card-header {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
    
    .header-actions {
      width: 100%;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
  }
  
  /* 统一所有移动端按钮样式 */
  /* 但排除 mobile-action-bar 中的按钮，它们使用统一样式 */
  .email-queue-admin .el-button:not(.search-button-inside) {
    width: 100% !important;
    min-width: 100% !important;
    max-width: 100% !important;
    height: 44px !important;
    font-size: 16px !important;
    font-weight: 500 !important;
    margin: 0 !important;
    border-radius: 6px !important;
    padding: 0 16px !important;
    
    :deep(.el-icon) {
      margin-right: 6px;
      font-size: 16px;
    }
  }
  
  // mobile-action-bar 样式已统一在 list-common.scss 中定义
  // 这里不再重复定义，使用统一样式
  
  /* 操作按钮组 */
  .action-buttons {
    display: flex;
    flex-direction: column;
    gap: 12px;
    width: 100%;
    
    .el-button {
      width: 100% !important;
      min-width: 100% !important;
      max-width: 100% !important;
      height: 44px !important;
      font-size: 16px !important;
    }
  }
  
  /* 卡片操作按钮 */
  .card-actions {
    display: flex;
    flex-direction: column;
    gap: 12px;
    width: 100%;
    margin-top: 12px;
    
    .el-button {
      width: 100% !important;
      min-width: 100% !important;
      max-width: 100% !important;
      height: 44px !important;
      font-size: 16px !important;
    }
  }
  
  /* 对话框底部按钮 */
  .dialog-footer-buttons {
    display: flex;
    flex-direction: column;
    gap: 12px;
    width: 100%;
    
    .mobile-action-btn,
    .el-button {
      width: 100% !important;
      min-width: 100% !important;
      max-width: 100% !important;
      height: 44px !important;
      font-size: 16px !important;
      margin: 0 !important;
    }
  }
  
  /* 统计卡片按钮 */
  .stat-card.clickable {
    .stat-content {
      padding: 16px;
    }
  }
  
  /* 统计卡片点击区域 */
  .stat-card {
    .stat-content {
      padding: 16px;
    }
  }
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
</style>
