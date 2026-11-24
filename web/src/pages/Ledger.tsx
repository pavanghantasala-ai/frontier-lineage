import { useEffect, useState } from 'react'
import { api } from '../api'

export default function Ledger() {
  const [rows, setRows] = useState<any[] | null>(null)
  useEffect(() => { api.ledger().then(setRows) }, [])
  return (
    <div>
      <h1 style={{ marginTop: 18 }}>Decision ledger</h1>
      <p className="sub">Every card, version, verdict and human decision, newest first.</p>
      <div className="card">
        <table>
          <thead><tr><th>When</th><th>Kind</th><th>Target</th><th>Note</th></tr></thead>
          <tbody>
            {(rows ?? []).map((r) => (
              <tr key={r.id}><td className="small muted">{r.at.replace('T', ' ').slice(0, 19)}</td><td>{r.kind}</td><td>{r.target}</td><td>{r.note}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
