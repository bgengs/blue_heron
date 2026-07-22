"""Resume-safe pipeline state stored in book/state/pipeline.json."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from config import CHAPTER_COUNT, DONE_PATH, PIPELINE_STATE_PATH, ensure_dirs

Phase = Literal[
    "bootstrap",
    "draft",
    "review",
    "revise",
    "managing",
    "complete",
]


@dataclass
class ChapterState:
    drafted: bool = False
    dual_done: bool = False
    revision_round: int = 0
    body_chars: int = 0
    scores: dict[str, float] = field(default_factory=dict)
    fail_reasons: list[str] = field(default_factory=list)
    needs_revision: bool = False
    validation_ok: bool = False


@dataclass
class PipelineState:
    phase: Phase = "bootstrap"
    current_chapter: int = 1
    chapters: dict[str, ChapterState] = field(default_factory=dict)
    voice_bible_ready: bool = False
    managing_recommendation: str | None = None
    overall_score: float | None = None
    ticks: int = 0
    last_error: str | None = None
    updated_at: str = ""

    def chapter(self, n: int) -> ChapterState:
        key = f"{n:02d}"
        if key not in self.chapters:
            self.chapters[key] = ChapterState()
        return self.chapters[key]


def _chapter_from_dict(data: dict[str, Any]) -> ChapterState:
    return ChapterState(
        drafted=bool(data.get("drafted", False)),
        dual_done=bool(data.get("dual_done", False)),
        revision_round=int(data.get("revision_round", 0)),
        body_chars=int(data.get("body_chars", 0)),
        scores=dict(data.get("scores") or {}),
        fail_reasons=list(data.get("fail_reasons") or []),
        needs_revision=bool(data.get("needs_revision", False)),
        validation_ok=bool(data.get("validation_ok", False)),
    )


def default_state() -> PipelineState:
    st = PipelineState()
    for n in range(1, CHAPTER_COUNT + 1):
        st.chapter(n)
    return st


def load_state() -> PipelineState:
    ensure_dirs()
    if not PIPELINE_STATE_PATH.exists():
        return default_state()
    raw = json.loads(PIPELINE_STATE_PATH.read_text(encoding="utf-8"))
    chapters = {
        k: _chapter_from_dict(v) for k, v in (raw.get("chapters") or {}).items()
    }
    st = PipelineState(
        phase=raw.get("phase", "bootstrap"),
        current_chapter=int(raw.get("current_chapter", 1)),
        chapters=chapters,
        voice_bible_ready=bool(raw.get("voice_bible_ready", False)),
        managing_recommendation=raw.get("managing_recommendation"),
        overall_score=raw.get("overall_score"),
        ticks=int(raw.get("ticks", 0)),
        last_error=raw.get("last_error"),
        updated_at=raw.get("updated_at", ""),
    )
    for n in range(1, CHAPTER_COUNT + 1):
        st.chapter(n)
    return st


def save_state(state: PipelineState) -> None:
    ensure_dirs()
    state.updated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "phase": state.phase,
        "current_chapter": state.current_chapter,
        "chapters": {k: asdict(v) for k, v in state.chapters.items()},
        "voice_bible_ready": state.voice_bible_ready,
        "managing_recommendation": state.managing_recommendation,
        "overall_score": state.overall_score,
        "ticks": state.ticks,
        "last_error": state.last_error,
        "updated_at": state.updated_at,
    }
    PIPELINE_STATE_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def mark_done(message: str = "All acceptance criteria met.") -> None:
    ensure_dirs()
    DONE_PATH.write_text(
        f"{message}\n{datetime.now(timezone.utc).isoformat()}\n",
        encoding="utf-8",
    )


def is_done() -> bool:
    return DONE_PATH.exists()
