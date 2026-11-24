import { useEffect, useState } from 'react'
import { api, type Status } from '../api'

export default function RunPanel({ status }: { status: Status | null }) {
  const [models, setModels] = useState<string[]>([])
  const [runs, setRuns] = useState(2)
  const [maxCards, setMaxCards] = useState(3)
  const [live, setLive] = useState(false)
  const [err, setErr] = useState('')
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (status && models.length === 0) setModels(status.default_models)
  }, [status, models.length])

  if (!status) return null
  const running = status.cycle.running

  const start = async () => {
    setErr('')
    try {
      await api.startCycle({ models, runs, max_cards: maxCards, live, seeds: true })
      setOpen(true)
    } catch (e) {
      setErr((e as Error).message)
    }
  }

  return (
    <div className="card">
      <div className="row">
        <div className="grow">
          <b>Run a cycle</b>
          <div className="small muted">
            Scout → Extractor → Replicator → Adversary over {status.n_tasks} graded tasks. Nothing is promoted without you.
          </div>
        </div>
        <button onClick={() => setOpen(!open)}>{open ? 'Hide' : 'Options'}</button>
        <button className="primary" disabled={running || models.length === 0} onClick={start}>
          {running ? 'Running…' : 'Run cycle'}
        </button>
      </div>
      {err && <div className="error" style={{ marginTop: 10 }}>{err}</div>}
      {open && (
        <div style={{ marginTop: 12 }}>
          <div className="row" style={{ marginBottom: 8 }}>
            <span className="small muted">Models:</span>
            {status.models.map((m) => (
              <label key={m.id} title={m.available ? m.model : 'API key not set'}>
                <input type="checkbox" disabled={!m.available} checked={models.includes(m.id)}
                  onChange={(e) => setModels(e.target.checked ? [...models, m.id] : models.filter((x) => x !== m.id))} />{' '}
                {m.id}
              </label>
            ))}
          </div>
          <div className="row" style={{ marginBottom: 8 }}>
            <label>Runs per task <input type="number" min={1} max={5} value={runs} onChange={(e) => setRuns(+e.target.value)} style={{ width: 56 }} /></label>
            <label>Max cards <input type="number" min={1} max={10} value={maxCards} onChange={(e) => setMaxCards(+e.target.value)} style={{ width: 56 }} /></label>
            <label><input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} /> Fetch live lab sources</label>
          </div>
          {status.cycle.error && <div className="error">{status.cycle.error}</div>}
          {status.cycle.log.length > 0 && <pre className="log">{status.cycle.log.join('\n')}</pre>}
        </div>
      )}
    </div>
  )
}
