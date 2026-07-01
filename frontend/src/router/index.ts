import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: '首页' },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录', guest: true },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { title: '注册', guest: true },
  },
  {
    path: '/rewrite/:id?',
    name: 'rewrite',
    component: () => import('@/views/RewriteView.vue'),
    meta: { title: 'AI 改写', requireAuth: true },
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('@/views/HistoryView.vue'),
    meta: { title: '改写历史', requireAuth: true },
  },
  {
    path: '/publish/:articleId',
    name: 'publish',
    component: () => import('@/views/PublishView.vue'),
    meta: { title: '一键发布', requireAuth: true },
  },
  {
    path: '/trending',
    name: 'trending',
    component: () => import('@/views/TrendingView.vue'),
    meta: { title: '热榜发现', requireAuth: true },
  },
  {
    path: '/monitor',
    name: 'monitor',
    component: () => import('@/views/MonitorView.vue'),
    meta: { title: '竞品监控', requireAuth: true },
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: '设置', requireAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ── Navigation guard ────────────────────────────────────────────────────────
router.beforeEach((to, _from, next) => {
  // Set page title
  document.title = `${to.meta.title ?? '信息实验室'} - 信息实验室`

  const token = localStorage.getItem('access_token')
  const requireAuth = to.meta.requireAuth as boolean | undefined
  const isGuest = to.meta.guest as boolean | undefined

  if (requireAuth && !token) {
    next({ name: 'login', query: { redirect: to.fullPath } })
  } else if (isGuest && token) {
    next({ name: 'home' })
  } else {
    next()
  }
})

export default router
