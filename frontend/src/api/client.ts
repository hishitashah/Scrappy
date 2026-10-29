/** The single place every HTTP call goes through (CLAUDE.md conventions). */

import { accessToken, signOut } from '../auth/session'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Call the Scrappy API, carrying the signed-in user's access token.
 *
 * Every request is authorized here rather than in each hook, so no call can forget.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await accessToken()

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    // The token is missing, expired beyond refresh, or revoked. Staying "signed in" with
    // credentials the API rejects only produces a broken-looking app, so end the session.
    if (response.status === 401) {
      await signOut()
    }
    throw new ApiError(response.status, `${init?.method ?? 'GET'} ${path} failed`)
  }
  // 204 No Content, e.g. removing a pantry item.
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}
