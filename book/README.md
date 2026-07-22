# Great Blue Heron Book Pipeline

Agno + Ollama Cloud multi-agent system that drafts, reviews, and revises the 24-chapter manuscript defined in `plan.md` until acceptance gates pass.

## Setup

```bash
cd book
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # if needed; set OLLAMA=your_key
```

Put your Ollama Cloud API key in `book/.env`:

```
OLLAMA=your_key_here
```

The runner maps `OLLAMA` → `OLLAMA_API_KEY` for Agno.

## Run with PM2

```bash
cd book
pm2 start ecosystem.config.cjs
pm2 logs blue-heron-book
```

The process loops until `state/DONE` is written, then exits `0` (PM2 stops restarting that run).

```bash
pm2 stop blue-heron-book
pm2 delete blue-heron-book
```

## Run without PM2

```bash
cd book
python runner.py
```

## Done criteria

- Chapter body 7,500–10,000 characters each
- Factcheck ≥90, history ≥92, museum ≥90, style ≥85
- Managing editor ≥90; recommendation not `rebuild`
- Style consistency ≥85; nonsense / fabricated-source rejects
- DuckDuckGo research enabled; agents cannot delete other agents’ files

## Layout

- `manuscript/chapters/` — **reader prose only** (the book)
- `manuscript/meta/` — photo recommendations, source ledger, character count, self-eval (not counted toward length)
- `reports/` — specialist reports
- `state/pipeline.json` — resume state
- `config.py` — model IDs and thresholds
- `runner.py` — PM2 entrypoint

Prose must be 7,500–10,000 characters of real museum paragraphs. Outline stubs and padding with recommendations will fail validation.

## Models

Configured in `config.py` (`MODELS`): gpt-oss:120b-cloud, deepseek-v4-pro:cloud, glm-5.2:cloud, nemotron-3-ultra:cloud, gemma4:cloud.
