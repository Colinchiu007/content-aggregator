<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import type { FormInstance } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = ref({
  username: userStore.user?.username ?? '',
  email: userStore.user?.email ?? '',
})

onMounted(() => {
  if (!userStore.isLoggedIn) {
    router.push('/login')
  }
})

async function handleSave() {
  loading.value = true
  try {
    // Placeholder: save settings via API when backend supports it
    await new Promise((r) => setTimeout(r, 500))
    ElMessage.success('设置已保存')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="settings-view">
    <div class="page-header">
      <h2>账户设置</h2>
      <p class="page-desc">管理你的账户信息和偏好设置</p>
    </div>

    <el-card shadow="hover" class="settings-card">
      <template #header>
        <span>基本信息</span>
      </template>

      <el-form
        ref="formRef"
        :model="form"
        label-width="100px"
        label-position="right"
      >
        <el-form-item label="用户名">
          <el-input v-model="form.username" disabled />
        </el-form-item>

        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>

        <el-form-item label="订阅类型">
          <el-tag :type="userStore.subscriptionType === 'free' ? 'info' : 'success'">
            {{ userStore.subscriptionType }}
          </el-tag>
        </el-form-item>

        <el-form-item label="注册时间" v-if="userStore.user?.created_at">
          <span>{{ new Date(userStore.user.created_at).toLocaleDateString('zh-CN') }}</span>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleSave">
            保存设置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Danger zone -->
    <el-card shadow="hover" class="danger-card">
      <template #header>
        <span class="danger-header">危险操作</span>
      </template>
      <p class="danger-desc">删除账户将永久删除所有数据，此操作不可撤销。</p>
      <el-button type="danger" plain disabled>删除账户（开发中）</el-button>
    </el-card>
  </div>
</template>

<script lang="ts">
import { ElMessage } from 'element-plus'
</script>

<style scoped>
.settings-view {
  max-width: 640px;
  margin: 0 auto;
  padding: 32px 24px;
}

.page-header {
  margin-bottom: 32px;
}

.page-header h2 {
  margin: 0 0 8px;
  font-size: 24px;
}

.page-desc {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.settings-card {
  margin-bottom: 24px;
}

.danger-card {
  border-color: var(--el-color-danger-light-3);
}

.danger-header {
  color: var(--el-color-danger);
  font-weight: 500;
}

.danger-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0 0 16px;
}
</style>
