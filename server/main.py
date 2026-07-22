"""blueheron.gallery server — public site + JSON API + /admin dashboard.

Run:  python -m server.main   (or run-admin.bat)
"""

import time
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import io

from . import auth, edits, payments, pipeline, settings, store, titles
from .jobs import runner

app = FastAPI(title="blueheron.gallery", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.exception_handler(HTTPException)
async def redirect_handler(request: Request, exc: HTTPException):
    if exc.status_code == 303 and exc.headers and "Location" in exc.headers:
        return RedirectResponse(exc.headers["Location"], status_code=303)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


# ---------------- public API ----------------

@app.get("/api/photos")
async def api_photos():
    photos = sorted(store.active_photos(), key=lambda p: p.get("sort", 0))
    return {"photos": photos}


@app.get("/api/catalog")
async def api_catalog():
    return store.load_catalog()


@app.post("/api/checkout")
async def api_checkout(payload: dict):
    try:
        url = payments.create_checkout(
            str(payload.get("photo", "")),
            str(payload.get("format", "")),
            str(payload.get("size", "")),
            int(payload.get("qty", 1)),
        )
        return {"url": url}
    except payments.PaymentsNotConfigured as e:
        return JSONResponse({"error": str(e), "fallback": "email"}, status_code=503)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    try:
        payments.handle_webhook(payload, sig)
    except payments.PaymentsNotConfigured:
        return Response(status_code=503)
    except Exception:
        return Response(status_code=400)
    return {"received": True}


# ---------------- admin: auth ----------------

@app.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    warning = "" if settings.auth_configured() else (
        "Auth is not configured. Set ADMIN_PASSWORD and SECRET_KEY in .env, "
        "then restart the server."
    )
    return templates.TemplateResponse(
        request, "login.html", {"warning": warning, "error": ""}
    )


@app.post("/admin/login")
async def login_submit(request: Request, password: str = Form(...)):
    if not auth.check_password(password):
        time.sleep(1.0)  # soften brute-force attempts
        return templates.TemplateResponse(
            request, "login.html",
            {"warning": "", "error": "Wrong password."},
            status_code=401,
        )
    resp = RedirectResponse("/admin", status_code=303)
    resp.set_cookie(
        settings.SESSION_COOKIE,
        auth.make_token(),
        max_age=settings.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return resp


@app.get("/admin/logout")
async def logout():
    resp = RedirectResponse("/admin/login", status_code=303)
    resp.delete_cookie(settings.SESSION_COOKIE)
    return resp


# ---------------- admin: pages ----------------

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, _=Depends(auth.require_admin)):
    orders = store.list_orders(limit=50)
    return templates.TemplateResponse(request, "dashboard.html", {
        "folders": pipeline.scan_raw(),
        "job": runner.current.to_dict() if runner.current else None,
        "photo_count": len(store.load_photos()),
        "active_count": len(store.active_photos()),
        "new_orders": sum(1 for o in orders if o["fulfillment"] == "new"),
        "stripe_ok": settings.stripe_configured(),
    })


@app.post("/admin/process")
async def admin_process(folder: str = Form(""), _=Depends(auth.require_admin)):
    label = f"Process {folder or 'raw/ (loose files)'}"
    try:
        job = runner.submit("process", label,
                            lambda j: pipeline.run_process(j, folder))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return RedirectResponse(f"/admin/job/{job.id}", status_code=303)


@app.post("/admin/publish")
async def admin_publish(_=Depends(auth.require_admin)):
    try:
        job = runner.submit("publish", "Publish to site", pipeline.run_publish)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return RedirectResponse(f"/admin/job/{job.id}", status_code=303)


@app.get("/admin/job/{job_id}", response_class=HTMLResponse)
async def admin_job(job_id: str, request: Request, _=Depends(auth.require_admin)):
    job = runner.get(job_id)
    if not job:
        raise HTTPException(404, "No such job")
    return templates.TemplateResponse(
        request, "job.html", {"job": job.to_dict()}
    )


@app.get("/admin/job/{job_id}/json")
async def admin_job_json(job_id: str, request: Request, _=Depends(auth.require_admin)):
    job = runner.get(job_id)
    if not job:
        raise HTTPException(404, "No such job")
    d = job.to_dict()
    d["log"] = list(job.log_lines)[-40:]
    return d


@app.get("/admin/photos", response_class=HTMLResponse)
async def admin_photos(request: Request, _=Depends(auth.require_admin)):
    return templates.TemplateResponse(
        request, "photos.html", {"photos": store.load_photos()}
    )


@app.post("/admin/photos/{slug}")
async def admin_photo_save(
    slug: str,
    title: str = Form(""),
    caption: str = Form(""),
    sort: int = Form(0),
    active: str = Form(""),
    _=Depends(auth.require_admin),
):
    store.upsert_photo(slug, title=title, caption=caption,
                       sort=sort, active=bool(active))
    return RedirectResponse("/admin/photos", status_code=303)


# ---------------- admin: editor ----------------

@app.get("/admin/editor", response_class=HTMLResponse)
async def admin_editor_list(request: Request, _=Depends(auth.require_admin)):
    from core.processor import find_images

    settings.RAW_DIR.mkdir(exist_ok=True)
    files = sorted(
        [p for p in settings.RAW_DIR.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg")],
        key=lambda p: p.name,
    )
    all_edits = edits.load_edits()
    items = []
    for p in files:
        rel = p.relative_to(settings.RAW_DIR).as_posix()
        e = all_edits.get(p.name, {})
        items.append({
            "name": p.name, "rel": rel,
            "title": e.get("title", ""),
            "has_crop": bool(e.get("crop")) or bool(e.get("rotate")),
        })
    return templates.TemplateResponse(
        request, "editor_list.html", {"items": items}
    )


@app.get("/admin/editor/{name}", response_class=HTMLResponse)
async def admin_editor(name: str, request: Request, _=Depends(auth.require_admin)):
    src = settings.RAW_DIR / name
    if not src.exists():
        raise HTTPException(404, "No such raw photo")
    edit = edits.get_edit(name)
    return templates.TemplateResponse(request, "editor.html", {
        "name": name,
        "edit": edit,
        "ai_on": settings.ai_titles_configured(),
    })


@app.post("/admin/editor/{name}")
async def admin_editor_save(
    name: str,
    title: str = Form(""),
    caption: str = Form(""),
    rotate: int = Form(0),
    crop_x: float = Form(-1), crop_y: float = Form(-1),
    crop_w: float = Form(-1), crop_h: float = Form(-1),
    _=Depends(auth.require_admin),
):
    crop = None
    if crop_w > 0 and crop_h > 0:
        crop = {"x": crop_x, "y": crop_y, "w": crop_w, "h": crop_h}
    edits.save_edit(name, title=title, caption=caption, crop=crop, rotate=rotate)
    return RedirectResponse("/admin/editor", status_code=303)


@app.get("/admin/raw/{name}")
async def admin_raw(name: str, request: Request, max: int = 0,
                    _=Depends(auth.require_admin)):
    """Serve a raw photo (optionally downscaled) for the editor preview."""
    src = settings.RAW_DIR / name
    if not src.exists():
        raise HTTPException(404, "No such raw photo")
    if max and max > 0:
        from PIL import Image, ImageOps

        img = ImageOps.exif_transpose(Image.open(src))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.thumbnail((max, max))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        return Response(buf.getvalue(), media_type="image/jpeg")
    return FileResponse(src)


@app.post("/admin/api/suggest-titles/{name}")
async def admin_suggest_titles(name: str, request: Request,
                               _=Depends(auth.require_admin)):
    src = settings.RAW_DIR / name
    if not src.exists():
        raise HTTPException(404, "No such raw photo")
    return titles.suggest(src, subject_hint=name)


@app.get("/admin/orders", response_class=HTMLResponse)
async def admin_orders(request: Request, _=Depends(auth.require_admin)):
    orders = store.list_orders()
    for o in orders:
        o["hint"] = payments.fulfill_hint(o)
        o["amount"] = f"${(o['amount_total'] or 0) / 100:,.2f}"
    return templates.TemplateResponse(
        request, "orders.html", {"orders": orders}
    )


@app.post("/admin/orders/{order_id}")
async def admin_order_save(
    order_id: int,
    fulfillment: str = Form("new"),
    notes: str = Form(""),
    _=Depends(auth.require_admin),
):
    store.set_fulfillment(order_id, fulfillment, notes)
    return RedirectResponse("/admin/orders", status_code=303)


# ---------------- static site (must be mounted last) ----------------

app.mount("/", StaticFiles(directory=str(settings.SITE_DIR), html=True), name="site")


def run() -> None:
    import uvicorn

    uvicorn.run(app, host=settings.HOST, port=settings.PORT)


if __name__ == "__main__":
    run()
