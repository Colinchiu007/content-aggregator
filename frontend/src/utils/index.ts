import { ElMessage, ElMessageBox } from 'element-plus'
import type { RewriteStyle, RewriteLength, Platform } from '@/types'

// ── Formatting ──────────────────────────────────────────────────────────────

/** Format a date string to zh-CN locale */
export function formatDate(dateStr: string, options?: Intl.DateTimeFormatOptions): string {
  return new Date(dateStr).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    ...options,
  })
}

/** Format relative time (e.g. "3分钟前") */
export function formatRelativeTime(dateStr: string): string {
  const now = Date.now()
  const diff = now - new Date(dateStr).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return '刚刚'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}天前`
  return formatDate(dateStr)
}

/** Truncate text to given length */
export function truncateText(text: string, max: number): string {
  if (text.length <= max) return text
  return text.slice(0, max) + '...'
}

// ── Labels ──────────────────────────────────────────────────────────────────

/** Human-readable label for rewrite styles */
export function styleLabel(style: RewriteStyle): string {
  const map: Record<RewriteStyle, string> = {
    casual: '轻松随意',
    formal: '正式严谨',
    'eye-catching': '抓人眼球',
    'deep-analysis': '深度解析',
  }
  return map[style]
}

/** Human-readable label for rewrite lengths */
export function lengthLabel(length: RewriteLength): string {
  const map: Record<RewriteLength, string> = {
    original: '保持原长 (±10%)',
    shorter: '精简 (-30%)',
    longer: '扩写 (+30%)',
  }
  return map[length]
}

/** Human-readable label for source types */
export function sourceTypeLabel(type: string): string {
  const map: Record<string, string> = {
    url: 'URL 采集',
    text: '文本输入',
    file: '文件上传',
  }
  return map[type] ?? type
}

// ── Confirmations ───────────────────────────────────────────────────────────

/** Confirm before destructive action */
export async function confirmAction(msg: string): Promise<boolean> {
  try {
    await ElMessageBox.confirm(msg, '确认操作', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning',
    })
    return true
  } catch {
    return false
  }
}

// ── Notifications ───────────────────────────────────────────────────────────

export function notifySuccess(msg: string): void {
  ElMessage.success(msg)
}

export function notifyError(msg: string): void {
  ElMessage.error(msg)
}

export function notifyWarning(msg: string): void {
  ElMessage.warning(msg)
}

export function notifyInfo(msg: string): void {
  ElMessage.info(msg)
}

// ── Platforms ───────────────────────────────────────────────────────────────

/** Default platform list used in publish views */
export const DEFAULT_PLATFORMS: Platform[] = [
  { key: 'wechat', name: '微信公众号', icon: 'ChatDotRound', enabled: true },
  { key: 'zhihu', name: '知乎', icon: 'Reading', enabled: true },
  { key: 'toutiao', name: '今日头条', icon: 'Notebook', enabled: true },
  { key: 'jianshu', name: '简书', icon: 'Edit', enabled: false },
  { key: 'csdn', name: 'CSDN', icon: 'Document', enabled: false },
  { key: 'juejin', name: '掘金', icon: 'Coin', enabled: false },
]

/** Check if a token is expired (JWT expiry) */
export function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.exp * 1000 < Date.now()
  } catch {
    return true
  }
}

/** Copy text to clipboard */
export async function copyToClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    notifySuccess('已复制到剪贴板')
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = text
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    notifySuccess('已复制到剪贴板')
  }
}

/** Estimate reading time in minutes (zh-CN ~400 chars/min) */
export function readingTime(text: string): number {
  return Math.max(1, Math.ceil(text.length / 400))
}
