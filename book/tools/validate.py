"""Chapter validators: reader prose vs meta appendix; length; quality; nonsense."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from config import (
    CHAPTER_AVG_SUBSECTION_CHARS_MIN,
    CHAPTER_CHARS_MAX,
    CHAPTER_CHARS_MIN,
    CHAPTER_PROSE_PARAGRAPH_MIN,
    CITATION_ARTIFACT_RE,
    NONSENSE_BLOCKLIST,
    PLACEHOLDER_SOURCE_MARKERS,
    REQUIRED_META_MARKERS,
    REQUIRED_PROSE_MARKERS,
    SOURCE_LEDGER_MIN,
    chapter_meta_path,
    chapter_path,
)

# Anything from photograph recommendations onward is appendix/meta — not reader prose.
META_START_PATTERNS = (
    r"(?im)^#{2,4}\s*Photograph Recommendation",
    r"(?im)^#{2,4}\s*Source Ledger",
    r"(?im)^#{2,4}\s*Character Count",
    r"(?im)^#{2,4}\s*Self[-‐‑‒–—]Evaluation",
    r"(?im)^#{2,4}\s*Appendix\b",
)


@dataclass
class ValidationResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    body_chars: int = 0
    scores: dict[str, float] = field(default_factory=dict)

    def fail(self, reason: str) -> None:
        self.ok = False
        self.reasons.append(reason)


def normalize_headings(text: str) -> str:
    """Normalize fancy dashes in headings so ### Self‑Evaluation matches ASCII."""
    return (
        text.replace("\u2011", "-")
        .replace("\u2010", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
    )


def split_prose_and_meta(text: str) -> tuple[str, str]:
    """Split a monolithic chapter dump into reader prose + meta appendix."""
    text = normalize_headings(text)
    cut = len(text)
    for pat in META_START_PATTERNS:
        m = re.search(pat, text)
        if m:
            cut = min(cut, m.start())
    prose = text[:cut].strip()
    meta = text[cut:].strip()
    return prose, meta


def extract_chapter_body(text: str) -> str:
    """Reader-facing prose only (excludes photo/ledger/self-eval appendix)."""
    prose, _ = split_prose_and_meta(text)
    return prose


def count_body_chars(text: str) -> int:
    return len(extract_chapter_body(text))


def _has_marker(text: str, marker: str) -> bool:
    norm = normalize_headings(text)
    # Allow ## or ### and unicode dash variants already normalized
    flexible = re.escape(marker).replace(r"\#\#\#", r"#{2,4}")
    flexible = flexible.replace(r"Self\-Evaluation", r"Self[- ]?Evaluation")
    return bool(re.search(flexible, norm, re.IGNORECASE)) or marker in norm


def _prose_quality(prose: str, result: ValidationResult) -> None:
    if re.search(CITATION_ARTIFACT_RE, prose):
        result.fail(
            "Tool/RAG citation artifacts found (e.g. 【6†L2-L4】). "
            "Rewrite as clean museum prose with real source-ledger citations only."
        )

    # Paragraph density: non-empty lines that are not headings/tables/bullets
    paras = [
        ln.strip()
        for ln in prose.splitlines()
        if ln.strip()
        and not ln.strip().startswith("#")
        and not ln.strip().startswith("|")
        and not re.match(r"^[-*]\s+", ln.strip())
        and not re.match(r"^\d+[.)]\s+", ln.strip())
        and len(ln.strip()) > 80
    ]
    if len(paras) < CHAPTER_PROSE_PARAGRAPH_MIN:
        result.fail(
            f"Too few developed paragraphs ({len(paras)} < {CHAPTER_PROSE_PARAGRAPH_MIN}). "
            "Do not submit outline/bullet stubs — write full museum prose."
        )

    # Subsection substance
    parts = re.split(r"(?m)^#{2,3}\s+", prose)
    # parts[0] is title/opening; remaining are subsections
    subsections = [p.strip() for p in parts[1:] if p.strip()]
    content_subs = [
        s
        for s in subsections
        if not s.lower().startswith("heron fact")
        and not s.lower().startswith("myth or fact")
    ]
    if content_subs:
        avg = sum(len(s) for s in content_subs) / len(content_subs)
        if avg < CHAPTER_AVG_SUBSECTION_CHARS_MIN:
            result.fail(
                f"Subsections too thin (avg {avg:.0f} chars < {CHAPTER_AVG_SUBSECTION_CHARS_MIN}). "
                "Expand with researched explanation, not photo/meta padding."
            )

    bullet_lines = len(re.findall(r"(?m)^[-*]\s+\S+", prose))
    prose_chars = len(prose) or 1
    if bullet_lines >= 12 and (bullet_lines * 40) > prose_chars * 0.25:
        result.fail(
            "Chapter is too list/bullet-heavy. Prefer continuous prose paragraphs."
        )


def validate_prose_text(prose: str, chapter_keywords: list[str] | None = None) -> ValidationResult:
    result = ValidationResult(ok=True)
    prose = normalize_headings(prose or "")
    if not prose.strip():
        result.fail("Reader prose is empty")
        return result

    lower = prose.lower()
    for bad in NONSENSE_BLOCKLIST:
        if bad in lower:
            result.fail(f"Nonsense / off-domain content detected: {bad!r}")

    for marker in REQUIRED_PROSE_MARKERS:
        if not _has_marker(prose, marker):
            result.fail(f"Missing required prose section: {marker}")

    # Closing reflection should exist as prose near the end (before boxes is ok too)
    if "closing reflection" not in lower and len(prose) > 500:
        # Soft: look for a reflective final paragraph after myth box
        after_myth = prose.lower().split("myth or fact")[-1] if "myth or fact" in lower else ""
        # Many good chapters put closing before boxes; require either label or long tail
        if "closing" not in lower and len(extract_chapter_body(prose)) < CHAPTER_CHARS_MIN:
            pass  # length check covers thin endings

    body_chars = len(prose.strip())
    result.body_chars = body_chars
    if body_chars < CHAPTER_CHARS_MIN:
        result.fail(
            f"Reader prose {body_chars} chars below minimum {CHAPTER_CHARS_MIN} "
            "(photo recommendations and source ledger do NOT count)."
        )
    if body_chars > CHAPTER_CHARS_MAX:
        result.fail(
            f"Reader prose {body_chars} chars above maximum {CHAPTER_CHARS_MAX}"
        )

    _prose_quality(prose, result)

    if chapter_keywords:
        hits = sum(1 for kw in chapter_keywords if kw.lower() in lower)
        if hits < max(1, len(chapter_keywords) // 4):
            result.fail(
                f"Topic drift: only {hits}/{len(chapter_keywords)} chapter keywords present"
            )

    return result


def validate_meta_text(meta: str) -> ValidationResult:
    result = ValidationResult(ok=True)
    meta = normalize_headings(meta or "")
    if not meta.strip():
        result.fail("Meta appendix missing (photo recommendations, source ledger, self-eval)")
        return result

    for marker in REQUIRED_META_MARKERS:
        if not _has_marker(meta, marker):
            result.fail(f"Missing required meta section: {marker}")

    ledger = _extract_section(
        meta, "### Source Ledger", ("### Character Count", "### Self-Evaluation")
    )
    if not ledger:
        # try flexible
        m = re.search(r"(?im)^#{2,4}\s*Source Ledger\s*$", meta)
        if m:
            rest = meta[m.end() :]
            end_m = re.search(r"(?im)^#{2,4}\s*", rest)
            ledger = rest[: end_m.start()] if end_m else rest
    if ledger:
        entries = _count_ledger_entries(ledger)
        if entries < SOURCE_LEDGER_MIN:
            result.fail(f"Source ledger has {entries} entries; need ≥ {SOURCE_LEDGER_MIN}")
        for marker in PLACEHOLDER_SOURCE_MARKERS:
            if marker.lower() in ledger.lower():
                result.fail(f"Placeholder / fake source marker in ledger: {marker!r}")
    else:
        result.fail("Could not extract Source Ledger section")

    return result


def validate_chapter_text(text: str, chapter_keywords: list[str] | None = None) -> ValidationResult:
    """Validate a monolithic file (legacy) by splitting prose/meta."""
    prose, meta = split_prose_and_meta(text)
    # If split left almost everything as prose because meta headings missing,
    # still validate prose length; meta validation will fail separately.
    pr = validate_prose_text(prose, chapter_keywords)
    mr = validate_meta_text(meta) if meta else ValidationResult(
        ok=False, reasons=["Meta appendix not found — write manuscript/meta/ch-NN.meta.md"]
    )
    combined = ValidationResult(ok=pr.ok and mr.ok, body_chars=pr.body_chars)
    combined.reasons = pr.reasons + mr.reasons
    return combined


def validate_chapter_pair(
    prose_path: Path,
    meta_path: Path,
    chapter_keywords: list[str] | None = None,
) -> ValidationResult:
    if not prose_path.exists():
        return ValidationResult(ok=False, reasons=[f"Missing prose file: {prose_path}"])
    prose = prose_path.read_text(encoding="utf-8")
    # If prose file still contains meta (legacy), split and judge only prose portion for length
    prose_only, embedded_meta = split_prose_and_meta(prose)
    pr = validate_prose_text(prose_only, chapter_keywords)

    meta = ""
    if meta_path.exists():
        meta = meta_path.read_text(encoding="utf-8")
    elif embedded_meta:
        meta = embedded_meta
    mr = validate_meta_text(meta)

    # Fail if reader file is still polluted with photo/ledger blocks
    if embedded_meta and any(
        x in normalize_headings(prose) for x in ("### Photograph Recommendation", "### Source Ledger")
    ):
        pr.fail(
            "Reader chapter file still contains photo/source appendix. "
            "Keep only museum prose in ch-NN.md; put appendix in ch-NN.meta.md."
        )

    combined = ValidationResult(ok=pr.ok and mr.ok, body_chars=pr.body_chars)
    combined.reasons = pr.reasons + mr.reasons
    return combined


def validate_chapter_file(path: Path, chapter_keywords: list[str] | None = None) -> ValidationResult:
    """Validate chapter N from prose + meta paths (path may be ch-NN.md)."""
    name = path.name
    m = re.match(r"ch-(\d{2})\.md$", name)
    if m:
        n = int(m.group(1))
        return validate_chapter_pair(chapter_path(n), chapter_meta_path(n), chapter_keywords)
    return validate_chapter_text(path.read_text(encoding="utf-8"), chapter_keywords)


def write_split_chapter(n: int, content: str) -> tuple[Path, Path]:
    """Split agent output into prose + meta files. Returns paths written."""
    prose, meta = split_prose_and_meta(content)
    p = chapter_path(n)
    mp = chapter_meta_path(n)
    p.parent.mkdir(parents=True, exist_ok=True)
    mp.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(prose.strip() + "\n", encoding="utf-8")
    if meta.strip():
        mp.write_text(meta.strip() + "\n", encoding="utf-8")
    return p, mp


def parse_scores_from_report(text: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    for m in re.finditer(
        r"(?i)SCORE\s+(?:ch(?:apter)?[-\s]?)(\d{1,2})\s*[:=]\s*(\d{1,3}(?:\.\d+)?)",
        text,
    ):
        scores[f"ch-{int(m.group(1)):02d}"] = float(m.group(2))
    for m in re.finditer(
        r"(?i)\|\s*(?:ch(?:apter)?[-\s]?)(\d{1,2})\s*\|\s*(\d{1,3}(?:\.\d+)?)\s*\|",
        text,
    ):
        key = f"ch-{int(m.group(1)):02d}"
        scores.setdefault(key, float(m.group(2)))
    for m in re.finditer(
        r"(?i)(?:OVERALL|CONSISTENCY|VOICE\s*CONSISTENCY|BOOK[- ]WIDE)\s*(?:SCORE)?\s*[:=]\s*(\d{1,3}(?:\.\d+)?)",
        text,
    ):
        scores["overall"] = float(m.group(1))
    return scores


def parse_recommendation(text: str) -> str | None:
    m = re.search(
        r"(?i)FINAL\s+RECOMMENDATION\s*[:=]\s*(publish|revise|rebuild)",
        text,
    )
    if m:
        return m.group(1).lower()
    m = re.search(r"(?i)\b(publish|revise|rebuild)\b", text)
    return m.group(1).lower() if m else None


def extract_keywords_from_prompt(prompt: str, limit: int = 12) -> list[str]:
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "into", "about",
        "explain", "include", "write", "chapter", "should", "must", "their",
        "which", "when", "where", "what", "how", "why", "also", "than", "then",
        "great", "blue", "heron", "herons", "bird", "birds",
    }
    words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", prompt)
    scored: list[str] = []
    seen: set[str] = set()
    for w in words:
        lw = w.lower()
        if lw in stop or lw in seen:
            continue
        seen.add(lw)
        scored.append(lw)
        if len(scored) >= limit:
            break
    return scored


def _extract_section(text: str, start: str, ends: tuple[str, ...]) -> str:
    text = normalize_headings(text)
    idx = text.find(start)
    if idx < 0:
        return ""
    idx += len(start)
    end = len(text)
    for e in ends:
        j = text.find(e, idx)
        if j >= 0:
            end = min(end, j)
    return text[idx:end].strip()


def _count_ledger_entries(ledger: str) -> int:
    numbered = re.findall(r"(?m)^\s*\d+[.)]\s+\S+", ledger)
    if numbered:
        return len(numbered)
    bullets = re.findall(r"(?m)^\s*[-*]\s+\S+", ledger)
    return len(bullets)
