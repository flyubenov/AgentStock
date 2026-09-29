import { readFileSync, existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect } from 'vitest'

/** Spec §5.8 (2026-09-29): a static share image and the tags that point at it. */
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const html = readFileSync(resolve(root, 'index.html'), 'utf8')
const meta = (attr: 'property' | 'name', key: string) =>
  html.match(new RegExp(`<meta ${attr}="${key}" content="([^"]*)"`))?.[1]

describe('page metadata and share image', () => {
  it('carries the og and twitter tags', () => {
    expect(meta('property', 'og:title')).toBe('Intrinsica — Judge the business. Then judge the price.')
    expect(meta('property', 'og:description')).toBe(
      'Intrinsica answers with four scores from the fundamentals: Quality, Moat, Fair Value and Reward/Risk. Every input and weight is on show.')
    expect(meta('property', 'og:image')).toBe('/og-image.png')
    expect(meta('property', 'og:type')).toBe('website')
    expect(meta('name', 'twitter:card')).toBe('summary_large_image')
    expect(meta('name', 'description')).toBe(meta('property', 'og:description'))
  })

  it('ships a 1200 × 630 PNG', () => {
    const file = resolve(root, 'public/og-image.png')
    expect(existsSync(file)).toBe(true)
    const png = readFileSync(file)
    expect(png.subarray(1, 4).toString()).toBe('PNG')
    expect(png.readUInt32BE(16)).toBe(1200)
    expect(png.readUInt32BE(20)).toBe(630)
  })
})
