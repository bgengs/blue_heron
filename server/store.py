"""Data stores: photos manifest (JSON), print catalog (JSON), orders (SQLite)."""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

from . import settings

_lock = threading.Lock()

# ---------------- photos manifest ----------------

def load_photos() -> list[dict]:
    if not settings.PHOTOS_JSON.exists():
        return []
    return json.loads(settings.PHOTOS_JSON.read_text(encoding="utf-8"))


def save_photos(photos: list[dict]) -> None:
    with _lock:
        settings.PHOTOS_JSON.parent.mkdir(parents=True, exist_ok=True)
        settings.PHOTOS_JSON.write_text(
            json.dumps(photos, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def active_photos() -> list[dict]:
    return [p for p in load_photos() if p.get("active")]


def get_photo(slug: str) -> Optional[dict]:
    for p in load_photos():
        if p["slug"] == slug:
            return p
    return None


def upsert_photo(slug: str, **fields) -> dict:
    photos = load_photos()
    for p in photos:
        if p["slug"] == slug:
            p.update(fields)
            save_photos(photos)
            return p
    entry = {
        "slug": slug,
        "title": fields.get("title") or slug.replace("-", " ").replace("_", " ").title(),
        "caption": fields.get("caption", ""),
        "location": fields.get("location", "MONTANA"),
        "file": fields.get("file", f"{slug}.jpg"),
        "active": fields.get("active", True),
        "sort": fields.get("sort", len(photos)),
    }
    photos.append(entry)
    save_photos(photos)
    return entry


# ---------------- print catalog ----------------

def load_catalog() -> dict:
    if not settings.CATALOG_JSON.exists():
        return {"currency": "usd", "formats": {}}
    return json.loads(settings.CATALOG_JSON.read_text(encoding="utf-8"))


def price_for(fmt: str, size: str) -> Optional[int]:
    """Price in cents for a format+size, or None if not offered."""
    catalog = load_catalog()
    f = catalog.get("formats", {}).get(fmt)
    if not f:
        return None
    dollars = f.get("sizes", {}).get(size)
    if dollars is None:
        return None
    return int(round(float(dollars) * 100))


# ---------------- orders (SQLite) ----------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    stripe_session_id TEXT UNIQUE,
    payment_intent TEXT,
    email TEXT,
    name TEXT,
    amount_total INTEGER,
    currency TEXT,
    photo TEXT,
    format TEXT,
    size TEXT,
    qty INTEGER,
    shipping_json TEXT,
    status TEXT DEFAULT 'paid',
    fulfillment TEXT DEFAULT 'new',
    notes TEXT DEFAULT ''
);
"""


def _conn() -> sqlite3.Connection:
    settings.ORDERS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.ORDERS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def record_order(session: dict) -> None:
    """Insert an order from a Stripe checkout.session.completed payload."""
    md = session.get("metadata") or {}
    details = session.get("customer_details") or {}
    shipping = (
        session.get("shipping_details")
        or session.get("collected_information", {}).get("shipping_details")
        or {}
    )
    with _conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO orders
               (created, stripe_session_id, payment_intent, email, name,
                amount_total, currency, photo, format, size, qty, shipping_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                session.get("id"),
                session.get("payment_intent"),
                details.get("email") or session.get("customer_email"),
                details.get("name"),
                session.get("amount_total"),
                session.get("currency"),
                md.get("photo"),
                md.get("format"),
                md.get("size"),
                int(md.get("qty", "1")),
                json.dumps(shipping),
            ),
        )


def list_orders(limit: int = 200) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def set_fulfillment(order_id: int, fulfillment: str, notes: str = "") -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE orders SET fulfillment = ?, notes = ? WHERE id = ?",
            (fulfillment, notes, order_id),
        )
