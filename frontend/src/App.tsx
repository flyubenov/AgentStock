import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Progress from './pages/Progress'
import Results from './pages/Results'
import TickerDetail from './pages/TickerDetail'
import Database from './pages/Database'
import JobStatus from './pages/JobStatus'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/progress/:jobId" element={<Progress />} />
          <Route path="/results/:jobId" element={<Results />} />
          <Route path="/jobs/:jobId" element={<JobStatus />} />
          <Route path="/ticker/:jobId/:ticker" element={<TickerDetail />} />
          <Route path="/database" element={<Database />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
