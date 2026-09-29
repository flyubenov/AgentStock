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
