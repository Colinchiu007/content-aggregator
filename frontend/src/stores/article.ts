import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import * as articlesApi from '@/api/articles'
import * as collectorApi from '@/api/collector'
import * as rewriterApi from '@/api/rewriter'
import * as publisherApi from '@/api/publisher'
import type {
  Article,
  CollectResult,
  RewriteRequest,
  RewriteResult,
  PublishStatus,
} from '@/types'
import { notifySuccess } from '@/utils'

export const useArticleStore = defineStore('article', () => {
  // ── State ──────────────────────────────────────────────────────────────
  const currentArticle = ref<Article | null>(null)
  const articles = ref<Article[]>([])
  const total = ref(0)
  const loading = ref(false)
  const rewriteLoading = ref(false)
  const publishLoading = ref(false)

  // Collect state
  const collectResult = ref<CollectResult | null>(null)
  const collectLoading = ref(false)

  // Rewrite state
  const rewriteResult = ref<RewriteResult | null>(null)

  // Publish state
  const publishStatus = ref<PublishStatus | null>(null)

  // ── Getters ────────────────────────────────────────────────────────────
  const hasArticles = computed(() => articles.value.length > 0)
  const hasRewriteResult = computed(() => !!rewriteResult.value)

  // ── Article CRUD ───────────────────────────────────────────────────────
  async function fetchArticles(page = 1, pageSize = 20, search?: string) {
    loading.value = true
    try {
      const res = await articlesApi.listArticles({ page, page_size: pageSize, search })
      articles.value = res.data.items
      total.value = res.data.total
    } finally {
      loading.value = false
    }
  }

  async function fetchArticle(id: number) {
    loading.value = true
    try {
      const res = await articlesApi.getArticle(id)
      currentArticle.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function saveArticle(
    sourceType: 'url' | 'text' | 'file',
    content: string,
    sourceUrl?: string,
  ): Promise<Article | null> {
    loading.value = true
    try {
      const res = await articlesApi.createArticle({
        source_type: sourceType,
        source_content: content,
        source_url: sourceUrl,
      })
      currentArticle.value = res.data
      notifySuccess('文章已保存')
      return res.data
    } catch {
      return null
    } finally {
      loading.value = false
    }
  }

  async function updateArticle(
    id: number,
    data: Partial<Pick<Article, 'result_content' | 'rewrite_style' | 'rewrite_length'>>,
  ) {
    loading.value = true
    try {
      const res = await articlesApi.updateArticle(id, data)
      currentArticle.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function deleteArticle(id: number) {
    loading.value = true
    try {
      await articlesApi.deleteArticle(id)
      articles.value = articles.value.filter((a) => a.id !== id)
      notifySuccess('文章已删除')
    } finally {
      loading.value = false
    }
  }

  // ── Collector ──────────────────────────────────────────────────────────
  async function collectFromUrl(url: string) {
    collectLoading.value = true
    try {
      const res = await collectorApi.collectUrl({ url })
      collectResult.value = res.data
      return res.data
    } catch {
      return null
    } finally {
      collectLoading.value = false
    }
  }

  // ── Rewriter ───────────────────────────────────────────────────────────
  async function requestRewrite(data: RewriteRequest) {
    rewriteLoading.value = true
    try {
      const res = await rewriterApi.rewriteArticle(data)
      rewriteResult.value = res.data
      notifySuccess('改写完成')
      return res.data
    } catch {
      return null
    } finally {
      rewriteLoading.value = false
    }
  }

  // ── Publisher ──────────────────────────────────────────────────────────
  async function publish(data: { article_id: number; platforms: string[] }) {
    publishLoading.value = true
    try {
      const res = await publisherApi.publishArticle(data)
      publishStatus.value = res.data
      return res.data
    } catch {
      return null
    } finally {
      publishLoading.value = false
    }
  }

  async function checkPublishStatus(taskId: string) {
    try {
      const res = await publisherApi.getPublishStatus(taskId)
      publishStatus.value = res.data
      return res.data
    } catch {
      return null
    }
  }

  // ── Reset ──────────────────────────────────────────────────────────────
  function resetState() {
    currentArticle.value = null
    collectResult.value = null
    rewriteResult.value = null
    publishStatus.value = null
  }

  return {
    // state
    currentArticle,
    articles,
    total,
    loading,
    rewriteLoading,
    publishLoading,
    collectResult,
    collectLoading,
    rewriteResult,
    publishStatus,
    // getters
    hasArticles,
    hasRewriteResult,
    // actions
    fetchArticles,
    fetchArticle,
    saveArticle,
    updateArticle,
    deleteArticle,
    collectFromUrl,
    requestRewrite,
    publish,
    checkPublishStatus,
    resetState,
  }
})
