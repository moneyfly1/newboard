<template>
  <div class="admin-settings">
    <el-card>
      <template #header>
        <span>系统设置</span>
      </template>

      <el-tabs v-model="activeTab" type="border-card">
        <!-- 基本设置 -->
        <el-tab-pane label="基本设置" name="general">
          <el-form :model="generalSettings" :rules="generalRules" ref="generalFormRef" label-width="120px">
            <el-form-item label="网站名称" prop="site_name">
              <el-input v-model="generalSettings.site_name" />
            </el-form-item>
            <el-form-item label="网站描述" prop="site_description">
              <el-input v-model="generalSettings.site_description" type="textarea" />
            </el-form-item>
            <el-form-item label="网站Logo">
              <el-upload
                class="avatar-uploader"
                :action="uploadUrl"
                :show-file-list="false"
                :on-success="handleLogoSuccess"
                :before-upload="beforeLogoUpload"
              >
                <img v-if="generalSettings.site_logo" :src="generalSettings.site_logo" class="avatar" />
                <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
              </el-upload>
            </el-form-item>
            <el-form-item label="默认主题" prop="default_theme">
              <el-select v-model="generalSettings.default_theme">
                <el-option label="浅色主题" value="light" />
                <el-option label="深色主题" value="dark" />
                <el-option label="跟随系统" value="auto" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveGeneralSettings">保存基本设置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 注册设置 -->
        <el-tab-pane label="注册设置" name="registration">
          <el-form :model="registrationSettings" label-width="120px">
            <el-form-item label="开放注册">
              <el-switch v-model="registrationSettings.registration_enabled" />
            </el-form-item>
            <el-form-item label="邮箱验证">
              <el-switch v-model="registrationSettings.email_verification_required" />
            </el-form-item>
            <el-form-item label="最小密码长度" prop="min_password_length">
              <el-input-number v-model="registrationSettings.min_password_length" :min="6" :max="20" />
            </el-form-item>
            <el-form-item label="邀请码注册">
              <el-switch v-model="registrationSettings.invite_code_required" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveRegistrationSettings">保存注册设置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 通知设置 -->
        <el-tab-pane label="通知设置" name="notification">
          <el-form :model="notificationSettings" label-width="120px">
            <el-form-item label="系统通知">
              <el-switch v-model="notificationSettings.system_notifications" />
            </el-form-item>
            <el-form-item label="邮件通知">
              <el-switch v-model="notificationSettings.email_notifications" />
            </el-form-item>
            <el-form-item label="订阅到期提醒">
              <el-switch v-model="notificationSettings.subscription_expiry_notifications" />
            </el-form-item>
            <el-form-item label="新用户注册通知">
              <el-switch v-model="notificationSettings.new_user_notifications" />
            </el-form-item>
            <el-form-item label="新订单通知">
              <el-switch v-model="notificationSettings.new_order_notifications" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveNotificationSettings">保存通知设置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 主题设置 -->
        <el-tab-pane label="主题设置" name="theme">
          <el-form :model="themeSettings" label-width="120px">
            <el-form-item label="默认主题" prop="default_theme">
              <el-select v-model="themeSettings.default_theme" style="width: 100%">
                <el-option label="浅色主题" value="light">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #409EFF; border-radius: 2px; margin-right: 8px;"></span>
                  浅色主题
                </el-option>
                <el-option label="深色主题" value="dark">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #1a1a1a; border-radius: 2px; margin-right: 8px;"></span>
                  深色主题
                </el-option>
                <el-option label="蓝色主题" value="blue">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #1890ff; border-radius: 2px; margin-right: 8px;"></span>
                  蓝色主题
                </el-option>
                <el-option label="绿色主题" value="green">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #52c41a; border-radius: 2px; margin-right: 8px;"></span>
                  绿色主题
                </el-option>
                <el-option label="紫色主题" value="purple">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #722ed1; border-radius: 2px; margin-right: 8px;"></span>
                  紫色主题
                </el-option>
                <el-option label="橙色主题" value="orange">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #fa8c16; border-radius: 2px; margin-right: 8px;"></span>
                  橙色主题
                </el-option>
                <el-option label="红色主题" value="red">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #f5222d; border-radius: 2px; margin-right: 8px;"></span>
                  红色主题
                </el-option>
                <el-option label="青色主题" value="cyan">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #13c2c2; border-radius: 2px; margin-right: 8px;"></span>
                  青色主题
                </el-option>
                <el-option label="Luck主题" value="luck">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #FFD700; border-radius: 2px; margin-right: 8px;"></span>
                  Luck主题
                </el-option>
                <el-option label="Aurora主题" value="aurora">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #7B68EE; border-radius: 2px; margin-right: 8px;"></span>
                  Aurora主题
                </el-option>
                <el-option label="跟随系统" value="auto">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #909399; border-radius: 2px; margin-right: 8px;"></span>
                  跟随系统
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="允许用户自定义主题">
              <el-switch v-model="themeSettings.allow_user_theme" />
            </el-form-item>
            <el-form-item label="可用主题">
              <el-checkbox-group v-model="themeSettings.available_themes" style="display: flex; flex-wrap: wrap; gap: 16px;">
                <el-checkbox label="light">
                  <span style="display: inline-flex; align-items: center; gap: 6px;">
                    <span style="display: inline-block; width: 14px; height: 14px; background: #409EFF; border-radius: 2px;"></span>
                    浅色主题
                  </span>
                </el-checkbox>
                <el-checkbox label="dark">
                  <span style="display: inline-flex; align-items: center; gap: 6px;">
                    <span style="display: inline-block; width: 14px; height: 14px; background: #1a1a1a; border-radius: 2px;"></span>
                    深色主题
                  </span>
                </el-checkbox>
                <el-checkbox label="blue">
                  <span style="display: inline-flex; align-items: center; gap: 6px;">
                    <span style="display: inline-block; width: 14px; height: 14px; background: #1890ff; border-radius: 2px;"></span>
                    蓝色主题
                  </span>
                </el-checkbox>
                <el-checkbox label="green">
                  <span style="display: inline-flex; align-items: center; gap: 6px;">
                    <span style="display: inline-block; width: 14px; height: 14px; background: #52c41a; border-radius: 2px;"></span>
                    绿色主题
                  </span>
                </el-checkbox>
                <el-checkbox label="purple">
                  <span style="display: inline-flex; align-items: center; gap: 6px;">
                    <span style="display: inline-block; width: 14px; height: 14px; background: #722ed1; border-radius: 2px;"></span>
                    紫色主题
                  </span>
                </el-checkbox>
                <el-checkbox label="orange">
                  <span style="display: inline-flex; align-items: center; gap: 6px;">
                    <span style="display: inline-block; width: 14px; height: 14px; background: #fa8c16; border-radius: 2px;"></span>
                    橙色主题
                  </span>
                </el-checkbox>
                <el-checkbox label="red">
                  <span style="display: inline-flex; align-items: center; gap: 6px;">
                    <span style="display: inline-block; width: 14px; height: 14px; background: #f5222d; border-radius: 2px;"></span>
                    红色主题
                  </span>
                </el-checkbox>
                <el-checkbox label="cyan">
                  <span style="display: inline-flex; align-items: center; gap: 6px;">
                    <span style="display: inline-block; width: 14px; height: 14px; background: #13c2c2; border-radius: 2px;"></span>
                    青色主题
                  </span>
                </el-checkbox>
                <el-checkbox label="luck">
                  <span style="display: inline-flex; align-items: center; gap: 6px;">
                    <span style="display: inline-block; width: 14px; height: 14px; background: #FFD700; border-radius: 2px;"></span>
                    Luck主题
                  </span>
                </el-checkbox>
                <el-checkbox label="aurora">
                  <span style="display: inline-flex; align-items: center; gap: 6px;">
                    <span style="display: inline-block; width: 14px; height: 14px; background: #7B68EE; border-radius: 2px;"></span>
                    Aurora主题
                  </span>
                </el-checkbox>
                <el-checkbox label="auto">
                  <span style="display: inline-flex; align-items: center; gap: 6px;">
                    <span style="display: inline-block; width: 14px; height: 14px; background: #909399; border-radius: 2px;"></span>
                    跟随系统
                  </span>
                </el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveThemeSettings">保存主题设置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 安全设置 -->
        <el-tab-pane label="安全设置" name="security">
          <el-form :model="securitySettings" label-width="120px">
            <el-form-item label="登录失败限制" prop="login_fail_limit">
              <el-input-number v-model="securitySettings.login_fail_limit" :min="3" :max="10" />
            </el-form-item>
            <el-form-item label="登录失败锁定时间(分钟)" prop="login_lock_time">
              <el-input-number v-model="securitySettings.login_lock_time" :min="5" :max="60" />
            </el-form-item>
            <el-form-item label="会话超时时间(分钟)" prop="session_timeout">
              <el-input-number v-model="securitySettings.session_timeout" :min="15" :max="1440" />
            </el-form-item>
            <el-form-item label="启用设备指纹">
              <el-switch v-model="securitySettings.device_fingerprint_enabled" />
            </el-form-item>
            <el-form-item label="启用IP白名单">
              <el-switch v-model="securitySettings.ip_whitelist_enabled" />
            </el-form-item>
            <el-form-item label="IP白名单" v-if="securitySettings.ip_whitelist_enabled">
              <el-input v-model="securitySettings.ip_whitelist" type="textarea" rows="3" placeholder="每行一个IP地址" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveSecuritySettings">保存安全设置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useApi } from '@/utils/api'
import { useThemeStore } from '@/store/theme'

export default {
  name: 'AdminSettings',
  components: {
    Plus
  },
  setup() {
    const api = useApi()
    const themeStore = useThemeStore()
    const activeTab = ref('general')
    const generalFormRef = ref()
    const uploadUrl = '/api/v1/admin/upload'

    // 基本设置
    const generalSettings = reactive({
      site_name: '',
      site_description: '',
      site_logo: '',
      default_theme: 'default'
    })

    const generalRules = {
      site_name: [
        { required: true, message: '请输入网站名称', trigger: 'blur' }
      ]
    }

    // 注册设置
    const registrationSettings = reactive({
      registration_enabled: true,
      email_verification_required: true,
      min_password_length: 8,
      invite_code_required: false
    })

    // 通知设置
    const notificationSettings = reactive({
      system_notifications: true,
      email_notifications: true,
      subscription_expiry_notifications: true,
      new_user_notifications: true,
      new_order_notifications: true
    })

    // 安全设置
    const securitySettings = reactive({
      login_fail_limit: 5,
      login_lock_time: 30,
      session_timeout: 120,
      device_fingerprint_enabled: true,
      ip_whitelist_enabled: false,
      ip_whitelist: ''
    })

    // 主题设置
    const themeSettings = reactive({
      default_theme: 'light',
      allow_user_theme: true,
      available_themes: ['light', 'dark', 'blue', 'green', 'purple', 'orange', 'red', 'cyan', 'luck', 'aurora', 'auto']
    })

    const loadSettings = async () => {
      try {
        const response = await api.get('/admin/settings')
        // 检查响应格式 - 后端返回的是 ResponseBase 格式，数据在 response.data.data 中
        const settings = response.data?.data || response.data || {}
        // 加载各项设置
        if (settings.general) {
          Object.assign(generalSettings, settings.general)
          }
        if (settings.registration) {
          Object.assign(registrationSettings, settings.registration)
          }
        if (settings.notification) {
          Object.assign(notificationSettings, settings.notification)
          }
        if (settings.security) {
          Object.assign(securitySettings, settings.security)
          }
        if (settings.theme) {
          Object.assign(themeSettings, settings.theme)
          }
      } catch (error) {
        ElMessage.error('加载设置失败: ' + (error.response?.data?.message || error.message || '未知错误'))
      }
    }

    const saveGeneralSettings = async () => {
      try {
        await generalFormRef.value.validate()
        await api.put('/admin/settings/general', generalSettings)
        ElMessage.success('基本设置保存成功')
      } catch (error) {
        ElMessage.error('保存失败')
      }
    }

    const saveRegistrationSettings = async () => {
      try {
        await api.put('/admin/settings/registration', registrationSettings)
        ElMessage.success('注册设置保存成功')
      } catch (error) {
        ElMessage.error('保存失败')
      }
    }

    const saveNotificationSettings = async () => {
      try {
        await api.put('/admin/settings/notification', notificationSettings)
        ElMessage.success('通知设置保存成功')
      } catch (error) {
        ElMessage.error('保存失败')
      }
    }

    const saveSecuritySettings = async () => {
      try {
        await api.put('/admin/settings/security', securitySettings)
        ElMessage.success('安全设置保存成功')
      } catch (error) {
        ElMessage.error('保存失败')
      }
    }

    const saveThemeSettings = async () => {
      try {
        await api.put('/admin/settings/theme', themeSettings)
        
        // 立即应用主题设置
        if (themeSettings.default_theme) {
          await themeStore.setTheme(themeSettings.default_theme)
        }
        
        ElMessage.success('主题设置保存成功')
      } catch (error) {
        ElMessage.error('保存失败')
      }
    }

    const handleLogoSuccess = (response) => {
      generalSettings.site_logo = response.url
      ElMessage.success('Logo上传成功')
    }

    const beforeLogoUpload = (file) => {
      const isImage = file.type.startsWith('image/')
      const isLt2M = file.size / 1024 / 1024 < 2

      if (!isImage) {
        ElMessage.error('只能上传图片文件!')
        return false
      }
      if (!isLt2M) {
        ElMessage.error('图片大小不能超过 2MB!')
        return false
      }
      return true
    }

    onMounted(() => {
      loadSettings()
    })

    return {
      activeTab,
      generalSettings,
      generalRules,
      registrationSettings,
      notificationSettings,
      securitySettings,
      themeSettings,
      generalFormRef,
      uploadUrl,
      saveGeneralSettings,
      saveRegistrationSettings,
      saveNotificationSettings,
      saveSecuritySettings,
      saveThemeSettings,
      handleLogoSuccess,
      beforeLogoUpload
    }
  }
}
</script>

<style scoped>
.admin-settings {
  padding: 20px;
}

.avatar-uploader {
  text-align: center;
}

.avatar-uploader .avatar {
  width: 100px;
  height: 100px;
  display: block;
}

.avatar-uploader .el-upload {
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: var(--el-transition-duration-fast);
}

.avatar-uploader .el-upload:hover {
  border-color: var(--el-color-primary);
}

.avatar-uploader-icon {
  font-size: 28px;
  color: #8c939d;
  width: 100px;
  height: 100px;
  text-align: center;
  line-height: 100px;
}

:deep(.el-input__wrapper) {
  border-radius: 0 !important;
  box-shadow: none !important;
  border: 1px solid #dcdfe6 !important;
  background-color: #ffffff !important;
  padding: 0 !important;
}

:deep(.el-select .el-input__wrapper) {
  border-radius: 0 !important;
  box-shadow: none !important;
  border: 1px solid #dcdfe6 !important;
  background-color: #ffffff !important;
  padding: 0 !important;
}

:deep(.el-input__inner) {
  border-radius: 0 !important;
  border: none !important;
  box-shadow: none !important;
  background-color: transparent !important;
  padding: 0 11px !important;
}

:deep(.el-input__prefix),
:deep(.el-input__suffix) {
  background-color: transparent !important;
  border: none !important;
}

:deep(.el-input__wrapper:hover) {
  border-color: #c0c4cc !important;
  box-shadow: none !important;
}

:deep(.el-input__wrapper.is-focus) {
  border-color: #1677ff !important;
  box-shadow: none !important;
}

:deep(.el-textarea__inner) {
  border-radius: 0 !important;
  border: 1px solid #dcdfe6 !important;
  box-shadow: none !important;
}
</style> 