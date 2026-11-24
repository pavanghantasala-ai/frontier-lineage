import { useEffect, useState } from 'react'
import { api, STATIC, type Diff } from '../api'
import VerdictCard from './VerdictCard'

export default function DiffPage() {
  const [d, setD] = useState<Diff | null>(null)
  const [err, setErr] = useState('')
  const [copied, setCopied] = useState(false)
  const load = () => api.diff().then(setD).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])

  const decide = async (id: number, action: string) => {
    setErr('')
    try {
      await api.decide(id, action)
      load()
    } catch (e) {
      setErr((e as Error).message)
    }
  }
  const copy = async () => {
    await navigator.clipboard.writeText(await api.diffMarkdown())
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  if (!d) return err ? <div className="error">{err}</div> : <p className="muted">Loading…</p>
  const decided = [...d.replicated, ...d.partial, ...d.didnt_hold].filter((v) => v.decision)

  return (
    <div>
      <div className="row" style={{ marginTop: 18 }}>
        <div className="grow">
          <h1>Frontier Diff · {d.week}</h1>
          <p className="sub">{STATIC ? 'This week: agents scouted, implemented and tested these claims. A human decides what ships.' : 'Your weekly gate. Agents scouted, implemented and tested; you publish verdicts and promote versions.'}</p>
        </div>
        {!STATIC && <button onClick={copy}>{copied ? 'Copied' : 'Copy as Markdown'}</button>}
      </div>
      {err && <div className="error">{err}</div>}
      <div className="stats">
        <div className="stat"><b>{d.shipped.length}</b><span>posts scouted</span></div>
        <div className="stat"><b>{d.replicated.length}</b><span>replicated</span></div>
        <div className="stat"><b>{d.partial.length}</b><span>partly held</span></div>
        <div className="stat"><b>{d.didnt_hold.length}</b><span>didn't hold</span></div>
        <div className="stat"><b>{d.reference}</b><span>reference agent</span></div>
      </div>

      <h2>{STATIC ? 'Awaiting review' : 'Waiting for your decision'} ({d.pending.length})</h2>
      {d.pending.length === 0 && <p className="muted small">Nothing pending. Run a cycle to test new claims.</p>}
      {d.pending.map((v) => <VerdictCard key={v.verdict_id} v={v} onDecide={STATIC ? undefined : (a) => decide(v.verdict_id, a)} />)}

      {decided.length > 0 && (
        <>
          <h2>Decided this week</h2>
          {decided.map((v) => <VerdictCard key={v.verdict_id} v={v} />)}
        </>
      )}

      <h2>What shipped</h2>
      <div className="card">
        <table>
          <thead><tr><th>Lab</th><th>Post</th><th>Status</th></tr></thead>
          <tbody>
            {d.shipped.map((i) => (
              <tr key={i.url}>
                <td>{i.lab}</td>
                <td><a href={i.url} target="_blank" rel="noreferrer">{i.title || i.url}</a></td>
                <td className="muted small">{i.status.replace('_', ' ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
