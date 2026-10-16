import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("SITESENSE_MOCK", "1")


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.mark.parametrize("kind", ["community", "operator"])
def test_report_pdf_endpoint(client, kind):
    r = client.post("/api/report", json={"type": kind})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF") and len(r.content) > 20_000
    assert r.headers["x-sitesense-example"] == "1"
    assert "EXAMPLE" in r.headers["content-disposition"]


@pytest.mark.parametrize("kind", ["community", "operator"])
def test_report_map_png(client, kind):
    r = client.post("/api/report", json={"type": kind, "format": "png"})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(r.content)).size[0] >= 600


def test_community_data_labels_example_and_sources():
    import report
    d = report.community_data()
    assert d["example"] is True and d["name"].startswith("EXAMPLE")
    assert d["ndvi"] and 0 <= d["ndvi"]["drop_fraction"] <= 1
    assert d["treatments"], "demo AOIs become example treatment areas"
    assert all(t["id"] != "AOI-4" for t in d["treatments"]), "seasonal false positive excluded"
    assert [t["rank"] for t in d["treatments"]] == list(range(1, len(d["treatments"]) + 1))
    assert d["risk"]["rating"] in ("watch", "moderate", "high", "very-high", "extreme")


def test_community_outside_imagery_falls_back_to_fire_map(client):
    r = client.post("/api/report", json={"type": "community", "format": "json", "lat": 50.67, "lng": -120.33})
    j = r.json()
    assert r.status_code == 200 and j["treatments"] == []
    assert client.post("/api/report", json={"type": "community", "lat": 50.67, "lng": -120.33}).content.startswith(b"%PDF")


def test_operator_uses_supplied_survey_and_ground(client):
    survey = client.post("/api/drone", data={"use_samples": "1"}).json()
    import report
    d = report.operator_data(name="Test lease", lat=55.95, lon=-120.45, survey=survey)
    assert d["survey"]["image_count"] == survey["image_count"]
    assert d["work_order"]["firesmart"]["title"] == "Lease FireSmart"


def test_pdf_strings_include_licences(monkeypatch):
    from reportlab import rl_config
    import report
    monkeypatch.setattr(rl_config, "pageCompression", 0)
    for kind in report.TYPES:
        pdf, _, _ = report.generate(kind)
        assert b"Open Government Licence" in pdf and b"EXAMPLE" in pdf
        if kind == "community":
            assert b"Copernicus" in pdf and b"UBCM" in pdf
        else:
            assert b"Lease FireSmart" in pdf


@pytest.mark.parametrize("payload", [{"type": "bogus"}, {"type": "community", "format": "doc"},
                                     {"type": "community", "lat": 55}, {"type": "community", "lat": 99, "lng": 0}])
def test_report_validation(client, payload):
    assert client.post("/api/report", json=payload).status_code == 422
