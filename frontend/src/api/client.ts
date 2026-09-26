/** The single place every HTTP call goes through (CLAUDE.md conventions). */

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
 * Call the Scrappy API.
 *
 * The Cognito access token is attached here in M5; until then the backend runs in
 * shared mode and every caller is the same user.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    throw new ApiError(response.status, `${init?.method ?? 'GET'} ${path} failed`)
  }
  // 204 No Content, e.g. removing a pantry item.
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}
