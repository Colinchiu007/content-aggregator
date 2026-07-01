<script setup lang="ts">
import { ref } from 'vue'

const content = defineModel<string>('content', { default: '' })

const props = withDefaults(defineProps<{
  placeholder?: string
  maxlength?: number
  minRows?: number
}>(), {
  placeholder: '在此粘贴需要改写的内容...',
  maxlength: 50000,
  minRows: 8,
})

const wordCount = ref(0)

function onInput(value: string) {
  wordCount.value = value.length
}
</script>

<template>
  <div class="text-input">
    <el-input
      v-model="content"
      type="textarea"
      :placeholder="placeholder"
      :maxlength="maxlength"
      :rows="minRows"
      show-word-limit
      resize="vertical"
      @input="onInput"
    />
    <div class="text-stats" v-if="wordCount > 0">
      <span>约 {{ wordCount }} 字</span>
      <span class="separator">|</span>
      <span>预计阅读 {{ Math.max(1, Math.ceil(wordCount / 400)) }} 分钟</span>
    </div>
  </div>
</template>

<style scoped>
.text-input {
  width: 100%;
}

.text-stats {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  display: flex;
  gap: 8px;
}

.separator {
  color: var(--el-border-color);
}
</style>
