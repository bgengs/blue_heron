# PHP admin setup (2026-07-21)

## What the user asked
Whether admin is PHP / couldn't get it running. Referenced `run-admin.bat` and `web/`.

## Clarification (two admins)

| Tool | Stack | Purpose | How to run |
|------|--------|---------|------------|
| `run-admin.bat` | **Python** FastAPI (`server/`) | Local studio: crop, process, publish photos | `python -m server.main` → http://127.0.0.1:8807/admin |
| `web/admin/` | **PHP** | Live storefront order fulfillment | `cd web` then `php -S localhost:8808` → http://localhost:8808/admin/ |

Python publishes protected images + `photos.json` into `web/`. PHP is what deploys to the host.

## What was wrong
- PHP was not installed (`php` not on PATH).
- `run-admin.bat` never starts the PHP site — it only starts the Python studio.

## What we did
1. Installed **PHP 8.3.32** via `winget install --id PHP.PHP.8.3`.
2. Confirmed `web/config.local.php` and `web/vendor/` already present.
3. Started PHP built-in server: `php -S localhost:8808` from `web/` (port **8808**).

## URLs
- PHP site / orders admin: http://localhost:8808/ and http://localhost:8808/admin/
- Python studio admin: http://127.0.0.1:8807/admin (password in root `.env` as `ADMIN_PASSWORD`)
- PHP admin password: `admin_password` in `web/config.local.php`

## Notes for later
- New shells may need a restart (or refreshed PATH) after the winget PHP install.
- Optional: add a `run-web.bat` that cds to `web` and runs `php -S localhost:8808` so double-click matches `run-admin.bat`.

## Follow-up: PDO sqlite driver (same day)

After login, admin threw `PDOException: could not find driver` from `web/lib/db.php` — winget PHP had **no `php.ini`**, so `pdo_sqlite` was off.

Fix:
1. Copied `php.ini-development` → `php.ini` in the WinGet PHP package dir.
2. Enabled `extension_dir = "ext"`, `extension=pdo_sqlite`, `extension=sqlite3`.
3. Restarted `php -S localhost:8808`.

Verify: `php -m` shows `pdo_sqlite` and `sqlite3`.
