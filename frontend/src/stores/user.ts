import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import * as authApi from '@/api/auth'
import type { User, LoginRequest, RegisterRequest } from '@/types'
import { notifySuccess, notifyError } from '@/utils'

export const useUserStore = defineStore('user', () => {
  // ── State ──────────────────────────────────────────────────────────────
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const loading = ref(false)

  // ── Getters ────────────────────────────────────────────────────────────
  const isLoggedIn = computed(() => !!token.value)
  const username = computed(() => user.value?.username ?? '')
  const subscriptionType = computed(() => user.value?.subscription_type ?? 'free')

  // ── Actions ────────────────────────────────────────────────────────────
  function setAuth(accessToken: string, userData: User) {
    token.value = accessToken
    user.value = userData
    localStorage.setItem('access_token', accessToken)
    localStorage.setItem('user', JSON.stringify(userData))
  }

  function clearAuth() {
    token.value = null
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
  }

  function loadFromLocalStorage() {
    const savedToken = localStorage.getItem('access_token')
    const savedUser = localStorage.getItem('user')
    if (savedToken && savedUser) {
      token.value = savedToken
      try {
        user.value = JSON.parse(savedUser)
      } catch {
        clearAuth()
      }
    }
  }

  async function login(data: LoginRequest): Promise<boolean> {
    loading.value = true
    try {
      const res = await authApi.login(data)
      setAuth(res.data.access_token, res.data.user)
      notifySuccess('登录成功')
      return true
    } catch {
      // Error toast already shown by interceptor
      return false
    } finally {
      loading.value = false
    }
  }

  async function register(data: RegisterRequest): Promise<boolean> {
    loading.value = true
    try {
      const res = await authApi.register(data)
      setAuth(res.data.access_token, res.data.user)
      notifySuccess('注册成功')
      return true
    } catch {
      return false
    } finally {
      loading.value = false
    }
  }

  function logout() {
    clearAuth()
    notifySuccess('已退出登录')
  }

  // ── Init on store creation ─────────────────────────────────────────────
  loadFromLocalStorage()

  return {
    user,
    token,
    loading,
    isLoggedIn,
    username,
    subscriptionType,
    login,
    register,
    logout,
    clearAuth,
  }
})
