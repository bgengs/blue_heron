#!/usr/bin/env python3
"""Build the field-guide section from content/guide/*.md.

Converts the research markdown (with footnote citations and tables) into
PHP pages under web/guide/ that share the site's nav partial, plus an index.
Re-run any time the markdown changes:

    python scripts/build_guide.py
"""

from __future__ import annotations

import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "content" / "guide"
OUT = ROOT / "web" / "guide"

MD_EXT = ["extra", "tables", "footnotes", "sane_lists", "toc"]

# Slug (from NN-name.md) -> nav label + one-line teaser for the index.
PAGES = [
    ("01-overview", "Overview", "Meet Ardea herodias — the essentials at a glance."),
    ("02-identification", "Identification", "Size, shape, plumage, and how to be sure it's a great blue."),
    ("03-look-alikes", "Look-alikes", "Heron vs. egret vs. sandhill crane — telling them apart."),
    ("04-taxonomy-subspecies", "Taxonomy & Subspecies", "The great white heron and other regional forms."),
    ("05-habitat", "Habitat", "Where herons live, from tidal flats to dry fields."),
    ("06-range-distribution", "Range & Distribution", "Across North and Central America and beyond."),
    ("07-migration", "Migration", "Who moves, who stays, and why."),
    ("08-diet-hunting", "Diet & Hunting", "The statue, the strike, and everything on the menu."),
    ("09-behavior", "Behavior", "Territory, solitude, and the night shift."),
    ("10-breeding-rookeries", "Breeding & Rookeries", "Courtship, colonies, and nest building."),
    ("11-eggs-chicks", "Eggs & Chicks", "From pale-blue eggs to first flight."),
    ("12-sounds-calls", "Sounds & Calls", "The famous frawnk and other heron noises."),
    ("13-lifespan-predators", "Lifespan & Predators", "How long they live and what threatens them."),
    ("14-adaptations", "Adaptations", "Powder down, the pectinate claw, night vision."),
    ("15-conservation-status", "Conservation Status", "Population, trend, and protection."),
    ("16-threats", "Threats", "Eagles, disturbance, habitat loss, contaminants."),
    ("17-herons-and-people", "Herons & People", "The plume trade, fish ponds, and the law."),
    ("18-culture-symbolism", "Culture & Symbolism", "The heron in story, art, and city seals."),
    ("19-watching-guide", "Watching Guide", "How to find and watch herons without disturbing them."),
    ("20-faq-fun-facts", "FAQ & Fun Facts", "Quick answers and things that surprise people."),
    ("21-resources", "Resources", "Sources and where to learn more."),
]

# PHP header/footer shared by every generated guide page. Uses the site's
# nav/head/footer partials so the navigation is identical everywhere.
PHP_HEAD = """<?php
$rel = '../';
$active = 'guide';
$page_title = {title_php};
$page_desc = {teaser_php};
$extra_css = ['assets/guide.css'];
require dirname(__DIR__) . '/lib/data.php';
include dirname(__DIR__) . '/partials/head.php';
include dirname(__DIR__) . '/partials/nav.php';
?>
"""

PHP_FOOT = """<?php include dirname(__DIR__) . '/partials/footer.php'; ?>
"""

PAGE_BODY = """
<div class="guide-layout">
  <aside class="guide-nav">
    <p class="guide-nav-title">Field Guide</p>
    <ol>{toc}</ol>
  </aside>
  <article class="guide-article">
    {body}
    <div class="guide-pager">{pager}</div>
  </article>
</div>
"""

INDEX_BODY = """
<header class="guide-hero">
  <p class="section-kicker">FIELD GUIDE</p>
  <h1 class="section-title">The Great Blue Heron</h1>
  <p class="section-sub">Everything you ever wanted to know about <em>Ardea herodias</em> —
  compiled from Cornell Lab, Audubon, Birds of the World, and other public sources.</p>
</header>
<div class="guide-index">{cards}</div>
"""


def _php_str(s: str) -> str:
    """Render a Python string as a single-quoted PHP string literal."""
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def md_to_html(text: str) -> str:
    # Fix Kimi's [^1^] footnote style to Python-Markdown's [^1].
    text = re.sub(r"\[\^(\d+)\^\]", r"[^\1]", text)
    return markdown.markdown(text, extensions=MD_EXT)


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    slugs = [s for s, _, _ in PAGES]

    toc_items = "".join(
        f'<li><a href="{s}.php">{label}</a></li>' for s, label, _ in PAGES
    )

    for i, (slug, label, teaser) in enumerate(PAGES):
        src = SRC / f"{slug}.md"
        if not src.exists():
            print(f"  skip (missing): {slug}")
            continue
        body = md_to_html(src.read_text(encoding="utf-8"))

        prev_link = (
            f'<a href="{slugs[i-1]}.php">← {PAGES[i-1][1]}</a>' if i > 0 else "<span></span>"
        )
        next_link = (
            f'<a href="{slugs[i+1]}.php">{PAGES[i+1][1]} →</a>'
            if i < len(PAGES) - 1 else "<span></span>"
        )

        head = PHP_HEAD.format(
            title_php=_php_str(f"{label} — Field Guide"),
            teaser_php=_php_str(teaser),
        )
        page = head + PAGE_BODY.format(
            toc=toc_items, body=body, pager=prev_link + next_link,
        ) + PHP_FOOT
        (OUT / f"{slug}.php").write_text(page, encoding="utf-8")

    cards = "".join(
        f'<a class="guide-card" href="{s}.php"><span class="gc-num">{s[:2]}</span>'
        f'<span class="gc-title">{label}</span><span class="gc-teaser">{teaser}</span></a>'
        for s, label, teaser in PAGES
    )
    index_head = PHP_HEAD.format(
        title_php=_php_str("Field Guide"),
        teaser_php=_php_str("A research-backed field guide to the great blue heron."),
    )
    (OUT / "index.php").write_text(
        index_head + INDEX_BODY.format(cards=cards) + PHP_FOOT, encoding="utf-8"
    )
    print(f"Built {len(PAGES)} guide pages + index -> {OUT}")


if __name__ == "__main__":
    build()
