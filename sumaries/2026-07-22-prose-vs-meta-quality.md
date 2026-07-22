# 2026-07-22 — prose-vs-meta-quality

## Concern

Early drafts (ch-01, ch-02) were thin outline prose with photo/source appendix inline; ch-01 claimed length while real prose was ~3.6k chars; ch-02 had tool citation artifacts (`【†】`) and missing meta sections.

## Changes

- Split outputs: `manuscript/chapters/ch-NN.md` = reader prose; `manuscript/meta/ch-NN.meta.md` = photos/ledger/scores
- Length gate counts **prose only** (recommendations never pad)
- New quality gates: min paragraph count, avg subsection ≥900 chars, reject citation artifacts, reject bullet-heavy stubs
- Stronger agent instructions: museum paragraphs first; meta is secondary
- Existing ch-01/ch-02 split + remain `needs_revision` for rewrite

## Note

Pipeline will expand/rewrite failing chapters in the revise phase (already flagged). New drafts use the two-file layout.
