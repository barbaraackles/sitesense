import os
import sys
import json
import base64
import mimetypes
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODEL_API_BASE_URL = os.environ.get("MODEL_API_BASE_URL", "https://api.meta.ai/v1")
# NOTE: confirm exact model IDs and endpoint shapes on https://dev.meta.ai
SEG_MODEL = os.environ.get("SITESENSE_SEG_MODEL", "sam-3.1")
LLM_MODEL = os.environ.get("SITESENSE_LLM_MODEL", "muse-spark-1.3")


def is_mock() -> bool:
    """MOCK mode: no MODEL_API_KEY, or SITESENSE_MOCK=1."""
    return os.environ.get("SITESENSE_MOCK") == "1" or not os.environ.get("MODEL_API_KEY")


_client = None


def get_client():
    """Create the OpenAI-compatible client lazily so importing never needs a key."""
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(base_url=MODEL_API_BASE_URL, api_key=os.environ["MODEL_API_KEY"])
    return _client


class _LazyClient:
    """Keeps the original `client.xxx` call sites working while deferring creation."""

    def __getattr__(self, name):
        return getattr(get_client(), name)


client = _LazyClient()

def image_to_data_url(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    return f"data:{mime};base64,{b64}"

def segment_image(image_data_url: str, prompt: str = "pipe"):
    # TODO: SAM 3.1 request/response shape on the Meta Model API is UNVERIFIED.
    if is_mock():
        print("SAM segmentation complete (mock)")
        return mock_segment(prompt)
    response = client.responses.create(
        model=SEG_MODEL,
        input=[{
            "type": "message",
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": image_data_url},
            ],
        }],
    )
    print("SAM segmentation complete")
    return response

DIAGNOSIS_SYSTEM = """You are SiteSense, an expert field diagnostic assistant for technicians, inspectors, and operators.

You receive:
- An image (or cropped region from SAM 3.1 segmentation)
- Optional short user notes or voice transcription
- A domain context (e.g. industrial maintenance, agriculture, facilities, energy)

Your job is to produce a clear, actionable diagnosis that a field worker can act on immediately.

Rules:
- Be specific and practical. Prefer concrete observations over generic advice.
- Base severity and recommendations on visible evidence in the image + any user notes.
- If the image is unclear or the issue is ambiguous, lower confidence and note what is uncertain.
- Always include at least one immediate action and one longer-term recommendation when relevant.
- Flag safety concerns clearly when present.
- Keep language concise and field-friendly (avoid academic jargon).
- Never invent measurements, part numbers, or historical data you cannot see.
- If multiple issues are visible, focus on the most urgent one and briefly note others.
"""

DIAGNOSIS_SCHEMA = {
    "name": "sitesense_diagnosis",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "issue_summary": {"type": "string"},
            "severity": {"type": "string", "enum": ["Low", "Medium", "High", "Critical"]},
            "confidence": {"type": "number"},
            "observed_conditions": {"type": "array", "items": {"type": "string"}},
            "likely_causes": {"type": "array", "items": {"type": "string"}},
            "immediate_actions": {"type": "array", "items": {"type": "string"}},
            "recommended_next_steps": {"type": "array", "items": {"type": "string"}},
            "safety_notes": {"type": "array", "items": {"type": "string"}},
            "work_order_draft": {"type": "string"},
            "additional_issues": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "issue_summary", "severity", "confidence", "observed_conditions",
            "likely_causes", "immediate_actions", "recommended_next_steps",
            "safety_notes", "work_order_draft", "additional_issues"
        ],
        "additionalProperties": False,
    },
}

def _load_text(rel: str, fallback: str) -> str:
    p = BASE_DIR / rel
    return p.read_text(encoding="utf-8") if p.is_file() else fallback


def _load_json(rel: str, fallback: dict) -> dict:
    p = BASE_DIR / rel
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else fallback
    except (OSError, json.JSONDecodeError):
        return fallback


def is_oil_gas(domain: str) -> bool:
    d = (domain or "").lower()
    return any(k in d for k in ("oil", "gas", "wellsite", "pipeline"))


def prompt_and_schema(domain: str):
    """Pick the system prompt + schema for a domain (oil & gas gets its own)."""
    if is_oil_gas(domain):
        return (_load_text("prompts/oil_gas_system.txt", DIAGNOSIS_SYSTEM),
                _load_json("schemas/oil_gas_diagnosis.json", DIAGNOSIS_SCHEMA))
    return DIAGNOSIS_SYSTEM, DIAGNOSIS_SCHEMA


def diagnose(image_data_url: str, user_note: str = "", domain: str = "industrial maintenance") -> dict:
    if is_mock():
        return mock_diagnose(image_data_url, user_note, domain)
    system_prompt, schema = prompt_and_schema(domain)
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Domain: {domain}. User note: {user_note}"},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": schema,
        },
    )
    return json.loads(response.choices[0].message.content)

WORK_ORDER_SYSTEM = """You are a field operations assistant. You receive a structured SiteSense diagnosis and must produce a clean, ready-to-submit work order. Use the create_work_order tool."""

tools = [{
    "type": "function",
    "function": {
        "name": "create_work_order",
        "description": "Formats and finalizes a work order from a SiteSense diagnosis",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "priority": {"type": "string", "enum": ["Low", "Medium", "High", "Critical"]},
                "description": {"type": "string"},
                "immediate_actions": {"type": "array", "items": {"type": "string"}},
                "recommended_next_steps": {"type": "array", "items": {"type": "string"}},
                "safety_notes": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "priority", "description"],
        },
    },
}]

def create_work_order(diagnosis: dict) -> dict:
    if is_mock():
        return mock_work_order(diagnosis)
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": WORK_ORDER_SYSTEM},
            {"role": "user", "content": f"Here is the SiteSense diagnosis JSON:\n{json.dumps(diagnosis, indent=2)}\n\nPlease create a finalized work order."},
        ],
        tools=tools,
        tool_choice={"type": "function", "function": {"name": "create_work_order"}},
    )
    tool_call = response.choices[0].message.tool_calls[0]
    return json.loads(tool_call.function.arguments)

def run_pipeline(image_data_url: str, user_note: str = "", domain: str = "oil & gas",
                 seg_prompt: str = "equipment", hint: str = "", origin: dict | None = None) -> dict:
    """Full flow used by the web app: segment -> diagnose -> work order."""
    seg = segment_image(image_data_url, prompt=seg_prompt)
    if is_mock():  # hint (e.g. upload filename) helps pick a matching canned scenario
        diagnosis = mock_diagnose(image_data_url, user_note, domain, hint=hint)
    else:
        diagnosis = diagnose(image_data_url, user_note=user_note, domain=domain)
    work_order = create_work_order(diagnosis)
    seg_out = seg if isinstance(seg, dict) else {"raw": str(seg)[:500]}
    if origin:  # link the work order back to the satellite AOI / drone image that triggered it
        work_order["origin"] = origin
    return {"mock": is_mock(), "domain": domain, "segmentation": seg_out,
            "diagnosis": diagnosis, "work_order": work_order}


# ---------------------------------------------------------------------------
# Three-level inspection: SATELLITE -> DRONE -> GROUND
# ---------------------------------------------------------------------------
MODES = {
    "satellite": ("prompts/satellite_system.txt", "schemas/satellite_aoi.json"),
    "drone": ("prompts/drone_system.txt", "schemas/drone_finding.json"),
    "ground": ("prompts/oil_gas_system.txt", "schemas/oil_gas_diagnosis.json"),
}


def mode_prompt_and_schema(mode: str):
    p, s = MODES[mode]
    return _load_text(p, DIAGNOSIS_SYSTEM), _load_json(s, DIAGNOSIS_SCHEMA)


def _structured_call(mode: str, image_data_urls, text: str) -> dict:
    """One Muse Spark call with the mode's prompt + JSON schema (real mode only)."""
    system_prompt, schema = mode_prompt_and_schema(mode)
    content = [{"type": "text", "text": text}]
    content += [{"type": "image_url", "image_url": {"url": u}} for u in image_data_urls]
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": content}],
        response_format={"type": "json_schema", "json_schema": schema},
    )
    return json.loads(response.choices[0].message.content)


def analyze_satellite(image_data_urls, notes: str = "", scene_meta: dict | None = None) -> dict:
    """SATELLITE level: flag areas of interest (AOIs). Mock returns labelled DEMO AOIs."""
    if is_mock():
        return mock_satellite(notes)
    text = f"Scene metadata: {json.dumps(scene_meta or {})}\nNotes: {notes}"
    out = _structured_call("satellite", list(image_data_urls), text)
    out["demo"] = False
    return out


def analyze_drone_image(image_data_url: str, filename: str = "", notes: str = "",
                        aoi: dict | None = None) -> dict:
    if is_mock():
        return mock_drone_finding(image_data_url, filename, notes)
    text = f"Image: {filename}\nTriggering AOI: {json.dumps(aoi or {})}\nNotes: {notes}"
    return _structured_call("drone", [image_data_url], text)


def drone_survey(images, notes: str = "", aoi: dict | None = None) -> dict:
    """DRONE level: analyse a batch [(filename, data_url), ...], rank worst-first, combine."""
    findings = []
    for name, url in images:
        try:
            f = analyze_drone_image(url, name, notes, aoi)
        except Exception as exc:  # one bad image shouldn't kill the survey
            f = {"issue_summary": f"Analysis failed: {type(exc).__name__}: {exc}", "severity": "Low",
                 "confidence": 0.0, "error": True}
        f["image"] = name
        findings.append(f)
    findings.sort(key=lambda f: (SEVERITY_RANK.get(f.get("severity"), 0), f.get("confidence", 0)), reverse=True)
    for i, f in enumerate(findings, 1):
        f["rank"] = i
    counts = {s: sum(f.get("severity") == s for f in findings) for s in SEVERITY_RANK}
    worst = findings[0]["severity"] if findings else "Low"
    return {
        "mock": is_mock(), "aoi": aoi, "image_count": len(findings), "overall_severity": worst,
        "severity_counts": counts, "findings": findings,
        "ground_followups": [{"image": f["image"], "request": f.get("ground_photo_request", "")}
                             for f in findings if f.get("needs_ground_closeup")],
        "summary": (f"{len(findings)} aerial images reviewed; worst finding {worst}. "
                    f"{sum(bool(f.get('needs_ground_closeup')) for f in findings)} need a ground close-up. "
                    "Images cannot detect gas: confirm on site with calibrated detection."),
    }


def load_image_dir(folder) -> list:
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    return [(p.name, image_to_data_url(str(p))) for p in sorted(Path(folder).iterdir())
            if p.suffix.lower() in exts]


from mock_data import (mock_segment, mock_diagnose, mock_work_order,  # noqa: E402
                       mock_satellite, mock_drone_finding, SEVERITY_RANK)

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--drone":
        print(json.dumps(drone_survey(load_image_dir(sys.argv[2])), indent=2))
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "--satellite":
        print(json.dumps(analyze_satellite([]), indent=2))
        sys.exit(0)
    IMAGE_PATH = "sample_pipe.jpg"  # ← change this
    if len(sys.argv) > 1:
        IMAGE_PATH = sys.argv[1]
    elif not os.path.exists(IMAGE_PATH):
        IMAGE_PATH = str(BASE_DIR / "samples" / "corroded_pipe.jpg")
    if is_mock():
        print("[MOCK MODE] No MODEL_API_KEY (or SITESENSE_MOCK=1): using canned responses.")
    image_url = image_to_data_url(IMAGE_PATH)

    try:
        print("1. SAM 3.1 segmentation...")
        segment_image(image_url, prompt="pipe")

        print("2. Muse Spark diagnosis...")
        diagnosis = diagnose(image_url, user_note="noticed this on the main supply line yesterday")
        print(json.dumps(diagnosis, indent=2))

        print("3. Finalizing work order...")
        work_order = create_work_order(diagnosis)
        print(json.dumps(work_order, indent=2))
    except Exception as exc:  # keep CLI failures readable
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
