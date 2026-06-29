<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import {
  HomeFilled, EditPen, Clock, Setting, Fold, Expand, Moon, Sunny, Fire,
} from '@element-plus/icons-vue'

const props = defineProps<{ collapsed: boolean }>()
const emit = defineEmits<{ 'update:collapsed': [v: boolean] }>()

const router = useRouter()
const userStore = useUserStore()

const activeRoute = computed(() => router.currentRoute.value.path)

const menuItems = [
  { path: '/', icon: HomeFilled, label: '首页' },
  { path: '/rewrite', icon: EditPen, label: 'AI 改写' },
  { path: '/trending', icon: Fire, label: '热榜发现' },
  { path: '/history', icon: Clock, label: '历史记录' },
  { path: '/settings', icon: Setting, label: '设置' },
]

function toggleCollapse() {
  emit('update:collapsed', !props.collapsed)
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <!-- Logo -->
    <div class="sidebar-header">
      <router-link to="/" class="logo-link">
        <div class="logo-icon">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="8" fill="#4F46E5"/>
            <path d="M8 10h12M8 14h10M8 18h8" stroke="white" stroke-width="2" stroke-linecap="round"/>
            <circle cx="21" cy="18" r="3" fill="#818CF8"/>
          </svg>
        </div>
        <span v-show="!collapsed" class="logo-text">信息实验室</span>
      </router-link>
    </div>

    <!-- Nav -->
    <el-menu
      :default-active="activeRoute"
      :collapse="collapsed"
      router
      class="sidebar-menu"
      background-color="transparent"
      text-color="#94A3B8"
      active-text-color="#F8FAFC"
    >
      <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </el-menu-item>
    </el-menu>

    <!-- Bottom -->
    <div class="sidebar-footer">
      <el-tooltip :content="collapsed ? '展开侧栏' : '收起侧栏'" placement="right">
        <el-button text class="footer-btn" @click="toggleCollapse">
          <el-icon><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
          <span v-show="!collapsed">收起侧栏</span>
        </el-button>
      </el-tooltip>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  width: var(--il-sidebar-width);
  height: 100vh;
  background: var(--il-sidebar-bg);
  display: flex;
  flex-direction: column;
  z-index: 100;
  transition: width var(--il-transition-slow);
  overflow: hidden;
}

.sidebar.collapsed {
  width: var(--il-sidebar-collapsed);
}

/* Header */
.sidebar-header {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid var(--il-sidebar-border);
  flex-shrink: 0;
}

.logo-link {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
}

.logo-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: #F8FAFC;
  white-space: nowrap;
}

/* Menu */
.sidebar-menu {
  flex: 1;
  border-right: none;
  padding: 8px;
}

.sidebar-menu .el-menu-item {
  border-radius: 6px;
  margin: 2px 0;
  height: 40px;
  line-height: 40px;
}

.sidebar-menu .el-menu-item:hover {
  background: var(--il-sidebar-hover) !important;
}

.sidebar-menu .el-menu-item.is-active {
  background: var(--il-sidebar-active-bg) !important;
}

.sidebar.collapsed .sidebar-menu .el-menu-item {
  padding: 0 12px !important;
  justify-content: center;
}

/* Footer */
.sidebar-footer {
  padding: 8px;
  border-top: 1px solid var(--il-sidebar-border);
  flex-shrink: 0;
}

.footer-btn {
  width: 100%;
  height: 36px;
  color: var(--il-sidebar-text);
  justify-content: flex-start;
  gap: 8px;
  padding: 0 10px;
  border-radius: 6px;
}

.footer-btn:hover {
  color: var(--il-sidebar-active);
  background: var(--il-sidebar-hover);
}

.sidebar.collapsed .footer-btn {
  justify-content: center;
  padding: 0;
}
</style>
