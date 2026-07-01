<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Delete, Edit, View } from '@element-plus/icons-vue'
import { useArticleStore } from '@/stores/article'
import { useUserStore } from '@/stores/user'
import { formatDate, formatRelativeTime, truncateText, sourceTypeLabel, confirmAction } from '@/utils'
import type { Article } from '@/types'

const router = useRouter()
const articleStore = useArticleStore()
const userStore = useUserStore()

const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = ref(20)

onMounted(async () => {
  if (!userStore.isLoggedIn) {
    router.push('/login')
    return
  }
  await loadArticles()
})

async function loadArticles() {
  await articleStore.fetchArticles(currentPage.value, pageSize.value, searchQuery.value || undefined)
}

async function handleSearch() {
  currentPage.value = 1
  await loadArticles()
}

function handleClearSearch() {
  searchQuery.value = ''
  handleSearch()
}

async function handleDelete(article: Article) {
  const ok = await confirmAction(`确定删除这篇改写记录？`)
  if (ok) {
    await articleStore.deleteArticle(article.id)
  }
}

function viewRewrite(article: Article) {
  router.push(`/rewrite/${article.id}`)
}

function editRewrite(article: Article) {
  router.push(`/rewrite/${article.id}`)
}

function goToPublish(article: Article) {
  router.push(`/publish/${article.id}`)
}

function handlePageChange(page: number) {
  currentPage.value = page
  loadArticles()
}

const tableColumns = [
  { prop: 'id', label: 'ID', width: 70 },
  { prop: 'source_content', label: '内容预览' },
  { prop: 'source_type', label: '来源', width: 100 },
  { prop: 'rewrite_style', label: '风格', width: 100 },
  { prop: 'created_at', label: '时间', width: 160 },
]
</script>

<template>
  <div class="history-view">
    <div class="page-header">
      <h2>改写历史</h2>
      <p class="page-desc">管理所有改写记录</p>
    </div>

    <!-- Search bar -->
    <div class="search-bar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索改写内容..."
        :prefix-icon="Search"
        clearable
        @keyup.enter="handleSearch"
        @clear="handleClearSearch"
        class="search-input"
      />
    </div>

    <!-- Table -->
    <el-card shadow="hover" v-loading="articleStore.loading">
      <el-table
        :data="articleStore.articles"
        stripe
        empty-text="暂无改写记录"
        style="width: 100%"
      >
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="内容预览" min-width="280">
          <template #default="{ row }">
            <div class="content-preview">
              <span class="source-type-tag">
                <el-tag size="small" type="info">{{ sourceTypeLabel(row.source_type) }}</el-tag>
              </span>
              <span>{{ truncateText(row.source_content, 80) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="source_type" label="来源" width="100">
          <template #default="{ row }">
            {{ sourceTypeLabel(row.source_type) }}
          </template>
        </el-table-column>
        <el-table-column label="风格" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.rewrite_style" size="small" type="success">
              {{ row.rewrite_style }}
            </el-tag>
            <el-tag v-else size="small" type="info">未改写</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">
            <el-tooltip :content="formatDate(row.created_at)">
              <span>{{ formatRelativeTime(row.created_at) }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button size="small" text :icon="View" @click="viewRewrite(row)">
                查看
              </el-button>
              <el-button size="small" text :icon="Edit" @click="editRewrite(row)">
                改写
              </el-button>
              <el-button size="small" text type="danger" :icon="Delete" @click="handleDelete(row)">
                删除
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination" v-if="articleStore.total > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="articleStore.total"
          layout="prev, pager, next, total"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.history-view {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 24px;
}

.page-header {
  margin-bottom: 24px;
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

.search-bar {
  margin-bottom: 20px;
}

.search-input {
  max-width: 400px;
}

.content-preview {
  display: flex;
  align-items: center;
  gap: 8px;
}

.source-type-tag {
  flex-shrink: 0;
}

.pagination {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
</style>
