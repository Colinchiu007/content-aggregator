<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchPlatforms, fetchTrending, rewriteTrendingTopic } from '@/api/trending'
import type { TrendingItem, PlatformInfo } from '@/api/trending'

const router = useRouter()

// ── State ──
const platforms = ref<PlatformInfo[]>([])
const activePlatform = ref<string>('all')
const items = ref<TrendingItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const rewritingId = ref<number | null>(null)

// ── Computed ──
const activePlatformName = computed(() => {
  if (activePlatform.value === 'all') return '全部'
  return platforms.value.find(p => p.code === activePlatform.value)?.name ?? activePlatform.value
})

// ── Lifecycle ──
onMounted(async () => {
  await loadPlatforms()
  await loadData()
})

// ── Data loading ──
async function loadPlatforms() {
  try {
    const res = await fetchPlatforms()
    platforms.value = res.data?.platforms ?? []
  } catch {
    // silently fail — platforms list is non-critical
  }
}

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize }
    if (activePlatform.value !== 'all') {
      params.platforms = activePlatform.value
    }
    const res = await fetchTrending(params as any)
    items.value = res.data?.items ?? []
    total.value = res.pagination?.total ?? 0
  } catch {
    ElMessage.error('加载热榜数据失败')
    items.value = []
  } finally {
    loading.value = false
  }
}

function switchPlatform(code: string) {
  activePlatform.value = code
  page.value = 1
  loadData()
}

function formatHotValue(val: string | number): string {
  if (!val && val !== 0) return ''
  const n = typeof val === 'string' ? parseFloat(val) : val
  if (n >= 10000) { return (n / 10000).toFixed(1) + '万' }
  if (n >= 1000) { return (n / 1000).toFixed(1) + 'k' }
  return String(n)
}

// ── 一键改写 ──
async function handleRewrite(item: TrendingItem) {
  rewritingId.value = item.id
  try {
    const res = await rewriteTrendingTopic({
      topic_id: item.id,
      topic_url: item.topic_url,
      title: item.title,
      platform_code: item.platform.code,
    })
    if (res.data?.article_id) {
      ElMessage.success('内容已采集，正在跳转到改写页')
      router.push(`/rewrite/${res.data.article_id}`)
    }
  } catch {
    ElMessage.error('改写失败，请稍后重试')
  } finally {
    rewritingId.value = null
  }
}
</script>

<template>
  <div class="trending-view">
    <!-- Header -->
    <div class="page-header">
      <h2>🔥 热榜发现</h2>
      <p class="page-desc">实时聚合各平台热门话题，选中心仪内容一键改写</p>
    </div>

    <!-- Platform tabs -->
    <div class="platform-bar">
      <button
        :class="['platform-tab', { active: activePlatform === 'all' }]"
        @click="switchPlatform('all')"
      >
        全部
      </button>
      <button
        v-for="p in platforms"
        :key="p.code"
        :class="['platform-tab', { active: activePlatform === p.code }]"
        @click="switchPlatform(p.code)"
      >
        {{ p.name }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="il-empty">
      <div class="il-empty-icon">⏳</div>
      <div class="il-empty-title">加载中...</div>
      <div class="il-empty-desc">正在获取热榜数据</div>
    </div>

    <!-- Empty -->
    <div v-else-if="items.length === 0" class="il-empty">
      <div class="il-empty-icon">📭</div>
      <div class="il-empty-title">暂无数据</div>
      <div class="il-empty-desc">当前没有热榜内容，请稍后再来</div>
    </div>

    <!-- Trending list -->
    <div v-else class="trending-list">
      <div
        v-for="item in items"
        :key="item.id"
        class="trending-item il-card"
      >
        <!-- Rank badge -->
        <div class="rank-badge" :class="{ top3: item.rank <= 3 }">
          {{ item.rank }}
        </div>

        <!-- Content -->
        <div class="item-body">
          <div class="item-title">{{ item.title }}</div>
          <div class="item-meta">
            <span class="platform-tag">{{ item.platform.name }}</span>
            <span class="hot-value">{{ formatHotValue(item.hot_value_norm || item.hot_value) }}</span>
            <span class="category-tag" v-if="item.category && item.category !== 'general'">{{ item.category }}</span>
          </div>
        </div>

        <!-- Action -->
        <div class="item-action">
          <el-button
            type="primary"
            size="small"
            :loading="rewritingId === item.id"
            :disabled="rewritingId !== null"
            @click="handleRewrite(item)"
          >
            {{ rewritingId === item.id ? '改写中...' : '一键改写' }}
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.trending-view {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px 0;
}

/* Header */
.page-header {
  margin-bottom: 24px;
}
.page-header h2 {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--il-text);
}
.page-desc {
  margin: 0;
  font-size: 14px;
  color: var(--il-text-secondary);
}

/* Platform bar */
.platform-bar {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.platform-tab {
  padding: 6px 16px;
  border: 1px solid var(--il-border);
  border-radius: 20px;
  background: var(--il-surface);
  color: var(--il-text-secondary);
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}
.platform-tab:hover {
  border-color: var(--il-primary);
  color: var(--il-primary);
}
.platform-tab.active {
  background: var(--il-primary);
  color: #fff;
  border-color: var(--il-primary);
}

/* Trending list */
.trending-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.trending-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-radius: var(--il-radius-lg);
  border: 1px solid var(--il-border);
  transition: border-color 0.2s;
}
.trending-item:hover {
  border-color: var(--il-primary);
}

/* Rank */
.rank-badge {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 700;
  color: var(--il-text-muted);
  background: var(--il-surface-hover);
  flex-shrink: 0;
}
.rank-badge.top3 {
  color: #fff;
  background: linear-gradient(135deg, #F59E0B, #EF4444);
}

/* Item body */
.item-body {
  flex: 1;
  min-width: 0;
}
.item-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--il-text);
  margin-bottom: 6px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}
.platform-tag {
  color: var(--il-primary);
  font-weight: 500;
}
.hot-value {
  color: var(--il-text-muted);
}
.category-tag {
  padding: 1px 8px;
  border-radius: 10px;
  background: rgba(79, 70, 229, 0.08);
  color: var(--il-primary);
}

/* Action */
.item-action {
  flex-shrink: 0;
}
</style>
