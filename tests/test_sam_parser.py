"""Live SAM 3.1 output parsing (no network)."""
import sitesense
from sitesense import parse_sam_output


def test_plain_json():
    out = parse_sam_output('{"detections":[{"label":"pipe","box_2d":[100,200,300,400],"score":0.9}]}', "pipe")
    assert out["bbox"] == [0.2, 0.1, 0.4, 0.3]
    assert out["note"] == "SAM 3.1 live"


def test_code_fenced_json():
    raw = 'Here you go:\n```json\n{"detections":[{"label":"pipe","box_2d":[0,0,500,500]}]}\n```'
    assert parse_sam_output(raw, "pipe")["bbox"] == [0.0, 0.0, 0.5, 0.5]


def test_bare_list_and_bad_first_box():
    raw = '[{"label":"x","box_2d":[1,2]}, {"label":"y","box_2d":[10,20,30,40]}]'
    out = parse_sam_output(raw, "pipe")
    assert out["bbox"] == [0.02, 0.01, 0.04, 0.03]


def test_garbage_never_raises():
    for raw in ["", "no boxes here", "{bad json", '{"detections": "nope"}', '{"detections":[1,2]}', None]:
        out = parse_sam_output(raw, "pipe")
        assert out["bbox"] is None and out["mock"] is False


def test_api_failure_never_raises(monkeypatch):
    monkeypatch.delenv("SITESENSE_MOCK", raising=False)
    monkeypatch.setattr(sitesense, "is_mock", lambda: False)

    class Boom:
        class responses:
            @staticmethod
            def create(**kw):
                raise RuntimeError("401 unauthorized")
    monkeypatch.setattr(sitesense, "client", Boom)
    out = sitesense.segment_image("data:image/jpeg;base64,AAAA", "pipe")
    assert out["bbox"] is None and "failed" in out["note"]
