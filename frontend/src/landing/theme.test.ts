import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect } from 'vitest'

/** Spec §4 (2026-09-29): the palette is pinned value for value, because every
 *  component reads colour only through these tokens. */
const here = dirname(fileURLToPath(import.meta.url))
const css = readFileSync(resolve(here, 'theme.css'), 'utf8')
const rule = (selector: string) => {
  const i = css.indexOf(`${selector} {`)
  expect(i, `rule ${selector}`).toBeGreaterThan(-1)
  return css.slice(i, css.indexOf('}', i))
}

describe('theme — palette tokens (spec §4)', () => {
  it.each([
    ['--bg', '#fdfcf9'], ['--bg2', '#f6f3ec'], ['--bg3', '#efebe2'],
    ['--border', '#e8e3d8'], ['--border2', '#ddd7ca'],
    ['--text', '#141414'], ['--dim', '#57534b'], ['--mute', '#8c877c'],
    ['--accent', '#0f5257'], ['--accent-d', '#0a3d41'], ['--accent-soft', '#e4eee9'],
    ['--q', '#22c55e'], ['--mo', '#3d8bff'], ['--fv', '#d4b106'], ['--rr', '#440ab8'],
  ])('%s is %s', (token, value) => {
    expect(rule('.intrinsica')).toContain(`${token}: ${value};`)
  })

  it('keeps no trace of the old indigo accent', () => {
    for (const old of ['#4f46e5', '#4338ca', '#eef0ff', '#7c74f2', '#c7c3ff', '#e0e7ff', 'rgba(79,70,229']) {
      expect(css).not.toContain(old)
    }
  })

  it('moves the hard-coded colours onto the palette', () => {
    expect(rule('.intrinsica .nav')).toContain('rgba(253,252,249,.88)')
    expect(rule('.intrinsica .runbar .mini.ind')).toContain('#dfe6df')
    expect(rule('.intrinsica .wtoast a')).toContain('#9fd3cf')
    expect(css).toContain('rgba(15,82,87,.28)')
  })
})

describe('theme — pricing highlight (spec §5.7)', () => {
  it('sets included cells in bold teal, not green', () => {
    const on = rule('.intrinsica table.cmp-plans td.on')
    expect(on).toContain('color: var(--accent)')
    expect(on).toContain('font-weight: 700')
    expect(on).not.toContain('var(--pos)')
  })

  it('no longer paints the FREE badge green', () => {
    expect(css).not.toMatch(/\.pc-badge\.free\s*\{[^}]*var\(--pos\)/)
  })
})

describe('theme — teal question band (spec §5.4)', () => {
  it('is a full-width teal band with light text', () => {
    const band = rule('.intrinsica .qband')
    expect(band).toContain('background: var(--accent)')
    expect(band).toContain('padding: 64px 0')
    expect(band).not.toContain('border-top')
    expect(rule('.intrinsica .qband h2')).toContain('color: #fff')
    expect(rule('.intrinsica .qband p')).toContain('color: #cfe3e1')
  })
})
