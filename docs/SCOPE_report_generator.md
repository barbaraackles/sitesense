# SCOPE: Report Generator

## Already existed (reused, unchanged)
- Mock mode (`SITESENSE_MOCK=1`, `mock_data.py`) for satellite AOIs, drone findings, ground diagnosis, work orders.
- Sentinel-2 NDVI change clip (`samples/satellite/`, `tools/fetch_sentinel.py`, Element84 Earth Search STAC), with `ndvi_drop_fraction` in `scene.json`; 4 hand-placed DEMO AOIs (`demo_aoi.json`).
- Wildfire layer `firerisk.py`: `/api/risk` historical exposure (BCWS fire origins 2015-2025, OGL-BC), AOI badges, burn-scar relabel, `firesmart_section()`.
- Drone batch ranking (`sitesense.drone_survey`), ground pipeline + work order (`run_pipeline`) with Lease FireSmart.
- Printable HTML only (`/api/work_order.html`, `/api/drone/report.html`); no PDF library, no community-facing deliverable.

## New
- `report.py`: data assembly + reportlab PDFs + PIL map PNGs.
  - **community**: AOI, map (true colour + NDVI-drop blend, treatment markers, scale bar), NDVI table, historical exposure rating, prioritized treatment areas (imagery priority then exposure; seasonal false positives excluded), methods, data sources/licences (BCWS OGL-BC, Copernicus), limitations. Outside the bundled clip: fire-history map, no NDVI/treatments.
  - **operator**: summary, ranked drone findings with photo thumbnails, ground inspection photo, work order, Lease FireSmart, fire-history map + exposure, sign-off lines.
- `POST /api/report` (`type`, `format` pdf|png|json, `name`, `lat`, `lng`, optional `survey`/`ground`).
- UI tab "4 · Report".
- EXAMPLE labelling: red banner, footer "EXAMPLE DATA - NOT FOR SUBMISSION", stamped maps, `_EXAMPLE` filenames, `X-SiteSense-Example` header.
- `tests/test_report.py`, samples in `docs/samples/`.

## Out of scope / caveats
- No on-demand Sentinel-2 fetch per AOI (needs `tools/fetch_sentinel.py`); no fire perimeters; not a QP/RPF assessment; UBCM 2027 program-guide requirements not encoded - check the current guide.
