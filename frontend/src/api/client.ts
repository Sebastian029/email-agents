const API_BASE = import.meta.env.VITE_API_URL ?? '/api'

export class ApiError extends Error {
  status: number
  data: unknown

  constructor(message: string, status: number, data: unknown = null) {
    super(message)
    this.status = status
    this.data = data
  }
}

type RequestOptions = RequestInit & { skipAuth?: boolean }

async function refreshAccessToken(): Promise<string | null> {
  const refresh = localStorage.getItem('refresh_token')
  if (!refresh) return null

  const res = await fetch(`${API_BASE}/auth/token/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  })

  if (!res.ok) {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    return null
  }

  const data = (await res.json()) as { access: string; refresh?: string }
  localStorage.setItem('access_token', data.access)
  if (data.refresh) {
    localStorage.setItem('refresh_token', data.refresh)
  }
  return data.access
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { skipAuth, headers, ...rest } = options
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`

  const buildHeaders = (token: string | null): HeadersInit => ({
    'Content-Type': 'application/json',
    ...(token && !skipAuth ? { Authorization: `Bearer ${token}` } : {}),
    ...headers,
  })

  let token = skipAuth ? null : localStorage.getItem('access_token')

  let response = await fetch(url, {
    ...rest,
    headers: buildHeaders(token),
  })

  if (response.status === 401 && !skipAuth) {
    token = await refreshAccessToken()
    if (token) {
      response = await fetch(url, {
        ...rest,
        headers: buildHeaders(token),
      })
    }
  }

  const text = await response.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }

  if (!response.ok) {
    const message =
      (data && typeof data === 'object' && 'detail' in data
        ? String((data as { detail: unknown }).detail)
        : null) ??
      (data && typeof data === 'object'
        ? JSON.stringify(data)
        : response.statusText)
    throw new ApiError(message, response.status, data)
  }

  return data as T
}
