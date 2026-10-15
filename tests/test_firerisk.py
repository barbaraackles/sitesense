"""Emberline wildfire layer: data, risk logic, API, satellite/drone/work-order integration."""
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import firerisk

ROOT = Path(__file__).resolve().parent.parent
DONNIE = (57.6187, -122.0123)       # Donnie Creek 2023 origin (619,072 ha)
DAWSON = (55.7596, -120.235)
FSJ = (56.2524, -120.8464)
OPEN_OCEAN = (50.0, -140.0)


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("SITESENSE_MOCK", "1")


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_geojson_is_licensed_and_small():
    p = ROOT / "data" / "bc_fires.geojson"
    assert p.stat().st_size < 2_000_000
    fc = json.loads(p.read_text())
    assert "Open Government Licence" in fc["metadata"]["licence"]
    kinds = {f["properties"]["kind"] for f in fc["features"]}
    assert kinds == {"fire", "hotspot"}
    credits = (ROOT / "samples" / "CREDITS.md").read_text()
    assert "Open Government Licence" in credits and "bc_fires.geojson" in credits


def test_haversine():
    assert firerisk.haversine_km(55, -120, 55, -120) == 0
    assert 110 < firerisk.haversine_km(55, -120, 56, -120) < 112


def test_rating_bands():
    assert firerisk.rating_for(0) == "watch"
    assert firerisk.rating_for(38) == "moderate"
    assert firerisk.rating_for(56) == "high"
    assert firerisk.rating_for(75) == "very-high"
    assert firerisk.rating_for(99) == "extreme"


def test_risk_matches_emberline_towns():
    # Ring counts equal Emberline's per-town values; ratings agree for these Peace towns.
    r = firerisk.risk_at(*DAWSON)
    assert r["rings"]["10km"]["fires"] == 2 and r["rings"]["25km"]["fires"] == 20
    assert r["rating"] == "watch"
    assert firerisk.risk_at(*FSJ)["rating"] == "high"


def test_risk_fields_and_mix():
    r = firerisk.risk_at(*FSJ)
    assert set(r["rings"]) == {"10km", "25km", "50km"}
    assert r["rings"]["10km"]["fires"] <= r["rings"]["25km"]["fires"] <= r["rings"]["50km"]["fires"]
    pct = r["cause_mix"]["percent"]
    assert set(pct) == {"human", "lightning", "unknown"} and 98 <= sum(pct.values()) <= 102
    assert r["nearest_big_fire"]["ha"] >= firerisk.BIG_FIRE_HA


def test_risk_outside_data_is_watch():
    r = firerisk.risk_at(*OPEN_OCEAN)
    assert r["rings"]["50km"]["fires"] == 0 and r["rating"] == "watch" and r["nearest_big_fire"] is None


def test_api_risk(client):
    j = client.get("/api/risk", params={"lat": DONNIE[0], "lng": DONNIE[1]}).json()
    assert j["largest_within_50km"]["name"] == "DONNIE CREEK"
    assert client.get("/api/risk", params={"lat": 95, "lng": 0}).status_code == 422
    assert client.get("/api/risk", params={"lat": "x", "lng": 0}).status_code == 422


def test_burn_scar_relabels_vegetation_drop():
    aoi = {"id": "T", "lat": DONNIE[0] + 0.1, "lon": DONNIE[1], "type": "possible_staining",
           "priority": "High", "description": "dark patch"}
    a = firerisk.annotate_aoi(aoi, after_year=2024)
    assert a["interpretation"] == "possible burn scar / fire recovery"
    assert a["burn_scar"]["name"] == "DONNIE CREEK" and "fire_risk" in a
    # A fire after the 'after' image cannot explain the drop.
    assert "burn_scar" not in firerisk.annotate_aoi(aoi, after_year=2020) or \
        firerisk.annotate_aoi(aoi, after_year=2020)["burn_scar"]["year"] <= 2020
    # Lease changes are not relabelled.
    assert "interpretation" not in firerisk.annotate_aoi(dict(aoi, type="lease_change"), 2024)


def test_satellite_demo_has_fire_badges(client):
    j = client.get("/api/satellite/demo").json()
    for a in j["aois"]:
        assert a["fire_risk"]["rating"] in firerisk.RATING_RANK
    # The bundled clip has no recorded fire under it, so nothing is relabelled.
    assert not any(a.get("interpretation") for a in j["aois"])


def _finding(sev, flags=(), text=""):
    return {"severity": sev, "confidence": 0.5, "hazard_flags": list(flags), "issue_summary": text}


def test_drone_fire_bonus_rules():
    hi = {"rating": "high"}
    leak = _finding("High", ["leak_or_stain"])
    assert firerisk.drone_fire_bonus(leak, hi, date(2026, 7, 1)) == 0.5
    assert firerisk.drone_fire_bonus(leak, {"rating": "moderate"}, date(2026, 7, 1)) == 0.25
    assert firerisk.drone_fire_bonus(leak, hi, date(2026, 12, 1)) == 0      # out of season
    assert firerisk.drone_fire_bonus(_finding("High"), hi, date(2026, 7, 1)) == 0  # not fire-relevant
    assert firerisk.drone_fire_bonus(leak, None, date(2026, 7, 1)) == 0


def test_drone_ranking_uses_fire_season(monkeypatch):
    import sitesense
    fake = {"a.jpg": _finding("High", [], "Gauge housing cracked"),
            "b.jpg": _finding("High", ["ignition_source"], "Cured grass against the flare stack"),
            "c.jpg": _finding("Critical", [], "Major release")}
    monkeypatch.setattr(sitesense, "analyze_drone_image", lambda url, name, notes, aoi: dict(fake[name]))
    aoi = {"id": "X", "lat": FSJ[0], "lon": FSJ[1]}
    batch = [(n, "data:") for n in fake]
    summer = sitesense.drone_survey(batch, aoi=aoi, today=date(2026, 7, 15))
    assert [f["image"] for f in summer["findings"]] == ["c.jpg", "b.jpg", "a.jpg"]
    assert summer["fire_context"]["applied"] is True
    winter = sitesense.drone_survey(batch, aoi=aoi, today=date(2026, 1, 15))
    assert winter["fire_context"]["applied"] is False
    assert all(f["fire_bonus"] == 0 for f in winter["findings"])


def test_work_order_has_firesmart(client):
    img = (ROOT / "samples" / "wellhead.jpg").read_bytes()
    origin = json.dumps({"aoi": {"id": "AOI-1", "lat": 55.966, "lon": -120.482}})
    j = client.post("/api/diagnose", files={"image": ("wellhead.jpg", img, "image/jpeg")},
                    data={"domain": "oil_gas", "origin": origin}).json()
    fs = j["work_order"]["firesmart"]
    text = " ".join(fs["items"]).lower()
    for word in ("wellhead", "flare", "firebreak", "overwintering", "muster", "h2s"):
        assert word in text
    assert fs["rating"] in firerisk.RATING_RANK
    html = client.post("/api/work_order.html", json=j).text
    assert "Lease FireSmart" in html
    # Non oil & gas domains do not get the lease section.
    j2 = client.post("/api/diagnose", files={"image": ("wellhead.jpg", img, "image/jpeg")},
                     data={"domain": "facilities"}).json()
    assert "firesmart" not in j2["work_order"]


def test_firesmart_has_no_invented_numbers():
    import re
    for item in firerisk.firesmart_section()["items"]:
        assert not re.search(r"\d", item.replace("H2S", "")), item
