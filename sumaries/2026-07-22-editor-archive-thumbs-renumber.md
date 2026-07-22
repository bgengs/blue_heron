# Editor archive, larger thumbs, renumber

## What changed
- **Archive** in editor (per photo + bulk “Archive all DJI originals”). Flag in `data/edits.json`; files stay on disk; archived drop out of editor list/counter.
- Editor list **dedupes** basename (root over `exp/`), sorts **`gbh_fly` first**, larger tiles (`minmax(320px)`, `?max=720`), shows index.
- Photos admin: **larger thumbs** (168×112), **Reset sort numbers** → `gbh_fly` = 1…N then the rest (`store.renumber_sort`).

## How to use
1. Editor → **Archive all DJI originals** → counter ~75 (crops only).
2. Photos → **Reset sort numbers** if gallery Sort looks wrong.
3. Restore via Archived view or per-photo Restore.

## Files
`server/edits.py`, `server/store.py`, `server/main.py`, `server/templates/{editor,editor_list,photos,base}.html`
