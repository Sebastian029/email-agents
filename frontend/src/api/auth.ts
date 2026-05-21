import { apiRequest } from './client'
import type { TokenPair, User } from '../types'

export function login(username: string, password: string) {
  return apiRequest<TokenPair>('/auth/token/', {
    method: 'POST',
    skipAuth: true,
    body: JSON.stringify({ username, password }),
  })
}

export function register(
  username: string,
  email: string,
  password: string,
) {
  return apiRequest<User>('/auth/register/', {
    method: 'POST',
    skipAuth: true,
    body: JSON.stringify({ username, email, password }),
  })
}

export function fetchMe() {
  return apiRequest<User>('/auth/me/')
}
