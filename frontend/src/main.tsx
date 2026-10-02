import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { captureAttribution } from './lib/attribution'

// Before the router renders, so the arrival's tags are read and then cleaned out of
// the address bar (launch checklist B1).
captureAttribution()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
