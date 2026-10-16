"""SiteSense Report Generator: branded PDF + map PNG.

Two report types:
  community - wildfire mapping deliverable for BC towns / regional districts (supporting
              material for a UBCM CRI FireSmart application or a Community Wildfire
              Resiliency Plan): AOI, NDVI change, historical wildfire exposure, prioritized
              treatment areas, methods and data sources.
  operator  - oil & gas site inspection report: drone findings, photos, work order and a
              Lease FireSmart section.

Anything that comes from mock mode or the hand-placed demo AOIs is stamped EXAMPLE.
Figures that are computed from real open data (BCWS fire history, the bundled Sentinel-2
clip) are labelled with their source and limits; nothing is presented as field-verified.
"""
from __future__ import annotations

import base64
import io
import json
import math
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (Image as RLImage, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

import firerisk
import sitesense

ROOT = Path(__file__).resolve().parent
SAT_DIR = ROOT / "samples" / "satellite"
DRONE_DIR = ROOT / "samples" / "drone"
ORANGE = colors.HexColor("#ff6a00")
DARK = colors.HexColor("#1b1d21")
RATING_COLORS = {"watch": "#2e7d32", "moderate": "#f9a825", "high": "#ff6a00",
                 "very-high": "#d84315", "extreme": "#b71c1c"}
SEV_COLORS = {"Critical": "#d50000", "High": "#ff6a00", "Medium": "#f9a825", "Low": "#2e7d32"}
TYPES = ("community", "operator")
EXAMPLE_TEXT = ("EXAMPLE DATA - generated in demo/mock mode. Areas of interest, findings and "
                "work orders are illustrative and NOT field-verified results.")
OGL = "Open Government Licence - British Columbia"
COPERNICUS = "Contains modified Copernicus Sentinel data [2018, 2021]."


# --------------------------------------------------------------------------- helpers
def _scene():
    return json.loads((SAT_DIR / "scene.json").read_text())


def _in_clip(lat, lon, scene=None) -> bool:
    w, s, e, n = (scene or _scene())["bbox_lonlat"]
    return w <= lon <= e and s <= lat <= n


def _font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _stamp(img: Image.Image, text: str):
    d = ImageDraw.Draw(img)
    f = _font(max(12, img.width // 40))
    d.rectangle([0, 0, img.width, f.size + 10], fill=(183, 28, 28))
    d.text((8, 4), text, fill="white", font=f)


# --------------------------------------------------------------------------- maps
def community_map(aois: list, example: bool) -> Image.Image:
    """Sentinel-2 true colour (after) with the NDVI-drop layer blended in and AOI markers."""
    base = Image.open(SAT_DIR / "truecolor_after.jpg").convert("RGB")
    ndvi = Image.open(SAT_DIR / "ndvi_change.png").convert("RGB").resize(base.size)
    img = Image.blend(base, ndvi, 0.45)
    sx = img.width / _scene()["size_px"][0]
    d = ImageDraw.Draw(img)
    f = _font(max(12, img.width // 45))
    for t in aois:
        if not t.get("pixel_xy"):
            continue
        x, y = t["pixel_xy"][0] * sx, t["pixel_xy"][1] * sx
        r = img.width // 28
        col = SEV_COLORS.get(t.get("priority"), "#ffffff")
        d.ellipse([x - r, y - r, x + r, y + r], outline=col, width=4)
        d.text((x + r + 3, y - r), t.get("label", t["id"]), fill="white", font=f,
               stroke_width=2, stroke_fill="black")
    # scale bar (10 m pixels)
    px_per_km = 1000 / _scene()["pixel_m"] * sx
    y0 = img.height - 30
    d.rectangle([20, y0, 20 + 2 * px_per_km, y0 + 8], fill="white", outline="black")
    d.text((20, y0 - f.size - 4), "2 km", fill="white", font=f, stroke_width=2, stroke_fill="black")
    d.text((img.width - 30, 20), "N", fill="white", font=_font(28), stroke_width=2, stroke_fill="black")
    if example:
        _stamp(img, "EXAMPLE - treatment areas are illustrative, not assessed")
    return img


def fire_history_map(lat: float, lon: float, size: int = 800, example: bool = False) -> Image.Image:
    """Schematic map of BCWS historical fire origins (2015-2025) within 50 km, rings 10/25/50 km."""
    fires, _, _ = firerisk.load()
    img = Image.new("RGB", (size, size), (24, 27, 31))
    d = ImageDraw.Draw(img)
    c = size / 2
    scale = (size / 2 - 20) / 50.0  # px per km
    kx = 111.32 * math.cos(math.radians(lat))
    f = _font(14)
    for km in firerisk.RINGS_KM:
        r = km * scale
        d.ellipse([c - r, c - r, c + r, c + r], outline=(110, 110, 110), width=1)
        d.text((c + 4, c - r + 2), f"{km} km", fill=(170, 170, 170), font=f)
    for fr in fires:
        dx, dy = (fr["lon"] - lon) * kx, (fr["lat"] - lat) * 111.0
        if dx * dx + dy * dy > 50 * 50:
            continue
        r = max(2, min(18, math.log10(max(fr["ha"], 1)) * 3.5))
        col = {"lightning": (255, 193, 7), "human": (255, 106, 0)}.get(fr["cause"], (180, 180, 180))
        x, y = c + dx * scale, c - dy * scale
        d.ellipse([x - r, y - r, x + r, y + r], fill=col + (0,), outline=(0, 0, 0))
    d.polygon([(c, c - 9), (c - 8, c + 7), (c + 8, c + 7)], fill="white", outline="black")
    d.text((10, size - 60), "Fire origins >=1 ha, 2015-2025 (size ~ log area)", fill="white", font=f)
    d.text((10, size - 40), "orange = human  yellow = lightning  grey = unknown", fill="white", font=f)
    d.text((10, size - 20), f"Source: BC Wildfire Service, {OGL}", fill=(170, 170, 170), font=f)
    if example:
        _stamp(img, "EXAMPLE site location")
    return img


def _png_bytes(img: Image.Image) -> bytes:
    b = io.BytesIO()
    img.save(b, "PNG", optimize=True)
    return b.getvalue()


# --------------------------------------------------------------------------- data assembly
def community_data(name: str = "", lat: float | None = None, lon: float | None = None) -> dict:
    scene = _scene()
    clon, clat = scene["center_lonlat"]
    lat = clat if lat is None else lat
    lon = clon if lon is None else lon
    example = sitesense.is_mock()
    risk = firerisk.risk_at(lat, lon)
    use_clip = _in_clip(lat, lon, scene) or math.hypot((lat - clat) * 111, (lon - clon) * 62) < 15
    treatments = []
    if use_clip:
        sat = sitesense.analyze_satellite([], scene_meta=scene) if example else {"aois": []}
        if not example:  # real model on the bundled clip
            urls = [sitesense.image_to_data_url(str(SAT_DIR / f)) for f in
                    ("truecolor_before.jpg", "truecolor_after.jpg", "ndvi_change.png")]
            sat = sitesense.analyze_satellite(urls, scene_meta=scene)
        prio = {"High": 3, "Medium": 2, "Low": 1}
        rows = []
        for a in sat.get("aois", []):
            if a.get("type") == "seasonal_false_positive":
                continue
            r = (a.get("fire_risk") or {})
            rows.append((prio.get(a.get("priority"), 1) + firerisk.RATING_RANK.get(r.get("rating"), 0) / 10, a))
        rows.sort(key=lambda x: x[0], reverse=True)
        for i, (_, a) in enumerate(rows, 1):
            treatments.append({
                "id": a["id"], "label": f"T{i}", "rank": i, "priority": a.get("priority", "Low"),
                "lat": a.get("lat"), "lon": a.get("lon"), "pixel_xy": a.get("pixel_xy"),
                "basis": a.get("description", "").replace("DEMO EXAMPLE: ", ""),
                "fire_rating": (a.get("fire_risk") or {}).get("rating", "n/a"),
                "suggested": _suggest(a),
            })
    return {
        "type": "community", "example": example,
        "name": name or ("EXAMPLE Community - Peace Region study area" if example else "Unnamed area"),
        "lat": lat, "lon": lon, "created": time.strftime("%Y-%m-%d"),
        "aoi_bbox": scene["bbox_lonlat"] if use_clip else None,
        "ndvi": ({"before": "2018-08-02 (S2A_10VFH_20180802)", "after": "2021-09-02 (S2A_10VFH_20210902)",
                  "drop_fraction": scene.get("ndvi_drop_fraction"), "pixel_m": scene["pixel_m"]}
                 if use_clip else None),
        "risk": risk, "treatments": treatments,
    }


def _suggest(a: dict) -> str:
    t = a.get("type")
    if t == "vegetation_stress":
        return "Field-check fuel loading at the pad edge; candidate for fuel thinning / surface fuel removal."
    if t == "new_disturbance":
        return "Confirm cause of disturbance; check for slash or debris piles that add fuel."
    if t == "lease_change":
        return "Check clearance between the cleared pad and adjacent forest edge; candidate for a fuel break."
    return "Field-check before any treatment is planned."


def operator_data(name: str = "", lat: float | None = None, lon: float | None = None,
                  survey: dict | None = None, ground: dict | None = None) -> dict:
    example = sitesense.is_mock() or survey is None
    if lat is None or lon is None:
        a = json.loads((SAT_DIR / "demo_aoi.json").read_text())["aois"][1]
        lat, lon = a["lat"], a["lon"]
    aoi = {"id": "SITE", "lat": lat, "lon": lon}
    if survey is None:
        survey = sitesense.drone_survey(sitesense.load_image_dir(DRONE_DIR), aoi=aoi)
    if ground is None:
        url = sitesense.image_to_data_url(str(ROOT / "samples" / "wellhead.jpg"))
        ground = sitesense.run_pipeline(url, domain="oil & gas wellsite and pipeline inspection",
                                        hint="wellhead.jpg", origin={"aoi": aoi})
    risk = firerisk.risk_at(lat, lon)
    wo = ground.get("work_order", {})
    if not wo.get("firesmart"):
        wo["firesmart"] = firerisk.firesmart_section(risk)
    return {"type": "operator", "example": example,
            "name": name or ("EXAMPLE Operator - Lease inspection" if example else "Site inspection"),
            "lat": lat, "lon": lon, "created": time.strftime("%Y-%m-%d"),
            "survey": survey, "ground": ground, "work_order": wo, "risk": risk}


# --------------------------------------------------------------------------- PDF
_ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=_ss["Heading1"], textColor=DARK, fontSize=18, spaceAfter=6)
H2 = ParagraphStyle("h2", parent=_ss["Heading2"], textColor=ORANGE, fontSize=13, spaceBefore=10)
BODY = ParagraphStyle("b", parent=_ss["BodyText"], fontSize=9.5, leading=13)
SMALL = ParagraphStyle("s", parent=BODY, fontSize=8, leading=10, textColor=colors.HexColor("#555555"))
BANNER = ParagraphStyle("ban", parent=BODY, textColor=colors.white, backColor=colors.HexColor("#b71c1c"),
                        borderPadding=6, fontSize=10, leading=13, spaceAfter=10)


def _e(v) -> str:
    return (str(v if v is not None else "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _p(t, st=BODY):
    return Paragraph(t, st)


def _table(rows, widths, header=True):
    cells = [[c if not isinstance(c, str) else _p(c) for c in r] for r in rows]
    if header:
        cells[0] = [_p(f"<font color='white'><b>{c}</b></font>") if isinstance(c, str) else c for c in rows[0]]
    t = Table(cells, colWidths=widths, repeatRows=1)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), DARK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    t.setStyle(TableStyle(style))
    return t


def _img(pil: Image.Image, width: float):
    b = io.BytesIO()
    pil = pil.convert("RGB")
    max_px = int(width / inch * 200)  # ~200 dpi
    if pil.width > max_px:
        pil = pil.resize((max_px, round(pil.height * max_px / pil.width)))
    pil.save(b, "JPEG", quality=82)
    b.seek(0)
    return RLImage(b, width=width, height=width * pil.height / pil.width)


def _img_url(url: str, width: float):
    if url.startswith("data:"):
        return _img(Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))), width)
    return None


def _decor(title, example):
    def draw(canvas, doc):
        canvas.saveState()
        w, h = letter
        canvas.setFillColor(DARK)
        canvas.rect(0, h - 36, w, 36, fill=1, stroke=0)
        canvas.setFillColor(ORANGE)
        canvas.rect(0, h - 40, w, 4, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(0.6 * inch, h - 24, "SiteSense")
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(w - 0.6 * inch, h - 24, title)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.setFont("Helvetica", 7.5)
        foot = "SiteSense - Dawson Creek, BC  |  AI-assisted draft; verify in the field."
        if example:
            foot = "EXAMPLE DATA - NOT FOR SUBMISSION  |  " + foot
        canvas.drawString(0.6 * inch, 0.45 * inch, foot)
        canvas.drawRightString(w - 0.6 * inch, 0.45 * inch, f"Page {doc.page}")
        canvas.restoreState()
    return draw


def _risk_block(r: dict):
    col = RATING_COLORS.get(r["rating"], "#555555")
    rows = [["Measure", "Value"],
            ["Historical exposure rating", f"<font color='{col}'><b>{_e(r['rating']).upper()}</b></font> (score {r['score']} / 100)"]]
    for k, v in r["rings"].items():
        rows.append([f"Fires within {k}", f"{v['fires']} fires, {v['ha']:,.0f} ha"])
    cm = r["cause_mix"]
    rows.append(["Cause mix within 25 km", f"human {cm['percent']['human']}%, lightning {cm['percent']['lightning']}%, unknown {cm['percent']['unknown']}% ({cm['fires']} fires)"])
    nb = r.get("nearest_big_fire")
    if nb:
        rows.append(["Nearest fire >= 1,000 ha", f"{_e(nb['name'])} ({nb['year']}), {nb['ha']:,.0f} ha, {nb['km']} km"])
    return [_table(rows, [2.2 * inch, 4.6 * inch]),
            _p(f"Computed by SiteSense from BC Wildfire Service historical fire incident locations "
               f"({r['years'][0]}-{r['years'][1]}). {_e(r['note'])}", SMALL)]


def _build(path_or_buf, title, story, example):
    doc = SimpleDocTemplate(path_or_buf, pagesize=letter, topMargin=0.85 * inch, bottomMargin=0.75 * inch,
                            leftMargin=0.6 * inch, rightMargin=0.6 * inch, title=title, author="SiteSense")
    deco = _decor(title, example)
    doc.build(story, onFirstPage=deco, onLaterPages=deco)


def community_pdf(data: dict, out) -> Image.Image:
    ex = data["example"]
    m = (community_map(data["treatments"], ex) if data["ndvi"]
         else fire_history_map(data["lat"], data["lon"], example=ex))
    s = []
    if ex:
        s.append(_p("<b>" + EXAMPLE_TEXT + "</b>", BANNER))
    s += [_p("Community Wildfire Mapping Report", H1),
          _p(f"<b>{_e(data['name'])}</b> &nbsp;|&nbsp; Prepared {data['created']} &nbsp;|&nbsp; "
             f"Centre {data['lat']:.4f} N, {abs(data['lon']):.4f} W"),
          _p("Supporting wildfire mapping for a UBCM Community Resiliency Investment (CRI) FireSmart "
             "application or a Community Wildfire Resiliency Plan. Check the current program guide for "
             "required content; this report does not replace a qualified professional's assessment.", SMALL),
          _p("1. Area of interest", H2)]
    if data["aoi_bbox"]:
        w, so, e, n = data["aoi_bbox"]
        s.append(_p(f"Bounding box: {so:.4f} to {n:.4f} N, {abs(w):.4f} to {abs(e):.4f} W "
                    f"(about 8 x 8 km, UTM 10N)."))
    else:
        s.append(_p("Point AOI. Bundled satellite imagery does not cover this location; the map shows "
                    "historical fire origins within 50 km. Run tools/fetch_sentinel.py for this AOI to add NDVI change."))
    s += [_img(m, 6.6 * inch if data["ndvi"] else 5.0 * inch),
          _p("Map: Sentinel-2 true colour (2021) blended with the NDVI change layer (orange = NDVI drop > 0.15, "
             "green = gain > 0.15); circles mark treatment areas T1..Tn. " + COPERNICUS if data["ndvi"] else
             "Map: BCWS fire origins within 10/25/50 km.", SMALL), PageBreak(),
          _p("2. Vegetation change (NDVI)", H2)]
    nd = data["ndvi"]
    if nd:
        s += [_table([["Item", "Value"], ["Before scene", nd["before"]], ["After scene", nd["after"]],
                      ["Pixel size", f"{nd['pixel_m']} m"],
                      ["Share of AOI with NDVI drop > 0.15", f"{nd['drop_fraction'] * 100:.1f}% (computed from the scenes)"]],
                     [2.6 * inch, 4.2 * inch]),
              _p("Most of the drop in this scene pair is farm harvest and the seasonal difference "
                 "(early August vs early September), not wildfire or fuel change. NDVI change flags where to look; "
                 "it does not measure fuel load.", SMALL)]
    else:
        s.append(_p("Not available for this AOI in this report."))
    s.append(_p("3. Wildfire risk rating (historical exposure)", H2))
    s += _risk_block(data["risk"])
    s.append(_p("4. Prioritized treatment areas", H2))
    if data["treatments"]:
        if ex:
            s.append(_p("<b>EXAMPLE:</b> these areas were hand-placed on visible features of the imagery to "
                        "illustrate the format. They are not an assessment of fuel hazard.", SMALL))
        rows = [["#", "Priority", "Location", "Basis", "Suggested next step"]]
        for t in data["treatments"]:
            rows.append([t["label"], t["priority"], f"{t['lat']:.4f}, {t['lon']:.4f}<br/>exposure: {t['fire_rating']}",
                         _e(t["basis"]), _e(t["suggested"])])
        s.append(_table(rows, [0.35 * inch, 0.7 * inch, 1.3 * inch, 2.2 * inch, 2.25 * inch]))
        s.append(_p("Ranking: imagery priority first, then historical wildfire exposure at each point. "
                    "Field verification by a qualified professional is required before any treatment.", SMALL))
    else:
        s.append(_p("No treatment areas identified from the available imagery."))
    s += [_p("5. Methods", H2),
          _p("1) Sentinel-2 L2A scenes retrieved from the Element84 Earth Search STAC (AWS Open Data); "
             "NDVI = (B08 - B04) / (B08 + B04) computed for each date and differenced. "
             "2) Candidate areas flagged on the change map " + ("(hand-placed in this EXAMPLE). " if ex else "with AI-assisted review. ")
             + "3) Historical exposure: BCWS fire origins (>= 1 ha) counted within 10, 25 and 50 km and scored "
             "0-100 (weights calibrated against Emberline town scores; rating bands watch to extreme). "
             "4) Areas ranked by imagery priority, then exposure."),
          _p("6. Data sources and licences", H2),
          _table([["Data", "Source", "Licence / attribution"],
                  ["Historical fire incident locations 2015-2025", "BC Wildfire Service (BC Data Catalogue)", OGL],
                  ["Sentinel-2 L2A imagery", "Copernicus / ESA via Element84 Earth Search STAC", COPERNICUS],
                  ["Risk scoring method", "SiteSense / Emberline", "Historical exposure, not a forecast"]],
                 [2.2 * inch, 2.4 * inch, 2.2 * inch]),
          _p("Contains information licensed under the Open Government Licence - British Columbia.", SMALL),
          _p("7. Limitations", H2),
          _p("Fire data are origin points, not perimeters. 10 m imagery cannot resolve individual trees or "
             "surface fuels. Ratings reflect 2015-2025 history and are not a fire danger forecast; check current "
             "BC Wildfire Service danger ratings, bans and evacuation orders.", SMALL)]
    _build(out, "Community Wildfire Mapping Report", s, ex)
    return m


def operator_pdf(data: dict, out) -> Image.Image:
    ex = data["example"]
    sv, wo, gr = data["survey"], data["work_order"], data["ground"]
    m = fire_history_map(data["lat"], data["lon"], example=ex)
    s = []
    if ex:
        s.append(_p("<b>" + EXAMPLE_TEXT + "</b>", BANNER))
    s += [_p("Site Inspection Report", H1),
          _p(f"<b>{_e(data['name'])}</b> &nbsp;|&nbsp; Prepared {data['created']} &nbsp;|&nbsp; "
             f"Site {data['lat']:.4f} N, {abs(data['lon']):.4f} W &nbsp;|&nbsp; LSD: ____________"),
          _p("1. Summary", H2),
          _table([["Item", "Value"], ["Drone images reviewed", str(sv.get("image_count"))],
                  ["Overall severity", f"<font color='{SEV_COLORS.get(sv.get('overall_severity'), '#000')}'><b>{_e(sv.get('overall_severity'))}</b></font>"],
                  ["Ground close-ups requested", str(len(sv.get("ground_followups", [])))],
                  ["Work order priority", _e(wo.get("priority"))],
                  ["Historical wildfire exposure", f"{_e(data['risk']['rating'])} (score {data['risk']['score']})"]],
                 [2.4 * inch, 4.4 * inch]),
          _p(_e(sv.get("summary")), SMALL),
          _p("2. Drone findings (ranked worst first)", H2)]
    rows = [["#", "Photo", "Severity", "Finding and actions"]]
    for f in sv.get("findings", []):
        p = DRONE_DIR / f.get("image", "")
        thumb = _img(Image.open(p), 1.3 * inch) if p.is_file() else ""
        acts = "".join(f"<br/>- {_e(a)}" for a in f.get("immediate_actions", []))
        rows.append([str(f.get("rank")), thumb,
                     f"<font color='{SEV_COLORS.get(f.get('severity'), '#000')}'><b>{_e(f.get('severity'))}</b></font>",
                     f"<b>{_e(f.get('image'))}</b>: {_e(f.get('issue_summary'))}{acts}"])
    s.append(_table(rows, [0.3 * inch, 1.4 * inch, 0.75 * inch, 4.35 * inch]))
    s.append(PageBreak())
    s.append(_p("3. Ground inspection", H2))
    dx = gr.get("diagnosis", {})
    gphoto = ROOT / "samples" / "wellhead.jpg"
    cell = [_p(f"<b>{_e(dx.get('asset_type', ''))}</b>: {_e(dx.get('issue_summary', ''))}"),
            _p("Observed: " + "; ".join(_e(o) for o in dx.get("observed_conditions", [])), SMALL)]
    s.append(Table([[_img(Image.open(gphoto), 2.2 * inch) if gphoto.is_file() else "", cell]],
                   colWidths=[2.4 * inch, 4.4 * inch], style=[("VALIGN", (0, 0), (-1, -1), "TOP")]))
    s.append(_p("4. Work order", H2))
    lst = lambda xs: "".join(f"<br/>{i}. {_e(x)}" for i, x in enumerate(xs or [], 1))
    s.append(_table([["Field", "Detail"], ["Title", _e(wo.get("title"))], ["Priority", _e(wo.get("priority"))],
                     ["Description", _e(wo.get("description"))],
                     ["Immediate actions", lst(wo.get("immediate_actions"))[5:]],
                     ["Next steps", lst(wo.get("recommended_next_steps"))[5:]],
                     ["Safety notes", lst(wo.get("safety_notes"))[5:]]], [1.6 * inch, 5.2 * inch]))
    fs = wo.get("firesmart") or {}
    s += [_p("5. Lease FireSmart", H2), _p(_e(fs.get("summary")))]
    s += [_p("- " + _e(i)) for i in fs.get("items", [])]
    s += [KeepTogether([_p("6. Wildfire history around the site", H2), _img(m, 4.2 * inch)])]
    s += _risk_block(data["risk"])
    s += [_p("7. Notes and sources", H2),
          _p("Images cannot detect gas or H2S: confirm with calibrated detection. AI-assisted draft; verify on site. "
             "Not a substitute for permits, regulatory inspection or the operator's procedures. "
             "Fire history: BC Wildfire Service, " + OGL + ". Photos: see samples/CREDITS.md.", SMALL),
          Spacer(1, 30),
          Table([["Inspected by: ______________________", "Supervisor approval: ______________________"]],
                colWidths=[3.4 * inch, 3.4 * inch])]
    _build(out, "Site Inspection Report", s, ex)
    return m


def generate(kind: str, **kw) -> tuple[bytes, bytes, dict]:
    """Return (pdf_bytes, map_png_bytes, data)."""
    if kind not in TYPES:
        raise ValueError(f"type must be one of {TYPES}")
    data = community_data(**kw) if kind == "community" else operator_data(**kw)
    buf = io.BytesIO()
    m = (community_pdf if kind == "community" else operator_pdf)(data, buf)
    return buf.getvalue(), _png_bytes(m), data
