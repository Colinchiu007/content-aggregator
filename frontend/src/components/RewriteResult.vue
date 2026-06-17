<script setup lang="ts">
import { ref, computed } from 'vue'
import { Edit } from '@element-plus/icons-vue'
import { copyToClipboard } from '@/utils'

const props = defineProps<{
  original: string
  rewritten: string
  wordCountOriginal?: number
  wordCountRewritten?: number
}>()

const emit = defineEmits<{
  save: [content: string]
  retry: []
}>()

const editingRewritten = ref(false)
const editedContent = ref(props.rewritten)

const originalLines = computed(() => props.original.split('\n'))
const rewrittenLines = computed(() =>
  (editingRewritten.value || props.rewritten).split('\n'),
)

function toggleEdit() {
  if (editingRewritten.value) {
    emit('save', editedContent.value)
  }
  editingRewritten.value = !editingRewritten.value
}

function handleRetry() {
  editedContent.value = props.rewritten
  emit('retry')
}
</script>

<template>
  <div class="rewrite-result">
    <!-- Result header -->
    <div class="result-header">
      <h3>改写结果</h3>
      <div class="result-actions">
        <el-button text @click="copyToClipboard(editingRewritten ? editedContent : rewritten)">
          复制结果
        </el-button>
        <el-button text :icon="Edit" @click="toggleEdit">
          {{ editingRewritten ? '保存编辑' : '手动编辑' }}
        </el-button>
        <el-button text type="warning" @click="handleRetry">重新改写</el-button>
      </div>
    </div>

    <!-- Side-by-side comparison -->
    <div class="comparison">
      <div class="column original-column">
        <div class="column-header">
          <span>原文</span>
          <span class="word-count">{{ wordCountOriginal ?? original.length }} 字</span>
        </div>
        <div class="column-content" v-if="!editingRewritten">
          <p v-for="(line, i) in originalLines" :key="'o-' + i">{{ line || '\u00A0' }}</p>
        </div>
        <div class="column-content" v-else>
          <p v-for="(line, i) in originalLines" :key="'o-' + i">{{ line || '\u00A0' }}</p>
        </div>
      </div>

      <div class="column rewritten-column">
        <div class="column-header">
          <span>改写后</span>
          <span class="word-count">{{ wordCountRewritten ?? (editingRewritten ? editedContent.length : rewritten.length) }} 字</span>
        </div>
        <div class="column-content" v-if="!editingRewritten">
          <p v-for="(line, i) in rewrittenLines" :key="'r-' + i">{{ line || '\u00A0' }}</p>
        </div>
        <div class="column-content" v-else>
          <el-input
            v-model="editedContent"
            type="textarea"
            :rows="Math.max(12, rewrittenLines.length + 2)"
            resize="vertical"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rewrite-result {
  margin-top: 24px;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.result-header h3 {
  margin: 0;
  font-size: 18px;
}

.result-actions {
  display: flex;
  gap: 4px;
}

.comparison {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.column {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  overflow: hidden;
}

.column-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  font-size: 14px;
  font-weight: 500;
}

.word-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.column-content {
  padding: 16px;
  max-height: 600px;
  overflow-y: auto;
}

.column-content p {
  margin: 0 0 4px;
  line-height: 1.8;
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.original-column .column-content {
  background: var(--el-fill-color-lighter);
}

.rewritten-column .column-content {
  background: #f0f9eb;
}
</style>
