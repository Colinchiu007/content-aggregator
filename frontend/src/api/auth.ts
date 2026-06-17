import api from './index'
import type { ApiResponse, LoginRequest, RegisterRequest, AuthResponse } from '@/types'

const AUTH = '/auth'

export async function login(data: LoginRequest): Promise<ApiResponse<AuthResponse>> {
  const form = new FormData()
  form.append('username', data.username)
  form.append('password', data.password)
  const res = await api.post<ApiResponse<AuthResponse>>(`${AUTH}/login`, form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return res.data
}

export async function register(data: RegisterRequest): Promise<ApiResponse<AuthResponse>> {
  const res = await api.post<ApiResponse<AuthResponse>>(`${AUTH}/register`, data)
  return res.data
}

export async function getMe(): Promise<ApiResponse<typeof import('@/types').User>> {
  const res = await api.get(`${AUTH}/me`)
  return res.data
}
