# 2026-07-21 — book-agno-pm2-pipeline

## Accomplished

Implemented the full Great Blue Heron book agent pipeline under `book/` per the Agno + Ollama Cloud + PM2 plan.

### Added

- `book/config.py` — paths, model IDs, gates, dual-draft chapter set, nonsense blocklist
- `book/models.py` — loads `book/.env`, maps `OLLAMA` → `OLLAMA_API_KEY`, Agno `Ollama` factory
- `book/prompts.py` — parses `plan.md` into master + 24 chapter + 6 specialist prompts
- `book/tools/files.py` — scoped read/write/append toolkit (**no delete**); write allowlist per agent
- `book/tools/research.py` — Agno `DuckDuckGoTools` wrapper
- `book/tools/validate.py` — length, structure, source-ledger, nonsense, score parsers
- `book/agents/chapter.py` — chapter writers, dual-draft, merge agents
- `book/agents/specialists.py` — agents 25–30
- `book/pipeline/state.py` — resume-safe `state/pipeline.json` + `DONE`
- `book/pipeline/gates.py` — acceptance criteria evaluation
- `book/pipeline/orchestrator.py` — tick loop: draft → review → revise → managing → complete
- `book/runner.py` — PM2 entrypoint; `python runner.py --status`
- `book/ecosystem.config.cjs`, `requirements.txt`, `.env.example`, `README.md`

### Gates

Science ≥90, history ≥92, museum ≥90, style ≥85, managing ≥90; chapter body 7,500–10,000 chars; anti-hallucination blocklist; no cross-agent deletes.

### How to run

```bash
cd book
pip install -r requirements.txt
pm2 start ecosystem.config.cjs
```

### Next enhancements

- Add structured JSON output schemas (Pydantic) for specialist scores to reduce parse misses
- Optional rate-limit / concurrency controls for Ollama Cloud quotas
- Wire Agent 29 more tightly to `data/photos.json` inventory
- Export final manuscript binder (single markdown/PDF) when `DONE` is written
