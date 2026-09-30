import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Progress from './pages/Progress'
import Results from './pages/Results'
import TickerDetail from './pages/TickerDetail'
import Database from './pages/Database'
import LandingPage from './landing/LandingPage'
import CheckoutPage from './landing/CheckoutPage'

/** Production builds set VITE_PUBLIC_MODE=1: intrinsica.io serves only the fake door.
 *  The Agent Stock analyst pages are not registered, and because Vite inlines this
 *  constant at build time Rollup drops them from the bundle. Every other path shows
 *  the landing page (future /t/{TICKER} share links included). Unset in local dev. */
const PUBLIC_MODE = import.meta.env.VITE_PUBLIC_MODE === '1'

/** The landing page owns `/` and renders outside Layout: Layout is the dark analyst
 *  chrome, and the landing page is light. The analyst app moves to /app.
 *
 *  `/checkout` is the landing page's own last step (spec 6) and belongs on the
 *  same light surface, so it renders outside Layout too. It is mounted here
 *  rather than nested under `/` because it is a separate page, not a section:
 *  LandingPage navigates to it from every plan CTA.
 *
 *  In public mode (production) only `/` and `/checkout` exist; see PUBLIC_MODE. */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/checkout" element={<CheckoutPage />} />
        {PUBLIC_MODE ? (
          <Route path="*" element={<LandingPage />} />
        ) : (
          <>
            <Route path="/app" element={<Layout><Home /></Layout>} />
            <Route path="/progress/:jobId" element={<Layout><Progress /></Layout>} />
            <Route path="/results/:jobId" element={<Layout><Results /></Layout>} />
            <Route path="/ticker/:jobId/:ticker" element={<Layout><TickerDetail /></Layout>} />
            <Route path="/database" element={<Layout><Database /></Layout>} />
          </>
        )}
      </Routes>
    </BrowserRouter>
  )
}
