"""Chapter-writing Agno agents (1–24) including dual-draft and merge."""

from __future__ import annotations

from pathlib import Path

from agno.agent import Agent

from config import (
    GUIDE_DIR,
    VOICE_BIBLE_PATH,
    chapter_meta_path,
    chapter_path,
    draft_path,
)
from models import model_for
from prompts import chapter_writer_instructions, character_check_prompt, load_chapter_specs
from tools.files import ScopedFileTools
from tools.research import make_search_tools


PROSE_FIRST_RULES = """
OUTPUT LAYOUT (mandatory):
1) Write READER PROSE first — this is the book chapter people read:
   - Chapter title
   - Opening passage (400–700 characters)
   - Four to six titled subsections of CONTINUOUS PROSE (not bullet outlines)
   - Each subsection should usually be 900+ characters of real explanation
   - Heron Fact box and Myth or Fact? box
   - Closing reflection (400–700 characters)
2) Then write the META APPENDIX (does NOT count toward the 7,500–10,000 character body):
   - Photograph Recommendation 1 and 2
   - Source Ledger (8–15 real sources)
   - Character Count (count ONLY reader prose)
   - Self-Evaluation

FILES:
- Save reader prose to manuscript/chapters/ch-NN.md
- Save meta appendix to manuscript/meta/ch-NN.meta.md
- Never pad length with photo recommendations or the source ledger.
- Never leave tool citation junk like 【6†L2-L4】 in the prose.
- Prefer paragraphs over bullet lists. This is a museum book, not a slide deck.
"""


def _base_instructions(chapter_number: int) -> list[str]:
    return [
        chapter_writer_instructions(chapter_number),
        character_check_prompt(),
        PROSE_FIRST_RULES,
        "Use web_search to find verifiable sources before asserting specific facts.",
        "If web_search returns ok:false or empty results, do NOT retry endlessly. "
        "Fall back to local content/guide notes and well-known institutional sources; "
        "never invent URLs, DOIs, quotations, or study results.",
        "Prefer .gov, .edu, museum, IUCN, USGS, Birds of the World, and peer-reviewed papers.",
        f"Writable paths: manuscript/chapters/ch-{chapter_number:02d}.md and "
        f"manuscript/meta/ch-{chapter_number:02d}.meta.md",
        "Call write_own twice (prose file, then meta file) or write a full package and the "
        "orchestrator will split — prefer two write_own calls.",
        "Do not attempt to delete files. Do not write other chapters' files.",
    ]


def build_chapter_agent(
    chapter_number: int,
    *,
    role: str = "chapter",
    write_target: Path | None = None,
    name_suffix: str = "",
) -> Agent:
    target = write_target or chapter_path(chapter_number)
    if write_target and write_target != chapter_path(chapter_number):
        meta = write_target.with_suffix(".meta.md")
    else:
        meta = chapter_meta_path(chapter_number)
    spec = load_chapter_specs()[chapter_number - 1]
    files = ScopedFileTools(
        write_allowlist=[target, meta],
        agent_label=f"ch{chapter_number:02d}{name_suffix}",
    )
    return Agent(
        name=f"Chapter {chapter_number} — {spec.title}{name_suffix}",
        model=model_for(role),
        tools=[make_search_tools(), files],
        instructions=_base_instructions(chapter_number),
        markdown=True,
    )


def build_dual_draft_agents(chapter_number: int) -> tuple[Agent, Agent]:
    a = build_chapter_agent(
        chapter_number,
        role="dual_a",
        write_target=draft_path(chapter_number, "a"),
        name_suffix=" [draft-A]",
    )
    b = build_chapter_agent(
        chapter_number,
        role="dual_b",
        write_target=draft_path(chapter_number, "b"),
        name_suffix=" [draft-B]",
    )
    return a, b


def build_merge_agent(chapter_number: int) -> Agent:
    target = chapter_path(chapter_number)
    meta = chapter_meta_path(chapter_number)
    files = ScopedFileTools(
        write_allowlist=[target, meta],
        agent_label=f"ch{chapter_number:02d}-merge",
    )
    return Agent(
        name=f"Chapter {chapter_number} merge editor",
        model=model_for("merge"),
        tools=[make_search_tools(), files],
        instructions=[
            "You merge two independent chapter drafts into one consistent chapter.",
            "Compare drafts fact by fact. Select the stronger foundation.",
            "Preserve independently verified material that improves the final chapter.",
            "Do not combine passages mechanically. Rewrite into one consistent voice.",
            "Never invent facts or sources. Drop any unverifiable claim.",
            chapter_writer_instructions(chapter_number),
            character_check_prompt(),
            PROSE_FIRST_RULES,
            f"Write prose to manuscript/chapters/ch-{chapter_number:02d}.md and "
            f"meta to manuscript/meta/ch-{chapter_number:02d}.meta.md via write_own.",
            "You may read both draft files and the voice bible.",
        ],
        markdown=True,
    )


def chapter_user_prompt(chapter_number: int, *, dual_variant: str | None = None) -> str:
    if dual_variant:
        target = draft_path(chapter_number, dual_variant)
        meta = target.with_suffix(".meta.md")
    else:
        target = chapter_path(chapter_number)
        meta = chapter_meta_path(chapter_number)

    from config import BOOK_ROOT

    def rel(p: Path) -> str:
        try:
            return p.relative_to(BOOK_ROOT).as_posix()
        except ValueError:
            return p.as_posix()

    voice_note = (
        f"Read {VOICE_BIBLE_PATH.name} if it exists and match its style."
        if VOICE_BIBLE_PATH.exists()
        else "No voice bible yet; follow the master prompt tone strictly."
    )
    guide_note = (
        f"You may read local field-guide notes under {GUIDE_DIR} for grounding, "
        "but every specific claim still needs a ledger source."
    )
    return (
        f"Write Chapter {chapter_number} now.\n"
        f"PROSE (reader book text) → {rel(target)}\n"
        f"META (photos, sources, scores — not counted) → {rel(meta)}\n"
        f"{voice_note}\n"
        f"{guide_note}\n"
        "Prioritize rich museum prose. Photo recommendations are secondary.\n"
        "Research with web_search, then write_own both files."
    )


def merge_user_prompt(chapter_number: int) -> str:
    a = draft_path(chapter_number, "a")
    b = draft_path(chapter_number, "b")
    out = chapter_path(chapter_number)
    meta = chapter_meta_path(chapter_number)
    from config import BOOK_ROOT

    def rel(p: Path) -> str:
        try:
            return p.relative_to(BOOK_ROOT).as_posix()
        except ValueError:
            return p.as_posix()

    return (
        f"Merge dual drafts for chapter {chapter_number}.\n"
        f"Draft A: {rel(a)}\n"
        f"Draft B: {rel(b)}\n"
        f"Prose output: {rel(out)}\n"
        f"Meta output: {rel(meta)}\n"
        "Produce full museum prose (7,500–10,000 chars) plus separate meta appendix."
    )
