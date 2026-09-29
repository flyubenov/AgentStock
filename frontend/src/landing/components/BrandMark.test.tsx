import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import BrandMark, { KEYHOLE, MARK } from './BrandMark'
import { Logo } from './Nav'

describe('BrandMark (spec §4)', () => {
  it('draws the keyhole on the teal plate, fully lit in the four logo colours', () => {
    const { container } = render(<BrandMark />)
    const svg = container.querySelector('svg.brandmark')!
    expect(svg).toHaveAttribute('aria-hidden', 'true')
    expect(svg).toHaveAttribute('width', '42')
    expect(svg.querySelector('path')).toHaveAttribute('d', KEYHOLE)
    const stops = Array.from(svg.querySelectorAll('stop')).map(s => s.getAttribute('stop-color'))
    expect(stops).toEqual(['#17696f', '#0a3a3e'])
    const fills = Array.from(svg.querySelectorAll('g rect')).map(r => r.getAttribute('fill'))
    expect(fills).toEqual(['#66fff7', '#3d8bff', '#fae842', '#440ab8'])
    const rim = svg.querySelector('path[stroke]')!
    expect(rim).toHaveAttribute('stroke', '#8fc4c5')
    expect(rim).toHaveAttribute('stroke-width', '1.6')
    expect(MARK).toMatchObject({ q: '#66fff7', mo: '#3d8bff', fv: '#fae842', rr: '#440ab8' })
  })

  // Review Focus 5: the nav and the checkout mini-nav can both be mounted; a
  // shared gradient / clip id would let the second mark lose its fill.
  it('gives every instance its own gradient and clip ids', () => {
    const { container } = render(<><BrandMark /><BrandMark size={16} /></>)
    const ids = Array.from(container.querySelectorAll('[id]')).map(e => e.id)
    expect(ids).toHaveLength(4)
    expect(new Set(ids).size).toBe(4)
    for (const svg of container.querySelectorAll('svg')) {
      const own = Array.from(svg.querySelectorAll('[id]')).map(e => e.id)
      expect(svg.querySelector('rect')!.getAttribute('fill')).toBe(`url(#${own[0]})`)
      expect(svg.querySelector('g')!.getAttribute('clip-path')).toBe(`url(#${own[1]})`)
    }
  })

  it('sits in the logo beside the wordmark, replacing the old letter tile', () => {
    const { container } = render(<Logo />)
    expect(container.querySelector('.logo svg.brandmark')).toBeInTheDocument()
    expect(container.querySelector('.logo .mk')).toBeNull()
    expect(screen.getByText('Intrinsica')).toBeInTheDocument()
  })

  it('ships the same mark as the favicon', () => {
    const here = dirname(fileURLToPath(import.meta.url))
    const svg = readFileSync(resolve(here, '../../../public/favicon.svg'), 'utf8')
    for (const v of [KEYHOLE, '#17696f', '#0a3a3e', '#8fc4c5', '#66fff7', '#3d8bff', '#fae842', '#440ab8']) {
      expect(svg).toContain(v)
    }
  })
})
