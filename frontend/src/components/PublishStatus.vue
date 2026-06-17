<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheck, CircleClose, Loading, Clock } from '@element-plus/icons-vue'
import type { PublishStatus } from '@/types'

const props = defineProps<{
  status: PublishStatus
}>()

const statusIcon = computed(() => {
  switch (props.status.status) {
    case 'success': return CircleCheck
    case 'failed': return CircleClose
    case 'running': return Loading
    default: return Clock
  }
})

const statusColor = computed(() => {
  switch (props.status.status) {
    case 'success': return 'var(--el-color-success)'
    case 'failed': return 'var(--el-color-danger)'
    case 'running': return 'var(--el-color-primary)'
    default: return 'var(--el-text-color-secondary)'
  }
})

const statusLabel = computed(() => {
  switch (props.status.status) {
    case 'success': return '发布完成'
    case 'failed': return '发布失败'
    case 'running': return '发布中...'
    default: return '等待中'
  }
})

const platformResults = computed(() => {
  return Object.entries(props.status.results).map(([key, val]) => ({
    platform: key,
    ...val,
  }))
})
</script>

<template>
  <div class="publish-status">
    <!-- Overall status -->
    <div class="status-header">
      <el-icon :size="24" :color="statusColor">
        <component :is="statusIcon" :class="{ 'is-loading': status.status === 'running' }" />
      </el-icon>
      <span class="status-text" :style="{ color: statusColor }">{{ statusLabel }}</span>
    </div>

    <!-- Per-platform results -->
    <div class="platform-results" v-if="platformResults.length > 0">
      <div
        v-for="item in platformResults"
        :key="item.platform"
        class="platform-row"
      >
        <span class="platform-key">{{ item.platform }}</span>
        <el-tag
          :type="item.status === 'success' ? 'success' : item.status === 'failed' ? 'danger' : 'warning'"
          size="small"
        >
          {{ item.status === 'success' ? '成功' : item.status === 'failed' ? '失败' : '进行中' }}
        </el-tag>
        <span v-if="item.error" class="platform-error">{{ item.error }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.publish-status {
  padding: 24px 0;
}

.status-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding: 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.status-text {
  font-size: 18px;
  font-weight: 600;
}

.platform-results {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.platform-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}

.platform-key {
  font-size: 14px;
  font-weight: 500;
  min-width: 80px;
}

.platform-error {
  font-size: 12px;
  color: var(--el-color-danger);
  margin-left: auto;
}

.is-loading {
  animation: rotating 1.5s linear infinite;
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
