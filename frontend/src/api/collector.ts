import api from './index'
import type { ApiResponse, CollectRequest, CollectResult } from '@/types'

const COLLECTOR = '/collect'

export async function collectUrl(data: CollectRequest): Promise<ApiResponse<CollectResult>> {
  const res = await api.post<ApiResponse<CollectResult>>(`${COLLECTOR}/url`, data)
  return res.data
}

export async function collectText(content: string): Promise<ApiResponse<{ word_count: number }>> {
  const res = await api.post(`${COLLECTOR}/text`, { content })
  return res.data
}
