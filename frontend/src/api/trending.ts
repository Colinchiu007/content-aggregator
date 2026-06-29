import api from './index'
import type { ApiResponse } from '@/types'

export interface TrendingItem {
  id: number
  platform: { code: string; name: string; icon_url: string }
  rank: number
  title: string
  hot_value: string
  hot_value_norm: number
  topic_url: string
  category: string
  snapshot_at: string
}

export interface PlatformInfo {
  code: string
  name: string
  name_en: string
  icon_url: string
  is_active: boolean
}

export interface TrendingResponse {
  items: TrendingItem[]
}

export interface RewriteResult {
  article_id: number
  title: string
  word_count: number
  source_url: string
}

const BASE = '/trending'

export async function fetchPlatforms(): Promise<ApiResponse<{ platforms: PlatformInfo[] }>> {
  const res = await api.get<ApiResponse<{ platforms: PlatformInfo[] }>>(`${BASE}/platforms`)
  return res.data
}

export async function fetchTrending(params: {
  platforms?: string
  category?: string
  page?: number
  page_size?: number
}): Promise<{ data: { items: TrendingItem[] }; pagination: { page: number; page_size: number; total: number; total_pages: number } }> {
  const res = await api.get(BASE, { params })
  return res.data
}

export async function fetchPlatformTrending(
  platform: string,
  page = 1,
  pageSize = 50,
): Promise<{ data: { items: TrendingItem[] }; pagination: { page: number; page_size: number; total: number; total_pages: number } }> {
  const res = await api.get(`${BASE}/${platform}`, { params: { page, page_size: pageSize } })
  return res.data
}

export async function rewriteTrendingTopic(data: {
  topic_id: number
  topic_url: string
  title: string
  platform_code: string
}): Promise<ApiResponse<RewriteResult>> {
  const res = await api.post<ApiResponse<RewriteResult>>(`${BASE}/rewrite`, data)
  return res.data
}
