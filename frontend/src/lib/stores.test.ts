import { describe, expect, it } from 'vitest'

import { STORES, searchUrl, storeName } from './stores'

describe('searchUrl', () => {
  it('encodes a name with a space', () => {
    // Raw interpolation would cut the query at the space and search for "Olive".
    expect(searchUrl('walmart', 'Olive Oil')).toBe(
      'https://www.walmart.com/search?q=Olive%20Oil',
    )
  })

  it('encodes the characters that would otherwise change the query', () => {
    expect(searchUrl('target', 'Salt & Pepper')).toBe(
      'https://www.target.com/s?searchTerm=Salt%20%26%20Pepper',
    )
  })

  it('builds a URL for every chain in the catalog', () => {
    for (const store of STORES) {
      const url = searchUrl(store.key, 'Olive Oil')
      expect(url).toContain('Olive%20Oil')
      // The placeholder is substituted, not left in the URL we send someone to.
      expect(url).not.toContain('{query}')
      expect(url.startsWith('https://')).toBe(true)
    }
  })
})

describe('storeName', () => {
  it('gives each chain its display name', () => {
    expect(storeName('whole-foods')).toBe('Whole Foods')
    expect(storeName('heb')).toBe('H-E-B')
  })
})
