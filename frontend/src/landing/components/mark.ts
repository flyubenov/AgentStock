/** The brand mark's geometry and colours (spec §4), kept apart from BrandMark.tsx
 *  so that file exports only its component (react-refresh). BrandMark.test.tsx
 *  checks the favicon against these same values. */

/** The keyhole outline: a round head over a tapered slot. It reads as a letter i. */
export const KEYHOLE = 'M43.10 51.32 A15 15 0 1 1 56.90 51.32 L62 80 L38 80 Z'

/** Spec §4. The logo keeps its own shades for Quality (aqua) and Fair Value
 *  (bright yellow): the page's green melts into the teal plate, and the page's
 *  gold would dull the light. Moat and Reward/Risk match the page tokens. */
export const MARK = {
  plateTop: '#17696f', plateBot: '#0a3a3e', rim: '#8fc4c5',
  q: '#66fff7', mo: '#3d8bff', fv: '#fae842', rr: '#440ab8',
} as const
