// ============================================================================
// Project 001 HotRewrite v2 — TypeScript Interfaces
// ============================================================================

// ── User ────────────────────────────────────────────────────────────────────
export interface User {
  id: number
  username: string
  email: string
  subscription_type: 'free' | 'basic' | 'pro' | 'enterprise'
  created_at: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

// ── Article ─────────────────────────────────────────────────────────────────
export interface Article {
  id: number
  user_id: number
  source_type: 'url' | 'text' | 'file'
  source_content: string
  source_url?: string
  rewrite_style?: string
  rewrite_length?: string
  result_content?: string
  word_count_original: number
  word_count_result?: number
  created_at: string
}

// ── Collector ───────────────────────────────────────────────────────────────
export interface CollectResult {
  title: string
  content: string
  author?: string
  word_count: number
  source_url: string
}

export interface CollectRequest {
  url: string
}

// ── Rewriter ────────────────────────────────────────────────────────────────
export type RewriteStyle = 'casual' | 'formal' | 'eye-catching' | 'deep-analysis'

export type RewriteLength = 'original' | 'shorter' | 'longer'

export interface RewriteRequest {
  article_id: number
  style: RewriteStyle
  length: RewriteLength
  seo_optimize?: boolean
}

export interface RewriteResult {
  result_content: string
  word_count: number
}

// ── Publisher ───────────────────────────────────────────────────────────────
export interface PublishRequest {
  article_id: number
  platforms: string[]
}

export interface PublishStatus {
  task_id: string
  status: 'pending' | 'running' | 'success' | 'failed'
  results: Record<string, { status: string; error?: string }>
}

// ── API ─────────────────────────────────────────────────────────────────────
export interface ApiResponse<T = unknown> {
  data: T
  message?: string
  code?: number
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  total: number
  page: number
  page_size: number
}

export interface ApiError {
  message: string
  code?: number
  detail?: string
}

// ── Platform ────────────────────────────────────────────────────────────────
export interface Platform {
  key: string
  name: string
  icon: string
  enabled: boolean
}
