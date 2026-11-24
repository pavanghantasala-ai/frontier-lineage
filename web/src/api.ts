export type ModelResult = {
  delta: number
  ci_low: number
  ci_high: number
  cost_increase: number
  groundedness_delta: number
  mock: boolean
  regressions: number
}

export type VerdictView = {
  verdict_id: number
  verdict: string
  decision: string | null
  published: boolean
  card_id: number
  title: string
  lab: string
  url: string
  claim: string
  config_patch: Record<string, unknown>
  fidelity: number
  models: Record<string, ModelResult>
  summary: { passed: string[]; positive: string[]; negative: string[]; model_specific: boolean; required_models: number }
  version_id: number
  parent_id: number
  decided_at?: string
}

export type Diff = {
  week: string
  reference: string
  mock: boolean
  shipped: { lab: string; title: string; url: string; status: string }[]
  replicated: VerdictView[]
  partial: VerdictView[]
  didnt_hold: VerdictView[]
  proposed_promotions: VerdictView[]
  pending: VerdictView[]
  spend_usd: number
  budget_usd: number
}

export type Status = {
  models: { id: string; provider: string; model: string; available: boolean; mock: boolean }[]
  default_models: string[]
  cycle: { running: boolean; log: string[]; error: string | null }
  reference: string
  spend_usd: number
  budget_usd: number
  n_tasks: number
  counts: Record<string, number>
  exported_at?: string
}

export type Card = {
  id: number
  item_id: number
  status: string
  created_at: string
  data: Record<string, any>
  verdict?: { id: number; verdict: string; decision: string | null; published: number } | null
}

export type Version = {
  id: number
  parent_id: number | null
  card_id: number | null
  label: string
  status: string
  created_at: string
  promoted_at: string | null
  diff: { path: string; from: unknown; to: unknown }[]
  config: Record<string, any>
  scores: Record<string, Record<string, any>>
  card_title: string | null
  lab: string | null
  verdict: string | null
  decision: string | null
}

export const STATIC = import.meta.env.VITE_STATIC === '1'

export type Item = {
  id: number
  lab: string
  title: string
  url: string
  published: string | null
  fetched_at: string
  status: string
  card_id: number | null
  verdict: string | null
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  if (STATIC) {
    if (init?.method && init.method !== 'GET') throw new Error('This is a read-only view.')
    path = `${import.meta.env.BASE_URL}data/${path.replace(/^\/api\//, '')}.json`
  }
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!r.ok) {
    let msg = r.statusText
    try {
      msg = (await r.json()).detail ?? msg
    } catch {
      /* not json */
    }
    throw new Error(msg)
  }
  const type = r.headers.get('content-type') ?? ''
  return (type.includes('json') ? r.json() : r.text()) as Promise<T>
}

export const api = {
  status: () => req<Status>('/api/status'),
  diff: () => req<Diff>('/api/diff'),
  diffMarkdown: () => req<string>('/api/diff/markdown'),
  scoreboard: () => req<VerdictView[]>('/api/scoreboard'),
  cards: () => req<Card[]>('/api/cards'),
  card: (id: number) => req<any>(`/api/cards/${id}`),
  versions: () => req<Version[]>('/api/versions'),
  ledger: () => req<any[]>('/api/ledger'),
  items: () => req<Item[]>('/api/items'),
  startCycle: (body: { models?: string[]; runs: number; max_cards: number; live: boolean; seeds: boolean }) =>
    req('/api/cycle', { method: 'POST', body: JSON.stringify(body) }),
  decide: (verdictId: number, action: string, note = '') =>
    req(`/api/verdicts/${verdictId}/decision`, { method: 'POST', body: JSON.stringify({ action, note }) }),
  rollback: (version_id: number) => req('/api/rollback', { method: 'POST', body: JSON.stringify({ version_id }) }),
  ingest: (url: string) => req<{ item_id: number }>('/api/ingest', { method: 'POST', body: JSON.stringify({ url }) }),
}

export const pts = (x: number) => `${x >= 0 ? '+' : ''}${(x * 100).toFixed(1)}`
export const pct = (x: number) => `${x >= 0 ? '+' : ''}${(x * 100).toFixed(0)}%`
