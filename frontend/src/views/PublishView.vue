<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useArticleStore } from '@/stores/article'
import { useUserStore } from '@/stores/user'
import { notifySuccess, notifyError } from '@/utils'
import type { PublishStatus as PublishStatusType } from '@/types'
import PublishPanel from '@/components/PublishPanel.vue'
import PublishStatusComponent from '@/components/PublishStatus.vue'

const route = useRoute()
const router = useRouter()
const articleStore = useArticleStore()
const userStore = useUserStore()

const publishing = ref(false)
const publishStatus = ref<PublishStatusType | null>(null)
const taskId = ref<string | null>(null)
let pollingTimer: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  if (!userStore.isLoggedIn) {
    router.push('/login')
    return
  }
  const articleId = Number(route.params.articleId)
  if (articleId) {
    await articleStore.fetchArticle(articleId)
  }
  if (!articleStore.currentArticle) {
    router.push('/history')
  }
})

async function handlePublish(platforms: string[]) {
  if (!articleStore.currentArticle) return

  publishing.value = true
  try {
    const result = await articleStore.publish({
      article_id: articleStore.currentArticle.id,
      platforms,
    })
    if (result) {
      publishStatus.value = result
      taskId.value = result.task_id
      notifySuccess('发布任务已创建')
      startPolling(result.task_id)
    }
  } catch {
    notifyError('发布失败')
  } finally {
    publishing.value = false
  }
}

function startPolling(tId: string) {
  stopPolling()
  pollingTimer = setInterval(async () => {
    const status = await articleStore.checkPublishStatus(tId)
    if (status) {
      publishStatus.value = status
      if (status.status === 'success' || status.status === 'failed') {
        stopPolling()
      }
    }
  }, 3000)
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

function goToHistory() {
  router.push('/history')
}
</script>

<template>
  <div class="publish-view">
    <div class="page-header">
      <h2>一键发布</h2>
      <p class="page-desc">选择目标平台，将改写后的内容一键发布</p>
    </div>

    <!-- No article -->
    <el-empty
      v-if="!articleStore.currentArticle"
      description="没有可发布的文章"
      :image-size="120"
    >
      <el-button type="primary" @click="goToHistory">查看改写历史</el-button>
    </el-empty>

    <template v-else>
      <!-- Article preview -->
      <el-card shadow="hover" class="article-card">
        <div class="article-header">
          <span class="article-label">待发布文章</span>
          <span class="article-meta">
            {{ articleStore.currentArticle.result_content?.length ?? articleStore.currentArticle.source_content.length }} 字
          </span>
        </div>
        <div class="article-preview">
          {{ (articleStore.currentArticle.result_content ?? articleStore.currentArticle.source_content).slice(0, 300) }}{{ (articleStore.currentArticle.result_content ?? articleStore.currentArticle.source_content).length > 300 ? '...' : '' }}
        </div>
      </el-card>

      <!-- Publish panel -->
      <PublishPanel
        v-if="!publishStatus || (publishStatus.status !== 'running' && publishStatus.status !== 'pending')"
        @publish="handlePublish"
      />

      <!-- Publish status -->
      <PublishStatusComponent
        v-if="publishStatus"
        :status="publishStatus"
      />
    </template>
  </div>
</template>

<style scoped>
.publish-view {
  max-width: 800px;
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

.article-card {
  margin-bottom: 24px;
}

.article-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.article-label {
  font-size: 14px;
  font-weight: 500;
}

.article-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.article-preview {
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-regular);
  background: var(--el-fill-color-lighter);
  padding: 16px;
  border-radius: 8px;
  max-height: 200px;
  overflow-y: auto;
}
</style>
