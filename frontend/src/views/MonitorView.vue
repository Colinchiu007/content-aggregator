<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, Delete, Edit, View, Search, Refresh,
  Reading, Promotion,
} from '@element-plus/icons-vue'
import {
  fetchMonitors, createMonitor, updateMonitor, deleteMonitor, getMonitor,
  fetchMonitorArticles, markArticleRead, rewriteMonitorArticle,
} from '@/api/monitors'
import type {
  MonitorSourceListItem, MonitorSource,
  MonitorArticleListItem,
} from '@/api/monitors'
import { formatDate } from '@/utils'

const router = useRouter()

// ── Tabs ──
const activeTab = ref('sources')

// ── Monitor Sources State ──
const sources = ref<MonitorSourceListItem[]>([])
const sourcesTotal = ref(0)
const sourcesPage = ref(1)
const sourcesPageSize = 20
const sourcesLoading = ref(false)
const searchQuery = ref('')
const sourceTypeFilter = ref('')
const showSourceDialog = ref(false)
const editingSource = ref<MonitorSource | null>(null)
const sourceForm = ref({
  name: '',
  source_type: 'wechat',
  identifier: '',
  schedule_cron: '',
  is_active: true,
})
const saving = ref(false)

const sourceTypeOptions = [
  { value: 'wechat', label: '微信公众号' },
  { value: 'zhihu', label: '知乎' },
  { value: 'url', label: '通用 URL' },
]

// ── Monitor Articles State ──
const articles = ref<MonitorArticleListItem[]>([])
const articlesTotal = ref(0)
const articlesPage = ref(1)
const articlesPageSize = ref(20)
const articlesLoading = ref(false)
const articleFilterSourceId = ref('')
const articleFilterUnreadOnly = ref(false)
const rewritingArticleId = ref<string | null>(null)

// ── Lifecycle ──
onMounted(async () => {
  await loadSources()
  await loadArticles()
})

// ── Load Sources ──
async function loadSources() {
  sourcesLoading.value = true
  try {
    const res = await fetchMonitors({
      page: sourcesPage.value,
      page_size: sourcesPageSize,
      search: searchQuery.value || undefined,
      source_type: sourceTypeFilter.value || undefined,
    })
    sources.value = res.items ?? []
    sourcesTotal.value = res.total ?? 0
  } catch {
    ElMessage.error('加载监控源列表失败')
    sources.value = []
  } finally {
    sourcesLoading.value = false
  }
}

// ── Source CRUD ──
function openAddDialog() {
  editingSource.value = null
  sourceForm.value = {
    name: '',
    source_type: 'wechat',
    identifier: '',
    schedule_cron: '',
    is_active: true,
  }
  showSourceDialog.value = true
}

async function openEditDialog(source: MonitorSourceListItem) {
  try {
    const detail = await getMonitor(source.id)
    editingSource.value = detail
    sourceForm.value = {
      name: detail.name,
      source_type: detail.source_type,
      identifier: detail.identifier,
      schedule_cron: detail.schedule_cron ?? '',
      is_active: detail.is_active,
    }
    showSourceDialog.value = true
  } catch {
    ElMessage.error('获取监控源详情失败')
  }
}

async function saveSource() {
  if (!sourceForm.value.name || !sourceForm.value.identifier) {
    ElMessage.warning('请填写必填项')
    return
  }
  saving.value = true
  try {
    if (editingSource.value) {
      await updateMonitor(editingSource.value.id, sourceForm.value)
      ElMessage.success('监控源已更新')
    } else {
      await createMonitor(sourceForm.value)
      ElMessage.success('监控源已创建')
    }
    showSourceDialog.value = false
    await loadSources()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDeleteSource(source: MonitorSourceListItem) {
  try {
    await ElMessageBox.confirm(
      `确定删除监控源「${source.name}」？关联的监控文章也将被删除。`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
    await deleteMonitor(source.id)
    ElMessage.success('已删除')
    await loadSources()
  } catch {
    // cancelled or error
  }
}

function handleSourcePageChange(page: number) {
  sourcesPage.value = page
  loadSources()
}

function handleSearch() {
  sourcesPage.value = 1
  loadSources()
}

// ── Load Articles ──
async function loadArticles() {
  articlesLoading.value = true
  try {
    const params: Record<string, unknown> = {
      page: articlesPage.value,
      page_size: articlesPageSize.value,
    }
    if (articleFilterSourceId.value) {
      params.source_id = articleFilterSourceId.value
    }
    if (articleFilterUnreadOnly.value) {
      params.is_read = false
    }
    const res = await fetchMonitorArticles(params as any)
    articles.value = res.items ?? []
    articlesTotal.value = res.total ?? 0
  } catch {
    ElMessage.error('加载监控文章失败')
    articles.value = []
  } finally {
    articlesLoading.value = false
  }
}

function handleArticlePageChange(page: number) {
  articlesPage.value = page
  loadArticles()
}

// ── Article actions ──
async function handleMarkRead(article: MonitorArticleListItem) {
  try {
    await markArticleRead(article.id)
    article.is_read = true
    ElMessage.success('已标记为已读')
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleRewrite(article: MonitorArticleListItem) {
  rewritingArticleId.value = article.id
  try {
    const res = await rewriteMonitorArticle(article.id, {
      style: '轻松易懂',
      length: 'keep',
    })
    ElMessage.success('改写完成！')
    router.push(`/rewrite/${res.article_id}`)
  } catch {
    ElMessage.error('改写失败')
  } finally {
    rewritingArticleId.value = null
  }
}

function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return '-'
  return formatDate(dateStr)
}

const typeLabel = (type: string): string => {
  const map: Record<string, string> = {
    wechat: '微信公众号',
    zhihu: '知乎',
    url: '通用 URL',
  }
  return map[type] ?? type
}

const openUrl = (url: string) => {
  window.open(url, '_blank')
}
</script>

<template>
  <div class="monitor-view">
    <div class="page-header">
      <h2>竞品监控</h2>
      <p class="page-desc">添加竞品账号，自动采集最新文章</p>
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" class="monitor-tabs">
      <!-- Tab 1: 监控源管理 -->
      <el-tab-pane label="监控源管理" name="sources">
        <div class="toolbar">
          <div class="toolbar-left">
            <el-input
              v-model="searchQuery"
              placeholder="搜索监控源名称..."
              :prefix-icon="Search"
              clearable
              @keyup.enter="handleSearch"
              style="width: 240px"
            />
            <el-select
              v-model="sourceTypeFilter"
              placeholder="类型筛选"
              clearable
              @change="handleSearch"
              style="width: 140px"
            >
              <el-option
                v-for="opt in sourceTypeOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button type="primary" :icon="Plus" @click="openAddDialog">
              新增监控源
            </el-button>
          </div>
        </div>

        <el-card shadow="hover" v-loading="sourcesLoading">
          <el-table
            :data="sources"
            stripe
            empty-text="暂无监控源，点击上方按钮添加"
            style="width: 100%"
          >
            <el-table-column prop="name" label="名称" min-width="160" />
            <el-table-column label="类型" width="120">
              <template #default="{ row }">
                <el-tag
                  :type="row.source_type === 'wechat' ? 'success' : row.source_type === 'zhihu' ? 'primary' : 'info'"
                  size="small"
                >
                  {{ typeLabel(row.source_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="identifier" label="标识符" min-width="200" show-overflow-tooltip />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
                  {{ row.is_active ? '启用' : '暂停' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="上次采集" width="170">
              <template #default="{ row }">
                {{ formatDateTime(row.last_collected_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button text type="primary" :icon="Edit" size="small" @click="openEditDialog(row)">
                  编辑
                </el-button>
                <el-button text type="danger" :icon="Delete" size="small" @click="handleDeleteSource(row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrap" v-if="sourcesTotal > sourcesPageSize">
            <el-pagination
              v-model:current-page="sourcesPage"
              :page-size="sourcesPageSize"
              :total="sourcesTotal"
              layout="prev, pager, next"
              @current-change="handleSourcePageChange"
            />
          </div>
        </el-card>
      </el-tab-pane>

      <!-- Tab 2: 监控文章 -->
      <el-tab-pane label="监控文章" name="articles">
        <div class="toolbar">
          <div class="toolbar-left">
            <el-select
              v-model="articleFilterSourceId"
              placeholder="按监控源筛选"
              clearable
              @change="() => { articlesPage = 1; loadArticles() }"
              style="width: 200px"
            >
              <el-option
                v-for="src in sources"
                :key="src.id"
                :label="src.name"
                :value="src.id"
              />
            </el-select>
            <el-checkbox
              v-model="articleFilterUnreadOnly"
              label="仅显示未读"
              @change="() => { articlesPage = 1; loadArticles() }"
            />
          </div>
          <div class="toolbar-right">
            <el-button :icon="Refresh" @click="loadArticles">刷新</el-button>
          </div>
        </div>

        <el-card shadow="hover" v-loading="articlesLoading">
          <el-table
            :data="articles"
            stripe
            empty-text="暂无监控文章"
            style="width: 100%"
          >
            <el-table-column label="状态" width="70">
              <template #default="{ row }">
                <el-tag :type="row.is_read ? 'info' : 'warning'" size="small">
                  {{ row.is_read ? '已读' : '未读' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="250" show-overflow-tooltip />
            <el-table-column prop="author" label="作者" width="140" />
            <el-table-column label="采集时间" width="170">
              <template #default="{ row }">
                {{ formatDateTime(row.collected_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="210" fixed="right">
              <template #default="{ row }">
                <el-button text type="primary" :icon="View" size="small" @click="openUrl(row.url)">
                  原文
                </el-button>
                <el-button
                  v-if="!row.is_read"
                  text type="warning" :icon="Reading" size="small"
                  @click="handleMarkRead(row)"
                >
                  标为已读
                </el-button>
                <el-button
                  text type="success" :icon="Promotion" size="small"
                  :loading="rewritingArticleId === row.id"
                  @click="handleRewrite(row)"
                >
                  改写
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrap" v-if="articlesTotal > articlesPageSize">
            <el-pagination
              v-model:current-page="articlesPage"
              :page-size="articlesPageSize"
              :total="articlesTotal"
              layout="prev, pager, next"
              @current-change="handleArticlePageChange"
            />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- Add/Edit Dialog -->
    <el-dialog
      v-model="showSourceDialog"
      :title="editingSource ? '编辑监控源' : '新增监控源'"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form :model="sourceForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="sourceForm.name" placeholder="给监控源起个名字" maxlength="200" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="sourceForm.source_type" style="width: 100%">
            <el-option
              v-for="opt in sourceTypeOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标识符" required>
          <el-input
            v-model="sourceForm.identifier"
            :placeholder="sourceForm.source_type === 'wechat' ? '公众号ID' : sourceForm.source_type === 'zhihu' ? '知乎UID' : '完整URL'"
            type="textarea"
            :rows="2"
          />
        </el-form-item>
        <el-form-item label="采集频率">
          <el-input v-model="sourceForm.schedule_cron" placeholder="Cron 表达式，留空使用系统默认" />
          <div class="form-tip">例如：0 */6 * * *（每6小时）</div>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="sourceForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSourceDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveSource">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.monitor-view {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 700;
  color: var(--il-text-primary, #1e293b);
}

.page-desc {
  margin: 0;
  font-size: 14px;
  color: var(--il-text-secondary, #64748b);
}

.monitor-tabs {
  margin-top: 16px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-right {
  flex-shrink: 0;
}

.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 20px;
  padding: 12px 0;
}

.form-tip {
  font-size: 12px;
  color: var(--il-text-secondary, #94a3b8);
  margin-top: 4px;
}
</style>
