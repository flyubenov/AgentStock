import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// Self-hosted fonts (ticker links spec D11): bundled by Vite, so no request goes to
// Google. Only the weights the site uses.
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
import '@fontsource/inter/800.css'
import '@fontsource/space-grotesk/500.css'
import '@fontsource/space-grotesk/600.css'
import '@fontsource/space-grotesk/700.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@fontsource/jetbrains-mono/600.css'

import './index.css'
import App from './App'
import { captureAttribution } from './lib/attribution'
import { markOwnerFromUrl } from './lib/analytics'

// Before the router renders, so the arrival's tags (and the ?me owner marker) are read
// and then cleaned out of the address bar (launch checklist B1).
markOwnerFromUrl()
captureAttribution()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
