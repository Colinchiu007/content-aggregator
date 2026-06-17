<script setup lang="ts">
import { computed } from 'vue'
import type { RewriteLength } from '@/types'
import { lengthLabel } from '@/utils'

const model = defineModel<RewriteLength>('length', { default: 'original' })

const options = computed(() => {
  const lengths: RewriteLength[] = ['original', 'shorter', 'longer']
  return lengths.map((l) => ({
    value: l,
    label: lengthLabel(l),
  }))
})
</script>

<template>
  <div class="length-selector">
    <label class="selector-label">文章长度</label>
    <el-radio-group v-model="model" size="large">
      <el-radio-button
        v-for="opt in options"
        :key="opt.value"
        :value="opt.value"
      >
        {{ opt.label }}
      </el-radio-button>
    </el-radio-group>
  </div>
</template>

<style scoped>
.length-selector {
  margin-bottom: 16px;
}

.selector-label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}
</style>
