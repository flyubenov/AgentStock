/** The Share button's link and text (ticker links spec §6), tagged so whoever opens
 *  it is recorded as channel `share` (B1). The production build (VITE_PUBLIC_MODE=1)
 *  always links to the canonical site, whatever host the page is on. Any other build
 *  links to the address it is running on (user decision 2026-10-03), so a link
 *  shared from a local or preview build opens there rather than on production,
 *  which may not have the feature yet. Read at call time so tests can switch it. */
export function shareUrl(t: string): string {
  const site = import.meta.env.VITE_PUBLIC_MODE === '1' ? 'https://intrinsica.io' : window.location.origin
  return `${site}/t/${t}?ref=share`
}
export const shareText = (t: string) => `${t} on Intrinsica: quality business? Durable moat? Fair price?`
