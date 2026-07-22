# 2026-07-22 — ddg-search-resilience

## Problem

PM2 `blue-heron-book` agents failed on `web_search` with `ddgs.exceptions.DDGSException: No results found` when DuckDuckGo HTML returned HTTP 202 / empty.

## Fix

- Replaced Agno `DuckDuckGoTools` with custom `ResilientSearchTools` in `book/tools/research.py`
- Tries backends in order: `auto`, `duckduckgo`, `bing`, `brave`, `yahoo`, `google`
- Soft-fails with JSON guidance instead of raising (agents continue via local guide + known institutions; no invented URLs)
- Updated chapter/specialist instructions not to retry search endlessly

## Verify

```bash
cd book
python -c "from tools.research import make_search_tools; print(make_search_tools().web_search('Ardea herodias USGS')[:400])"
pm2 restart blue-heron-book
```
