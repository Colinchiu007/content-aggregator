<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { UploadFilled } from '@element-plus/icons-vue'
import { useArticleStore } from '@/stores/article'
import { useUserStore } from '@/stores/user'
import { notifySuccess, notifyError } from '@/utils'
import UrlInput from '@/components/UrlInput.vue'
import TextInput from '@/components/TextInput.vue'

const router = useRouter()
const articleStore = useArticleStore()
const userStore = useUserStore()

// ── Tabs ──────────────────────────────────────────────────────────────────
const activeTab = ref<'url' | 'text' | 'file'>('url')

// ── URL input ─────────────────────────────────────────────────────────────
const sourceUrl = ref('')

async function handleUrlCollect(url: string) {
  sourceUrl.value = url
  const result = await articleStore.collectFromUrl(url)
  if (result) {
    notifySuccess(`采集成功: ${result.title} (${result.word_count} 字)`)
    const article = await articleStore.saveArticle('url', result.content, url)
    if (article) {
      router.push(`/rewrite/${article.id}`)
    }
  } else {
    notifyError('采集失败，请检查链接是否可访问')
  }
}

// ── Text input ─────────────────────────────────────────────────────────────
const textContent = ref('')

async function handleTextSubmit() {
  const trimmed = textContent.value.trim()
  if (!trimmed) {
    notifyError('请输入内容')
    return
  }
  if (trimmed.length < 50) {
    notifyError('内容太短，请至少输入50字')
    return
  }
  const article = await articleStore.saveArticle('text', trimmed)
  if (article) {
    router.push(`/rewrite/${article.id}`)
  }
}

// ── File upload ────────────────────────────────────────────────────────────
const fileUploadRef = ref()

async function handleFileUpload(file: File) {
  try {
    const text = await file.text()
    if (text.length < 50) {
      notifyError('文件内容太短，请至少包含50字')
      return
    }
    textContent.value = text
    activeTab.value = 'text'
    notifySuccess('文件加载成功')
  } catch {
    notifyError('文件读取失败，请检查格式')
  }
}

function beforeUpload(file: File) {
  const validTypes = ['text/plain', 'text/markdown', 'text/html', '.md', '.txt']
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  const isValid = validTypes.includes(file.type) || validTypes.includes(ext)
  if (!isValid) {
    notifyError('仅支持 .txt / .md / .html 文件')
    return false
  }
  handleFileUpload(file)
  return false // prevent auto-upload
}
</script>

<template>
  <div class="home-view">
    <!-- Hero -->
    <section class="hero">
      <h1 class="hero-title">热文采集改写一站式平台</h1>
      <p class="hero-subtitle">
        采集优质内容 → AI 智能改写 → 一键发布多平台，让内容创作效率提升 70%
      </p>
    </section>

    <!-- Input section -->
    <section class="input-section">
      <el-card shadow="hover" class="input-card">
        <el-tabs v-model="activeTab" class="input-tabs">
          <!-- URL tab -->
          <el-tab-pane label="URL 采集" name="url">
            <UrlInput @collect="handleUrlCollect" />
          </el-tab-pane>

          <!-- Text tab -->
          <el-tab-pane label="粘贴文本" name="text">
            <TextInput v-model:content="textContent" />
            <div class="tab-action">
              <el-button
                type="primary"
                size="large"
                :disabled="textContent.trim().length < 50"
                @click="handleTextSubmit"
              >
                开始改写
              </el-button>
            </div>
          </el-tab-pane>

          <!-- File tab -->
          <el-tab-pane label="文件上传" name="file">
            <el-upload
              ref="fileUploadRef"
              drag
              :auto-upload="false"
              :before-upload="beforeUpload"
              :show-file-list="false"
              accept=".txt,.md,.html"
              class="file-upload"
            >
              <el-icon :size="48" color="var(--el-color-primary)"><UploadFilled /></el-icon>
              <div class="upload-text">
                <p>将文件拖到此处，或 <em>点击上传</em></p>
                <p class="upload-hint">支持 .txt / .md / .html 文件</p>
              </div>
            </el-upload>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </section>

    <!-- Features -->
    <section class="features">
      <h2>核心功能</h2>
      <el-row :gutter="24">
        <el-col :span="8" v-for="f in features" :key="f.title">
          <el-card shadow="hover" class="feature-card">
            <div class="feature-icon">{{ f.icon }}</div>
            <h3>{{ f.title }}</h3>
            <p>{{ f.desc }}</p>
          </el-card>
        </el-col>
      </el-row>
    </section>
  </div>
</template>

<script lang="ts">
const features = [
  { icon: '📝', title: '智能采集', desc: '支持 URL 链接、文本粘贴、文件上传三种输入方式' },
  { icon: '🤖', title: 'AI 改写', desc: '多风格选择，长度可控，支持 SEO 优化' },
  { icon: '🚀', title: '一键发布', desc: '同时发布到微信、知乎、头条等多个平台' },
]
</script>

<style scoped>
.home-view {
  max-width: 900px;
  margin: 0 auto;
  padding: 48px 24px;
}

/* Hero */
.hero {
  text-align: center;
  margin-bottom: 48px;
}

.hero-title {
  font-size: 36px;
  font-weight: 800;
  margin: 0 0 16px;
  background: linear-gradient(135deg, var(--el-color-primary) 0%, var(--el-color-primary-light-3) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-subtitle {
  font-size: 16px;
  color: var(--el-text-color-secondary);
  margin: 0;
  line-height: 1.6;
}

/* Input card */
.input-card {
  margin-bottom: 64px;
}

.input-tabs {
  padding: 8px 0;
}

.tab-action {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.file-upload {
  width: 100%;
}

.upload-text p {
  margin: 8px 0;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.upload-hint {
  font-size: 12px !important;
  color: var(--el-text-color-placeholder) !important;
}

/* Features */
.features h2 {
  text-align: center;
  margin-bottom: 32px;
  font-size: 24px;
}

.feature-card {
  text-align: center;
  margin-bottom: 24px;
}

.feature-icon {
  font-size: 40px;
  margin-bottom: 12px;
}

.feature-card h3 {
  margin: 0 0 8px;
  font-size: 16px;
}

.feature-card p {
  margin: 0;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}
</style>
