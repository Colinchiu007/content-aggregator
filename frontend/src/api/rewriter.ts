import api from './index'
import type { ApiResponse, RewriteRequest, RewriteResult } from '@/types'

const REWRITER = '/rewrite'

export async function rewriteArticle(data: RewriteRequest): Promise<ApiResponse<RewriteResult>> {
  const res = await api.post<ApiResponse<RewriteResult>>(`${REWRITER}/rewrite`, data)
  return res.data
}

export async function getRewriteStatus(articleId: number): Promise<ApiResponse<{ status: string; result?: RewriteResult }>> {
  const res = await api.get(`${REWRITER}/status/${articleId}`)
  return res.data
}
