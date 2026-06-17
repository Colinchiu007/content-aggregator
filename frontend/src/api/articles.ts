import api from './index'
import type { ApiResponse, Article } from '@/types'

const ARTICLES = '/articles'

export async function listArticles(params?: {
  page?: number
  page_size?: number
  search?: string
}): Promise<ApiResponse<{ items: Article[]; total: number; page: number; page_size: number }>> {
  const res = await api.get(ARTICLES, { params })
  return res.data
}

export async function getArticle(id: number): Promise<ApiResponse<Article>> {
  const res = await api.get(`${ARTICLES}/${id}`)
  return res.data
}

export async function createArticle(data: {
  source_type: string
  source_content: string
  source_url?: string
}): Promise<ApiResponse<Article>> {
  const res = await api.post(ARTICLES, data)
  return res.data
}

export async function updateArticle(
  id: number,
  data: Partial<Pick<Article, 'result_content' | 'rewrite_style' | 'rewrite_length'>>,
): Promise<ApiResponse<Article>> {
  const res = await api.put(`${ARTICLES}/${id}`, data)
  return res.data
}

export async function deleteArticle(id: number): Promise<ApiResponse<null>> {
  const res = await api.delete(`${ARTICLES}/${id}`)
  return res.data
}
