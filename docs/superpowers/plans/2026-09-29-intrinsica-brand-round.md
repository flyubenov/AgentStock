# Intrinsica Brand Round Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-skin the Intrinsica landing page with the approved brand. That covers the teal accent on warm paper, the re-balanced assessment colours, the keyhole mark with its favicon, line icons, the teal question band and the float-in on scroll. It also shortens the Framework panel into collapsible categories, rewords the method paragraph, and adds a static share image with og tags.

**Architecture:** All of this lives in the landing route tree `frontend/src/landing/`, scoped under `.intrinsica` so the dark analyst app is untouched.
- **Colours:** the tokens change in `theme.css`. Components already read colours only from tokens.
- **Framework copy:** the copy stays data in `content/framework.ts`, and its shape changes. `Framework.tsx` renders the new shape.
- **Brand mark:** one React component, plus a static SVG copy for the favicon.
- **Motion:** a small DOM module, `reveal.ts`, started once by `LandingPage`.
- **Icons:** they come from `lucide-react`, which is already a dependency (v1.8.0).

**Tech Stack:** React 19, TypeScript, Vite, Vitest with jsdom and Testing Library, plain CSS (`theme.css`), and `lucide-react`.

**Spec:** `docs/superpowers/specs/2026-09-23-intrinsica-fake-door-design.md`, revision 2026-09-29: §4, §5, §5.2, §5.4, §5.7, §5.8, §11. It was approved by the user on 2026-09-29.

## Global Constraints

- **Branch:** all work stays on `01-fake-door-test`. Never merge or push without asking the user.
- **Never commit** `backend/tests/__pycache__/*.pyc`. Stage files by name, never `git add -A` or `git add .`.
- **Commit trailer:** `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **The Why section's content never changes:** `Why.tsx` is not edited, and its emoji stay. It only takes part in the scroll reveal, which is applied from outside by selector.
- **Copy rules (spec §8):**
  - never the word "signal"; never "Risk/Reward", always "Reward / Risk" or "Reward/Risk";
  - no raw `[A-Z_]{4,}` identifiers in user-facing strings;
  - no per-metric thresholds in the Framework copy.
- **Assessment colours come only from the tokens** `var(--q)`, `var(--mo)`, `var(--fv)` and `var(--rr)`. There are no colour literals in `content/framework.ts`.
- **Tokens, verbatim from spec §4:**
  - `--bg #fdfcf9`, `--bg2 #f6f3ec`, `--bg3 #efebe2`;
  - `--border #e8e3d8`, `--border2 #ddd7ca`;
  - `--text #141414`, `--dim #57534b`, `--mute #8c877c`;
  - `--accent #0f5257`, `--accent-d #0a3d41`, `--accent-soft #e4eee9`;
  - `--q #22c55e`, `--mo #3d8bff`, `--fv #d4b106`, `--rr #440ab8`;
  - `--pos`, `--neg`, `--warn` and `--blue` are unchanged.
- **Brand mark, verbatim from spec §4:**
  - plate gradient `#17696f → #0a3a3e`, `rx 22` at x/y 4–96 on a 100 viewBox;
  - keyhole `M43.10 51.32 A15 15 0 1 1 56.90 51.32 L62 80 L38 80 Z`, rim `#8fc4c5` at width 1.6;
  - fill: head aqua `#66fff7` | azure `#3d8bff`, slot yellow `#fae842` | violet `#440ab8`, split at x = 50 and y = 53;
  - 42 px in the nav; the wordmark is 23 px with an 11 px gap.
- **The mark appears only in the nav logo and the favicon**, never on result cards or comparison rows.
- **Test gate:** `cd frontend && npx vitest run` green. `npx tsc -b` clean. `npx eslint .` must add no problems over the branch baseline of 6.

## Review Focus

1. **Funnel tests and the reveal's observer.** `funnel.test.tsx` stubs `IntersectionObserver` and fires *every* registered callback. If the reveal registers one under test, those callbacks receive fake entries. Expected: the reveal no-ops when `window.matchMedia` is missing, as in jsdom, so the funnel tests see only Pricing's observer. Pinned in Task 6.
2. **Content already on screen at load must never be hidden.** A visitor who lands on `/#pricing`, or refreshes mid-page, must see the pricing immediately. Expected: targets whose top is inside the viewport when the reveal starts are skipped. Pinned in Task 6.
3. **A tab switch while category rows are open.** Expected: the new panel arrives with every row collapsed, as the calibrations already do. Pinned in Task 5.
4. **Icon buttons lose their names.** Swapping `☆` or `✕` for an SVG must keep the accessible names ("Add AAPL to a watchlist", "Dismiss", "Close"). Expected: screen readers announce the same names as before. Pinned in Task 3.
5. **Two brand marks on one page, such as the nav plus the checkout mini-nav.** Duplicate SVG gradient or clip ids would make the second mark borrow or lose the first one's fill. Expected: each instance has unique ids. Pinned in Task 2.

---

### Task 1: Palette, pricing highlight and teal question band (theme.css)

**Files:**
- Modify: `frontend/src/landing/theme.css`. The token block is at lines 9–17. The rules to change are at lines 35, 204–206, 289, 331, 347, 394 and 415.
- Create: `frontend/src/landing/theme.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: the new token values, which every later task renders with. The classes `.qband`, `.pc-badge.free` and `table.cmp-plans td.on` keep their names.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/landing/theme.test.ts`:

```ts
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/landing/theme.test.ts`
Expected: FAIL. The token assertions report, for example, `expected '…--bg: #ffffff…' to contain '--bg: #fdfcf9;'`, and the indigo test finds `#4f46e5`.

- [ ] **Step 3: Implement the CSS changes**

In `theme.css`, replace the first four token lines of `.intrinsica { … }` (lines 10–13). Keep the `--fh`/`--fb`/`--fm` and `--r`/`--sh` lines as they are.

```css
  --bg: #fdfcf9; --bg2: #f6f3ec; --bg3: #efebe2; --border: #e8e3d8; --border2: #ddd7ca;
  --text: #141414; --dim: #57534b; --mute: #8c877c;
  --accent: #0f5257; --accent-d: #0a3d41; --accent-soft: #e4eee9;
  --pos: #16a34a; --neg: #dc2626; --warn: #d97706; --blue: #2563eb;
  --q: #22c55e; --mo: #3d8bff; --fv: #d4b106; --rr: #440ab8;
```

Then edit these rules:
- **Line 35, `.intrinsica .nav`:** `background: rgba(255,255,255,.86)` → `background: rgba(253,252,249,.88)`.
- **Lines 204–206, the question band.** Replace the three rules with:

```css
.intrinsica .qband { background: var(--accent); padding: 64px 0; text-align: center; }
.intrinsica .qband h2 { font: 700 34px/1.15 var(--fh); letter-spacing: -.02em; text-wrap: balance; color: #fff; }
.intrinsica .qband p { color: #cfe3e1; font-size: 17px; max-width: 62ch; margin: 12px auto 0; }
```

- **Line 289:** delete `.intrinsica .pc-badge.free { color: var(--pos); }`. The base `.pc-badge` is already bold `var(--accent)`.
- **Line 331:** `.intrinsica table.cmp-plans td.on { color: var(--pos); font-weight: 600; }` → `.intrinsica table.cmp-plans td.on { color: var(--accent); font-weight: 700; }`.
- **Line 347:** `rgba(79,70,229,.28)` → `rgba(15,82,87,.28)`.
- **Line 394, `.intrinsica .runbar .mini.ind`:** `#e0e7ff` → `#dfe6df`.
- **Line 415, `.intrinsica .wtoast a`:** `#c7c3ff` → `#9fd3cf`.
- **Line 39, the `.logo .mk` rule with `#7c74f2`:** leave it for Task 2, which removes it. This task's indigo test stays red until then, so run Step 4 with that one test excluded as shown below.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/landing/theme.test.ts -t "^(?!.*indigo)"`
Expected: PASS for every test except "keeps no trace of the old indigo accent". That test is still red on `#7c74f2`, and Task 2 turns it green.

Then run: `cd frontend && npx vitest run src/landing`
Expected: all previously green tests are still green, because the component tests assert no colours.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/landing/theme.css frontend/src/landing/theme.test.ts
git commit -m "feat(landing): teal accent on warm paper, re-balanced assessment colours, teal question band, teal pricing highlight

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Brand mark, nav logo and favicon

**Files:**
- Create: `frontend/src/landing/components/BrandMark.tsx`
- Create: `frontend/src/landing/components/BrandMark.test.tsx`
- Modify: `frontend/src/landing/components/Nav.tsx` (`Logo`, line 10–12)
- Modify: `frontend/src/landing/theme.css` (`.logo` line 38, remove `.logo .mk` lines 39–40)
- Modify: `frontend/public/favicon.svg` (replace Vite's bolt entirely)

**Interfaces:**
- Consumes: nothing.
- Produces: `export default function BrandMark({ size }: { size?: number }): JSX.Element`, which renders `<svg class="brandmark" aria-hidden="true">`. It also exports `KEYHOLE: string` and `MARK: { plateTop, plateBot, rim, q, mo, fv, rr }`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/landing/components/BrandMark.test.tsx`:

```tsx
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/landing/components/BrandMark.test.tsx`
Expected: FAIL with `Failed to resolve import "./BrandMark"`.

- [ ] **Step 3: Implement**

Create `frontend/src/landing/components/BrandMark.tsx`:

```tsx
import { useId } from 'react'

/** The keyhole outline: a round head over a tapered slot. It reads as a letter i. */
export const KEYHOLE = 'M43.10 51.32 A15 15 0 1 1 56.90 51.32 L62 80 L38 80 Z'

/** Spec §4. The logo keeps its own shades for Quality (aqua) and Fair Value
 *  (bright yellow): the page's green melts into the teal plate, and the page's
 *  gold would dull the light. Moat and Reward/Risk match the page tokens. */
export const MARK = {
  plateTop: '#17696f', plateBot: '#0a3a3e', rim: '#8fc4c5',
  q: '#66fff7', mo: '#3d8bff', fv: '#fae842', rr: '#440ab8',
} as const

/** "Light through the keyhole", always fully lit. The head holds Quality |
 *  Moat and the slot holds Fair Value | Reward/Risk. It appears only as the
 *  logo and the favicon (spec §4), never on a result. */
export default function BrandMark({ size = 42 }: { size?: number }) {
  // useId keeps two marks on one page from sharing a gradient or clip id.
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const plate = `bm-p-${id}`, clip = `bm-k-${id}`
  return (
    <svg className="brandmark" width={size} height={size} viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={plate} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={MARK.plateTop} />
          <stop offset="1" stopColor={MARK.plateBot} />
        </linearGradient>
        <clipPath id={clip}><path d={KEYHOLE} /></clipPath>
      </defs>
      <rect x="4" y="4" width="92" height="92" rx="22" fill={`url(#${plate})`} />
      <g clipPath={`url(#${clip})`}>
        <rect x="0" y="0" width="50" height="53" fill={MARK.q} />
        <rect x="50" y="0" width="50" height="53" fill={MARK.mo} />
        <rect x="0" y="53" width="50" height="47" fill={MARK.fv} />
        <rect x="50" y="53" width="50" height="47" fill={MARK.rr} />
      </g>
      <path d={KEYHOLE} fill="none" stroke={MARK.rim} strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  )
}
```

Note on the test's first `querySelector('path')`: the first `<path>` in document order is the one inside `<clipPath>`, and it carries `d={KEYHOLE}`. That is intended.

In `Nav.tsx`, add `import BrandMark from './BrandMark'` and replace `Logo`:

```tsx
/** The logo block, shared with the checkout's mini-nav. */
export function Logo() {
  return <div className="logo"><BrandMark size={42} />Intrinsica</div>
}
```

In `theme.css`, replace lines 38–40, which are the `.logo` rule and the two-line `.logo .mk` rule, with:

```css
.intrinsica .logo { display: flex; align-items: center; gap: 11px; font: 700 23px var(--fh); letter-spacing: -.02em; }
.intrinsica .logo .brandmark { display: block; flex: none; }
```

Replace the whole of `frontend/public/favicon.svg` with:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <defs>
    <linearGradient id="p" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#17696f"/><stop offset="1" stop-color="#0a3a3e"/></linearGradient>
    <clipPath id="k"><path d="M43.10 51.32 A15 15 0 1 1 56.90 51.32 L62 80 L38 80 Z"/></clipPath>
  </defs>
  <rect x="4" y="4" width="92" height="92" rx="22" fill="url(#p)"/>
  <g clip-path="url(#k)">
    <rect x="0" y="0" width="50" height="53" fill="#66fff7"/><rect x="50" y="0" width="50" height="53" fill="#3d8bff"/>
    <rect x="0" y="53" width="50" height="47" fill="#fae842"/><rect x="50" y="53" width="50" height="47" fill="#440ab8"/>
  </g>
  <path d="M43.10 51.32 A15 15 0 1 1 56.90 51.32 L62 80 L38 80 Z" fill="none" stroke="#8fc4c5" stroke-width="1.6" stroke-linejoin="round"/>
</svg>
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/landing/components/BrandMark.test.tsx src/landing/theme.test.ts`
Expected: PASS, including Task 1's "keeps no trace of the old indigo accent" now that `#7c74f2` is gone.

Then run: `cd frontend && npx vitest run src/landing`
Expected: all green. `CheckoutPage` renders `Logo` too, and it must still pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/landing/components/BrandMark.tsx frontend/src/landing/components/BrandMark.test.tsx frontend/src/landing/components/Nav.tsx frontend/src/landing/theme.css frontend/public/favicon.svg
git commit -m "feat(landing): keyhole brand mark in the nav and as the favicon

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Line icons

**Files:**
- Modify: `frontend/src/landing/components/ResultCard.tsx` (`Star` line 43–49; `Tile` line 77–93)
- Modify: `frontend/src/landing/components/Pricing.tsx` (line 100–102)
- Modify: `frontend/src/landing/components/WatchToast.tsx` (line 27)
- Modify: `frontend/src/landing/components/OpenBreakdown.tsx` (line 28)
- Modify: `frontend/src/landing/components/Framework.tsx` (the calibration `▾` span)
- Modify: `frontend/src/landing/CheckoutPage.tsx` (lines 206–207)
- Modify: `frontend/src/landing/theme.css` (lines 298 and 453; add icon rules)
- Test: `ResultCard.test.tsx`, `Pricing.test.tsx`, `WatchToast.test.tsx`, `OpenBreakdown.test.tsx`, `Framework.test.tsx`, `CheckoutPage.test.tsx` (existing files, new tests appended)

**Interfaces:**
- Consumes: `lucide-react` exports `Bookmark`, `ChevronDown`, `Check` and `X`. Each renders `<svg class="lucide lucide-<name> …">`.
- Produces: no new exports. The markup changes are:
  - the watch button contains `svg.lucide-bookmark`;
  - each `.rc-tile` contains `svg.tile-chev`;
  - each `.feature-list li` starts with `svg.fl-check`;
  - `.wtoast .x` and `.bk-x` contain `svg.lucide-x`;
  - each calibration `.arow .ah` ends with `svg.chev`.

- [ ] **Step 1: Write the failing tests**

Each assertion goes into the component's existing test file and uses that file's own render helper. Every block below uses a shared constant, so add this line near the top of each file that gets a block:

```tsx
const GLYPHS = /[☆✕✓▾]/
```

**`components/ResultCard.test.tsx`** — this file's helper is `show()`, which renders one AAPL row in the tiles view. Append:

```tsx
describe('ResultCard — line icons (spec §4)', () => {
  it('draws the watch button as a bookmark and keeps its name', () => {
    const { container } = show()
    const watch = screen.getByRole('button', { name: 'Add AAPL to a watchlist' })
    expect(watch.querySelector('svg.lucide-bookmark')).toBeInTheDocument()
    expect(watch.textContent).not.toMatch(GLYPHS)
    // spec §4: the brand mark never appears on a result
    expect(container.querySelector('.brandmark')).toBeNull()
  })

  it('ends every score tile in a drawn chevron', () => {
    const { container } = show()
    const tiles = Array.from(container.querySelectorAll('.rc-tile'))
    expect(tiles).toHaveLength(4)
    for (const t of tiles) expect(t.querySelector('svg.tile-chev')).toBeInTheDocument()
  })
})
```

**`components/Pricing.test.tsx`** — append this, using the same props the file already passes at line 311:

```tsx
describe('Pricing — line icons (spec §4)', () => {
  it('checks each plan bullet with a drawn check, text unchanged', () => {
    const { container } = render(<Pricing billing="annual" onBilling={vi.fn()} onChoose={vi.fn()} />)
    const bullets = Array.from(container.querySelectorAll('.feature-list li'))
    expect(bullets.length).toBeGreaterThan(0)
    for (const li of bullets) {
      expect(li.firstElementChild).toHaveClass('fl-check')
      expect(li.textContent).not.toMatch(GLYPHS)
    }
  })
})
```

If `onView` is a required prop there, pass `onView={vi.fn()}` as line 311 does.

**`components/WatchToast.test.tsx`**, append:

```tsx
describe('WatchToast — line icons (spec §4)', () => {
  it('closes with a drawn × and keeps the name Dismiss', () => {
    render(<WatchToast onClose={vi.fn()} />)
    const x = screen.getByRole('button', { name: 'Dismiss' })
    expect(x.querySelector('svg.lucide-x')).toBeInTheDocument()
    expect(x.textContent).not.toMatch(GLYPHS)
  })
})
```

**`components/OpenBreakdown.test.tsx`** — this file's fixture is `ROW`. Append inside its `describe`:

```tsx
  it('closes with a drawn × and keeps the name Close', () => {
    render(<OpenBreakdown row={ROW} tab={1} onTab={vi.fn()} onClose={vi.fn()} />)
    const x = screen.getByRole('button', { name: 'Close' })
    expect(x.querySelector('svg.lucide-x')).toBeInTheDocument()
    expect(x.textContent).not.toMatch(GLYPHS)
  })
```

**`components/Framework.test.tsx`** — this file's helper is `show()`. Append inside `describe('Framework — calibrations')`:

```tsx
  it('opens calibration rows with a drawn chevron', () => {
    const { container } = show(0)
    const heads = Array.from(container.querySelectorAll('.cal-wrap .arow .ah'))
    expect(heads.length).toBeGreaterThan(0)
    for (const h of heads) {
      expect(h.querySelector('svg.chev')).toBeInTheDocument()
      expect(h.textContent).not.toMatch(GLYPHS)
    }
  })
```

**`CheckoutPage.test.tsx`** — add inside its existing test that clicks Proceed to payment and sees the disclosure:

```tsx
    const h2 = document.querySelector('.disclosure h2')!
    expect(h2.querySelector('svg.lucide-check')).toBeInTheDocument()
    expect(h2.textContent).not.toContain('✓')
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/landing -t "line icons|drawn"`
Expected: FAIL. `svg.lucide-bookmark` is not found, and the text contains `☆`. The same happens for each glyph. Also run `src/landing/CheckoutPage.test.tsx`, which fails on the missing `svg.lucide-check`.

- [ ] **Step 3: Implement**

**`ResultCard.tsx`:** add `import { Bookmark, ChevronDown } from 'lucide-react'`. In `Star`, replace the `☆` child:

```tsx
            onClick={e => { e.stopPropagation(); onWatch(ticker) }}>
      <Bookmark size={15} strokeWidth={1.8} aria-hidden="true" />
    </button>
```

In `Tile`, add as the button's last child:

```tsx
      <ChevronDown className="tile-chev" size={15} strokeWidth={2} aria-hidden="true" />
```

**`Pricing.tsx`:** add `import { Check } from 'lucide-react'`, and at line 101:

```tsx
                  {p.features.map(f => (
                    <li key={f}><Check className="fl-check" size={15} strokeWidth={2.4} aria-hidden="true" />{f}</li>
                  ))}
```

**`WatchToast.tsx`:** add `import { X } from 'lucide-react'`, and replace `✕` with `<X size={16} aria-hidden="true" />`.

**`OpenBreakdown.tsx`:** add `import { X } from 'lucide-react'`, and replace `<span aria-hidden="true">✕</span>` with `<X size={14} aria-hidden="true" />`.

**`Framework.tsx`:** add `import { ChevronDown } from 'lucide-react'`, and in the calibration row replace `<span className="chev" aria-hidden="true">▾</span>` with:

```tsx
                      <ChevronDown className="chev" size={16} aria-hidden="true" />
```

**`CheckoutPage.tsx`:** add `import { Check } from 'lucide-react'`, and replace the h2's content:

```tsx
            <h2>
              <Check className="co-check" size={18} strokeWidth={2.4} aria-hidden="true" />
              {free ? "You're on the Intrinsica early-access list" : "You're on the Intrinsica founding list"}
            </h2>
```

**`theme.css`:**
- Line 298: replace the `.feature-list li::before { content: "✓"; … }` rule with `.intrinsica .feature-list .fl-check { color: var(--accent); flex: none; margin-top: 4px; }`.
- Line 453: replace the `.rc-tile::after { content: "↓"; … }` rule with `.intrinsica .rc-tile .tile-chev { position: absolute; right: 12px; top: 12px; color: var(--mute); }`.
- Append:

```css
.intrinsica .rc .watch svg, .intrinsica .wtoast .x svg { display: block; }
.intrinsica .rc .watch { display: inline-grid; place-items: center; }
.intrinsica .bk-x svg { display: inline-block; vertical-align: -2px; }
.intrinsica .disclosure h2 { display: flex; align-items: center; gap: 8px; }
```

(The last line adds to the existing `.disclosure h2` rule. Place it directly after that rule.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/landing`
Expected: all green. `OpenBreakdown.test` and `LandingPage.test` click the button named `'Close'`, and it keeps that name because the SVG is `aria-hidden`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/landing/components/ResultCard.tsx frontend/src/landing/components/ResultCard.test.tsx frontend/src/landing/components/Pricing.test.tsx frontend/src/landing/components/WatchToast.test.tsx frontend/src/landing/components/OpenBreakdown.test.tsx frontend/src/landing/components/Framework.test.tsx frontend/src/landing/components/Pricing.tsx frontend/src/landing/components/WatchToast.tsx frontend/src/landing/components/OpenBreakdown.tsx frontend/src/landing/components/Framework.tsx frontend/src/landing/CheckoutPage.tsx frontend/src/landing/CheckoutPage.test.tsx frontend/src/landing/theme.css
git commit -m "feat(landing): one drawn line-icon set for watch, tiles, bullets, close and calibrations

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Framework content — the new shape, the short copy and the method paragraph

**Files:**
- Modify: `frontend/src/landing/content/framework.ts`. The interfaces are at lines 15–33, `FRAMEWORK` at 48–141, and `OVERVIEW.judgment` at 157–160.
- Modify: `frontend/src/landing/content/framework.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:

```ts
export interface AssessmentGroup {
  title: string
  question: string        // one plain line under the title
  weight: string          // shown on the closed row: '35%', '40 pts', 'typically 40–60%', '6 factors · scored 1–5'
  share: number | null    // fixed share for the mini bar (Quality %, Moat pts); null for ranges
  metrics: string[]       // one chip each
  hi: string              // a few words
  lo: string
}
export interface AssessmentContent {
  name: string; color: string; question: string; scale: string; what: string
  hiLabel: string         // 'High' (Fair Value: 'Weighted up')
  loLabel: string         // 'Low'  (Fair Value: 'Weighted down')
  groups: AssessmentGroup[]
  bands: string[]         // scale-strip cells, worst → best; [] for Fair Value
  note: string            // the one line under the strip
}
```

- [ ] **Step 1: Write the failing test**

In `framework.test.ts`, first replace the two shape constants:

```ts
const SHAPE = ['name', 'color', 'question', 'scale', 'what',
               'hiLabel', 'loLabel', 'groups', 'bands', 'note']
const GROUP_SHAPE = ['title', 'question', 'weight', 'share', 'metrics', 'hi', 'lo']
```

Next, replace the test `'leaves no field of any assessment or group empty'` with:

```ts
  it('leaves no field of any assessment or group empty', () => {
    for (const a of FRAMEWORK) {
      for (const k of SHAPE) {
        if (k === 'groups' || k === 'bands') continue
        expect(a[k as 'name']).toBeTruthy()
      }
      for (const g of a.groups) {
        for (const k of ['title', 'question', 'weight', 'hi', 'lo'] as const) expect(g[k]).toBeTruthy()
        expect(g.metrics.length).toBeGreaterThan(0)
        for (const m of g.metrics) expect(m).toBeTruthy()
      }
    }
  })
```

Then replace the test `'uses the scores-high / scores-low vocabulary…'` with:

```ts
  // Spec 5.4 item 3 (2026-09-29): ▲ High / ▼ Low everywhere, except Fair Value,
  // which has no score to be high or low — a method is weighted up or down.
  it('uses the high / low vocabulary, weighted only for Fair Value', () => {
    expect(FRAMEWORK.map(a => a.hiLabel)).toEqual(['High', 'High', 'Weighted up', 'High'])
    expect(FRAMEWORK.map(a => a.loLabel)).toEqual(['Low', 'Low', 'Weighted down', 'Low'])
  })
```

Finally, append these tests inside the `describe`:

```ts
  // Spec 5.4 item 3 — the approved copy table, verbatim.
  const COPY: [string, string, string, string][] = [
    ['Growth & Margins', 'Is it growing — and profitably?', 'compounding revenue, margins holding', 'stalled growth, margins sliding'],
    ['Returns on Capital', 'Does it earn more than its capital costs?', 'well above its cost of capital', 'barely matches it'],
    ['Balance-Sheet Strength', 'Can it weather a bad year?', 'little debt, capex easily funded', 'leverage that needs a kind cycle'],
    ['Shareholder Alignment', 'Are owners treated well?', 'buybacks, earnings that arrive as cash', 'steady dilution, paper earnings'],
    ['Magnitude', 'How far above its cost of capital does it earn?', 'returns far above the cost of capital', 'returns that merely match it'],
    ['Durability', 'Does the edge last, year after year?', 'a decade of above-cost returns, margins that hold', 'a good spell inside a cyclical swing'],
    ['Cash-backing', 'Does the profit turn into cash?', 'profit that becomes cash', 'profit that stays on paper'],
    ['Cash-flow models', 'What will the business pay out over time?', 'steady, predictable cash flows', 'erratic cash flows, or pre-profit'],
    ['Earnings multiples', 'How is it priced against its earnings?', 'meaningful profits, comparable with peers', 'losses, or earnings distorted by amortization'],
    ['Sales multiples', 'What is growth worth before profit?', 'fast growth, no profit yet', 'a mature, profitable company'],
    ['Income & asset models', 'What do its dividends or assets say?', 'dividend payers, lenders, asset-heavy names', 'asset-light businesses'],
    ['Reward axis', 'How much upside is left?', 'a growing business well below its highs', 'a full price, little left to re-rate'],
    ['Risk axis · a high score here is the bad one', 'How much can go wrong?', 'leverage and volatility stacking up', 'light debt, a steady price, self-funded'],
  ]
  it('carries the approved question and ▲ / ▼ line for every category', () => {
    expect(FRAMEWORK.flatMap(a => a.groups.map(g => [g.title, g.question, g.hi, g.lo]))).toEqual(COPY)
  })

  // Categories, weights and metric lists are unchanged (spec 5.4): the chips
  // are the old metric string split one metric per chip, so the counts match
  // the "N metrics" the old pills announced.
  it('keeps the weights, shares and metric counts', () => {
    const [q, m, fv, rr] = FRAMEWORK
    expect(q.groups.map(g => g.weight)).toEqual(['35%', '30%', '15%', '20%'])
    expect(q.groups.map(g => g.share)).toEqual([35, 30, 15, 20])
    expect(q.groups.map(g => g.metrics.length)).toEqual([7, 4, 3, 5])
    expect(m.groups.map(g => g.weight)).toEqual(['40 pts', '50 pts', '10 pts'])
    expect(m.groups.map(g => g.share)).toEqual([40, 50, 10])
    expect(m.groups.map(g => g.metrics.length)).toEqual([2, 3, 1])
    expect(fv.groups.map(g => g.weight)).toEqual(['typically 40–60%', 'typically 20–40%', '0–20%', '0–60%'])
    expect(fv.groups.every(g => g.share === null)).toBe(true)
    expect(rr.groups.map(g => g.weight)).toEqual(['6 factors · scored 1–5', '6 factors · scored 1–5'])
    expect(rr.groups.every(g => g.share === null)).toBe(true)
    expect(rr.groups.map(g => g.metrics.length)).toEqual([6, 6])
  })

  // Spec 5.4 item 4: the closing note becomes a scale strip plus one line.
  it('carries the scale strip and its line for each assessment', () => {
    expect(FRAMEWORK.map(a => a.bands)).toEqual([
      ['below 5 · Weak', '5–7 · Moderate', '7–8 · Strong', '8–9 · Excellent', '9+ · Top-decile'],
      ['below 40 · Little or none', '40–59 · Narrow', '60–79 · Established', '80+ · Wide'],
      [],
      ['below 0.5× · Value Trap', '0.5–0.8× · Risk-Favored', '0.8–1.3× · Balanced', '1.3–2.0× · Reward-Favored', '2.0×+ · Asymmetric Upside'],
    ])
    expect(FRAMEWORK.map(a => a.note)).toEqual([
      'Each metric is scored against fixed thresholds; the category weights follow the sector profile (Tech / Growth shown).',
      'An economic-profit gate caps any company that does not out-earn its cost of capital.',
      'The company’s type sets the blend — a bank leans on price / book, a mega cap on cash flows. Every analysis shows the exact blend it used.',
      'Reward ÷ risk, clamped to 0.2–5.0×.',
    ])
  })

  // Spec 5.4 overview item 2, reworded 2026-09-29: the method is stated as fixed.
  it('states the method as fixed, and drops "no single agreed"', () => {
    expect(OVERVIEW.judgment.body).toBe(
      'Quality, Moat and Reward/Risk aren’t printed in any filing; they have to be assessed. ' +
      'Intrinsica assesses them with one fixed methodology: it takes the fundamentals that matter for each, ' +
      'weights them and condenses them into a single score, the same way for every company. ' +
      'Each score opens up to the inputs and weights behind it.')
    expect(everyString(OVERVIEW)).not.toMatch(/no single agreed/i)
  })
```

Leave `'names no moat source it cannot measure'` as it is. The new Moat copy still says "economic profit" through the `note`, and in the `what` field, which is unchanged.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/landing/content/framework.test.ts`
Expected: FAIL. The shape tests report missing `bands` and `question`, and the copy test reports a mismatch.

- [ ] **Step 3: Implement**

In `framework.ts`, replace the two interfaces with the ones in **Produces** above, keeping the comments to the house style. Then replace each assessment's `hiLabel`, `loLabel`, `groups` and `note`, and add `bands` after `groups`. Leave `name`, `color`, `question`, `scale` and `what` exactly as they are.

```ts
  // Quality
    hiLabel: 'High', loLabel: 'Low',
    groups: [
      { title: 'Growth & Margins', question: 'Is it growing — and profitably?', weight: '35%', share: 35,
        metrics: ['Revenue growth (3-yr)', 'EPS growth (3-yr)', 'FCF growth (3-yr)', 'Operating margin', 'Gross margin', 'Margin trend', 'FCF margin'],
        hi: 'compounding revenue, margins holding', lo: 'stalled growth, margins sliding' },
      { title: 'Returns on Capital', question: 'Does it earn more than its capital costs?', weight: '30%', share: 30,
        metrics: ['ROIC (trailing)', 'ROIC (5-yr)', 'ROIC − WACC spread', 'Return on tangible equity'],
        hi: 'well above its cost of capital', lo: 'barely matches it' },
      { title: 'Balance-Sheet Strength', question: 'Can it weather a bad year?', weight: '15%', share: 15,
        metrics: ['Net debt / EBITDA', 'Net debt / FCF', 'Operating cash flow / capex'],
        hi: 'little debt, capex easily funded', lo: 'leverage that needs a kind cycle' },
      { title: 'Shareholder Alignment', question: 'Are owners treated well?', weight: '20%', share: 20,
        metrics: ['Share-count trend', 'Stock comp % of revenue', 'Earnings quality (FCF / net income)', 'Insider ownership', 'Shareholder yield'],
        hi: 'buybacks, earnings that arrive as cash', lo: 'steady dilution, paper earnings' },
    ],
    bands: ['below 5 · Weak', '5–7 · Moderate', '7–8 · Strong', '8–9 · Excellent', '9+ · Top-decile'],
    note: 'Each metric is scored against fixed thresholds; the category weights follow the sector profile (Tech / Growth shown).',

  // Moat
    hiLabel: 'High', loLabel: 'Low',
    groups: [
      { title: 'Magnitude', question: 'How far above its cost of capital does it earn?', weight: '40 pts', share: 40,
        metrics: ['ROIC level (up to 20 pts)', 'Economic spread, ROIC − WACC (up to 20 pts)'],
        hi: 'returns far above the cost of capital', lo: 'returns that merely match it' },
      { title: 'Durability', question: 'Does the edge last, year after year?', weight: '50 pts', share: 50,
        metrics: ['Persistence of economic profit (25 pts)', 'Consistency of returns (10 pts)', 'Margin durability (15 pts)'],
        hi: 'a decade of above-cost returns, margins that hold', lo: 'a good spell inside a cyclical swing' },
      { title: 'Cash-backing', question: 'Does the profit turn into cash?', weight: '10 pts', share: 10,
        metrics: ['Free-cash-flow conversion (10 pts)'],
        hi: 'profit that becomes cash', lo: 'profit that stays on paper' },
    ],
    bands: ['below 40 · Little or none', '40–59 · Narrow', '60–79 · Established', '80+ · Wide'],
    note: 'An economic-profit gate caps any company that does not out-earn its cost of capital.',

  // Fair Value
    hiLabel: 'Weighted up', loLabel: 'Weighted down',
    groups: [
      { title: 'Cash-flow models', question: 'What will the business pay out over time?', weight: 'typically 40–60%', share: null,
        metrics: ['Discounted cash flow', 'Free cash flow to equity'],
        hi: 'steady, predictable cash flows', lo: 'erratic cash flows, or pre-profit' },
      { title: 'Earnings multiples', question: 'How is it priced against its earnings?', weight: 'typically 20–40%', share: null,
        metrics: ['EV / EBITDA', 'P / E (forward earnings when trailing ones are distorted)'],
        hi: 'meaningful profits, comparable with peers', lo: 'losses, or earnings distorted by amortization' },
      { title: 'Sales multiples', question: 'What is growth worth before profit?', weight: '0–20%', share: null,
        metrics: ['EV / Sales'],
        hi: 'fast growth, no profit yet', lo: 'a mature, profitable company' },
      { title: 'Income & asset models', question: 'What do its dividends or assets say?', weight: '0–60%', share: null,
        metrics: ['Dividend discount', 'Price / book', 'Residual income', 'Net asset value'],
        hi: 'dividend payers, lenders, asset-heavy names', lo: 'asset-light businesses' },
    ],
    bands: [],
    note: 'The company’s type sets the blend — a bank leans on price / book, a mega cap on cash flows. Every analysis shows the exact blend it used.',

  // Reward / Risk
    hiLabel: 'High', loLabel: 'Low',
    groups: [
      { title: 'Reward axis', question: 'How much upside is left?', weight: '6 factors · scored 1–5', share: null,
        metrics: ['Discount to 52-week high (24%)', 'Valuation (18%)', 'Growth (18%)', 'RSI (16%)', 'Profitability (12%)',
                  'Analyst upside (8–18%, weighted by how many analysts agree)'],
        hi: 'a growing business well below its highs', lo: 'a full price, little left to re-rate' },
      // The direction has to be stated outright, exactly as the breakdown
      // panel's own risk axis does: on this one category a high score is bad.
      { title: 'Risk axis · a high score here is the bad one', question: 'How much can go wrong?', weight: '6 factors · scored 1–5', share: null,
        metrics: ['Volatility (22%)', 'Leverage (18%)', 'Trend vs 200-day (18%)', 'Burn / margin (15%)', 'Beta (15%)', 'Liquidity (12%)'],
        hi: 'leverage and volatility stacking up', lo: 'light debt, a steady price, self-funded' },
    ],
    bands: ['below 0.5× · Value Trap', '0.5–0.8× · Risk-Favored', '0.8–1.3× · Balanced', '1.3–2.0× · Reward-Favored', '2.0×+ · Asymmetric Upside'],
    note: 'Reward ÷ risk, clamped to 0.2–5.0×.',
```

Keep the existing comment about Fair Value's vocabulary above its `hiLabel`, reworded to match: "Fair Value has no score to be high or low: a method is weighted up or down in the blend."

Replace `OVERVIEW.judgment.body` with the exact string in the Step 1 test, and update the comment above `judgment` to record the 2026-09-29 rewording and why: "no single agreed way" read as if Intrinsica had no settled method.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/landing/content/framework.test.ts`
Expected: PASS.

`npx tsc -b` now fails in `Framework.tsx` (`g.metrics` is an array, and `a.note` is still used). Task 5 fixes that, so do not commit a red type-check on its own: go straight on to Task 5 and commit both together at the end of Task 5.

---

### Task 5: Framework panel — collapsed category rows and the scale strip

**Files:**
- Modify: `frontend/src/landing/components/Framework.tsx`, lines 36–55 for the state and lines 106–126 for the detail panel.
- Modify: `frontend/src/landing/components/Framework.test.tsx`, which covers the detail panel and judgment tests.
- Modify: `frontend/src/landing/theme.css`. Delete the old `.grp`, `.gwhen`, `.gmetrics` and `.note` rules at lines 220–229, and add the row rules.

**Interfaces:**
- Consumes: Task 4's `AssessmentGroup` and `AssessmentContent`.
- Produces: the markup that Task 6's reveal and the tests rely on. The detail panel contains:
  - `.crows > .crow`, one per group, with `.crow.open` when expanded;
  - inside each row, a `button.ch[aria-expanded]` with `.nm` (title), `.cq` (question), `.cw` (weight) and an optional `.cbar > i`;
  - when open, `.cb` with `ul.chips > li` and `p.chl`;
  - then `ol.bands > li`, which is absent when `bands` is empty, and `p.note`.

- [ ] **Step 1: Write the failing test**

In `Framework.test.tsx`, first add a helper after `show`:

```tsx
const rows = (c: HTMLElement) => Array.from(c.querySelectorAll<HTMLElement>('.mdetail .crow'))
const openAll = async (c: HTMLElement) => {
  for (const b of c.querySelectorAll<HTMLButtonElement>('.crow .ch')) await userEvent.click(b)
}
```

Next, replace the whole `describe('Framework — detail panel', …)` block with:

```tsx
describe('Framework — detail panel', () => {
  it('shows every category collapsed: title, question and weight, no metrics yet', () => {
    const { container } = show(0)
    const rs = rows(container)
    expect(rs).toHaveLength(FRAMEWORK[0].groups.length)
    FRAMEWORK[0].groups.forEach((g, i) => {
      expect(rs[i].querySelector('.nm')).toHaveTextContent(g.title)
      expect(rs[i].querySelector('.cq')).toHaveTextContent(g.question)
      expect(rs[i].querySelector('.cw')).toHaveTextContent(g.weight)
      expect(rs[i].querySelector('.ch')).toHaveAttribute('aria-expanded', 'false')
      expect(rs[i].querySelector('.chips')).toBeNull()
    })
  })

  it('opens a row to its metric chips and one ▲ / ▼ line, and rows toggle independently', async () => {
    const { container } = show(0)
    const [first, second] = FRAMEWORK[0].groups
    await userEvent.click(screen.getByRole('button', { name: new RegExp(first.title) }))
    let rs = rows(container)
    expect(rs[0]).toHaveClass('open')
    expect(rs[0].querySelectorAll('.chips li')).toHaveLength(first.metrics.length)
    expect(rs[0].querySelector('.chl')).toHaveTextContent(`High: ${first.hi}`)
    expect(rs[0].querySelector('.chl')).toHaveTextContent(`Low: ${first.lo}`)
    expect(rs[1]).not.toHaveClass('open')

    await userEvent.click(screen.getByRole('button', { name: new RegExp(second.title) }))
    rs = rows(container)
    expect(rs[0]).toHaveClass('open')
    expect(rs[1]).toHaveClass('open')

    await userEvent.click(screen.getByRole('button', { name: new RegExp(first.title) }))
    expect(rows(container)[0]).not.toHaveClass('open')
  })

  // Spec 5.4: "identical in shape across all four". Every field has to reach
  // the DOM on every tab once the rows are open.
  it('renders every declared field of every assessment, on every tab', async () => {
    for (const tab of TABS) {
      const a = FRAMEWORK[tab]
      const { container, unmount } = show(tab)
      await openAll(container)
      const panel = container.querySelector<HTMLElement>('.mdetail')!
      expect(panel).toHaveTextContent(a.name)
      expect(panel).toHaveTextContent(a.scale)
      expect(panel).toHaveTextContent(a.what)
      expect(panel.querySelector('.note')).toHaveTextContent(a.note)
      expect(panel.querySelectorAll('.bands li')).toHaveLength(a.bands.length)
      for (const g of a.groups) {
        expect(panel).toHaveTextContent(g.title)
        expect(panel).toHaveTextContent(g.question)
        for (const m of g.metrics) expect(panel).toHaveTextContent(m)
        expect(panel).toHaveTextContent(g.hi)
        expect(panel).toHaveTextContent(g.lo)
      }
      expect(within(panel).getAllByText(`${a.hiLabel}:`)).toHaveLength(a.groups.length)
      expect(within(panel).getAllByText(`${a.loLabel}:`)).toHaveLength(a.groups.length)
      unmount()
    }
  })

  it('draws a weight bar only for fixed shares, scaled to the largest category', () => {
    const { container, unmount } = show(0)
    const widths = rows(container).map(r => r.querySelector<HTMLElement>('.cbar i')!.style.width)
    expect(widths).toEqual(['100%', '86%', '43%', '57%'])   // 35 / 30 / 15 / 20 of 35
    unmount()
    const fv = show(2)
    expect(fv.container.querySelector('.cbar')).toBeNull()
  })

  it('shows the scale strip, or only the line for Fair Value', () => {
    const { container, unmount } = show(0)
    expect(Array.from(container.querySelectorAll('.bands li')).map(l => l.textContent))
      .toEqual(FRAMEWORK[0].bands)
    unmount()
    const fv = show(2)
    expect(fv.container.querySelector('.bands')).toBeNull()
    expect(fv.container.querySelector('.note')).toHaveTextContent(FRAMEWORK[2].note)
  })

  // Review Focus 3: a new panel arrives with every row collapsed.
  it('collapses open rows when the assessment changes', async () => {
    const { container, rerender } = show(0)
    await openAll(container)
    rerender(<Framework tab={1} onTab={vi.fn()} />)
    expect(rows(container).every(r => !r.classList.contains('open'))).toBe(true)
  })

  it('switches the whole panel when the selected assessment changes', () => {
    const { unmount } = show(0)
    expect(screen.getByText('Growth & Margins')).toBeInTheDocument()
    expect(screen.queryByText('Cash-backing')).not.toBeInTheDocument()
    unmount()
    show(1)
    expect(screen.getByText('Cash-backing')).toBeInTheDocument()
    expect(screen.queryByText('Growth & Margins')).not.toBeInTheDocument()
  })

  it('says Weighted up / down on Fair Value and High / Low elsewhere', async () => {
    const fv = show(2)
    await openAll(fv.container)
    expect(screen.getAllByText('Weighted up:').length).toBeGreaterThan(0)
    expect(screen.queryByText('High:')).not.toBeInTheDocument()
    fv.unmount()
    const rr = show(3)
    await openAll(rr.container)
    expect(screen.getAllByText('High:').length).toBeGreaterThan(0)
    expect(screen.queryByText('Weighted up:')).not.toBeInTheDocument()
  })
})
```

In `describe('Framework — calibrations')`, scope every `.arow` selector to the calibrations: `.arow .nm` becomes `.cal-wrap .arow .nm`, and likewise for the others. Category rows use `.crow`, so this is only a guard against future class reuse.

Then, in the judgment test at the end of the file, replace the three `toHaveTextContent` lines about the old sentence with:

```tsx
    // Reworded 2026-09-29 (user decision): the old "no single agreed way…" read as
    // if Intrinsica itself had no settled method.
    expect(note).toHaveTextContent(/aren’t printed in any filing; they have to be assessed\./)
    expect(note).toHaveTextContent(/one fixed methodology/)
    expect(note).toHaveTextContent(/the same way for every company\./)
    expect(note).toHaveTextContent(/Each score opens up to the inputs and weights behind it\.$/)
    expect(note).not.toHaveTextContent(/no single agreed/i)
```

Keep the rest of that test.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/landing/components/Framework.test.tsx`
Expected: FAIL. `.crow` is not found, because the panel still renders `.grpblock`.

- [ ] **Step 3: Implement**

In `Framework.tsx`, add the row state beside `openCal`, and reset it in the existing render-phase tab adjustment:

```tsx
  // Which category rows are open, by title. Collapsed by default and
  // independent of each other, like the calibrations (spec 5.4 item 3).
  const [openGroups, setOpenGroups] = useState<ReadonlySet<string>>(() => new Set())
  const toggleGroup = (title: string) => setOpenGroups(prev => {
    const next = new Set(prev)
    if (next.has(title)) next.delete(title); else next.add(title)
    return next
  })
```

```tsx
  if (shownTab !== tab) {
    setShownTab(tab)
    setOpenCal(null)
    setOpenGroups(new Set())
  }
  const a = FRAMEWORK[tab]
  const maxShare = Math.max(0, ...a.groups.map(g => g.share ?? 0))
```

Replace the `{a.groups.map(g => (<div className="grpblock">…))}` block and the `<p className="note">` line with:

```tsx
            <div className="crows">
              {a.groups.map(g => {
                const open = openGroups.has(g.title)
                return (
                  <div key={g.title} className={open ? 'crow open' : 'crow'}>
                    <button type="button" className="ch" aria-expanded={open}
                            onClick={() => toggleGroup(g.title)}>
                      <span>
                        <span className="nm">{g.title}</span>
                        <span className="cq">{g.question}</span>
                      </span>
                      <span className="cw">
                        {g.weight}
                        {g.share !== null && maxShare > 0 && (
                          <span className="cbar" aria-hidden="true">
                            <i style={{ width: `${Math.round((g.share / maxShare) * 100)}%`, background: a.color }} />
                          </span>
                        )}
                      </span>
                      <ChevronDown className="chev" size={16} aria-hidden="true" />
                    </button>
                    {open && (
                      <div className="cb">
                        <ul className="chips">{g.metrics.map(m => <li key={m}>{m}</li>)}</ul>
                        <p className="chl">
                          <span className="up"><span aria-hidden="true">▲ </span><b>{a.hiLabel}:</b> {g.hi}</span>
                          <span className="dn"><span aria-hidden="true">▼ </span><b>{a.loLabel}:</b> {g.lo}</span>
                        </p>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            {a.bands.length > 0 && (
              <ol className="bands" style={{ '--c': a.color } as CSSProperties}>
                {a.bands.map((b, i) => (
                  <li key={b} style={{ '--a': `${Math.round(10 + (60 * i) / Math.max(1, a.bands.length - 1))}%` } as CSSProperties}>{b}</li>
                ))}
              </ol>
            )}
            <p className="note">{a.note}</p>
```

Add `import type { CSSProperties } from 'react'`. `ChevronDown` is already imported from Task 3.

In `theme.css`, delete the rules for `.grp`, `.grp .wt2`, `.gwhen`, `.gwhen b`, `.gwhen b.up/.dn` and `.gmetrics`, plus the old `.note` rule at line 229. Delete any other `.grp…` lines in 220–229 as well. Add:

```css
.intrinsica .crows { margin-top: 14px; }
.intrinsica .crow { background: var(--bg); border: 1px solid var(--border); border-radius: 10px; margin-bottom: 8px; }
.intrinsica .crow .ch { width: 100%; display: grid; grid-template-columns: 1fr auto 18px; align-items: center; gap: 14px;
  padding: 12px 14px; background: none; border: 0; border-radius: 9px; text-align: left; color: inherit; font: inherit; cursor: pointer; }
.intrinsica .crow .ch:hover { background: var(--bg2); }
.intrinsica .crow .nm { display: block; font: 700 14px var(--fh); }
.intrinsica .crow .cq { display: block; font-size: 13px; color: var(--dim); margin-top: 2px; }
.intrinsica .crow .cw { display: flex; align-items: center; gap: 8px; font: 600 12px var(--fm); color: var(--dim); white-space: nowrap; }
.intrinsica .crow .cbar { width: 70px; height: 6px; border-radius: 3px; background: var(--bg3); overflow: hidden; }
.intrinsica .crow .cbar i { display: block; height: 100%; }
.intrinsica .crow .chev { color: var(--mute); transition: transform .15s; }
.intrinsica .crow.open .chev { transform: rotate(180deg); color: var(--accent); }
.intrinsica .crow .cb { padding: 12px 14px 14px; border-top: 1px dashed var(--border); }
.intrinsica .chips { list-style: none; display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.intrinsica .chips li { font-size: 12px; background: var(--bg2); border: 1px solid var(--border); border-radius: 999px; padding: 3px 9px; }
.intrinsica .chl { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13px; color: var(--dim); }
.intrinsica .chl b { font-weight: 700; } .intrinsica .chl .up b { color: var(--pos); } .intrinsica .chl .dn b { color: var(--warn); }
.intrinsica .bands { list-style: none; display: flex; gap: 4px; margin-top: 14px; font: 600 11.5px var(--fb); }
.intrinsica .bands li { flex: 1; text-align: center; padding: 6px 4px; border-radius: 6px;
  background: color-mix(in srgb, var(--c) var(--a), var(--bg)); }
.intrinsica .note { margin-top: 8px; font-size: 12.5px; color: var(--mute); }
@media (max-width: 600px) { .intrinsica .bands { flex-direction: column; } .intrinsica .crow .cbar { display: none; } }
```

- [ ] **Step 4: Run the tests and the type-check**

Run: `cd frontend && npx vitest run src/landing && npx tsc -b`
Expected: all tests green, and `tsc` has no errors.

- [ ] **Step 5: Commit (Tasks 4 and 5 together)**

```bash
git add frontend/src/landing/content/framework.ts frontend/src/landing/content/framework.test.ts frontend/src/landing/components/Framework.tsx frontend/src/landing/components/Framework.test.tsx frontend/src/landing/theme.css
git commit -m "feat(landing): Framework categories as collapsed rows with one-line questions and scale strips; method paragraph reworded

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Scroll reveal

**Files:**
- Create: `frontend/src/landing/reveal.ts`
- Create: `frontend/src/landing/reveal.test.ts`
- Modify: `frontend/src/landing/LandingPage.tsx` (add one `useEffect` next to the existing ones at line ~206)
- Modify: `frontend/src/landing/LandingPage.test.tsx` (one test)
- Modify: `frontend/src/landing/theme.css` (append the reveal rules)

**Interfaces:**
- Consumes: the section markup from the earlier tasks: `.qband .container`, `#how .ovcard`, `#how .mpl`, `#how .mcard`, `#how .mdetail`, `#why .diff`, `#workflow .wf`, `#pricing .price-card`, `#pricing .compare`, `.footer`, plus each section's `.kicker`, `.stitle` and `.ssub`.
- Produces: `export function startReveal(root?: ParentNode): () => void`, and the constants `REVEAL_SELECTOR: string`, `STAGGER_MS = 90` and `STAGGER_STEPS = 4`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/landing/reveal.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { startReveal, STAGGER_MS } from './reveal'

type IOCb = (entries: { isIntersecting: boolean; target: Element }[]) => void
let observed: Element[] = []
let unobserved: Element[] = []
let fire: IOCb = () => {}
let disconnected = false

function stubBrowser({ reduced = false } = {}) {
  vi.stubGlobal('matchMedia', vi.fn((q: string) => ({ matches: reduced && q.includes('reduce') })))
  vi.stubGlobal('IntersectionObserver', class {
    constructor(cb: IOCb) { fire = cb }
    observe(e: Element) { observed.push(e) }
    unobserve(e: Element) { unobserved.push(e) }
    disconnect() { disconnected = true }
  })
}

/** Everything sits below the fold except what is listed in `inView`. */
function page(inView: string[] = []) {
  document.body.innerHTML = `
    <section class="hero"><div id="analyze" class="kicker">hero</div></section>
    <div class="qband"><div class="container">band</div></div>
    <section id="why"><div class="container"><div class="kicker">k</div>
      <div class="diff-grid">${'<div class="diff">c</div>'.repeat(5)}</div></div></section>
    <section id="pricing"><div class="container"><div class="price-grid">
      <div class="price-card" id="p1"></div><div class="price-card" id="p2"></div></div></div></section>`
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
    const top = inView.some(s => this.matches(s)) ? 100 : 2000
    return { top, bottom: top + 50, left: 0, right: 0, width: 0, height: 50, x: 0, y: top, toJSON: () => ({}) } as DOMRect
  })
  vi.stubGlobal('innerHeight', 900)
}

beforeEach(() => { observed = []; unobserved = []; disconnected = false; document.body.innerHTML = '' })

describe('startReveal (spec §4 Motion)', () => {
  // Review Focus 1: jsdom has no matchMedia; the funnel tests stub only
  // IntersectionObserver and fire every callback — the reveal must stay out.
  it('does nothing where matchMedia or IntersectionObserver is missing', () => {
    page()
    vi.stubGlobal('matchMedia', undefined)
    vi.stubGlobal('IntersectionObserver', class { observe() {} disconnect() {} })
    startReveal()
    expect(document.querySelectorAll('.rv')).toHaveLength(0)
  })

  it('does nothing when the visitor asks for reduced motion', () => {
    page(); stubBrowser({ reduced: true })
    startReveal()
    expect(document.querySelectorAll('.rv')).toHaveLength(0)
  })

  it('hides below-the-fold blocks until they scroll in, never the hero', () => {
    page(); stubBrowser()
    startReveal()
    expect(document.querySelector('.hero .kicker')).not.toHaveClass('rv')
    expect(document.querySelector('.qband .container')).toHaveClass('rv')
    expect(document.querySelectorAll('#why .diff.rv')).toHaveLength(5)
    expect(observed.length).toBe(document.querySelectorAll('.rv').length)
  })

  // Review Focus 2: a visitor landing on /#pricing sees the plans at once.
  it('leaves blocks that are already on screen alone', () => {
    page(['.price-card']); stubBrowser()
    startReveal()
    expect(document.querySelectorAll('.price-card.rv')).toHaveLength(0)
    expect(document.querySelector('.qband .container')).toHaveClass('rv')
  })

  it('staggers cards in a row by 90 ms, capped at four steps', () => {
    page(); stubBrowser()
    startReveal()
    const delays = Array.from(document.querySelectorAll<HTMLElement>('#why .diff')).map(e => e.style.transitionDelay)
    expect(delays).toEqual(['0ms', `${STAGGER_MS}ms`, `${2 * STAGGER_MS}ms`, `${3 * STAGGER_MS}ms`, `${3 * STAGGER_MS}ms`])
  })

  it('shows a block once it intersects, and stops watching it', () => {
    page(); stubBrowser()
    startReveal()
    const band = document.querySelector('.qband .container')!
    fire([{ isIntersecting: false, target: band }])
    expect(band).not.toHaveClass('in')
    fire([{ isIntersecting: true, target: band }])
    expect(band).toHaveClass('in')
    expect(unobserved).toContain(band)
  })

  it('cleans up: disconnects and leaves everything visible', () => {
    page(); stubBrowser()
    const stop = startReveal()
    stop()
    expect(disconnected).toBe(true)
    expect(document.querySelectorAll('.rv')).toHaveLength(0)
  })
})
```

Append to `LandingPage.test.tsx`. Use the file's own `renderSettled()` helper, which exists at line 47:

```tsx
describe('LandingPage — scroll reveal', () => {
  it('starts the reveal once the page has mounted', async () => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false })))
    vi.stubGlobal('IntersectionObserver', class { observe() {} unobserve() {} disconnect() {} })
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue(
      { top: 5000, bottom: 5050, left: 0, right: 0, width: 0, height: 50, x: 0, y: 5000, toJSON: () => ({}) } as DOMRect)
    await renderSettled()
    expect(document.querySelector('.qband .container')).toHaveClass('rv')
    expect(document.querySelector('#analyze')!.closest('.rv')).toBeNull()
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/landing/reveal.test.ts src/landing/LandingPage.test.tsx -t "reveal"`
Expected: FAIL with `Failed to resolve import "./reveal"`, and the LandingPage test fails on `toHaveClass('rv')`.

- [ ] **Step 3: Implement**

Create `frontend/src/landing/reveal.ts`:

```ts
/** Spec §4 Motion: blocks below the first screen slide up and fade in as they
 *  enter the view, once each. It is an animation, not lazy loading: everything
 *  is already in the DOM, and the hidden state is added here, by script, never
 *  by static CSS, so a page whose script does not run is simply visible.
 *
 *  Targets are named by selector rather than marked in JSX so the Why section
 *  (whose markup is frozen by user decision) takes part without being edited. */
export const REVEAL_SELECTOR = [
  '.qband .container',
  '#how .ovcard', '#how .mpl', '#how .mcard', '#how .mdetail',
  '#why .kicker', '#why .stitle', '#why .ssub', '#why .why-lbl', '#why .diff',
  '#workflow .kicker', '#workflow .stitle', '#workflow .ssub', '#workflow .wf',
  '#pricing .kicker', '#pricing .stitle', '#pricing .ssub', '#pricing .price-card', '#pricing .compare',
  '.footer',
].join(', ')
export const STAGGER_MS = 90
export const STAGGER_STEPS = 4

export function startReveal(root: ParentNode = document): () => void {
  // jsdom has no matchMedia; old browsers have no IntersectionObserver.
  if (typeof window.matchMedia !== 'function' || typeof IntersectionObserver !== 'function') return () => {}
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return () => {}

  // Anything already on screen (a visitor landing on /#pricing) stays put.
  const fold = window.innerHeight
  const els = Array.from(root.querySelectorAll<HTMLElement>(REVEAL_SELECTOR))
    .filter(e => e.getBoundingClientRect().top > fold)

  const io = new IntersectionObserver(entries => {
    for (const en of entries) {
      if (!en.isIntersecting) continue
      en.target.classList.add('in')
      io.unobserve(en.target)
    }
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 })

  const targets = new Set(els)
  for (const e of els) {
    const row = Array.from(e.parentElement?.children ?? []).filter(s => targets.has(s as HTMLElement))
    e.style.transitionDelay = `${Math.min(row.indexOf(e), STAGGER_STEPS - 1) * STAGGER_MS}ms`
    e.classList.add('rv')
    io.observe(e)
  }

  return () => {
    io.disconnect()
    for (const e of els) { e.classList.remove('rv', 'in'); e.style.transitionDelay = '' }
  }
}
```

In `LandingPage.tsx`, add `import { startReveal } from './reveal'` and this effect beside the others:

```tsx
  // Spec §4 Motion: sections float in on scroll. Started once, after the first
  // render has put every section in the DOM.
  useEffect(() => startReveal(), [])
```

Append to `theme.css`:

```css
/* Spec §4 Motion. `.rv` is only ever added by reveal.ts, so without the script
 * nothing is hidden. */
.intrinsica .rv { opacity: 0; transform: translateY(32px);
  transition: opacity .7s cubic-bezier(.2,.7,.2,1), transform .7s cubic-bezier(.2,.7,.2,1); }
.intrinsica .rv.in { opacity: 1; transform: none; }
@media (prefers-reduced-motion: reduce) { .intrinsica .rv { opacity: 1; transform: none; transition: none; } }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/landing`
Expected: all green, including `funnel.test.tsx` unchanged (Review Focus 1).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/landing/reveal.ts frontend/src/landing/reveal.test.ts frontend/src/landing/LandingPage.tsx frontend/src/landing/LandingPage.test.tsx frontend/src/landing/theme.css
git commit -m "feat(landing): sections float in on scroll (once, staggered, off for reduced motion)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Share image and page metadata

**Files:**
- Create: `frontend/scripts/og-image.html` (the source of the image)
- Create: `frontend/public/og-image.png` (rendered from it, 1200 × 630)
- Modify: `frontend/index.html` (the `<head>`)
- Create: `frontend/src/landing/meta.test.ts`

**Interfaces:**
- Consumes: the brand-mark geometry from Task 2 (copied into the static HTML).
- Produces: `/og-image.png`, and the og/twitter tags.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/landing/meta.test.ts`:

```ts
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/landing/meta.test.ts`
Expected: FAIL. `og:title` is `undefined`, and `og-image.png` does not exist.

- [ ] **Step 3: Implement**

Add to `frontend/index.html` `<head>`, after `<title>Intrinsica</title>`:

```html
    <meta name="description" content="Intrinsica answers with four scores from the fundamentals: Quality, Moat, Fair Value and Reward/Risk. Every input and weight is on show." />
    <meta property="og:title" content="Intrinsica — Judge the business. Then judge the price." />
    <meta property="og:description" content="Intrinsica answers with four scores from the fundamentals: Quality, Moat, Fair Value and Reward/Risk. Every input and weight is on show." />
    <meta property="og:image" content="/og-image.png" />
    <meta property="og:type" content="website" />
    <meta name="twitter:card" content="summary_large_image" />
```

Create `frontend/scripts/og-image.html`:

```html
<!doctype html>
<!-- Source of public/og-image.png (spec §5.8). Re-render with the command in
     docs/superpowers/plans/2026-09-29-intrinsica-brand-round.md, Task 7. -->
<html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500&family=Space+Grotesk:wght@700&display=swap" rel="stylesheet">
<style>
  html, body { margin: 0; width: 1200px; height: 630px; background: #fdfcf9; overflow: hidden; }
  body { display: flex; flex-direction: column; justify-content: center; padding: 0 96px; box-sizing: border-box;
         font-family: Inter, sans-serif; color: #141414; border-top: 14px solid #0f5257; }
  .brand { display: flex; align-items: center; gap: 26px; font: 700 64px 'Space Grotesk', sans-serif; letter-spacing: -.02em; }
  h1 { font: 700 60px/1.1 'Space Grotesk', sans-serif; letter-spacing: -.02em; margin: 44px 0 20px; }
  p { font-size: 28px; color: #57534b; margin: 0; }
</style></head>
<body>
  <div class="brand">
    <svg width="160" height="160" viewBox="0 0 100 100">
      <defs>
        <linearGradient id="p" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#17696f"/><stop offset="1" stop-color="#0a3a3e"/></linearGradient>
        <clipPath id="k"><path d="M43.10 51.32 A15 15 0 1 1 56.90 51.32 L62 80 L38 80 Z"/></clipPath>
      </defs>
      <rect x="4" y="4" width="92" height="92" rx="22" fill="url(#p)"/>
      <g clip-path="url(#k)">
        <rect x="0" y="0" width="50" height="53" fill="#66fff7"/><rect x="50" y="0" width="50" height="53" fill="#3d8bff"/>
        <rect x="0" y="53" width="50" height="47" fill="#fae842"/><rect x="50" y="53" width="50" height="47" fill="#440ab8"/>
      </g>
      <path d="M43.10 51.32 A15 15 0 1 1 56.90 51.32 L62 80 L38 80 Z" fill="none" stroke="#8fc4c5" stroke-width="1.6" stroke-linejoin="round"/>
    </svg>
    Intrinsica
  </div>
  <h1>Judge the business. Then judge the price.</h1>
  <p>Quality · Moat · Fair Value · Reward/Risk — from the fundamentals, all shown.</p>
</body></html>
```

Render it (Windows, Git Bash). This needs network access for the Google Fonts:

```bash
cd frontend && "/c/Program Files/Google/Chrome/Application/chrome.exe" --headless=new --disable-gpu --hide-scrollbars \
  --window-size=1200,630 --virtual-time-budget=5000 \
  --screenshot="$(pwd -W)/public/og-image.png" "file:///$(pwd -W)/scripts/og-image.html"
```

Open `public/og-image.png` with the Read tool and check it visually. It should show the mark and the wordmark, the headline on one or two lines, and the subline, with nothing clipped and the fonts loaded (not a serif fallback). If the fonts did not load, raise `--virtual-time-budget` and render again.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/landing/meta.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html frontend/scripts/og-image.html frontend/public/og-image.png frontend/src/landing/meta.test.ts
git commit -m "feat(landing): static share image and og/twitter metadata

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Whole-branch verification in the real page

**Files:** none are created. Fixes land in the files of the task that owns them, with a failing test first.

**Interfaces:**
- Consumes: everything above.
- Produces: the verified branch.

- [ ] **Step 1: Run the full gate**

Run: `cd frontend && npx vitest run > ../.superpowers/brand-gate.log 2>&1; tail -5 ../.superpowers/brand-gate.log; npx tsc -b; npx eslint . | tail -3`
Expected:
- vitest: all files pass;
- tsc: no output;
- eslint: at most the 6 baseline problems, none of them in the files this plan touched.

- [ ] **Step 2: Look at the real page**

Start the dev servers with `cd backend && python -m uvicorn main:app --port 8000` and `cd frontend && npx vite --port 5173`. Then take full-page screenshots at 1440 px and at 390 px with headless Chrome: `--headless=new --screenshot --window-size=1440,6000 http://localhost:5173/`. Check them against spec §4 and §5 with the Read tool:
- **Nav:** the 42 px keyhole beside the wordmark.
- **Colours:**
  - teal buttons;
  - warm paper background;
  - Quality green, Moat azure, Fair Value gold and Reward/Risk violet, identical on the card and the Framework tabs.
- **Icons:** the bookmark on the card, chevrons on the tiles, teal checks on the plans.
- **Question band:** teal.
- **Framework:** rows collapsed, with the scale strip.
- **Pricing:** bold teal "Full / Yes" cells and the FREE badge.
- **Favicon:** the tab shows the keyhole.
- **Why section:** identical to before, emoji included.

Headless screenshots are taken without scrolling, and the reveal only hides blocks below the fold. So to see the sections themselves, take the screenshot with `--force-prefers-reduced-motion` (Chrome flag), or check the page in the companion. **Do not open extra browser windows for the user.**

- [ ] **Step 3: Report**

Tell the user what shipped, the gate results with numbers, and the screenshots checked. Nothing is pushed or merged; ask before either.

---

## Self-review notes (for the executor)

- **Spec coverage:**

  | Spec section | Task |
  |---|---|
  | §4 tokens and hard-coded colours | Task 1 |
  | §4 brand mark and favicon | Task 2 |
  | §4 line icons | Task 3 |
  | §4 rhythm (§5.4 band) | Task 1 |
  | §4 motion | Task 6 |
  | §5 nav logo | Task 2 |
  | §5.2 bookmark | Task 3 |
  | §5.4 paragraph | Task 4 |
  | §5.4 rows and strip | Tasks 4–5 |
  | §5.7 teal cells, badge and checks | Tasks 1 and 3 |
  | §5.8 share image and meta | Task 7 |
  | §11 tests | inside each task |

  The fonts are unchanged, so no task is needed for them.
- **Task 4 leaves `tsc` red until Task 5.** They are committed together on purpose.
