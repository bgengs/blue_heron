# Fix brutal git push (3.8GB binaries)

## Problem
Unpushed commits included full-res `raw/` DJI JPGs + published `web/images/{web,thumb}` (~3.8 GB pack). Push crawled at ~300 KB/s.

## Fix
- `.gitignore`: `raw/*` (keep `.gitkeep`), `web/images/web/*` + `thumb/*` (keep placeholders)
- Soft-reset 3 bloated commits onto `origin/main`, recommit code-only (~26 MB)
- `git gc --prune=now` to drop orphaned blobs locally

## Deploy note
Gallery images stay on the machine / server via **Publish**; they are not in git anymore.
