"""Stripe Checkout integration.

Payment only — fulfillment stays manual-first (place the order in the
Prodigi dashboard from the admin Orders page). Automating Prodigi's API
later only touches fulfill_hint(), nothing else.
"""

from typing import Optional

from . import settings, store


class PaymentsNotConfigured(Exception):
    pass


def _stripe():
    if not settings.stripe_configured():
        raise PaymentsNotConfigured(
            "Stripe keys are not set. Add STRIPE_SECRET_KEY to .env."
        )
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def create_checkout(photo_slug: str, fmt: str, size: str, qty: int) -> str:
    """Validate the item server-side and return a Stripe Checkout URL."""
    photo = store.get_photo(photo_slug)
    if not photo or not photo.get("active"):
        raise ValueError("Unknown photo")
    catalog = store.load_catalog()
    fmt_def = catalog.get("formats", {}).get(fmt)
    if not fmt_def:
        raise ValueError("Unknown format")
    unit_cents = store.price_for(fmt, size)
    if unit_cents is None:
        raise ValueError("Unknown size for this format")
    qty = max(1, min(int(qty), 10))

    stripe = _stripe()
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "quantity": qty,
            "price_data": {
                "currency": catalog.get("currency", "usd"),
                "unit_amount": unit_cents,
                "product_data": {
                    "name": f"{photo['title']} — {fmt_def['label']}, {size}\"",
                    "description": "Great blue heron fine art print — blueheron.gallery",
                },
            },
        }],
        shipping_address_collection={"allowed_countries": ["US", "CA"]},
        metadata={
            "photo": photo_slug,
            "format": fmt,
            "size": size,
            "qty": str(qty),
        },
        success_url=f"{settings.SITE_URL}/order-success.html",
        cancel_url=f"{settings.SITE_URL}/order.html?cancelled=1",
    )
    return session.url


def handle_webhook(payload: bytes, sig_header: Optional[str]) -> None:
    """Verify and process a Stripe webhook event."""
    stripe = _stripe()
    if settings.STRIPE_WEBHOOK_SECRET:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    else:
        # Dev fallback (stripe CLI without a configured secret): trust payload.
        import json

        event = json.loads(payload)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        store.record_order(session)


def fulfill_hint(order: dict) -> str:
    """Everything needed to place this order in the Prodigi dashboard."""
    import json

    ship = {}
    try:
        ship = json.loads(order.get("shipping_json") or "{}")
    except json.JSONDecodeError:
        pass
    addr = (ship.get("address") or {}) if isinstance(ship, dict) else {}
    lines = [
        f"Photo: {order.get('photo')}  |  {order.get('format')} {order.get('size')}\"  x{order.get('qty')}",
        f"Print file: output/print/{order.get('photo')}.jpg  (300 DPI, full res)",
        f"Ship to: {ship.get('name') or order.get('name') or ''}",
        f"  {addr.get('line1', '')} {addr.get('line2') or ''}".rstrip(),
        f"  {addr.get('city', '')}, {addr.get('state', '')} {addr.get('postal_code', '')} {addr.get('country', '')}",
        f"Customer email: {order.get('email')}",
    ]
    return "\n".join(lines)
