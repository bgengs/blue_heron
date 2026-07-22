"""Title-idea suggestions for art prints.

Two sources, same output shape (a list of strings):
  - curated: an offline generator built from heron-themed word banks. Always
    available, instant, free. Titles are evocative but generic (it can't see
    the photo).
  - ai: if ANTHROPIC_API_KEY is set, Claude looks at the actual image and
    proposes titles specific to what's in the frame.
"""

import base64
import json
import random
from pathlib import Path

from . import settings

# ---------------- curated generator ----------------

_OPENERS = [
    "The {noun}", "A {noun}", "{noun}", "Of {plural}", "Where {clause}",
    "In the {place}", "{adj} {noun}",
]

_NOUNS = [
    "Sentinel", "Patience", "Stillness", "Vigil", "Reflection", "Solitude",
    "Watcher", "Homecoming", "Courtship", "Reverie", "Quietude", "Keeper",
    "Wanderer", "Elder", "Statue", "Silhouette", "Vow", "Gathering",
]
_PLURAL = ["Solitudes", "Patiences", "Shallows", "Reflections", "Reeds",
           "Cottonwoods", "Small Hours", "Long Waits", "Still Waters"]
_ADJ = ["Patient", "Silent", "Still", "Lone", "Ancient", "Watchful", "Grey",
        "Morning", "Quiet", "Tidal", "Wading", "Feathered"]
_PLACE = ["Shallows", "Rookery", "Cottonwoods", "Marsh Light", "River Bend",
          "Reeds", "Slough", "Wetland Dawn", "Still Water"]
_CLAUSE = ["Granite Meets Water", "the River Waits", "Stillness Is Shared",
           "the Reeds Keep Watch", "Morning Finds the Nest",
           "Patience Has a Shape", "the Long Wait Begins"]
_PAIR = [
    "Two Against the Morning", "A Pair of Solitudes", "Side by Side",
    "The Long Marriage", "Nest and Keep", "Both of Us, Waiting",
    "Home in the High Branches", "The Stick Ceremony", "Bound for the Season",
]
_SINGLE = [
    "The Patient Hour", "Keeper of the Shallows", "A Geography of Patience",
    "The Statue and the Stream", "Grey Against the Green",
    "One Foot in the Water", "The Long Wait", "Sentinel at First Light",
    "Still as Granite", "The Waiting Kind",
]


def _compose() -> str:
    tmpl = random.choice(_OPENERS)
    return tmpl.format(
        noun=random.choice(_NOUNS), plural=random.choice(_PLURAL),
        adj=random.choice(_ADJ), place=random.choice(_PLACE),
        clause=random.choice(_CLAUSE),
    )


def curated_titles(n: int = 8, subject_hint: str = "") -> list[str]:
    """A varied handful of ready-made titles + composed ones."""
    pool = list(_SINGLE)
    # Nudge toward pair titles when the filename hints at two birds.
    if any(w in subject_hint.lower() for w in ("pair", "love", "two", "together", "couple")):
        pool = list(_PAIR) + pool
    picks = random.sample(pool, min(n, len(pool)))
    while len(picks) < n:
        c = _compose()
        if c not in picks:
            picks.append(c)
    random.shuffle(picks)
    return picks[:n]


# ---------------- AI (optional) ----------------

_PROMPT = (
    "You are helping a wildlife photographer name a fine-art print of a great "
    "blue heron for a gallery shop. Look at the photo and suggest 8 evocative, "
    "gallery-worthy titles. Keep each under 5 words, title case, no quotes, no "
    "numbering. Vary the mood (poetic, place-based, plain-strong). Return ONLY "
    "a JSON array of 8 strings."
)


def ai_titles(image_path: Path, n: int = 8) -> list[str]:
    """Claude looks at the actual image. Raises if not configured/available."""
    if not settings.ai_titles_configured():
        raise RuntimeError("No ANTHROPIC_API_KEY set")
    import anthropic  # lazy — optional dependency

    data = image_path.read_bytes()
    media = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": media,
                    "data": base64.standard_b64encode(data).decode(),
                }},
                {"type": "text", "text": _PROMPT},
            ],
        }],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end != -1:
        try:
            titles = json.loads(text[start:end + 1])
            return [str(t).strip() for t in titles][:n]
        except json.JSONDecodeError:
            pass
    # Fallback: split lines if the model didn't return clean JSON.
    return [ln.strip(" -*\t") for ln in text.splitlines() if ln.strip()][:n]


def suggest(image_path: Path, subject_hint: str = "", n: int = 8) -> dict:
    """Best available source. Never raises — falls back to curated."""
    if settings.ai_titles_configured() and image_path.exists():
        try:
            return {"source": "ai", "titles": ai_titles(image_path, n)}
        except Exception as e:  # network, quota, missing sdk, bad response
            return {
                "source": "curated",
                "titles": curated_titles(n, subject_hint),
                "note": f"AI unavailable ({type(e).__name__}); showing curated ideas.",
            }
    return {"source": "curated", "titles": curated_titles(n, subject_hint)}
