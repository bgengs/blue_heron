"""Specialist editorial agents 25–30."""

from __future__ import annotations

from pathlib import Path

from agno.agent import Agent

from config import (
    CHAPTERS_DIR,
    FACTCHECK_DIR,
    HISTORY_DIR,
    MANAGING_DIR,
    MUSEUM_DIR,
    PHOTOS_DIR,
    PHOTOS_JSON,
    STYLE_DIR,
    VOICE_BIBLE_PATH,
    report_path,
)
from models import model_for
from prompts import specialist_instructions
from tools.files import ScopedFileTools
from tools.research import make_search_tools

_ROLE_BY_AGENT = {
    25: ("factcheck", "factcheck", FACTCHECK_DIR),
    26: ("history", "history", HISTORY_DIR),
    27: ("museum", "museum", MUSEUM_DIR),
    28: ("style", "style", STYLE_DIR),
    29: ("photos", "photos", PHOTOS_DIR),
    30: ("managing", "managing", MANAGING_DIR),
}


def build_specialist_agent(agent_number: int, *, chapter_number: int | None = None) -> Agent:
    if agent_number not in _ROLE_BY_AGENT:
        raise KeyError(f"Not a specialist agent: {agent_number}")
    model_role, kind, write_dir = _ROLE_BY_AGENT[agent_number]
    write_allow = [write_dir]
    # Style agent may also create/update the voice bible (orchestrator-owned normally,
    # but allow write so it can propose; orchestrator copies if valid)
    if agent_number == 28:
        write_allow.append(VOICE_BIBLE_PATH)

    files = ScopedFileTools(
        write_allowlist=write_allow,
        agent_label=f"agent{agent_number}",
    )
    tools: list = [files]
    if agent_number in (25, 26, 30):
        tools.insert(0, make_search_tools())

    return Agent(
        name=f"Agent {agent_number}",
        model=model_for(model_role),
        tools=tools,
        instructions=[
            specialist_instructions(agent_number),
            "Read chapters from manuscript/chapters/.",
            "Write reports only under your reports/ subdirectory.",
            "For each chapter reviewed, include a line: SCORE ch-NN: <0-100>",
            "Never delete files. Never overwrite chapter manuscript files.",
            "Flag fabricated sources, invented quotes, and off-topic nonsense as critical.",
            "If web_search fails or returns empty, do not invent sources; score conservatively "
            "and note verification limits.",
        ],
        markdown=True,
    )


def specialist_user_prompt(agent_number: int, chapter_number: int | None = None) -> str:
    if chapter_number is not None:
        out = report_path(_ROLE_BY_AGENT[agent_number][1], chapter_number)
        ch = CHAPTERS_DIR / f"ch-{chapter_number:02d}.md"
        from config import BOOK_ROOT

        def rel(p: Path) -> str:
            try:
                return p.relative_to(BOOK_ROOT).as_posix()
            except ValueError:
                return p.as_posix()

        extra = ""
        if agent_number == 28 and chapter_number <= 2:
            extra = (
                f" If style is strong, also write a short voice bible to "
                f"{rel(VOICE_BIBLE_PATH)} capturing diction, rhythm, bans, and reflection rules."
            )
        if agent_number == 29:
            photo_hint = (
                f" Photo inventory metadata may be at {PHOTOS_JSON} (read-only)."
                if PHOTOS_JSON.exists()
                else " No photo inventory file found; work from chapter photo recommendations."
            )
            extra += photo_hint

        return (
            f"Review chapter {chapter_number}.\n"
            f"Read: {rel(ch)}\n"
            f"Write report to: {rel(out)}\n"
            f"Include: SCORE ch-{chapter_number:02d}: <number>\n"
            f"{extra}"
        )

    # Book-wide pass
    kind = _ROLE_BY_AGENT[agent_number][1]
    out = report_path(kind, None)
    from config import BOOK_ROOT

    try:
        out_rel = out.relative_to(BOOK_ROOT).as_posix()
    except ValueError:
        out_rel = out.as_posix()

    return (
        f"Review all chapters in manuscript/chapters/.\n"
        f"Write the book-wide report to: {out_rel}\n"
        "Include SCORE ch-NN for every chapter and OVERALL SCORE / CONSISTENCY SCORE as applicable.\n"
        "For Agent 30 also include FINAL RECOMMENDATION: publish|revise|rebuild"
    )
