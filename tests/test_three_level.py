import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("SITESENSE_MOCK", "1")


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.mark.parametrize("mode", ["satellite", "drone", "ground"])
def test_mode_prompts_keep_gas_rule(mode):
    import sitesense
    prompt, schema = sitesense.mode_prompt_and_schema(mode)
    assert "detect gas" in prompt.lower() or "gas detection" in prompt.lower()
    assert schema["strict"] is True and schema["schema"]["additionalProperties"] is False


def test_satellite_prompt_states_resolution_limits():
    text = (ROOT / "prompts" / "satellite_system.txt").read_text().lower()
    assert "10 m" in text and "cannot detect gas" in text


def test_satellite_mock_is_labelled_demo():
    import sitesense
    s = sitesense.analyze_satellite([])
    assert s["demo"] is True and "NOT detected leaks" in s["summary"]
    assert len(s["aois"]) >= 3
    for a in s["aois"]:
        assert a["description"].startswith("DEMO EXAMPLE")
        assert 55.8 < a["lat"] < 56.1 and -120.6 < a["lon"] < -120.3
    schema = json.loads((ROOT / "schemas" / "satellite_aoi.json").read_text())["schema"]
    req = set(schema["properties"]["aois"]["items"]["required"])
    assert all(req <= set(a) for a in s["aois"])


def test_drone_survey_ranks_worst_first():
    import sitesense
    r = sitesense.drone_survey(sitesense.load_image_dir(ROOT / "samples" / "drone"))
    sev = [sitesense.SEVERITY_RANK[f["severity"]] for f in r["findings"]]
    assert sev == sorted(sev, reverse=True)
    assert r["overall_severity"] == r["findings"][0]["severity"]
    assert [f["rank"] for f in r["findings"]] == list(range(1, len(sev) + 1))
    schema = json.loads((ROOT / "schemas" / "drone_finding.json").read_text())["schema"]
    for f in r["findings"]:
        assert set(schema["required"]) <= set(f)


def test_api_satellite_demo(client):
    j = client.get("/api/satellite/demo").json()
    assert j["demo"] and j["aois"] and j["images"]["ndvi_change"].endswith(".png")
    assert client.get(j["images"]["truecolor_after"]).status_code == 200


def test_api_drone_batch_upload_and_report(client):
    names = ["pipeline_row.jpg", "well_pad_gas_leak_aliso.jpg", "sagd_well_pad.jpg"]
    files = [("images", (n, (ROOT / "samples" / "drone" / n).read_bytes(), "image/jpeg")) for n in names]
    aoi = {"id": "AOI-2", "lat": 55.9, "lon": -120.4}
    r = client.post("/api/drone", files=files, data={"aoi": json.dumps(aoi)})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["image_count"] == 3 and j["findings"][0]["image"] == "well_pad_gas_leak_aliso.jpg"
    assert j["aoi"]["id"] == "AOI-2"
    h = client.post("/api/drone/report.html", json=j)
    assert h.status_code == 200 and "Drone Survey Report" in h.text and "AOI-2" in h.text


def test_api_drone_samples_and_validation(client):
    assert client.post("/api/drone", data={}).status_code == 400
    j = client.post("/api/drone", data={"use_samples": "1"}).json()
    assert j["image_count"] == len(client.get("/api/drone/samples").json()["images"]) >= 3


def test_ground_work_order_links_origin(client):
    origin = {"aoi": {"id": "AOI-1", "lat": 55.96, "lon": -120.48}, "drone_image": "well_pad_gas_leak_aliso.jpg",
              "drone_rank": 1, "drone_severity": "Critical"}
    with open(ROOT / "samples" / "leak_stain_soil.jpg", "rb") as f:
        r = client.post("/api/diagnose", files={"image": ("leak_stain_soil.jpg", f, "image/jpeg")},
                        data={"domain": "oil_gas", "origin": json.dumps(origin)})
    j = r.json()
    assert j["work_order"]["origin"]["aoi"]["id"] == "AOI-1"
    h = client.post("/api/work_order.html", json=j).text
    assert "Satellite AOI-1" in h and "well_pad_gas_leak_aliso.jpg" in h
