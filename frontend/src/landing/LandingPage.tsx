import { useEffect } from 'react'
import './theme.css'
import Nav from './components/Nav'
import SiteFooter from './components/SiteFooter'
import { track, EVENTS } from '../lib/analytics'

export default function LandingPage() {
  useEffect(() => {
    track(EVENTS.pageView)
  }, [])

  // index.css sets a global dark body background; the elastic overscroll gutter
  // (below short content, and the rubber-band area past the top/bottom on touch
  // devices) shows through the .intrinsica wrapper straight to that dark body. Set
  // the body background to match this page's own light background while mounted,
  // and restore whatever was there before on unmount so the dark analyst app gets
  // its background back untouched.
  useEffect(() => {
    const previous = document.body.style.backgroundColor
    document.body.style.backgroundColor = '#ffffff'
    return () => {
      document.body.style.backgroundColor = previous
    }
  }, [])

  return (
    <div className="intrinsica">
      <Nav />
      <main>
        {/* Hero, results, methodology, why, workflow and pricing are added by the
            tasks that follow; each mounts into this main element. */}
      </main>
      <SiteFooter />
    </div>
  )
}
