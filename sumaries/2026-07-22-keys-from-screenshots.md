# Keys transferred from eagle.mt .env screenshots (2026-07-22)

User could not copy-paste from nano; keys were read from screenshots and written into gitignored local config:

- `web/config.local.php` — Stripe live + Prodigi live (`prodigi_sandbox` false)
- `.env` — same Stripe/Prodigi for Python studio
- `book/.env` — Lulu client key/secret (+ base64 basic auth) for book printing later

`site_url` left as localhost for local PHP; Prodigi asset download needs a public URL when testing live fulfillment.
