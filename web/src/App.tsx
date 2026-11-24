import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { api, STATIC, type Status } from './api'
import Research from './pages/Research'
import DiffPage from './pages/DiffPage'
import Scoreboard from './pages/Scoreboard'
import Claims from './pages/Claims'
import ClaimDetail from './pages/ClaimDetail'
import Lineage from './pages/Lineage'
import Ledger from './pages/Ledger'
import RunPanel from './pages/RunPanel'

export default function App() {
  const [status, setStatus] = useState<Status | null>(null)
  const [tick, setTick] = useState(0)
  const running = status?.cycle.running

  useEffect(() => {
    let alive = true
    const load = () => api.status().then((s) => alive && setStatus(s)).catch(() => {})
    load()
    if (STATIC) return
    const t = setInterval(load, running ? 1500 : 6000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [running])

  useEffect(() => {
    if (running === false) setTick((t) => t + 1)
  }, [running])

  const mockOnly = status ? status.default_models.every((id) => status.models.find((m) => m.id === id)?.mock) : false

  return (
    <div className="shell">
      <header className="top">
        <div className="brand">
          Frontier Lineage<small>Replicating frontier lab techniques, one verdict at a time</small>
        </div>
        <nav>
          <NavLink to="/" end>Frontier Diff</NavLink>
          <NavLink to="/research">Research</NavLink>
          <NavLink to="/scoreboard">{STATIC ? 'Verdicts' : 'Scoreboard'}</NavLink>
          <NavLink to="/claims">Claims</NavLink>
          <NavLink to="/lineage">Lineage</NavLink>
          <NavLink to="/ledger">Ledger</NavLink>
        </nav>
        {status && (
          <div className="status-pill">
            <span>Reference <b>{status.reference}</b></span>
            <span>Spend ${status.spend_usd.toFixed(2)} / ${status.budget_usd.toFixed(0)}</span>
            {status.cycle.running && <span className="badge candidate">Cycle running</span>}
          </div>
        )}
      </header>
      {STATIC && (
        <div className="card intro">
          <b>Live, read-only view of my lab.</b> Each week it reads what Anthropic, OpenAI, Google DeepMind and other labs
          publish, turns each technique into a testable claim, applies it to my reference agent, and checks whether it
          measurably helps on GPT-4.1-mini and the open-weights Qwen 2.5. I review every verdict before a change is
          promoted.{' '}
          <a href="https://pavanghantasala.com/lab/posts/frontier-lineage.html">How it works →</a>
          {status?.exported_at && <span className="muted small"> · Updated {status.exported_at.slice(0, 10)}</span>}
        </div>
      )}
      {mockOnly && (
        <div className="banner">
          No model API key with credit is available, so evals run on the deterministic mock model. Verdicts are
          labeled "mock" and are for exercising the loop, not for publishing.
        </div>
      )}
      <Routes>
        <Route path="/" element={<>{!STATIC && <RunPanel status={status} />}<DiffPage key={tick} /></>} />
        <Route path="/research" element={<Research key={tick} />} />
        <Route path="/scoreboard" element={<Scoreboard key={tick} />} />
        <Route path="/claims" element={<Claims key={tick} />} />
        <Route path="/claims/:id" element={<ClaimDetail />} />
        <Route path="/lineage" element={<Lineage key={tick} />} />
        <Route path="/ledger" element={<Ledger key={tick} />} />
      </Routes>
    </div>
  )
}
