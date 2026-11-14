const configured = import.meta.env.VITE_API_URL as string | undefined
const apiOrigin = configured || (import.meta.env.DEV ? 'http://localhost:8000' : '')
export const API_BASE = apiOrigin.replace(/\/$/, '')
export function websocketUrl(path: string): string {
  if (apiOrigin) return apiOrigin.replace(/^http/, 'ws').replace(/\/$/, '') + path
  return `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}${path}`
}
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const session = supabase ? await supabase.auth.getSession() : null
  const token = session?.data.session?.access_token || localStorage.getItem('awaaz-access-token')
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init?.headers } })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try { message = (await response.json()).detail || message } catch { /* leave generic */ }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}
import { supabase } from './supabase'
