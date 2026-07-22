# blueheron.gallery

Print-shop + field-guide site for Bernie Gengel's great blue heron photographs.
Same shape as eagle.mt: hero → story → facts → gallery → prints → field guide,
with the eagle app's copyright-protection pipeline and a password-protected
`/admin` for processing photos and fulfilling orders.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # then edit — a random ADMIN_PASSWORD/SECRET_KEY
                              # were already generated into .env for you
python -m server.main         # or double-click run-admin.bat on Windows
```

- Public site:  http://127.0.0.1:8807/
- Admin:        http://127.0.0.1:8807/admin   (password is in `.env`)

## The photo workflow (what you asked for)

1. Drop raw JPGs into `raw/` — loose, or in subfolders (one per shoot).
   These are your unprotected originals; nothing here is ever published as-is.
2. (Optional) Go to **/admin → Editor**. Click any photo to **crop** (drag the
   box, snap to 3:2 / 1:1 / etc.), **rotate**, and set a **title + caption**.
   Stuck on a name? Hit **Suggest titles** for ideas. Edits are non-destructive
   — stored as fractions in `data/edits.json`, applied only when you Process,
   your originals never change. Re-crop and re-Process any time.
3. Go to **/admin → Process**. This runs the protection pipeline and writes
   `output/{thumbnails,web,print,watermarked,raw}/`:
   - **web** — 1600px, visible corner watermark + full-frame wash + invisible
     DCT watermark (survives re-compression) + registered perceptual hash.
   - **print** — full-resolution, 300 DPI, clean (this is the file you send
     to the print lab).
   - **watermarked** — full-res protected JPG + a lossless PNG proof carrying
     an LSB steganographic SHA-512.
4. **/admin → Publish** copies the protected *web* images into the site and
   adds any new photo to the gallery manifest (`data/photos.json`). Titles set
   in the Editor ride along automatically.
5. **/admin → Photos** — fine-tune each photo's title, caption, sort order, and
   live/hidden. These drive the public gallery and the order page.

Your ~30 incoming photos: just drop them in `raw/`, Process, Publish, then
title them. The gallery and order dropdown update automatically.

The invisible protection is real — verified end-to-end: a processed web image
re-extracts to the exact photo ID it was stamped with. To prove ownership of a
suspect image later: `python -m core` tooling from the eagle app, or the
`registry.json` shipped to `data/`.

### Prints & payment

- Formats/sizes/prices + Prodigi SKUs live in `web/data/catalog.json`.
- Stripe Checkout records the order; with `prodigi_api_key` set in
  `web/config.local.php`, the webhook creates the Prodigi print order
  automatically (see `web/README.md`). Without a key, fulfill from `/admin`
  in the Prodigi dashboard by hand.

### Title suggestions

The Editor's **Suggest titles** button works offline out of the box (a curated
heron-themed generator). If you want ideas drawn from the *actual photo*, set
`ANTHROPIC_API_KEY` in `.env` and `pip install anthropic` — then Claude looks
at the image and proposes titles. It falls back to curated automatically if the
key is missing or the call fails.

### Products & Prodigi's range

`web/data/catalog.json` already lists wall art (paper, framed, canvas, metal,
acrylic, wood, tiles), home (cushions, blankets, placemats, shower curtains),
drinkware, tech cases, and stationery — each option mapped to a Prodigi SKU
under the format’s `prodigi` key. Verify SKUs against your Prodigi account
before going live. Keep on-site checkout to what you want to sell; Etsy can
still carry the long tail via Prodigi’s Etsy channel.

### Selling on Etsy too

Prodigi has a native Etsy integration: connect your Etsy shop in the Prodigi
dashboard (Sales channels → Connect your store) and paid Etsy orders route to
Prodigi automatically for print + ship. So you can run **two** storefronts off
the same photos: this site (Stripe → Prodigi API auto-fulfill) and Etsy
(Prodigi’s native channel). The protected web images in `web/images/web/` are
also what you'd upload as Etsy listing photos.

### Turning Stripe on

1. Create a Stripe account, grab your **test** secret key (`sk_test_…`).
2. Put it in `.env` as `STRIPE_SECRET_KEY`, restart.
3. For order recording, run the Stripe CLI in dev:
   `stripe listen --forward-to 127.0.0.1:8807/api/stripe/webhook`
   and copy the `whsec_…` it prints into `STRIPE_WEBHOOK_SECRET`.
4. Test a purchase with card `4242 4242 4242 4242`. Go live by swapping in
   `sk_live_…` keys and a production webhook endpoint.

## Deploy

Two moving parts: the static `site/` and the Python `server/` (needed for
`/admin` + checkout). Simplest path: run `python -m server.main` on a small
VPS behind Caddy/Nginx with TLS for blueheron.gallery, and redirect
greatblueheron.gallery → blueheron.gallery. If you ever want the front to be
pure-static (Cloudflare Pages), the gallery already falls back to a baked-in
manifest, but you lose `/admin` and checkout.

## Layout

```
raw/            drop originals here (gitignored)
output/         pipeline output (gitignored)
core/           protection pipeline (ported from the eagle app)
server/         FastAPI: public API + /admin + Stripe
  main.py       routes + static mount
  pipeline.py   scan raw / process / publish jobs
  store.py      photos manifest, catalog, orders (SQLite)
  payments.py   Stripe Checkout + webhook + fulfillment hint
  edits.py      non-destructive crop/rotate/title store (data/edits.json)
  titles.py     title suggestions (curated + optional Claude vision)
  auth.py       cookie-session admin login
site/           the public site (static)
  order.html    print picker → Stripe
  guide/        field guide (built from content/guide)
content/guide/  field-guide markdown (edit, then rebuild)
data/           photos.json, catalog.json, orders.db, registry.json
scripts/        resize_photos.py, frame_photos.py, build_guide.py
```

Rebuild the field guide after editing `content/guide/*.md`:
`python scripts/build_guide.py`
