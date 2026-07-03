<script setup lang="ts">
import { ref, computed } from 'vue'
import { Promotion } from '@element-plus/icons-vue'
import { DEFAULT_PLATFORMS } from '@/utils'
import type { Platform } from '@/types'

const emit = defineEmits<{
  publish: [platforms: string[]]
}>()

const platforms = ref<Platform[]>(JSON.parse(JSON.stringify(DEFAULT_PLATFORMS)))
const selectedPlatforms = ref<string[]>(
  platforms.value.filter((p) => p.enabled).map((p) => p.key),
)
const loading = ref(false)

const canPublish = computed(() => selectedPlatforms.value.length > 0)

function togglePlatform(key: string) {
  const idx = selectedPlatforms.value.indexOf(key)
  if (idx >= 0) {
    selectedPlatforms.value.splice(idx, 1)
  } else {
    selectedPlatforms.value.push(key)
  }
}

async function handlePublish() {
  if (!canPublish.value) return
  loading.value = true
  try {
    emit('publish', selectedPlatforms.value)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="publish-panel">
    <h3>选择发布平台</h3>

    <div class="platform-grid">
      <el-card
        v-for="p in platforms"
        :key="p.key"
        :class="['platform-card', { selected: selectedPlatforms.includes(p.key) }]"
        shadow="hover"
        @click="togglePlatform(p.key)"
      >
        <div class="platform-info">
          <el-icon :size="28"><component :is="p.icon" /></el-icon>
          <span class="platform-name">{{ p.name }}</span>
        </div>
        <el-tag
          :type="selectedPlatforms.includes(p.key) ? 'success' : 'info'"
          size="small"
          class="platform-tag"
        >
          {{ selectedPlatforms.includes(p.key) ? '已选' : '点击选择' }}
        </el-tag>
      </el-card>
    </div>

    <div class="publish-action">
      <el-button
        type="primary"
        size="large"
        :icon="Promotion"
        :loading="loading"
        :disabled="!canPublish"
        @click="handlePublish"
      >
        一键发布（已选 {{ selectedPlatforms.length }} 个平台）
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.publish-panel {
  padding: 16px 0;
}

.publish-panel h3 {
  margin: 0 0 16px;
  font-size: 18px;
}

.platform-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.platform-card {
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.platform-card.selected {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-3);
}

.platform-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
}

.platform-name {
  font-size: 14px;
  font-weight: 500;
}

.platform-tag {
  margin-top: 8px;
  display: block;
  text-align: center;
}

.publish-action {
  display: flex;
  justify-content: center;
}
</style>
