"""Acceptance gates for chapters and the full manuscript."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from config import (
    CHAPTER_COUNT,
    GATE_HISTORY,
    GATE_MANAGING,
    GATE_MUSEUM,
    GATE_SCIENCE,
    GATE_STYLE,
    GATE_STYLE_CONSISTENCY,
    MANUSCRIPT_CHARS_MAX,
    MANUSCRIPT_CHARS_MIN,
    chapter_path,
    report_path,
)
from pipeline.state import ChapterState, PipelineState
from prompts import load_chapter_specs
from tools.validate import (
    extract_keywords_from_prompt,
    parse_recommendation,
    parse_scores_from_report,
    validate_chapter_file,
)


@dataclass
class GateResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)

    def fail(self, reason: str) -> None:
        self.ok = False
        self.reasons.append(reason)


def refresh_chapter_validation(state: PipelineState, n: int) -> GateResult:
    spec = load_chapter_specs()[n - 1]
    keywords = extract_keywords_from_prompt(spec.prompt)
    path = chapter_path(n)
    vr = validate_chapter_file(path, keywords)
    ch = state.chapter(n)
    ch.body_chars = vr.body_chars
    ch.validation_ok = vr.ok
    ch.fail_reasons = list(vr.reasons)
    if not vr.ok:
        ch.needs_revision = True
    result = GateResult(ok=vr.ok, reasons=list(vr.reasons))
    return result


def ingest_specialist_scores(
    state: PipelineState,
    kind: str,
    chapter_number: int | None = None,
) -> None:
    path = report_path(kind, chapter_number)
    if not path.exists():
        # try book-wide
        path = report_path(kind, None)
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    scores = parse_scores_from_report(text)
    for key, val in scores.items():
        if key.startswith("ch-"):
            n = int(key.split("-")[1])
            state.chapter(n).scores[kind] = val
        elif key == "overall" and kind == "style":
            state.chapter(1).scores["style_consistency"] = val
        elif key == "overall" and kind == "managing":
            state.overall_score = val

    if kind == "managing":
        rec = parse_recommendation(text)
        if rec:
            state.managing_recommendation = rec


def chapter_passes_specialist_gates(ch: ChapterState) -> GateResult:
    result = GateResult(ok=True)
    if not ch.validation_ok:
        result.fail("Structural / length / nonsense validation failed")
        for r in ch.fail_reasons:
            result.fail(r)
    checks = [
        ("factcheck", GATE_SCIENCE, "science/factcheck"),
        ("history", GATE_HISTORY, "history"),
        ("museum", GATE_MUSEUM, "museum"),
        ("style", GATE_STYLE, "style"),
        ("managing", GATE_MANAGING, "managing editor"),
    ]
    for key, threshold, label in checks:
        if key not in ch.scores:
            # managing may be book-wide only early on
            if key == "managing":
                continue
            result.fail(f"Missing {label} score")
            continue
        if ch.scores[key] < threshold:
            result.fail(f"{label} score {ch.scores[key]} < {threshold}")
    return result


def manuscript_complete(state: PipelineState) -> GateResult:
    result = GateResult(ok=True)
    total_chars = 0
    for n in range(1, CHAPTER_COUNT + 1):
        ch = state.chapter(n)
        total_chars += ch.body_chars
        gr = chapter_passes_specialist_gates(ch)
        if not gr.ok:
            result.fail(f"Chapter {n}: " + "; ".join(gr.reasons))
        if ch.scores.get("managing") is not None and ch.scores["managing"] < GATE_MANAGING:
            result.fail(
                f"Chapter {n}: managing score {ch.scores['managing']} < {GATE_MANAGING}"
            )

    if total_chars < MANUSCRIPT_CHARS_MIN:
        result.fail(
            f"Manuscript body chars {total_chars} < minimum {MANUSCRIPT_CHARS_MIN}"
        )
    # Upper manuscript bound is a soft target; per-chapter max is the hard gate.
    if total_chars > MANUSCRIPT_CHARS_MAX:
        result.reasons.append(
            f"NOTE: manuscript body chars {total_chars} above soft max {MANUSCRIPT_CHARS_MAX}"
        )

    consistency = None
    for n in range(1, CHAPTER_COUNT + 1):
        if "style_consistency" in state.chapter(n).scores:
            consistency = state.chapter(n).scores["style_consistency"]
            break
    style_book = report_path("style", None)
    if style_book.exists() and consistency is None:
        scores = parse_scores_from_report(style_book.read_text(encoding="utf-8"))
        consistency = scores.get("overall")
    if consistency is not None and consistency < GATE_STYLE_CONSISTENCY:
        result.fail(
            f"Style consistency {consistency} < {GATE_STYLE_CONSISTENCY}"
        )

    if state.managing_recommendation == "rebuild":
        result.fail("Managing editor recommendation: rebuild")
    if state.overall_score is not None and state.overall_score < GATE_MANAGING:
        result.fail(f"Overall managing score {state.overall_score} < {GATE_MANAGING}")

    # Require all chapters drafted and reviewed
    for n in range(1, CHAPTER_COUNT + 1):
        ch = state.chapter(n)
        if not ch.drafted:
            result.fail(f"Chapter {n} not drafted")
        for key in ("factcheck", "history", "museum", "style"):
            if key not in ch.scores:
                result.fail(f"Chapter {n} missing {key} score")

    return result


def chapters_needing_revision(state: PipelineState) -> list[int]:
    needing: list[int] = []
    for n in range(1, CHAPTER_COUNT + 1):
        ch = state.chapter(n)
        if ch.needs_revision or not chapter_passes_specialist_gates(ch).ok:
            needing.append(n)
    return needing
