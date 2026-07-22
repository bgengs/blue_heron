"""Pipeline configuration: paths, models, thresholds, dual-draft chapters."""

from __future__ import annotations

from pathlib import Path

BOOK_ROOT = Path(__file__).resolve().parent
REPO_ROOT = BOOK_ROOT.parent

PLAN_PATH = BOOK_ROOT / "plan.md"
ENV_PATH = BOOK_ROOT / ".env"

MANUSCRIPT_DIR = BOOK_ROOT / "manuscript"
CHAPTERS_DIR = MANUSCRIPT_DIR / "chapters"
META_DIR = MANUSCRIPT_DIR / "meta"
DRAFTS_DIR = MANUSCRIPT_DIR / "drafts"
VOICE_BIBLE_PATH = MANUSCRIPT_DIR / "voice_bible.md"

REPORTS_DIR = BOOK_ROOT / "reports"
FACTCHECK_DIR = REPORTS_DIR / "factcheck"
HISTORY_DIR = REPORTS_DIR / "history"
MUSEUM_DIR = REPORTS_DIR / "museum"
STYLE_DIR = REPORTS_DIR / "style"
PHOTOS_DIR = REPORTS_DIR / "photos"
MANAGING_DIR = REPORTS_DIR / "managing"

STATE_DIR = BOOK_ROOT / "state"
PIPELINE_STATE_PATH = STATE_DIR / "pipeline.json"
DONE_PATH = STATE_DIR / "DONE"
LOGS_DIR = BOOK_ROOT / "logs"

GUIDE_DIR = REPO_ROOT / "content" / "guide"
PHOTOS_JSON = REPO_ROOT / "data" / "photos.json"

# Character targets — READER PROSE only (title → closing reflection + fact boxes).
# Photo recommendations, source ledger, character report, and self-evaluation live in
# manuscript/meta/ and do NOT count toward length.
CHAPTER_CHARS_MIN = 7500
CHAPTER_CHARS_MAX = 10000
# Hard floor for narrative without counting only lists/outlines as "enough"
CHAPTER_PROSE_PARAGRAPH_MIN = 6
CHAPTER_AVG_SUBSECTION_CHARS_MIN = 900
MANUSCRIPT_CHARS_MIN = 190_000
MANUSCRIPT_CHARS_MAX = 240_000

# Specialist / editor gates
GATE_SCIENCE = 90
GATE_HISTORY = 92
GATE_MUSEUM = 90
GATE_STYLE = 85
GATE_STYLE_CONSISTENCY = 85
GATE_MANAGING = 90
GATE_SELF_EVAL_MIN = 7  # average self-eval out of 10 is soft signal

MAX_REVISION_ROUNDS = 5
TICK_SLEEP_SECONDS = 2.0
AGENT_TIMEOUT_SECONDS = 600

SOURCE_LEDGER_MIN = 8

# Chapters that get competitive dual drafts (plan §VIII)
DUAL_DRAFT_CHAPTERS = frozenset({3, 6, 7, 8, 10, 19, 22, 24})

# Ollama Cloud model IDs (swap freely)
MODELS = {
    "chapter": "gpt-oss:120b-cloud",
    "dual_a": "deepseek-v4-pro:cloud",
    "dual_b": "glm-5.2:cloud",
    "factcheck": "nemotron-3-ultra:cloud",
    "history": "glm-5.2:cloud",
    "museum": "nemotron-3-ultra:cloud",
    "style": "gemma4:cloud",
    "photos": "gpt-oss:120b-cloud",
    "managing": "deepseek-v4-pro:cloud",
    "merge": "deepseek-v4-pro:cloud",
}

CHAPTER_COUNT = 24

NONSENSE_BLOCKLIST = (
    "blockchain",
    "blowjob",
    "cryptocurrency",
    "nft",
    "metaverse",
    "onlyfans",
    "as an ai",
    "as a language model",
    "i cannot access",
    "chatgpt",
    "lorem ipsum",
)

PLACEHOLDER_SOURCE_MARKERS = (
    "example.com",
    "example.org",
    "TODO",
    "TBD",
    "insert source",
    "citation needed",
    "http://localhost",
)

REQUIRED_PROSE_MARKERS = (
    "### Heron Fact",
    "### Myth or Fact?",
)

REQUIRED_META_MARKERS = (
    "### Photograph Recommendation 1",
    "### Photograph Recommendation 2",
    "### Source Ledger",
    "### Character Count",
    "### Self-Evaluation",
)

# Back-compat alias
REQUIRED_CHAPTER_MARKERS = REQUIRED_PROSE_MARKERS + REQUIRED_META_MARKERS

# Tool/RAG citation garbage that must never appear in reader prose
CITATION_ARTIFACT_RE = r"[【\[]\d+[\†\‡\u2020\u2021].*?[】\]]|【\d+†L\d+-L\d+】"


def chapter_path(n: int) -> Path:
    return CHAPTERS_DIR / f"ch-{n:02d}.md"


def chapter_meta_path(n: int) -> Path:
    return META_DIR / f"ch-{n:02d}.meta.md"


def draft_path(n: int, variant: str) -> Path:
    return DRAFTS_DIR / f"ch-{n:02d}-{variant}.md"


def report_path(kind: str, n: int | None = None) -> Path:
    mapping = {
        "factcheck": FACTCHECK_DIR,
        "history": HISTORY_DIR,
        "museum": MUSEUM_DIR,
        "style": STYLE_DIR,
        "photos": PHOTOS_DIR,
        "managing": MANAGING_DIR,
    }
    base = mapping[kind]
    if n is None:
        return base / "book.md"
    return base / f"ch-{n:02d}.md"


def ensure_dirs() -> None:
    for d in (
        CHAPTERS_DIR,
        META_DIR,
        DRAFTS_DIR,
        FACTCHECK_DIR,
        HISTORY_DIR,
        MUSEUM_DIR,
        STYLE_DIR,
        PHOTOS_DIR,
        MANAGING_DIR,
        STATE_DIR,
        LOGS_DIR,
        BOOK_ROOT / "summaries",
    ):
        d.mkdir(parents=True, exist_ok=True)
