"""Resilient web search — tries multiple backends; never raises to the agent."""

from __future__ import annotations

import json
import time
from typing import Any, List, Optional

from agno.tools import Toolkit
from agno.utils.log import log_debug, log_warning

try:
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException
except ImportError as e:
    raise ImportError("`ddgs` not installed. Please install using `pip install ddgs`") from e

# Prefer auto, then named backends when DDG HTML returns 202/empty.
_BACKENDS = ("auto", "duckduckgo", "bing", "brave", "yahoo", "google")


class ResilientSearchTools(Toolkit):
    """Web search that swallows DDGS failures and falls back across backends."""

    def __init__(
        self,
        enable_search: bool = True,
        enable_news: bool = False,
        fixed_max_results: int = 8,
        timeout: int = 25,
        region: str = "us-en",
        **kwargs,
    ):
        self.fixed_max_results = fixed_max_results
        self.timeout = timeout
        self.region = region
        tools: List[Any] = []
        if enable_search:
            tools.append(self.web_search)
        if enable_news:
            tools.append(self.search_news)
        super().__init__(name="resilient_websearch", tools=tools, **kwargs)

    def web_search(self, query: str, max_results: int = 5) -> str:
        """Search the web for sources. Returns JSON results or a soft-failure message.

        If search is unavailable, continue using local field-guide notes and well-known
        institutional references; do not invent URLs or DOIs.
        """
        limit = self.fixed_max_results or max_results
        results, tried = self._search_text(query, limit)
        if results:
            return json.dumps(results, indent=2, ensure_ascii=False)

        # Simplify query and retry once
        simplified = " ".join(query.replace('"', "").split()[:8])
        if simplified and simplified != query:
            results, tried2 = self._search_text(simplified, limit)
            tried.extend(tried2)
            if results:
                return json.dumps(results, indent=2, ensure_ascii=False)

        payload = {
            "ok": False,
            "query": query,
            "results": [],
            "tried_backends": tried,
            "message": (
                "Web search returned no results (rate limit, block, or empty). "
                "Continue without live search: ground claims in local content/guide notes "
                "and cite only well-known institutional sources you can name accurately "
                "(e.g. USGS, USFWS, Birds of the World / Cornell Lab, museum monographs). "
                "Do not invent URLs, DOIs, quotations, or specific study findings."
            ),
        }
        log_warning("web_search soft-fail for %r backends=%s", query, tried)
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def search_news(self, query: str, max_results: int = 5) -> str:
        """Search news. Soft-fails like web_search."""
        limit = self.fixed_max_results or max_results
        results, tried = self._search_news(query, limit)
        if results:
            return json.dumps(results, indent=2, ensure_ascii=False)
        return json.dumps(
            {
                "ok": False,
                "query": query,
                "results": [],
                "tried_backends": tried,
                "message": "News search unavailable; skip news citations.",
            },
            indent=2,
            ensure_ascii=False,
        )

    def _search_text(self, query: str, limit: int) -> tuple[list[dict], list[str]]:
        tried: list[str] = []
        for backend in _BACKENDS:
            tried.append(backend)
            try:
                log_debug("search backend=%s query=%r", backend, query)
                with DDGS(timeout=self.timeout) as ddgs:
                    raw = ddgs.text(
                        query,
                        max_results=limit,
                        backend=backend,
                        region=self.region,
                    )
                if raw:
                    return list(raw), tried
            except DDGSException as e:
                log_warning("DDGS %s: %s", backend, e)
            except Exception as e:
                log_warning("search backend %s error: %s", backend, e)
            time.sleep(0.4)
        return [], tried

    def _search_news(self, query: str, limit: int) -> tuple[list[dict], list[str]]:
        tried: list[str] = []
        for backend in _BACKENDS:
            tried.append(backend)
            try:
                with DDGS(timeout=self.timeout) as ddgs:
                    raw = ddgs.news(
                        query,
                        max_results=limit,
                        backend=backend,
                        region=self.region,
                    )
                if raw:
                    return list(raw), tried
            except Exception as e:
                log_warning("news backend %s error: %s", backend, e)
            time.sleep(0.4)
        return [], tried


def make_search_tools(enable_news: bool = False) -> ResilientSearchTools:
    """Factory used by chapter and specialist agents."""
    return ResilientSearchTools(
        enable_search=True,
        enable_news=enable_news,
        fixed_max_results=8,
        timeout=25,
        region="us-en",
    )
