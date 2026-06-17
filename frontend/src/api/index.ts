import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ── Request interceptor: attach JWT token ──────────────────────────────────
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// ── Response interceptor: handle 401 / generic errors ──────────────────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const { status, data } = error.response
      if (status === 401) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
        if (window.location.pathname !== '/login') {
          ElMessage.error('登录已过期，请重新登录')
          window.location.href = '/login'
        }
      } else if (status === 403) {
        ElMessage.error('没有权限执行该操作')
      } else if (status >= 500) {
        ElMessage.error(data?.message || '服务器错误，请稍后重试')
      } else {
        // 400 / 404 / 422 etc.
        ElMessage.error(data?.message || data?.detail || '请求失败')
      }
    } else if (error.code === 'ECONNABORTED') {
      ElMessage.error('请求超时，请检查网络连接')
    } else {
      ElMessage.error('网络连接失败')
    }
    return Promise.reject(error)
  },
)

export default api
