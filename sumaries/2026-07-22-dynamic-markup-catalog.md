# Catalog expansion + dynamic Prodigi markup (2026-07-22)

## Why
User selling beyond wall prints (Etsy + site): mouse pads, home decor, etc., and
wanted retail driven by Prodigi wholesale × markup.

## Catalog adds (`web/data/catalog.json`)
- Tech: **mousepad** (`H-MOUSEMAT`), **desk-mat** (S/M/L)
- Home: **bath-mat**, **towel**, **tote**
- Category blurb updated to “Tech & Desk” / home decor

## Pricing
- `markup_multiplier` (default **2.5**) + `markup_quote_country` in config
- `bh_prodigi_refresh_prices()` quotes each SKU, sets
  `retail = ceil(cost × markup)`, stores `cost` on the prodigi map
- Admin UI: `/admin/prices.php` (linked from Orders)

## Local note
WinGet PHP build had **OpenSSL disabled**, so HTTPS quotes fail until
`extension=openssl` is enabled in `php.ini` (or run refresh on the host).
Production PHP hosts normally already have OpenSSL.
