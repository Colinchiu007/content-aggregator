<script setup lang="ts">
import { computed } from 'vue'
import type { RewriteStyle } from '@/types'
import { styleLabel } from '@/utils'

const model = defineModel<RewriteStyle>('style', { default: 'casual' })

const options = computed(() => {
  const styles: RewriteStyle[] = ['casual', 'formal', 'deep-analysis', 'eye-catching']
  return styles.map((s) => ({
    value: s,
    label: styleLabel(s),
  }))
})
</script>

<template>
  <div class="style-selector">
    <label class="selector-label">改写风格</label>
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
.style-selector {
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
