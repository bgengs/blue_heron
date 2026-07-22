"""Environment-driven settings. Reads .env at the project root."""

import os
from pathlib import Path

from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(APP_ROOT / ".env")

SITE_DIR = APP_ROOT / "site"
RAW_DIR = APP_ROOT / "raw"
OUTPUT_DIR = APP_ROOT / "output"
DATA_DIR = APP_ROOT / "data"          # studio-only: edits, registry, legacy orders
ORDERS_DB = DATA_DIR / "orders.db"

# The PHP site is the live deploy target. The Python studio tool publishes
# protected images and the photo manifest into it; PHP reads them.
WEB_ROOT = APP_ROOT / "web"
WEB_DATA = WEB_ROOT / "data"
PHOTOS_JSON = WEB_DATA / "photos.json"     # written by studio, read by PHP
CATALOG_JSON = WEB_DATA / "catalog.json"   # authored; PHP owns pricing
SITE_WEB_IMAGES = WEB_ROOT / "images" / "web"
SITE_THUMB_IMAGES = WEB_ROOT / "images" / "thumb"
SITE_PRINT_IMAGES = WEB_ROOT / "images" / "print"  # full-res for Prodigi asset URLs
SITE_FRAMED_IMAGES = WEB_ROOT / "images" / "framed"  # brand banner for site/share

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY", "")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8807")

# Optional: AI title suggestions from the actual photo. Without a key, the
# editor falls back to an offline curated generator.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

EDITS_JSON = DATA_DIR / "edits.json"   # studio-only, not deployed

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8807"))

SESSION_COOKIE = "bh_admin"
SESSION_MAX_AGE = 7 * 24 * 3600  # 7 days


def stripe_configured() -> bool:
    return bool(STRIPE_SECRET_KEY)


def ai_titles_configured() -> bool:
    return bool(ANTHROPIC_API_KEY)


def auth_configured() -> bool:
    return bool(ADMIN_PASSWORD and SECRET_KEY)
