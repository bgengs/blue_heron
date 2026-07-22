# Prodigi API auto-fulfillment (2026-07-21)

## Context
User expected successful Stripe purchases to create real Prodigi print orders across wall art, home, drinkware, tech, and stationery. The site previously recorded Stripe orders only and left Prodigi as a **manual** dashboard step.

## What changed
- `web/lib/prodigi.php` — Prodigi Print API v4 client (create order, SKU lookup, signed asset URLs). Uses PHP streams (no curl ext).
- `web/api/webhook.php` — after `checkout.session.completed`, records the order then POSTs to Prodigi when `prodigi_api_key` is set.
- `web/api/print-asset.php` — HMAC-signed endpoint so Prodigi can download full-res print JPGs.
- `web/lib/db.php` — `prodigi_order_id` / `prodigi_error` columns; auto fulfillment `placed-with-prodigi` or `prodigi-error`.
- `web/data/catalog.json` — every product option has a `prodigi` SKU map (verify before live).
- `web/config.php` + `config.local.php(.example)` — `prodigi_api_key`, `prodigi_sandbox`, `prodigi_shipping_method`, `asset_signing_secret`.
- Studio publish (`server/pipeline.py`) also copies `output/print/` → `web/images/print/` (denied by `.htaccess`; served only via signed URL).
- Admin UI shows Prodigi id / errors.

## To go live
1. Put Prodigi API key in `web/config.local.php` (`prodigi_sandbox: true` first).
2. Set `site_url` to a host Prodigi can reach (not localhost).
3. Publish print files into `web/images/print/`.
4. Verify each SKU with Prodigi’s product endpoint — some stationery/tech SKUs are best-effort placeholders.

## Note
Without `prodigi_api_key`, behavior stays manual (`fulfillment: new`).
