"""SiteSense web demo (FastAPI). Run: uvicorn app.main:app --reload"""

import base64
import html
import sys
import time
from pathlib import Path

import json
from typing import List

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import sitesense  # noqa: E402

app = FastAPI(title="SiteSense")
app.mount("/samples", StaticFiles(directory=ROOT / "samples"), name="samples")
STATIC = Path(__file__).parent / "static"
MAX_BYTES = 10 * 1024 * 1024
DOMAINS = {"oil_gas": "oil & gas wellsite and pipeline inspection",
           "industrial": "industrial maintenance",
           "agriculture": "agriculture",
           "facilities": "facilities"}


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(STATIC / "index.html")


async def _to_data_url(image: UploadFile) -> str:
    data = await image.read()
    if not data:
        raise HTTPException(400, "Empty image")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image too large (max 10 MB)")
    mime = image.content_type or "image/jpeg"
    if not mime.startswith("image/"):
        raise HTTPException(415, "Upload must be an image")
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


@app.get("/api/health")
def health():
    return {"ok": True, "mock": sitesense.is_mock()}


@app.post("/api/diagnose")
async def api_diagnose(image: UploadFile = File(...), domain: str = Form("oil_gas"),
                       notes: str = Form(""), origin: str = Form("")):
    url = await _to_data_url(image)
    try:
        origin_obj = json.loads(origin) if origin else None
    except json.JSONDecodeError:
        origin_obj = None
    domain_text = DOMAINS.get(domain, domain)
    try:
        result = sitesense.run_pipeline(url, user_note=notes[:2000], domain=domain_text,
                                        seg_prompt="equipment defect", hint=image.filename or "",
                                        origin=origin_obj)
    except Exception as exc:  # surface model/API errors to the UI
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=502)
    result["created_at"] = time.strftime("%Y-%m-%d %H:%M")
    return result


def _origin_text(o):
    if not o:
        return "Direct ground inspection"
    a = o.get("aoi") or {}
    parts = []
    if a:
        parts.append(f"Satellite {a.get('id', '')} ({a.get('lat', '')}, {a.get('lon', '')})")
    if o.get("drone_image"):
        parts.append(f"Drone image {o['drone_image']} (rank {o.get('drone_rank', '?')}, {o.get('drone_severity', '')})")
    return " → ".join(parts) + " → Ground"


def _li(items):
    return "".join(f"<li>{html.escape(str(i))}</li>" for i in items or [])


@app.post("/api/work_order.html", response_class=HTMLResponse)
async def work_order_html(payload: dict):
    """Printable, PDF-ready HTML of a work order (use the browser's Print > Save as PDF)."""
    wo, dx = payload.get("work_order", {}), payload.get("diagnosis", {})
    e = lambda v: html.escape(str(v or ""))
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Work order - {e(wo.get('title'))}</title>
<style>body{{font:14px/1.45 system-ui,sans-serif;max-width:780px;margin:24px auto;color:#111}}
h1{{border-bottom:4px solid #ff6a00;padding-bottom:6px}}.p{{display:inline-block;padding:2px 10px;border-radius:4px;background:#ff6a00;color:#fff;font-weight:700}}
td{{padding:4px 8px;vertical-align:top}}.sig{{margin-top:40px;display:flex;gap:40px}}.sig div{{flex:1;border-top:1px solid #333;padding-top:4px}}</style></head>
<body><h1>SiteSense Work Order</h1>
<table><tr><td><b>Title</b></td><td>{e(wo.get('title'))}</td></tr>
<tr><td><b>Priority</b></td><td><span class="p">{e(wo.get('priority'))}</span></td></tr>
<tr><td><b>Created</b></td><td>{e(payload.get('created_at'))}</td></tr>
<tr><td><b>Asset type</b></td><td>{e(dx.get('asset_type', ''))}</td></tr>
<tr><td><b>Origin</b></td><td>{e(_origin_text(wo.get('origin')))}</td></tr>
<tr><td><b>Location / LSD</b></td><td>______________________</td></tr></table>
<h3>Description</h3><p>{e(wo.get('description'))}</p>
<h3>Immediate actions</h3><ol>{_li(wo.get('immediate_actions'))}</ol>
<h3>Recommended next steps</h3><ol>{_li(wo.get('recommended_next_steps'))}</ol>
<h3>Safety notes</h3><ul>{_li(wo.get('safety_notes'))}</ul>
<p><i>{e(dx.get('regulatory_note', ''))}</i></p>
<p style="color:#666">AI-assisted draft. Verify on site; this is not a substitute for gas detection, permits or qualified inspection.</p>
<div class="sig"><div>Inspected by</div><div>Supervisor approval</div></div></body></html>"""


# --------------------------------------------------------------------------- satellite
SAT_DIR = ROOT / "samples" / "satellite"


@app.get("/api/satellite/demo")
def satellite_demo():
    """Bundled Sentinel-2 clip + DEMO areas of interest (mock, or real model if a key is set)."""
    meta = json.loads((SAT_DIR / "scene.json").read_text())
    urls = []
    if not sitesense.is_mock():
        urls = [sitesense.image_to_data_url(str(SAT_DIR / f)) for f in
                ("truecolor_before.jpg", "truecolor_after.jpg", "ndvi_change.png")]
    try:
        result = sitesense.analyze_satellite(urls, scene_meta=meta)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=502)
    result["scene"] = meta
    result["images"] = {k: f"/samples/satellite/{k}{ext}" for k, ext in
                        (("truecolor_before", ".jpg"), ("truecolor_after", ".jpg"), ("ndvi_change", ".png"))}
    return result


# --------------------------------------------------------------------------- drone
DRONE_DIR = ROOT / "samples" / "drone"
MAX_BATCH = 30


@app.get("/api/drone/samples")
def drone_samples():
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    return {"images": [f"/samples/drone/{p.name}" for p in sorted(DRONE_DIR.iterdir())
                       if p.suffix.lower() in exts]}


@app.post("/api/drone")
async def api_drone(images: List[UploadFile] = File(default=[]), notes: str = Form(""),
                    aoi: str = Form(""), use_samples: str = Form("")):
    """Batch survey: upload many images (or use samples/drone/), ranked worst-first."""
    try:
        aoi_obj = json.loads(aoi) if aoi else None
    except json.JSONDecodeError:
        aoi_obj = None
    if use_samples == "1":
        batch = sitesense.load_image_dir(DRONE_DIR)
    else:
        if not images:
            raise HTTPException(400, "Upload at least one image or set use_samples=1")
        if len(images) > MAX_BATCH:
            raise HTTPException(413, f"Max {MAX_BATCH} images per survey")
        batch = [(im.filename or f"image_{i}", await _to_data_url(im)) for i, im in enumerate(images)]
    report = sitesense.drone_survey(batch, notes=notes[:2000], aoi=aoi_obj)
    for f in report["findings"]:  # thumbnails for sample images
        if use_samples == "1":
            f["image_url"] = f"/samples/drone/{f['image']}"
    report["created_at"] = time.strftime("%Y-%m-%d %H:%M")
    return report


@app.post("/api/drone/report.html", response_class=HTMLResponse)
async def drone_report_html(report: dict):
    e = lambda v: html.escape(str(v if v is not None else ""))
    aoi = report.get("aoi") or {}
    rows = "".join(
        f"<tr><td>{e(f.get('rank'))}</td><td><span class='s {e(f.get('severity'))}'>{e(f.get('severity'))}</span></td>"
        f"<td>{e(f.get('image'))}</td><td>{e(f.get('issue_summary'))}<ul>{_li(f.get('immediate_actions'))}</ul>"
        f"{('<b>Ground close-up:</b> ' + e(f.get('ground_photo_request'))) if f.get('needs_ground_closeup') else ''}</td></tr>"
        for f in report.get("findings", []))
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>SiteSense drone survey report</title>
<style>body{{font:14px/1.45 system-ui,sans-serif;max-width:900px;margin:24px auto;color:#111}}
h1{{border-bottom:4px solid #ff6a00;padding-bottom:6px}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ccc;padding:6px;vertical-align:top;text-align:left}}.s{{padding:2px 8px;border-radius:4px;font-weight:700;color:#fff}}
.Critical{{background:#d50000}}.High{{background:#ff6a00}}.Medium{{background:#f9a825;color:#111}}.Low{{background:#2e7d32}}</style></head>
<body><h1>SiteSense Drone Survey Report</h1>
<p><b>Created:</b> {e(report.get('created_at'))} &nbsp; <b>Images:</b> {e(report.get('image_count'))}
&nbsp; <b>Overall:</b> <span class="s {e(report.get('overall_severity'))}">{e(report.get('overall_severity'))}</span></p>
<p><b>Area of interest:</b> {e(aoi.get('id', 'n/a'))} {e(aoi.get('lat', ''))} {e(aoi.get('lon', ''))} {e(aoi.get('description', ''))}</p>
<p>{e(report.get('summary'))}</p>
<table><tr><th>#</th><th>Severity</th><th>Image</th><th>Finding / actions</th></tr>{rows}</table>
<p style="color:#666">AI-assisted draft. Images cannot detect gas. Verify on site. Drone flights must follow
Transport Canada rules and have the site operator's permission.</p></body></html>"""
