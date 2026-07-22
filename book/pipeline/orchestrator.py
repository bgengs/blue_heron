"""Orchestrator: one work unit per tick, resume-safe until DONE."""

from __future__ import annotations

import logging

from agents.chapter import (
    build_chapter_agent,
    build_dual_draft_agents,
    build_merge_agent,
    chapter_user_prompt,
    merge_user_prompt,
)
from agents.specialists import build_specialist_agent, specialist_user_prompt
from config import (
    CHAPTER_COUNT,
    DUAL_DRAFT_CHAPTERS,
    MAX_REVISION_ROUNDS,
    VOICE_BIBLE_PATH,
    chapter_path,
    draft_path,
    ensure_dirs,
    report_path,
)
from pipeline.gates import (
    chapters_needing_revision,
    ingest_specialist_scores,
    manuscript_complete,
    refresh_chapter_validation,
)
from pipeline.state import (
    PipelineState,
    is_done,
    load_state,
    mark_done,
    save_state,
)
from tools.validate import validate_chapter_file, write_split_chapter

logger = logging.getLogger("book.orchestrator")

REVIEW_KINDS = (
    (25, "factcheck"),
    (26, "history"),
    (27, "museum"),
    (28, "style"),
    (29, "photos"),
)


def _run_agent(agent, prompt: str) -> str:
    logger.info("Running agent %s", agent.name)
    response = agent.run(prompt)
    content = getattr(response, "content", None) or str(response)
    return content if isinstance(content, str) else str(content)


def _ensure_chapter_on_disk(n: int, content: str | None) -> None:
    """Persist agent output as prose + meta without clobbering a valid pair."""
    path = chapter_path(n)
    existing_ok = path.exists() and validate_chapter_file(path).ok
    if existing_ok:
        return
    if content and len(content) > 800:
        write_split_chapter(n, content)
        logger.info("Orchestrator split/saved chapter %s prose+meta", n)
        return
    if path.exists() and path.stat().st_size > 100:
        existing = path.read_text(encoding="utf-8")
        if "### Source Ledger" in existing or "Photograph Recommendation" in existing:
            write_split_chapter(n, existing)
            logger.info("Orchestrator re-split existing chapter %s", n)


def _draft_chapter(state: PipelineState, n: int) -> None:
    if n in DUAL_DRAFT_CHAPTERS and not state.chapter(n).dual_done:
        a, b = build_dual_draft_agents(n)
        ca = _run_agent(a, chapter_user_prompt(n, dual_variant="a"))
        cb = _run_agent(b, chapter_user_prompt(n, dual_variant="b"))
        # Ensure drafts exist on disk even if tool write failed
        for variant, content in (("a", ca), ("b", cb)):
            dp = draft_path(n, variant)
            if not dp.exists() and content and len(content) > 500:
                dp.parent.mkdir(parents=True, exist_ok=True)
                dp.write_text(content, encoding="utf-8")
        merge = build_merge_agent(n)
        merged = _run_agent(merge, merge_user_prompt(n))
        _ensure_chapter_on_disk(n, merged)
        state.chapter(n).dual_done = True
    else:
        agent = build_chapter_agent(n)
        content = _run_agent(agent, chapter_user_prompt(n))
        _ensure_chapter_on_disk(n, content)

    state.chapter(n).drafted = True
    refresh_chapter_validation(state, n)
    if not state.chapter(n).validation_ok:
        state.chapter(n).needs_revision = True


def _ensure_report_on_disk(kind: str, n: int, content: str | None) -> None:
    path = report_path(kind, n)
    if path.exists() and path.stat().st_size > 50:
        return
    if content and len(content) > 100:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        logger.info("Orchestrator saved %s report for ch-%02d", kind, n)


def _review_chapter(state: PipelineState, n: int) -> None:
    for agent_number, kind in REVIEW_KINDS:
        agent = build_specialist_agent(agent_number, chapter_number=n)
        content = _run_agent(agent, specialist_user_prompt(agent_number, n))
        _ensure_report_on_disk(kind, n, content)
        ingest_specialist_scores(state, kind, n)
        if kind not in state.chapter(n).scores:
            ingest_specialist_scores(state, kind, n)
        if kind not in state.chapter(n).scores:
            state.chapter(n).needs_revision = True
            state.chapter(n).fail_reasons.append(f"Missing parseable {kind} score")
        elif kind == "factcheck" and state.chapter(n).scores[kind] < 90:
            state.chapter(n).needs_revision = True
        elif kind == "history" and state.chapter(n).scores[kind] < 92:
            state.chapter(n).needs_revision = True
        elif kind == "museum" and state.chapter(n).scores[kind] < 90:
            state.chapter(n).needs_revision = True
        elif kind == "style" and state.chapter(n).scores[kind] < 85:
            state.chapter(n).needs_revision = True

    refresh_chapter_validation(state, n)
    if VOICE_BIBLE_PATH.exists():
        state.voice_bible_ready = True


def _revise_chapter(state: PipelineState, n: int) -> None:
    ch = state.chapter(n)
    if ch.revision_round >= MAX_REVISION_ROUNDS:
        logger.warning(
            "Chapter %s hit max revisions (%s); escalating with dual-draft rewrite",
            n,
            MAX_REVISION_ROUNDS,
        )
        ch.dual_done = False
        ch.revision_round = 0
        _draft_chapter(state, n)
        _review_chapter(state, n)
        return

    ch.revision_round += 1
    reasons = "; ".join(ch.fail_reasons) or "gates failed"
    report_bits: list[str] = []
    for kind in ("factcheck", "history", "museum", "style"):
        rp = report_path(kind, n)
        if rp.exists():
            report_bits.append(f"--- {kind} report ---\n{rp.read_text(encoding='utf-8')[:4000]}")

    agent = build_chapter_agent(n)
    prompt = (
        chapter_user_prompt(n)
        + f"\n\nREVISION ROUND {ch.revision_round}. Fix these issues:\n{reasons}\n\n"
        + "\n\n".join(report_bits)
        + "\n\nRead existing prose + meta, revise via write_own to BOTH "
        "manuscript/chapters/ch-NN.md (full museum prose) and "
        "manuscript/meta/ch-NN.meta.md (photos/sources/scores). "
        "Expand thin subsections into real paragraphs. Remove citation artifacts. "
        "Do not pad length with recommendations."
    )
    content = _run_agent(agent, prompt)
    _ensure_chapter_on_disk(n, content)
    refresh_chapter_validation(state, n)
    # Re-run specialists after revision
    _review_chapter(state, n)
    from pipeline.gates import chapter_passes_specialist_gates

    if chapter_passes_specialist_gates(ch).ok and ch.validation_ok:
        ch.needs_revision = False
        ch.fail_reasons = []
    else:
        ch.needs_revision = True


def _managing_pass(state: PipelineState) -> None:
    agent = build_specialist_agent(30)
    content = _run_agent(agent, specialist_user_prompt(30))
    out = report_path("managing", None)
    if not out.exists() and content:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
    ingest_specialist_scores(state, "managing", None)
    # Also style book-wide consistency if missing
    style_agent = build_specialist_agent(28)
    style_content = _run_agent(
        style_agent,
        specialist_user_prompt(28)
        + "\nFocus on book-wide VOICE CONSISTENCY SCORE. Write reports/style/book.md",
    )
    style_book = report_path("style", None)
    if not style_book.exists() and style_content:
        style_book.write_text(style_content, encoding="utf-8")
    ingest_specialist_scores(state, "style", None)

    # Propagate managing per-chapter scores; if only overall, apply to all
    if state.overall_score is not None:
        for n in range(1, CHAPTER_COUNT + 1):
            if "managing" not in state.chapter(n).scores:
                state.chapter(n).scores["managing"] = state.overall_score


def tick(state: PipelineState | None = None) -> PipelineState:
    """Execute one unit of work. Returns updated state."""
    ensure_dirs()
    if is_done():
        st = state or load_state()
        st.phase = "complete"
        return st

    st = state or load_state()
    st.ticks += 1
    st.last_error = None

    try:
        if st.phase == "bootstrap":
            ensure_dirs()
            st.phase = "draft"
            st.current_chapter = 1
            save_state(st)
            return st

        if st.phase == "draft":
            n = st.current_chapter
            if n > CHAPTER_COUNT:
                st.phase = "review"
                st.current_chapter = 1
                save_state(st)
                return st
            if not st.chapter(n).drafted:
                logger.info("Drafting chapter %s", n)
                _draft_chapter(st, n)
            else:
                logger.info("Chapter %s already drafted; skipping", n)
            st.current_chapter = n + 1
            if st.current_chapter > CHAPTER_COUNT:
                st.phase = "review"
                st.current_chapter = 1
            save_state(st)
            return st

        if st.phase == "review":
            n = st.current_chapter
            if n > CHAPTER_COUNT:
                st.phase = "revise"
                save_state(st)
                return st
            logger.info("Reviewing chapter %s", n)
            refresh_chapter_validation(st, n)
            _review_chapter(st, n)
            st.current_chapter = n + 1
            if st.current_chapter > CHAPTER_COUNT:
                st.phase = "revise"
            save_state(st)
            return st

        if st.phase == "revise":
            needing = chapters_needing_revision(st)
            if not needing:
                st.phase = "managing"
                save_state(st)
                return st
            n = needing[0]
            logger.info("Revising chapter %s (reasons: %s)", n, st.chapter(n).fail_reasons)
            _revise_chapter(st, n)
            save_state(st)
            return st

        if st.phase == "managing":
            logger.info("Managing editor pass")
            _managing_pass(st)
            # Re-check who needs revision after managing scores
            for n in range(1, CHAPTER_COUNT + 1):
                refresh_chapter_validation(st, n)
                ch = st.chapter(n)
                from pipeline.gates import chapter_passes_specialist_gates

                if not chapter_passes_specialist_gates(ch).ok:
                    ch.needs_revision = True

            complete = manuscript_complete(st)
            if complete.ok and st.managing_recommendation != "rebuild":
                st.phase = "complete"
                save_state(st)
                mark_done("Manuscript met all gates.")
                logger.info("DONE — all criteria met")
                return st

            # Not done — back to revise
            for reason in complete.reasons:
                logger.warning("Gate fail: %s", reason)
            needing = chapters_needing_revision(st)
            if not needing:
                # Force weakest chapters into revision
                for n in range(1, CHAPTER_COUNT + 1):
                    st.chapter(n).needs_revision = True
            st.phase = "revise"
            save_state(st)
            return st

        if st.phase == "complete":
            if not is_done():
                mark_done("Phase complete.")
            return st

    except Exception as e:
        logger.exception("Tick failed: %s", e)
        st.last_error = str(e)
        save_state(st)
        raise

    save_state(st)
    return st
