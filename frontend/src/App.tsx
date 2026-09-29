import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Progress from './pages/Progress'
import Results from './pages/Results'
import TickerDetail from './pages/TickerDetail'
import Database from './pages/Database'
import LandingPage from './landing/LandingPage'
import CheckoutPage from './landing/CheckoutPage'

/** The landing page owns `/` and renders outside Layout: Layout is the dark analyst
 *  chrome, and the landing page is light. The analyst app moves to /app.
 *
 *  `/checkout` is the landing page's own last step (spec 6) and belongs on the
 *  same light surface, so it renders outside Layout too. It is mounted here
 *  rather than nested under `/` because it is a separate page, not a section:
 *  LandingPage navigates to it from every plan CTA. */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/checkout" element={<CheckoutPage />} />
        <Route path="/app" element={<Layout><Home /></Layout>} />
        <Route path="/progress/:jobId" element={<Layout><Progress /></Layout>} />
        <Route path="/results/:jobId" element={<Layout><Results /></Layout>} />
        <Route path="/ticker/:jobId/:ticker" element={<Layout><TickerDetail /></Layout>} />
        <Route path="/database" element={<Layout><Database /></Layout>} />
      </Routes>
    </BrowserRouter>
  )
}
