<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Edit, Refresh } from '@element-plus/icons-vue'
import { useArticleStore } from '@/stores/article'
import { useUserStore } from '@/stores/user'
import { notifyError, notifyInfo } from '@/utils'
import type { RewriteStyle, RewriteLength } from '@/types'
import StyleSelector from '@/components/StyleSelector.vue'
import LengthSelector from '@/components/LengthSelector.vue'
import RewriteResult from '@/components/RewriteResult.vue'

const route = useRoute()
const router = useRouter()
const articleStore = useArticleStore()
const userStore = useUserStore()

const rewriteStyle = ref<RewriteStyle>('casual')
const rewriteLength = ref<RewriteLength>('original')
const seoOptimize = ref(false)

const articleId = ref<number | null>(null)

onMounted(async () => {
  const id = route.params.id ? Number(route.params.id) : null
  if (id) {
    articleId.value = id
    await articleStore.fetchArticle(id)
  }
  // Redirect to home if not logged in and no article loaded
  if (!userStore.isLoggedIn && !articleStore.currentArticle) {
    router.push('/')
  }
})

async function handleRewrite() {
  if (!articleStore.currentArticle?.id) {
    notifyError('请先输入或采集文章内容')
    return
  }
  const result = await articleStore.requestRewrite({
    article_id: articleStore.currentArticle.id,
    style: rewriteStyle.value,
    length: rewriteLength.value,
    seo_optimize: seoOptimize.value,
  })
  if (result) {
    await articleStore.updateArticle(articleStore.currentArticle.id, {
      result_content: result.result_content,
      rewrite_style: rewriteStyle.value,
      rewrite_length: rewriteLength.value,
    })
  }
}

function handleSaveEdited(content: string) {
  if (articleStore.currentArticle) {
    articleStore.updateArticle(articleStore.currentArticle.id, {
      result_content: content,
    })
  }
}

function goToPublish() {
  if (articleStore.currentArticle) {
    router.push(`/publish/${articleStore.currentArticle.id}`)
  }
}

function goToHome() {
  router.push('/')
}
</script>

<template>
  <div class="rewrite-view">
    <div class="page-header">
      <h2>AI 智能改写</h2>
      <p class="page-desc">选择风格、调整长度，让 AI 帮你生成高质量内容</p>
    </div>

    <!-- No article loaded: show input redirect -->
    <el-empty
      v-if="!articleStore.currentArticle"
      description="还没有文章内容"
      :image-size="120"
    >
      <el-button type="primary" @click="goToHome">去输入内容</el-button>
    </el-empty>

    <!-- Article loaded -->
    <template v-else>
      <!-- Source info -->
      <el-alert
        :title="`原文 (${articleStore.currentArticle.word_count_original} 字)`"
        type="info"
        :closable="false"
        show-icon
        class="source-alert"
      >
        <template #default>
          <p class="source-preview">
            {{ articleStore.currentArticle.source_content.slice(0, 200) }}{{ articleStore.currentArticle.source_content.length > 200 ? '...' : '' }}
          </p>
        </template>
      </el-alert>

      <!-- Options -->
      <el-card shadow="hover" class="options-card">
        <StyleSelector v-model:style="rewriteStyle" />
        <LengthSelector v-model:length="rewriteLength" />

        <div class="advanced-options">
          <el-checkbox v-model="seoOptimize">
            SEO 优化（自动优化标题和关键词布局）
          </el-checkbox>
        </div>

        <div class="rewrite-action">
          <el-button
            type="primary"
            size="large"
            :icon="Edit"
            :loading="articleStore.rewriteLoading"
            @click="handleRewrite"
          >
            开始改写
          </el-button>
          <el-button
            v-if="articleStore.rewriteResult"
            size="large"
            :icon="Refresh"
            @click="handleRewrite"
          >
            重新改写
          </el-button>
        </div>
      </el-card>

      <!-- Rewrite result -->
      <RewriteResult
        v-if="articleStore.rewriteResult"
        :original="articleStore.currentArticle.source_content"
        :rewritten="articleStore.rewriteResult.result_content"
        :word-count-original="articleStore.currentArticle.word_count_original"
        :word-count-rewritten="articleStore.rewriteResult.word_count"
        @save="handleSaveEdited"
        @retry="handleRewrite"
      />

      <!-- Publish CTA -->
      <div v-if="articleStore.rewriteResult" class="publish-cta">
        <el-button type="success" size="large" @click="goToPublish">
          满意，去发布 →
        </el-button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.rewrite-view {
  max-width: 960px;
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

.source-alert {
  margin-bottom: 20px;
}

.source-preview {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
  max-height: 72px;
  overflow: hidden;
}

.options-card {
  margin-bottom: 24px;
}

.advanced-options {
  margin-bottom: 16px;
}

.rewrite-action {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.publish-cta {
  text-align: center;
  margin-top: 32px;
  padding: 24px 0;
}
</style>
