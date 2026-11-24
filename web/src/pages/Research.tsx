import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Item } from '../api'
import { VerdictBadge } from './VerdictCard'

const STATUS: Record<string, string> = {
  new: 'queued',
  carded: 'claim extracted',
  not_technique: 'no testable technique',
}

export default function Research() {
  const [items, setItems] = useState<Item[] | null>(null)
  const [lab, setLab] = useState('All')
  useEffect(() => { api.items().then(setItems) }, [])
  if (!items) return <p className="muted">Loading…</p>
  const labs = ['All', ...Array.from(new Set(items.map((i) => i.lab)))]
  const shown = items.filter((i) => lab === 'All' || i.lab === lab)
  return (
    <div>
      <h1 style={{ marginTop: 18 }}>Research feed</h1>
      <p className="sub">Everything the Scout has read from frontier labs, and what happened to it.</p>
      <div className="row" style={{ marginBottom: 12 }}>
        {labs.map((l) => (
          <button key={l} className={l === lab ? 'primary' : ''} onClick={() => setLab(l)}>{l}</button>
        ))}
      </div>
      <div className="card">
        <table>
          <thead><tr><th>Lab</th><th>Post</th><th>Status</th><th>Verdict</th></tr></thead>
          <tbody>
            {shown.map((i) => (
              <tr key={i.id}>
                <td className="small">{i.lab}</td>
                <td>
                  <a href={i.url} target="_blank" rel="noreferrer">{i.title || i.url}</a>
                  {i.published && <span className="small muted"> · {i.published.slice(0, 16)}</span>}
                </td>
                <td className="small muted">
                  {i.card_id ? <Link to={`/claims/${i.card_id}`}>{STATUS[i.status] ?? i.status}</Link> : STATUS[i.status] ?? i.status}
                </td>
                <td><VerdictBadge v={i.verdict} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
