import api from './index'
import type { ApiResponse, PublishRequest, PublishStatus } from '@/types'

const PUBLISHER = '/publisher'

export async function publishArticle(data: PublishRequest): Promise<ApiResponse<PublishStatus>> {
  const res = await api.post<ApiResponse<PublishStatus>>(`${PUBLISHER}/publish`, data)
  return res.data
}

export async function getPublishStatus(taskId: string): Promise<ApiResponse<PublishStatus>> {
  const res = await api.get(`${PUBLISHER}/status/${taskId}`)
  return res.data
}

export async function listPlatforms(): Promise<ApiResponse<{ key: string; name: string; enabled: boolean }[]>> {
  const res = await api.get(`${PUBLISHER}/platforms`)
  return res.data
}
