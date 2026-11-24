import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, pts, type VerdictView } from '../api'
import { VerdictBadge } from './VerdictCard'

export default function Scoreboard() {
  const [rows, setRows] = useState<VerdictView[] | null>(null)
  useEffect(() => { api.scoreboard().then(setRows) }, [])
  if (!rows) return <p className="muted">Loading…</p>
  const models = Array.from(new Set(rows.flatMap((r) => Object.keys(r.models))))
  return (
    <div>
      <h1 style={{ marginTop: 18 }}>Scoreboard</h1>
      <p className="sub">Published verdicts: which frontier lab claims held on our task suite, per model, with the test fixed before running.</p>
      {rows.length === 0 ? (
        <p className="muted">No published verdicts yet. Publish or promote one from the Frontier Diff.</p>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Verdict</th><th>Claim</th>
                {models.map((m) => <th key={m} className="num">{m}</th>)}
                <th>Decided</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.verdict_id}>
                  <td><VerdictBadge v={r.verdict} /></td>
                  <td>
                    <Link to={`/claims/${r.card_id}`}>{r.lab}: {r.title}</Link>
                    <div className="small muted">{r.claim}</div>
                  </td>
                  {models.map((m) => {
                    const x = r.models[m]
                    return <td key={m} className={`num ${x && x.delta > 0 ? 'pos' : x && x.delta < 0 ? 'neg' : ''}`}>{x ? `${pts(x.delta)}` : '—'}</td>
                  })}
                  <td className="small muted">{r.decided_at?.slice(0, 10)} · {r.decision}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="small muted">Accuracy change in points versus the parent version.</p>
        </div>
      )}
    </div>
  )
}
