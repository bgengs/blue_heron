"""Parse book/plan.md into master, chapter, and specialist prompts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from config import PLAN_PATH


@dataclass(frozen=True)
class ChapterSpec:
    number: int
    title: str
    prompt: str


@dataclass(frozen=True)
class SpecialistSpec:
    number: int
    name: str
    prompt: str


def _read_plan(path: Path | None = None) -> str:
    p = path or PLAN_PATH
    return p.read_text(encoding="utf-8")


def _section_after(text: str, heading: str, next_headings: list[str]) -> str:
    """Return text after `heading` until the earliest of next_headings."""
    start = text.find(heading)
    if start < 0:
        raise ValueError(f"Heading not found: {heading}")
    start += len(heading)
    end = len(text)
    for nh in next_headings:
        idx = text.find(nh, start)
        if idx >= 0:
            end = min(end, idx)
    return text[start:end].strip()


@lru_cache(maxsize=1)
def load_master_prompt() -> str:
    text = _read_plan()
    return _section_after(
        text,
        "## MASTER CHAPTER PROMPT",
        ["# III. THE 24 CHAPTER AGENTS"],
    )


@lru_cache(maxsize=1)
def load_chapter_specs() -> tuple[ChapterSpec, ...]:
    text = _read_plan()
    # AGENT N — TITLE ... until next AGENT or section IV
    pattern = re.compile(
        r"^# AGENT (\d+) — (.+?)\n+(.*?)(?=^# AGENT \d+ — |^# IV\. SIX SPECIALIST AGENTS)",
        re.MULTILINE | re.DOTALL,
    )
    specs: list[ChapterSpec] = []
    for m in pattern.finditer(text):
        num = int(m.group(1))
        if num > 24:
            continue
        title = m.group(2).strip()
        body = m.group(3).strip()
        # Prefer content under ## Chapter-specific prompt
        prompt_m = re.search(
            r"## Chapter-specific prompt\s*\n+(.*)",
            body,
            re.DOTALL | re.IGNORECASE,
        )
        prompt = prompt_m.group(1).strip() if prompt_m else body
        specs.append(ChapterSpec(number=num, title=title, prompt=prompt))
    if len(specs) != 24:
        raise ValueError(f"Expected 24 chapter agents, found {len(specs)}")
    return tuple(specs)


@lru_cache(maxsize=1)
def load_specialist_specs() -> tuple[SpecialistSpec, ...]:
    text = _read_plan()
    pattern = re.compile(
        r"^# AGENT (\d+) — (.+?)\n+(.*?)(?=^# AGENT \d+ — |^# V\. STANDARD OUTPUT FORMAT)",
        re.MULTILINE | re.DOTALL,
    )
    specs: list[SpecialistSpec] = []
    for m in pattern.finditer(text):
        num = int(m.group(1))
        if num < 25:
            continue
        name = m.group(2).strip()
        body = m.group(3).strip()
        prompt_m = re.search(r"## Prompt\s*\n+(.*)", body, re.DOTALL | re.IGNORECASE)
        prompt = prompt_m.group(1).strip() if prompt_m else body
        specs.append(SpecialistSpec(number=num, name=name, prompt=prompt))
    if len(specs) != 6:
        raise ValueError(f"Expected 6 specialist agents, found {len(specs)}")
    return tuple(specs)


def chapter_writer_instructions(chapter_number: int) -> str:
    master = load_master_prompt()
    spec = load_chapter_specs()[chapter_number - 1]
    universal = _universal_quality_rules()
    output_fmt = _output_format_reminder()
    return (
        f"{master}\n\n"
        f"---\n\n"
        f"# Chapter {spec.number}: {spec.title}\n\n"
        f"{spec.prompt}\n\n"
        f"---\n\n"
        f"{universal}\n\n"
        f"{output_fmt}\n\n"
        "HARD RULES:\n"
        "- Never invent facts, sources, quotations, or scientific results.\n"
        "- Never introduce absurd, off-topic, sexual, crypto, or surreal content.\n"
        "- Prefer peer-reviewed, government, museum, and university sources found via search.\n"
        "- Chapter body (excluding source ledger, photo recommendations, character count, "
        "self-evaluation) must be 7,500–10,000 characters including spaces.\n"
        "- Write the finished chapter to your allowed chapter file using the file tools.\n"
        "- If voice_bible.md exists, match its style closely.\n"
    )


def specialist_instructions(agent_number: int) -> str:
    for s in load_specialist_specs():
        if s.number == agent_number:
            return (
                f"You are Agent {s.number} — {s.name}.\n\n"
                f"{s.prompt}\n\n"
                "HARD RULES:\n"
                "- Score honestly. Do not inflate scores.\n"
                "- Flag fabricated sources, invented quotations, and off-topic nonsense.\n"
                "- Write your report only to your allowed report path.\n"
                "- Include explicit numeric scores so the orchestrator can parse them.\n"
                "- Prefer SCORE lines like: `SCORE ch-01: 91` or a markdown table with scores.\n"
            )
    raise KeyError(f"No specialist agent {agent_number}")


def _universal_quality_rules() -> str:
    text = _read_plan()
    try:
        return _section_after(
            text,
            "# VI. UNIVERSAL QUALITY RULES",
            ["# VII. BOOK-WIDE SCORING SYSTEM"],
        )
    except ValueError:
        return ""


def _output_format_reminder() -> str:
    text = _read_plan()
    try:
        return _section_after(
            text,
            "# V. STANDARD OUTPUT FORMAT FOR CHAPTER AGENTS",
            ["# VI. UNIVERSAL QUALITY RULES"],
        )
    except ValueError:
        return ""


def character_check_prompt() -> str:
    text = _read_plan()
    try:
        base = _section_after(
            text,
            "# IX. FINAL CHARACTER-CHECK PROMPT",
            ["# X. FRONTISPIECE AND CLOSING IMAGE"],
        )
    except ValueError:
        base = (
            "Count characters in the chapter body only (7,500–10,000). "
            "Exclude source ledger, photograph recommendations, character report, self-evaluation."
        )
    return (
        base
        + "\n\nIMPORTANT: Count ONLY reader prose in manuscript/chapters/ch-NN.md. "
        "Photo recommendations and the source ledger live in manuscript/meta/ and must not "
        "be used to pad the character count. Write full paragraphs, not outline stubs."
    )
