import { Link } from 'react-router-dom'
import { pct, pts, type VerdictView } from '../api'

export function VerdictBadge({ v }: { v: string | null }) {
  if (!v) return null
  return <span className={`badge ${v.replace(/[^A-Za-z]/g, '')}`}>{v}</span>
}

export function ModelTable({ models }: { models: VerdictView['models'] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Model</th>
          <th className="num">Accuracy change</th>
          <th className="num">95% interval</th>
          <th className="num">Groundedness</th>
          <th className="num">Cost per task</th>
          <th className="num">Regressed tasks</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(models).map(([id, m]) => (
          <tr key={id}>
            <td>{id}{m.mock && <span className="muted small"> (mock)</span>}</td>
            <td className={`num ${m.delta > 0 ? 'pos' : m.delta < 0 ? 'neg' : ''}`}>{pts(m.delta)} pts</td>
            <td className="num muted">{pts(m.ci_low)} to {pts(m.ci_high)}</td>
            <td className="num">{pts(m.groundedness_delta)} pts</td>
            <td className={`num ${m.cost_increase > 0.5 ? 'neg' : ''}`}>{pct(m.cost_increase)}</td>
            <td className="num">{m.regressions}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function VerdictCard({ v, onDecide }: { v: VerdictView; onDecide?: (action: string) => void }) {
  return (
    <div className="card">
      <div className="row">
        <VerdictBadge v={v.verdict} />
        <div className="grow">
          <Link to={`/claims/${v.card_id}`}><b>{v.lab}: {v.title}</b></Link>{' '}
          <a className="small" href={v.url} target="_blank" rel="noreferrer">source ↗</a>
        </div>
        {v.decision && <span className={`badge ${v.decision}`}>{v.decision}</span>}
      </div>
      <p style={{ margin: '8px 0' }}>{v.claim}</p>
      <div className="small muted" style={{ marginBottom: 8 }}>
        Change tested: <code>{Object.entries(v.config_patch).map(([k, val]) => `${k} = ${JSON.stringify(val)}`).join(', ')}</code>
        {' · '}Source fidelity {(v.fidelity * 100).toFixed(0)}%
        {v.summary.model_specific && ' · Model-specific: helps some models, hurts others'}
      </div>
      <ModelTable models={v.models} />
      {onDecide && !v.decision && (
        <div className="row" style={{ marginTop: 12 }}>
          <button className="primary" disabled={v.verdict !== 'Replicated'} onClick={() => onDecide('promote')}
            title={v.verdict !== 'Replicated' ? 'Only replicated claims can be promoted' : ''}>
            Promote to reference
          </button>
          <button onClick={() => onDecide('publish')}>Publish verdict only</button>
          <button className="danger" onClick={() => onDecide('discard')}>Discard</button>
        </div>
      )}
    </div>
  )
}
