# SiteSense

<p align="center"><img src="docs/hero.png" alt="SiteSense satellite screening tab near Dawson Creek, BC" width="360"></p>

**SiteSense is a multimodal field assistant for oil and gas wellsite and pipeline inspection in BC's Peace Region, built for the Meta Global AI Developer Hackathon (Oct 26 – Nov 4, 2026).** It works top-down: free Sentinel-2 satellite imagery flags areas of interest, a drone survey ranks the photos worst-first, and a phone close-up goes through **SAM 3.1** segmentation and **Muse Spark 1.3** diagnosis to produce a severity-rated, tool-called work order that links back to its origin. Every work order is safety-first: images never "detect gas", H2S cues are flagged, and a wildfire layer built from a decade of BC Wildfire Service data adds fire risk and Lease FireSmart checks.

**Built by** Barbara Ackles (Dawson Creek, BC), who also built [Emberline](https://github.com/barbaraackles/emberline), the BC wildfire hotspot and FireSmart planner that SiteSense's [wildfire layer](#emberline-wildfire-layer) comes from.

| 1 · Satellite | 2 · Drone | 3 · Ground |
|---|---|---|
| <img src="docs/screenshot_1_satellite.png" alt="Satellite tab" width="200"> | <img src="docs/screenshot_2_drone.png" alt="Drone survey" width="200"> | <img src="docs/screenshot_3_ground.png" alt="Ground diagnosis and work order" width="200"> |
| **4 · AOI wildfire badges** | **5 · Fire-season drone ranking** | **6 · Lease FireSmart** |
| <img src="docs/screenshot_4_wildfire_aoi_badges.png" alt="AOI wildfire badges" width="200"> | <img src="docs/screenshot_5_wildfire_drone_ranking.png" alt="Drone ranking" width="200"> | <img src="docs/screenshot_6_wildfire_firesmart.png" alt="Lease FireSmart" width="200"> |

## Try it in 60 seconds (mock mode)
No API key needed. Mock mode returns realistic canned responses, so the whole Satellite → Drone → Ground flow runs end to end.
```bash
git clone https://github.com/barbaraackles/sitesense && cd sitesense
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
SITESENSE_MOCK=1 uvicorn app.main:app --port 8000
# open http://localhost:8000 → Satellite: "Escalate → Drone" → "Use sample set" → "Escalate → Ground" → pick a sample → Inspect
# wildfire API: curl "http://localhost:8000/api/risk?lat=55.76&lng=-120.24"
```
Run the tests with `pip install -r requirements-dev.txt && pytest`. For real mode, set `MODEL_API_KEY` (see [Quick start](#quick-start)).

## Overview
Multimodal agentic field assistant for the **Meta Global AI Developer Hackathon** (Oct 26–Nov 4, 2026).

**Focus: oil & gas wellsite and pipeline inspection in the Peace Region (Dawson Creek, BC).** A lease operator photographs a wellhead, flange, gauge or stain on a phone. Before they leave the pad, SiteSense returns a severity-rated finding, safety-first actions (including H2S cues) and a ready-to-file work order.

Uses the Meta Model API:
- **SAM 3.1**: object segmentation
- **Muse Spark 1.3**: structured diagnosis + tool-calling agent loop

## Three-level inspection: Satellite → Drone → Ground
1. **Satellite** (free Sentinel-2, 10 m): screen a whole area for *areas of interest*: new clearings or lease changes, vegetation stress along a right-of-way (NDVI before/after), dark patches. It's cheap and wide, but can't see components or gas.
2. **Drone**: fly the flagged AOI and upload the whole batch at once. SiteSense ranks every shot **worst-first** and builds one combined survey report (JSON + printable HTML), saying which spots need a ground close-up and what to photograph.
3. **Ground** (phone): the close-up. The existing flow returns a structured diagnosis plus a tool-called **work order that links back** to its origin (Satellite AOI → Drone image → Ground).

```mermaid
flowchart LR
  S[Satellite<br/>Sentinel-2 true colour + NDVI change] -->|AOIs, prioritised| D[Drone survey<br/>batch upload, ranked worst-first]
  S -.->|seasonal / explained| X[Close AOI]
  D -->|combined report<br/>JSON + HTML| R[(Survey report)]
  D -->|needs close-up| G[Ground photo<br/>SAM 3.1 + Muse Spark]
  G -->|create_work_order tool| W[Work order<br/>origin: AOI → drone image]
```

Every mode has its own prompt (`prompts/satellite_system.txt`, `prompts/drone_system.txt`, `prompts/oil_gas_system.txt`) that is explicit about resolution limits. All three keep the rule that **images cannot detect gas**.

> **Satellite demo data:** the bundled clip is a real Sentinel-2 scene near Dawson Creek / Fort St. John, but the areas of interest in mock mode are **hand-placed demo examples, not detected leaks**. Much of the NDVI drop in that pair is harvest or seasonal change, which is exactly why SiteSense escalates instead of concluding.

### Drone flights: rules and permission
- Fly only within applicable **Transport Canada** drone rules: the right pilot certificate for the operation, a registered drone, visual line of sight, altitude limits, airspace authorization where required, and distance from people and aerodromes. Check current rules on the Transport Canada website before flying.
- Get the **site operator's / landowner's permission** before flying over leases, facilities or right-of-ways, and follow the company's site-entry, H2S and flight procedures.
- SiteSense never recommends flying outside these rules.

## Why oil & gas in the Peace Region
- Thousands of wellsites, pipelines and facilities are spread over remote leases, often checked by one operator per route.
- Findings are often written up hours later from memory. SiteSense turns a photo + a note into a consistent, structured record on the spot.
- Safety-first by design: H2S/sour-gas cues are flagged, and the model **never claims to detect gas from an image**. It always calls for calibrated gas detection.
- Regulatory context stays generic ("follow your company's procedures and applicable BC Energy Regulator requirements"), with no invented regulation numbers.

## What it does
Point a camera at equipment, a crop, or a defect → get a structured diagnosis, severity rating, immediate actions, and a ready-to-use work order.

Oil & gas mode (default in the web demo) also looks at leaks/stains, corrosion and pitting, valves and wellheads, flanges and gaskets, pressure gauges (only legible readings), tank/berm containment, signage, PPE, H2S cues and hot work. It adds `asset_type`, `hazard_flags`, `gauge_reading`, `requires_gas_detection` and `regulatory_note` to the output.

## Quick start
1. Get a key from [dev.meta.ai](https://dev.meta.ai) and export it:
   ```bash
   export MODEL_API_KEY="your_key_here"
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run:
   ```bash
   python sitesense.py
   ```
   (Update `IMAGE_PATH` inside the script first, or pass a path: `python sitesense.py samples/wellhead.jpg`.)

### No key yet? Mock mode
If `MODEL_API_KEY` is unset (or `SITESENSE_MOCK=1`), SiteSense returns realistic canned diagnoses, so the whole demo runs end to end:
```bash
pip install -r requirements.txt
python sitesense.py samples/corroded_pipe.jpg      # CLI
uvicorn app.main:app --reload --port 8000          # web demo → http://localhost:8000
```
Open the page on your phone (same Wi-Fi, `--host 0.0.0.0`) to use the camera directly.

### Real mode
```bash
export MODEL_API_KEY="..."                         # from dev.meta.ai
export MODEL_API_BASE_URL="https://api.meta.ai/v1" # default; confirm on dev.meta.ai
# optional overrides if the model IDs differ:
export SITESENSE_SEG_MODEL="sam-3.1" SITESENSE_LLM_MODEL="muse-spark-1.3"
uvicorn app.main:app --port 8000
```

### Three-level demo (CLI)
```bash
python sitesense.py --satellite              # demo AOIs (mock) / satellite screening (real)
python sitesense.py --drone samples/drone    # batch survey, worst-first
python sitesense.py samples/leak_stain_soil.jpg
```
Swap in your own drone photos by dropping them into `samples/drone/` (see `samples/drone/README.md`), or multi-select them in the Drone tab.

Refresh the satellite clip (free, no auth; Element84 Earth Search STAC → AWS COGs):
```bash
pip install rasterio numpy pillow pyproj
python tools/fetch_sentinel.py
```

### Tests
```bash
pip install -r requirements-dev.txt
pytest -q
```

## Emberline wildfire layer

SiteSense borrows the data and the per-town risk logic of **Emberline** (a BC wildfire hotspot and FireSmart planner) so every lease, AOI and work order knows its wildfire history. This matters in the Peace Region because the biggest BC fires of the decade burned through oil and gas country: Donnie Creek (2023, ~619,000 ha) and Nogah Creek (2024, ~508,000 ha).

- **Data:** `data/bc_fires.geojson` (~1 MB) holds 4,535 BC fire origin points (≥ 1 ha) and 558 ignition hotspot cells, covering 2015–2025. The source is BC Wildfire Service *Historical Fire Incident Locations*, under the Open Government Licence – BC (credit in `samples/CREDITS.md`). To regenerate it, run `python tools/export_emberline.py <emberline>/src/data/catalog.json`.
- **Risk module and API:** `firerisk.py` and `GET /api/risk?lat=55.76&lng=-120.24` return:
  - fires and hectares within 10/25/50 km
  - the human/lightning/unknown cause mix within 25 km
  - the nearest fire of 1,000 ha or more, and the largest fire within 50 km
  - a 0–100 score and a rating band (watch, moderate, high, very-high, extreme)

  The weights were calibrated on Emberline's 63 town scores: 45 of 63 ratings match exactly and all 63 are within one band. It shows **historical exposure, not a forecast**, so always check the current BC Wildfire Service fire danger, bans and evacuation orders.
- **Satellite:** each AOI gets a wildfire-risk badge. If a vegetation-drop AOI (vegetation stress, possible staining, new disturbance) sits inside or near a known fire's footprint, it is relabelled **"possible burn scar / fire recovery"** instead of a possible spill. Only fires up to the "after" image's year count. The footprint is approximated as a circle with the fire's area plus a 3 km margin, because the data has origin points, not perimeters. The bundled demo clip has no recorded fire under it, so its AOIs are not relabelled.
- **Drone ranking (fire season, April–October):** when the survey's AOI has a location, findings that add fuel or an ignition source get a small bonus. These are leaks/stains, containment breaches, hot work, ignition sources, or a flare, vegetation, grass, slash or debris in the description. The bonus is +0.5 when exposure is high or worse, +0.25 when moderate, and 0 otherwise. It is smaller than one severity step, so a Critical finding is never outranked by a High one. The bonus is shown per finding (`fire_bonus`) and in `fire_context`, and it is off outside fire season.
- **Work orders:** oil and gas work orders get a **Lease FireSmart** section, shown in the UI and the printable HTML. It covers:
  - vegetation clearance around the wellhead and flare
  - flare and hot-work checks
  - pipeline right-of-way firebreaks
  - overwintering (holdover) fires
  - the evacuation and H2S muster and second egress

  The checks are generic and defer to the operator's procedures and the rules that apply; they cite no regulation numbers.

| AOI wildfire badges | Fire-season drone ranking | Lease FireSmart in the work order |
|---|---|---|
| ![AOI badges](docs/screenshot_4_wildfire_aoi_badges.png) | ![Drone ranking](docs/screenshot_5_wildfire_drone_ranking.png) | ![FireSmart](docs/screenshot_6_wildfire_firesmart.png) |

## Report Generator (client PDFs)

`POST /api/report` and the **4 · Report** tab produce a branded PDF plus a map PNG (reportlab + Pillow, pure Python). It works fully in mock mode.

- **Community wildfire mapping** (`"type": "community"`): for BC towns and regional districts, as supporting mapping for a UBCM CRI FireSmart application or a Community Wildfire Resiliency Plan. It includes the area of interest, a Sentinel-2 NDVI change map, a historical wildfire exposure rating, prioritized treatment areas, methods, data sources and licences (BC Wildfire Service data under the Open Government Licence – BC; modified Copernicus Sentinel data), and limitations. Points outside the bundled imagery get a fire-history map instead of NDVI.
- **Operator site inspection** (`"type": "operator"`): ranked drone findings with photos, the ground inspection, the work order, a Lease FireSmart section and the wildfire history around the site. The UI sends your current drone survey and ground result; anything missing is filled with example data.

```bash
curl -X POST localhost:8000/api/report -H 'Content-Type: application/json' \
  -d '{"type":"community","name":"District of Example","lat":55.95,"lng":-120.45}' -o report.pdf
# "format": "png" returns the map image, "json" a summary
```

Mock/demo content is stamped **EXAMPLE DATA – NOT FOR SUBMISSION** on every page, and the maps and file names are marked too. The exposure figures are computed from real BCWS history, but they describe past fires, not a forecast. The report does not replace a qualified professional's assessment, so check the current UBCM program guide for what it requires. Samples: [`docs/samples/EXAMPLE_community_report.pdf`](docs/samples/EXAMPLE_community_report.pdf) and [`docs/samples/EXAMPLE_operator_report.pdf`](docs/samples/EXAMPLE_operator_report.pdf). Scope notes: [`docs/SCOPE_report_generator.md`](docs/SCOPE_report_generator.md).

## Demo flow
1. SAM 3.1 segments the object of interest
2. Muse Spark returns a structured JSON diagnosis (oil & gas prompt + schema when that domain is selected)
3. Second agent call finalizes a work order via tool calling
4. The web UI shows a severity badge, findings, safety notes and the work order, and offers it as JSON or printable (PDF-ready) HTML
5. Upstream of this, the satellite screening and drone batch survey choose *where* the ground photo gets taken (see the three-level section)

## Architecture
```
 Phone camera / upload ──► FastAPI (app/main.py) ──► sitesense.run_pipeline()
                                                      │
                     ┌────────────────────────────────┼─────────────────────────────┐
                     ▼                                ▼                             ▼
          segment_image()  SAM 3.1         diagnose()  Muse Spark 1.3      create_work_order()
          (object mask/box)                prompts/oil_gas_system.txt      tool call: create_work_order
                                           schemas/oil_gas_diagnosis.json  
                     └──────────── MOCK mode (mock_data.py) when no key ───────────┘
                                                      │
                               JSON ◄── severity · findings · safety · work order ──► HTML/PDF
```

| Path | Purpose |
|---|---|
| `sitesense.py` | Core pipeline + CLI (original flow kept; lazy client; mock switch) |
| `mock_data.py` | Canned corrosion / wellhead / gauge / spill scenarios |
| `prompts/`, `schemas/` | General and oil & gas prompts and JSON schemas |
| `app/` | FastAPI app + mobile page (Satellite / Drone / Ground tabs); `/api/satellite/demo`, `/api/drone`, `/api/drone/report.html`, `/api/diagnose`, `/api/work_order.html`, `/api/report` |
| `samples/` | Ground demo photos (public domain) |
| `samples/satellite/` | Sentinel-2 clips, NDVI change, demo AOIs (`tools/fetch_sentinel.py`) |
| `samples/drone/` | CC BY / CC BY-SA aerial stand-ins; drop your own drone photos here |
| `report.py` | Report Generator: community wildfire mapping + operator inspection PDFs and map PNGs |
| `tools/` | Data-fetch scripts |
| `tests/` | pytest for the mock pipeline and API |

## Hackathon fit
- Theme: “Build for Your World” + “Push the Frontier”
- Uses Muse Spark 1.3 + SAM 3.1
- $150 Meta Model API credits for accepted participants

### Judging-criteria checklist
- [x] **Real-world impact**: local, specific problem (Peace Region wellsite/pipeline inspection)
- [x] **Use of Meta models**: SAM 3.1 segmentation + Muse Spark structured output + tool calling
- [x] **Agentic behaviour**: multi-step pipeline ending in a tool-generated work order
- [x] **Frontier / multi-scale**: Satellite → Drone → Ground escalation with traceable work orders
- [x] **Working demo**: mobile web app, runs without a key (mock), tests pass
- [x] **Responsible AI**: never claims gas detection, reads only legible gauges, no invented part or regulation numbers, human sign-off on work orders
- [ ] **Live run on Meta Model API**: pending API key (verify endpoint shapes)
- [ ] **Demo video** (2–3 min: phone on a real lease → work order)
- [ ] **Offline/low-signal story** (queue photos, sync later)

## Known assumptions
- The SAM 3.1 call (`client.responses.create`) and its response shape are **unverified**. Confirm them on dev.meta.ai.
- It assumes an OpenAI-compatible Muse Spark endpoint that supports `response_format` `json_schema` and `tools`.
- Model IDs `sam-3.1` / `muse-spark-1.3` are placeholders until confirmed.
- Satellite and drone real-mode calls assume Muse Spark accepts multiple images per message and `json_schema` output. The satellite schema uses a nullable `["number","null"]` type, which some strict-mode implementations may reject.
- Bundled drone images are aerial stand-ins (mostly from crewed aircraft, some outside BC) until Barbara's own drone photos replace them.
