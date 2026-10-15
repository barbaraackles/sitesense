import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("SITESENSE_MOCK", "1")


def _url(name="corroded_pipe.jpg"):
    return "data:image/jpeg;base64," + base64.b64encode((ROOT / "samples" / name).read_bytes()).decode()


def test_import_without_key_and_mock_detected():
    import sitesense
    assert sitesense.is_mock()


def test_original_functions_in_mock():
    import sitesense
    url = _url()
    assert sitesense.segment_image(url, prompt="pipe")["mock"] is True
    d = sitesense.diagnose(url, user_note="rust on pipe")
    for k in sitesense.DIAGNOSIS_SCHEMA["schema"]["required"]:
        assert k in d
    assert "asset_type" not in d  # general domain stays on the original schema
    wo = sitesense.create_work_order(d)
    assert wo["title"] and wo["priority"] == d["severity"]


def test_oil_gas_pipeline_matches_schema():
    import sitesense
    schema = json.loads((ROOT / "schemas" / "oil_gas_diagnosis.json").read_text())["schema"]
    r = sitesense.run_pipeline(_url("wellhead.jpg"), domain="oil & gas", hint="wellhead.jpg")
    d = r["diagnosis"]
    assert set(schema["required"]) == set(d)
    assert d["severity"] in schema["properties"]["severity"]["enum"]
    assert d["asset_type"] == "wellhead"
    assert d["requires_gas_detection"] is True
    assert "BC Energy Regulator" in d["regulatory_note"]


@pytest.mark.parametrize("name,expected", [("leak_stain_soil.jpg", "Critical"),
                                           ("pressure_gauge.jpg", "Low")])
def test_api_diagnose(name, expected):
    from app.main import app
    c = TestClient(app)
    assert c.get("/api/health").json()["mock"] is True
    with open(ROOT / "samples" / name, "rb") as f:
        r = c.post("/api/diagnose", files={"image": (name, f, "image/jpeg")},
                   data={"domain": "oil_gas", "notes": ""})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["diagnosis"]["severity"] == expected
    h = c.post("/api/work_order.html", json=j)
    assert h.status_code == 200 and "SiteSense Work Order" in h.text


def test_api_rejects_non_image():
    from app.main import app
    r = TestClient(app).post("/api/diagnose", files={"image": ("x.txt", b"hi", "text/plain")})
    assert r.status_code == 415


def test_index_served():
    from app.main import app
    r = TestClient(app).get("/")
    assert r.status_code == 200 and "SiteSense" in r.text
