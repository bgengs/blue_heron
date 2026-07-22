# Fix unarchive for gbh_fly crops

Restore used POST `/admin/editor/{filename}.jpg/archive`, which is brittle with a `.jpg` in the path. Replaced with `/admin/editor/set-archive` (name + archived form fields).

Archived list now has a **Restore** button on each tile, plus **Restore all gbh_fly**. Bulk DJI archive still only matches names that *start with* `DJI_` (not crops that contain `DJI_` mid-name).
