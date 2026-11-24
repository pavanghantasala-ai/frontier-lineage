import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Card } from '../api'
import { VerdictBadge } from './VerdictCard'

export default function Claims() {
  const [cards, setCards] = useState<Card[] | null>(null)
  const [url, setUrl] = useState('')
  const [msg, setMsg] = useState('')
  const load = () => api.cards().then(setCards)
  useEffect(() => { load() }, [])

  const ingest = async () => {
    setMsg('')
    try {
      const r = await api.ingest(url)
      setMsg(`Added as item ${r.item_id}. It becomes a claim card on the next cycle.`)
      setUrl('')
    } catch (e) {
      setMsg((e as Error).message)
    }
  }

  return (
    <div>
      <h1 style={{ marginTop: 18 }}>Claim cards</h1>
      <p className="sub">Each card is one technique from a lab post: the claim, how to test it, and the threshold it must clear.</p>
      <div className="card row">
        <input type="text" className="grow" placeholder="Paste a lab post URL to test it" value={url} onChange={(e) => setUrl(e.target.value)} />
        <button className="primary" disabled={!url} onClick={ingest}>Add post</button>
        {msg && <div className="small muted" style={{ width: '100%' }}>{msg}</div>}
      </div>
      {!cards ? <p className="muted">Loading…</p> : cards.length === 0 ? <p className="muted">No cards yet. Run a cycle.</p> : (
        <div className="card">
          <table>
            <thead><tr><th>Card</th><th>Change</th><th>Status</th><th>Verdict</th></tr></thead>
            <tbody>
              {cards.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link to={`/claims/${c.id}`}>{c.data.lab}: {c.data.title}</Link>
                    <div className="small muted">{c.data.claim}</div>
                  </td>
                  <td><code className="small">{Object.entries(c.data.config_patch ?? {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ') || '—'}</code></td>
                  <td className="small muted">{c.status.replace(/_/g, ' ')}</td>
                  <td><VerdictBadge v={c.verdict?.verdict ?? null} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
