<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

function handleLogout() {
  userStore.logout()
  router.push('/')
}
</script>

<template>
  <el-header class="app-header">
    <div class="header-left">
      <router-link to="/" class="logo">
        <span class="logo-icon">🔥</span>
        <span class="logo-text">HotRewrite</span>
      </router-link>
    </div>

    <el-menu
      mode="horizontal"
      :default-active="router.currentRoute.value.path"
      :ellipsis="false"
      router
      class="header-menu"
    >
      <el-menu-item index="/">首页</el-menu-item>
      <el-menu-item index="/rewrite">AI 改写</el-menu-item>
      <el-menu-item index="/history">改写历史</el-menu-item>
    </el-menu>

    <div class="header-right">
      <template v-if="userStore.isLoggedIn">
        <el-dropdown trigger="click">
          <span class="user-info">
            <el-avatar :size="32" icon="UserFilled" />
            <span class="username">{{ userStore.username }}</span>
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push('/settings')">
                <el-icon><Setting /></el-icon>设置
              </el-dropdown-item>
              <el-dropdown-item @click="handleLogout" divided>
                <el-icon><SwitchButton /></el-icon>退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
      <template v-else>
        <el-button text @click="router.push('/login')">登录</el-button>
        <el-button type="primary" size="small" @click="router.push('/register')">注册</el-button>
      </template>
    </div>
  </el-header>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid var(--el-border-color-light);
  padding: 0 24px;
  height: 60px;
  position: sticky;
  top: 0;
  z-index: 1000;
}

.header-left .logo {
  display: flex;
  align-items: center;
  text-decoration: none;
  color: inherit;
}

.logo-icon {
  font-size: 24px;
  margin-right: 8px;
}

.logo-text {
  font-size: 20px;
  font-weight: 700;
  color: var(--el-color-primary);
}

.header-menu {
  flex: 1;
  margin: 0 32px;
  border-bottom: none !important;
}

.header-menu .el-menu-item {
  border-bottom: none;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.username {
  font-size: 14px;
  color: var(--el-text-color-primary);
}
</style>
