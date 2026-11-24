# Frontier Lineage

A self-driving lab that reads what frontier labs publish, implements each technique against a fixed reference agent, tests it across models against a pre-registered bar, and publishes the verdict. A human approves every promotion.

```
Scout ──► Extractor ──► Replicator ──► Adversary ──► Frontier Diff ──► you
lab feeds   claim card     candidate      paired evals    weekly page      publish / promote /
+ seeds     + test plan    version        across models                    discard / roll back
```

- **Scout** pulls Anthropic, OpenAI, Google DeepMind, Google Research, Hugging Face, Cursor, Cognition and Sierra posts (`backend/data/sources.json`), plus six offline seed posts.
- **Extractor** turns a post into a claim card: the claim, mechanism, a config patch for the reference agent, verbatim source quotes (scored for fidelity), and the pass bar, fixed before any eval runs. Uses the first working LLM, otherwise rule-based fallback.
- **Replicator** applies the patch to the current reference version and stores the candidate with its parent and diff.
- **Adversary** runs parent and candidate on the graded task suite on each model, computes paired per-task deltas with 95% bootstrap intervals, checks groundedness and cost guards, and returns **Replicated** (passes on at least 2 models), **Partial** or **Didn't hold**. Spend is capped per week (`WEEKLY_BUDGET_USD`).
- **Frontier Diff** is the weekly page: what shipped, what held, what didn't, and what's waiting for your decision.

The reference agent is an internal-policy assistant for a fictional bank over 10 policy docs (`backend/data/corpus`) with 41 graded tasks (policy Q&A, multi-hop, and questions it should refuse). Its knobs: quote-first prompting, citations, abstention, few-shot examples, retrieval top-k, chunk size, contextual chunks, query rewriting and self-check.

## Models

Configured in `backend/data/models.json`. A model is used when its key is set (or, for local models, when its endpoint answers):

| id | provider | needs |
|---|---|---|
| `gpt` | OpenAI `gpt-4.1-mini` | `OPENAI_API_KEY` |
| `claude` | Anthropic `claude-sonnet-4-5` | `ANTHROPIC_API_KEY` with credit |
| `qwen-local` | open weights `qwen2.5:1.5b` via [Ollama](https://ollama.com) | `ollama pull qwen2.5:1.5b` (override URL with `OLLAMA_BASE_URL`) |
| `llama-groq` | open weights `llama-3.3-70b-versatile` via Groq | `GROQ_API_KEY` |
| `gemini` | Google `gemini-2.5-flash` | `GEMINI_API_KEY` |
| `mock-*` | deterministic offline models | nothing |

Any OpenAI-compatible endpoint (vLLM, Together, OpenRouter) works by adding an `openai_compat` entry. Models whose calls fail (bad key, no credit) are dropped at the start of each cycle. Mock results are labeled in the UI and should not be published.

## Run it

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cd web && npm install && npm run build && cd ..

cd backend
uvicorn lineage.api:app --port 8000      # app at http://localhost:8000
```

For frontend development run `npm run dev` in `web/` (proxies `/api` to port 8000).

CLI:

```bash
cd backend
python -m lineage.cli cycle --models gpt,qwen-local --runs 2 --max-cards 4   # add --live for live lab feeds
python -m lineage.cli verdicts
python -m lineage.cli diff                                                  # Frontier Diff as Markdown
python -m lineage.cli reset
```

The database lives at `backend/lineage.db` (override with `LINEAGE_DB`).

## Tests

```bash
cd backend && python -m pytest -q
cd web && npm run lint && npm run build
```

## Public read-only site

`scripts/build_public.sh <out_dir>` exports a sanitized JSON snapshot of the lab (`python -m lineage.cli export`) and builds the web app in static mode (`VITE_STATIC=1`, hash routing, base path `VITE_BASE`, default `/lineage/`). The static build has no run, publish, promote or rollback controls and contains no article bodies or API keys.

`.github/workflows/weekly.yml` runs every Monday: it starts Qwen 2.5 under Ollama, runs a live cycle on GPT-4.1-mini and Qwen, commits the lab state in `backend/state/lineage.db`, then rebuilds `pavanghantasala.com/lineage` by pushing to `pavan-site`. It needs two repo secrets: `OPENAI_API_KEY` and `SITE_TOKEN` (a fine-grained token with Contents read/write on `pavan-site`). Verdicts still need a human review in the private app before anything is promoted.
