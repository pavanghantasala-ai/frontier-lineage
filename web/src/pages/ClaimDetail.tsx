import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, pct, pts } from '../api'
import { VerdictBadge } from './VerdictCard'

export default function ClaimDetail() {
  const { id } = useParams()
  const [c, setC] = useState<any>(null)
  useEffect(() => { api.card(Number(id)).then(setC) }, [id])
  if (!c) return <p className="muted">Loading…</p>
  const d = c.data
  const v = c.verdict
  return (
    <div>
      <p className="small" style={{ marginTop: 18 }}><Link to="/claims">← All claims</Link></p>
      <div className="row">
        <h1 className="grow">{d.lab}: {d.title}</h1>
        <VerdictBadge v={v?.verdict ?? null} />
      </div>
      <p className="sub"><a href={d.url} target="_blank" rel="noreferrer">{d.url}</a>{d.published ? ` · ${d.published}` : ''}</p>
      <div className="grid2">
        <div className="card">
          <dl className="kv">
            <dt>Claim</dt><dd>{d.claim}</dd>
            <dt>Mechanism</dt><dd>{d.mechanism}</dd>
            <dt>Test plan</dt><dd>{d.test_plan}</dd>
            <dt>Needs</dt><dd>{d.requirements}</dd>
            <dt>Effort / impact</dt><dd>{d.effort} / {d.expected_impact} of 5</dd>
            <dt>Change</dt><dd><code>{JSON.stringify(d.config_patch)}</code></dd>
            {d.untestable_reason && <><dt>Not testable</dt><dd>{d.untestable_reason}</dd></>}
            <dt>Extracted by</dt><dd>{d.extractor}</dd>
          </dl>
        </div>
        <div className="card">
          <b>Pre-registered test</b>
          <p className="small muted">Fixed before any eval ran.</p>
          <dl className="kv">
            <dt>Primary metric</dt><dd>{d.primary_metric}</dd>
            <dt>Must improve by</dt><dd>{(d.min_delta * 100).toFixed(0)} pts, with the 95% interval above zero</dd>
            <dt>Groundedness</dt><dd>may drop at most {(d.max_groundedness_drop * 100).toFixed(0)} pts</dd>
            <dt>Cost</dt><dd>may rise at most {(d.max_cost_increase * 100).toFixed(0)}%</dd>
            <dt>Replicated if</dt><dd>it passes on at least 2 models</dd>
          </dl>
          {d.fidelity == null ? <>
            <b style={{ display: 'block', marginTop: 14 }}>Supporting passages (paraphrased)</b>
            <p className="small muted">Extracted from a summary of the post, not the full text, so these are paraphrases. Read the source for the exact wording.</p>
          </> : <>
            <b style={{ display: 'block', marginTop: 14 }}>Source fidelity {(d.fidelity * 100).toFixed(0)}%</b>
            <p className="small muted">Share of supporting quotes found verbatim in the post.</p>
          </>}
          {(d.source_quotes ?? []).map((q: string, i: number) => <blockquote key={i} className="small" style={{ margin: '6px 0', paddingLeft: 10, borderLeft: '3px solid var(--line)' }}>{q}</blockquote>)}
        </div>
      </div>
      {v && (
        <div className="card">
          <b>Adversary results</b> <span className="small muted">({v.details.runs} runs per task, versions {v.parent_id} → {v.version_id})</span>
          <table style={{ marginTop: 8 }}>
            <thead><tr><th>Model</th><th className="num">Parent → candidate</th><th className="num">Change (95% CI)</th><th className="num">Policy Q&A</th><th className="num">Multi-hop</th><th className="num">Refusals</th><th className="num">Cost</th><th>Guards</th></tr></thead>
            <tbody>
              {Object.entries<any>(v.details.comparisons).map(([m, x]) => (
                <tr key={m}>
                  <td>{m}{x.mock && <span className="muted small"> (mock)</span>}</td>
                  <td className="num">{(x.parent_accuracy * 100).toFixed(0)}% → {(x.candidate_accuracy * 100).toFixed(0)}%</td>
                  <td className="num">{pts(x.accuracy.delta)} ({pts(x.accuracy.ci_low)}, {pts(x.accuracy.ci_high)})</td>
                  <td className="num">{pts(x.by_type.policy_qa ?? 0)}</td>
                  <td className="num">{pts(x.by_type.multi_hop ?? 0)}</td>
                  <td className="num">{pts(x.by_type.refusal ?? 0)}</td>
                  <td className="num">{pct(x.cost_increase)}</td>
                  <td>{x.guards_ok ? <span className="pos">ok</span> : <span className="neg">failed</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {Object.entries<any>(v.details.comparisons).some(([, x]) => x.regressions.length > 0) && (
            <p className="small muted" style={{ marginTop: 10 }}>
              Regression cases (tasks the candidate got wrong more often than its parent):{' '}
              {Array.from(new Set(Object.values<any>(v.details.comparisons).flatMap((x) => x.regressions.map((r: any) => r.task_id)))).join(', ')}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
