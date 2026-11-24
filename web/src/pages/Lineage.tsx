import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, STATIC, type Version } from '../api'
import { VerdictBadge } from './VerdictCard'

export default function Lineage() {
  const [vs, setVs] = useState<Version[] | null>(null)
  const [err, setErr] = useState('')
  const load = () => api.versions().then(setVs)
  useEffect(() => { load() }, [])
  if (!vs) return <p className="muted">Loading…</p>

  const depth = (v: Version): number => {
    const p = vs.find((x) => x.id === v.parent_id)
    return p ? depth(p) + 1 : 0
  }
  const ordered: Version[] = []
  const walk = (parent: number | null) => vs.filter((v) => v.parent_id === parent).forEach((v) => { ordered.push(v); walk(v.id) })
  walk(null)
  const models = Array.from(new Set(vs.flatMap((v) => Object.keys(v.scores))))

  const rollback = async (id: number) => {
    setErr('')
    try { await api.rollback(id); load() } catch (e) { setErr((e as Error).message) }
  }

  return (
    <div>
      <h1 style={{ marginTop: 18 }}>Lineage</h1>
      <p className="sub">Every version of the reference agent: its parent, the claim that caused it, its diff and its accuracy per model.</p>
      {err && <div className="error">{err}</div>}
      <div className="card">
        <table>
          <thead>
            <tr><th>Version</th><th>Caused by</th><th>Diff</th>{models.map((m) => <th key={m} className="num">{m}</th>)}<th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {ordered.map((v) => (
              <tr key={v.id}>
                <td><span className="tree-indent">{'· '.repeat(depth(v))}{depth(v) ? '└ ' : ''}</span><b>{v.label}</b></td>
                <td className="small">{v.card_id ? <Link to={`/claims/${v.card_id}`}>{v.lab}: {v.card_title}</Link> : <span className="muted">baseline</span>}</td>
                <td><code className="small">{v.diff.map((d) => `${d.path}: ${JSON.stringify(d.from)} → ${JSON.stringify(d.to)}`).join('; ') || '—'}</code></td>
                {models.map((m) => <td key={m} className="num">{v.scores[m] ? `${(v.scores[m].accuracy * 100).toFixed(0)}%` : '—'}</td>)}
                <td><span className={`badge ${v.status}`}>{v.status}</span> <VerdictBadge v={v.verdict} /></td>
                <td>{!STATIC && v.status === 'retired' && v.promoted_at && <button onClick={() => rollback(v.id)}>Roll back to this</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
