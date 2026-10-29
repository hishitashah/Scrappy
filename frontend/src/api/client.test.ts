import { HttpResponse, http } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { server } from '../test/server'
import { ApiError, apiFetch } from './client'

const API = 'http://localhost:8000'

// The seams under test are ours: that a token is attached, and that a 401 ends the session.
// Amplify's own behaviour is its problem, so it is mocked.
const { mockAccessToken, mockSignOut } = vi.hoisted(() => ({
  mockAccessToken: vi.fn<() => Promise<string | null>>(),
  mockSignOut: vi.fn<() => Promise<void>>(),
}))

vi.mock('../auth/session', () => ({
  accessToken: mockAccessToken,
  signOut: mockSignOut,
}))

describe('apiFetch', () => {
  beforeEach(() => {
    mockAccessToken.mockResolvedValue('test-access-token')
    mockSignOut.mockResolvedValue()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('sends the access token on every request', async () => {
    let seen: string | null = null
    server.use(
      http.get(`${API}/pantry`, ({ request }) => {
        seen = request.headers.get('authorization')
        return HttpResponse.json([])
      }),
    )

    await apiFetch('/pantry')

    expect(seen).toBe('Bearer test-access-token')
  })

  it('omits the header when nobody is signed in', async () => {
    mockAccessToken.mockResolvedValue(null)
    let seen: string | null = 'unset'
    server.use(
      http.get(`${API}/pantry`, ({ request }) => {
        seen = request.headers.get('authorization')
        return HttpResponse.json([])
      }),
    )

    await apiFetch('/pantry')

    expect(seen).toBeNull()
  })

  it('signs out when the API rejects the token', async () => {
    server.use(http.get(`${API}/pantry`, () => new HttpResponse(null, { status: 401 })))

    await expect(apiFetch('/pantry')).rejects.toBeInstanceOf(ApiError)

    expect(mockSignOut).toHaveBeenCalledOnce()
  })

  it('does not sign out for other failures', async () => {
    server.use(http.get(`${API}/pantry`, () => new HttpResponse(null, { status: 500 })))

    await expect(apiFetch('/pantry')).rejects.toBeInstanceOf(ApiError)

    expect(mockSignOut).not.toHaveBeenCalled()
  })

  it('returns nothing for a 204, rather than trying to parse a body', async () => {
    server.use(http.delete(`${API}/pantry/items/1`, () => new HttpResponse(null, { status: 204 })))

    await expect(apiFetch('/pantry/items/1', { method: 'DELETE' })).resolves.toBeUndefined()
  })
})
