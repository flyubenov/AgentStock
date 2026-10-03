import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect } from 'vitest'

/** Ticker links spec D11: fonts are self-hosted, so no visitor's IP goes to Google.
 *  The privacy notice stopped mentioning Google Fonts on the same day; this keeps
 *  the two true together. */
const src = dirname(fileURLToPath(import.meta.url))
function files(dir: string): string[] {
  return readdirSync(dir).flatMap(n => {
    const p = join(dir, n)
    return statSync(p).isDirectory() ? files(p) : /\.(css|ts|tsx)$/.test(n) && !n.endsWith('.test.ts') ? [p] : []
  })
}

describe('fonts', () => {
  it('are never loaded from Google', () => {
    const offenders = [...files(src), resolve(src, '../index.html')]
      .filter(f => /fonts\.(googleapis|gstatic)\.com/.test(readFileSync(f, 'utf8')))
    expect(offenders).toEqual([])
  })
})
