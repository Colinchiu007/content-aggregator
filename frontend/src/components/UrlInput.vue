<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Link } from '@element-plus/icons-vue'

const emit = defineEmits<{
  collect: [url: string]
}>()

const url = ref('')
const loading = ref(false)

function isValidUrl(value: string): boolean {
  try {
    new URL(value)
    return true
  } catch {
    return false
  }
}

async function handleCollect() {
  const trimmed = url.value.trim()
  if (!trimmed) {
    ElMessage.warning('请输入文章链接')
    return
  }
  if (!isValidUrl(trimmed)) {
    ElMessage.warning('请输入有效的 URL 地址')
    return
  }
  loading.value = true
  try {
    emit('collect', trimmed)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="url-input">
    <el-input
      v-model="url"
      placeholder="粘贴文章链接，如微信公众号、知乎、掘金..."
      size="large"
      clearable
      :prefix-icon="Link"
      @keyup.enter="handleCollect"
    >
      <template #append>
        <el-button
          type="primary"
          :loading="loading"
          :icon="Link"
          @click="handleCollect"
        >
          采集全文
        </el-button>
      </template>
    </el-input>
    <p class="url-hint">支持公众号、知乎、掘金、头条、简书等平台的文章链接</p>
  </div>
</template>

<style scoped>
.url-input {
  width: 100%;
}

.url-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
