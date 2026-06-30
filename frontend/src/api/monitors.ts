import api from './index'

export interface MonitorSource {
  id: string
  user_id: string
  name: string
  source_type: string
  identifier: string
  schedule_cron: string | null
  is_active: boolean
  last_collected_at: string | null
  created_at: string
  updated_at: string
}

export interface MonitorSourceListItem {
  id: string
  name: string
  source_type: string
  identifier: string
  is_active: boolean
  last_collected_at: string | null
  created_at: string
}

export interface MonitorArticleListItem {
  id: string
  source_id: string
  title: string
  url: string
  summary: string | null
  cover_url: string | null
  author: string | null
  published_at: string | null
  is_read: boolean
  collected_at: string
  created_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

const MONITORS_BASE = '/monitors'
const ARTICLES_BASE = '/monitor-articles'

// ── MonitorSource CRUD ────────────────────────────────────────────────────

export async function fetchMonitors(params: {
  page?: number
  page_size?: number
  search?: string
  source_type?: string
}): Promise<PaginatedResponse<MonitorSourceListItem>> {
  const res = await api.get(MONITORS_BASE, { params })
  return res.data
}

export async function createMonitor(data: {
  name: string
  source_type: string
  identifier: string
  schedule_cron?: string
  is_active?: boolean
}): Promise<MonitorSource> {
  const res = await api.post(MONITORS_BASE, data)
  return res.data
}

export async function getMonitor(id: string): Promise<MonitorSource> {
  const res = await api.get(`${MONITORS_BASE}/${id}`)
  return res.data
}

export async function updateMonitor(id: string, data: {
  name?: string
  identifier?: string
  schedule_cron?: string
  is_active?: boolean
}): Promise<MonitorSource> {
  const res = await api.put(`${MONITORS_BASE}/${id}`, data)
  return res.data
}

export async function deleteMonitor(id: string): Promise<void> {
  await api.delete(`${MONITORS_BASE}/${id}`)
}

// ── MonitorArticle ────────────────────────────────────────────────────────

export async function fetchMonitorArticles(params: {
  page?: number
  page_size?: number
  source_id?: string
  is_read?: boolean
}): Promise<PaginatedResponse<MonitorArticleListItem>> {
  const res = await api.get(ARTICLES_BASE, { params })
  return res.data
}

export async function markArticleRead(id: string): Promise<void> {
  await api.post(`${ARTICLES_BASE}/${id}/read`)
}

export async function rewriteMonitorArticle(id: string, data: {
  style?: string
  length?: string
}): Promise<{ article_id: string; title: string; word_count: number }> {
  const res = await api.post(`${ARTICLES_BASE}/${id}/rewrite`, data)
  return res.data
}
