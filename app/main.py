"""SiteSense web demo (FastAPI). Run: uvicorn app.main:app --reload"""

import base64
import html
import sys
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import sitesense  # noqa: E402

app = FastAPI(title="SiteSense")
STATIC = Path(__file__).parent / "static"
MAX_BYTES = 10 * 1024 * 1024
DOMAINS = {"oil_gas": "oil & gas wellsite and pipeline inspection",
           "industrial": "industrial maintenance",
           "agriculture": "agriculture",
           "facilities": "facilities"}


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "mock": sitesense.is_mock()}


@app.post("/api/diagnose")
async def api_diagnose(image: UploadFile = File(...), domain: str = Form("oil_gas"),
                       notes: str = Form("")):
    data = await image.read()
    if not data:
        raise HTTPException(400, "Empty image")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image too large (max 10 MB)")
    mime = image.content_type or "image/jpeg"
    if not mime.startswith("image/"):
        raise HTTPException(415, "Upload must be an image")
    url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    domain_text = DOMAINS.get(domain, domain)
    try:
        result = sitesense.run_pipeline(url, user_note=notes[:2000], domain=domain_text,
                                        seg_prompt="equipment defect", hint=image.filename or "")
    except Exception as exc:  # surface model/API errors to the UI
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=502)
    result["created_at"] = time.strftime("%Y-%m-%d %H:%M")
    return result


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
<tr><td><b>Location / LSD</b></td><td>______________________</td></tr></table>
<h3>Description</h3><p>{e(wo.get('description'))}</p>
<h3>Immediate actions</h3><ol>{_li(wo.get('immediate_actions'))}</ol>
<h3>Recommended next steps</h3><ol>{_li(wo.get('recommended_next_steps'))}</ol>
<h3>Safety notes</h3><ul>{_li(wo.get('safety_notes'))}</ul>
<p><i>{e(dx.get('regulatory_note', ''))}</i></p>
<p style="color:#666">AI-assisted draft. Verify on site; this is not a substitute for gas detection, permits or qualified inspection.</p>
<div class="sig"><div>Inspected by</div><div>Supervisor approval</div></div></body></html>"""
