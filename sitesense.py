#!/usr/bin/env python3
"""SiteSense: multimodal agentic field assistant.

Built for the Meta Global AI Developer Hackathon (Oct 26 - Nov 4, 2026).

Flow:
  1. SAM 3.1 segments the object in the photo.
  2. Muse Spark 1.3 returns a structured JSON diagnosis.
  3. An agent loop finalizes a work order via tool calling.
"""

import base64
import json
import mimetypes
import os
import sys
import time
from pathlib import Path

try:
    from openai import OpenAI, OpenAIError
except ImportError:  # pragma: no cover
    print("Missing dependency: run `pip install -r requirements.txt`", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
MODEL_API_BASE_URL = os.environ.get(
    "MODEL_API_BASE_URL", "https://api.example-meta-model-api.com/v1"  # placeholder
)
MODEL_API_KEY = os.environ.get("MODEL_API_KEY")

# NOTE: Confirm the exact model IDs on https://dev.meta.ai before running.
SEG_MODEL = "sam-3.1"
LLM_MODEL = "muse-spark-1.3"

IMAGE_PATH = "sample.jpg"  # update to your image
OUTPUT_DIR = BASE_DIR
MAX_AGENT_TURNS = 6

PROMPT_FILE = BASE_DIR / "prompts" / "diagnosis_system.txt"
SCHEMA_FILE = BASE_DIR / "schemas" / "diagnosis.json"

# ---------------------------------------------------------------------------
# Embedded prompt + schema (kept identical to prompts/ and schemas/ files)
# ---------------------------------------------------------------------------
DIAGNOSIS_SYSTEM_PROMPT = """You are SiteSense, an expert multimodal field-diagnosis assistant for technicians, farmers, inspectors and maintenance crews.

You receive a photo of a real-world subject plus a segmentation summary (label, bounding box, mask info) produced by an object-segmentation model. Subjects include:
- Equipment and machinery (pumps, motors, HVAC units, electrical panels, valves, pipes, generators, tools)
- Crops and plants (leaf disease, pests, nutrient deficiency, water stress, physical damage)
- Structural defects (cracks, corrosion, spalling, water damage, rot, deformation, failed fasteners or joints)
- Vehicles and other assets

Your job:
1. Identify the object and classify it into one category: equipment, crop, structure, vehicle, or other.
2. Describe only what is actually visible. List concrete observations (color, texture, wear, leaks, discoloration, deformation, residue, missing parts).
3. Give probable causes ranked by likelihood (0 to 1). Likelihoods are your honest estimates, not certainties.
4. Assign a severity: low, medium, high, or critical.
5. Recommend ordered, practical actions with a priority of immediate, soon, or routine.
6. Ask follow-up questions when information that would change the diagnosis is missing.

Safety first:
- If there is any risk of electrical shock, fire, gas leak, chemical exposure, structural collapse, falling objects, moving machinery, or pressurized systems, set safety_hazard to true and explain in safety_notes.
- When a hazard is present, the first recommended action must make the area safe (isolate power, lock out/tag out, evacuate, cordon off, stop the equipment).
- Never recommend an unsafe shortcut. Recommend a qualified professional when the work requires licensing or specialist skill.

Honesty about uncertainty:
- Do not overstate what the image shows. If the image is blurry, partial, poorly lit, or ambiguous, lower your confidence and say so.
- Set confidence (0 to 1) to reflect how sure you are about the overall diagnosis.
- Set needs_expert to true when confidence is low, severity is high or critical, or the fix requires specialist expertise.

Never invent facts:
- Never invent part numbers, model numbers, serial numbers, brand names, or specifications. Describe parts generically (for example "mechanical shaft seal" or "20 A breaker") unless a number is clearly legible in the image.
- Do not invent measurements you cannot see.

Output format:
- Return ONLY a single JSON object that matches the provided schema exactly.
- No markdown, no code fences, no commentary before or after the JSON.
- Include every required field. Use empty arrays or empty strings when there is nothing to report.
"""

DIAGNOSIS_SCHEMA = json.loads(
    """{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SiteSenseDiagnosis",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "object_label",
    "category",
    "issue_summary",
    "observations",
    "probable_causes",
    "severity",
    "confidence",
    "safety_hazard",
    "safety_notes",
    "recommended_actions",
    "needs_expert",
    "follow_up_questions"
  ],
  "properties": {
    "object_label": { "type": "string" },
    "category": {
      "type": "string",
      "enum": ["equipment", "crop", "structure", "vehicle", "other"]
    },
    "issue_summary": { "type": "string" },
    "observations": {
      "type": "array",
      "items": { "type": "string" }
    },
    "probable_causes": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["cause", "likelihood"],
        "properties": {
          "cause": { "type": "string" },
          "likelihood": { "type": "number", "minimum": 0, "maximum": 1 }
        }
      }
    },
    "severity": {
      "type": "string",
      "enum": ["low", "medium", "high", "critical"]
    },
    "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
    "safety_hazard": { "type": "boolean" },
    "safety_notes": { "type": "string" },
    "recommended_actions": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["step", "priority"],
        "properties": {
          "step": { "type": "string" },
          "priority": {
            "type": "string",
            "enum": ["immediate", "soon", "routine"]
          }
        }
      }
    },
    "needs_expert": { "type": "boolean" },
    "follow_up_questions": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
"""
)


def load_prompt_and_schema():
    """Prefer the on-disk prompt/schema files; fall back to embedded constants."""
    prompt, schema = DIAGNOSIS_SYSTEM_PROMPT, DIAGNOSIS_SCHEMA
    try:
        if PROMPT_FILE.is_file():
            prompt = PROMPT_FILE.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[warn] could not read {PROMPT_FILE}: {exc}; using embedded prompt")
    try:
        if SCHEMA_FILE.is_file():
            schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[warn] could not load {SCHEMA_FILE}: {exc}; using embedded schema")
    return prompt, schema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_client():
    if not MODEL_API_KEY:
        raise RuntimeError("MODEL_API_KEY is not set. Get one at https://dev.meta.ai")
    return OpenAI(api_key=MODEL_API_KEY, base_url=MODEL_API_BASE_URL)


def load_image_b64(path):
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Image not found: {p}")
    mime = mimetypes.guess_type(p.name)[0] or "image/jpeg"
    data = base64.b64encode(p.read_bytes()).decode("ascii")
    return data, mime


def data_url(b64, mime):
    return f"data:{mime};base64,{b64}"


# ---------------------------------------------------------------------------
# Step 1: segmentation
# ---------------------------------------------------------------------------
def segment_object(client, image_b64, mime):
    """Segment the main object with SAM 3.1.

    TODO: The exact Meta Model API endpoint/request shape for SAM 3.1 is
    UNVERIFIED. This assumes an OpenAI-compatible chat call that returns JSON.
    Replace with the documented segmentation endpoint from dev.meta.ai.

    Returns: {"label": str, "bbox": [x, y, w, h] | None, "mask": str | None}
    """
    try:
        resp = client.chat.completions.create(
            model=SEG_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Segment the primary object. Return JSON with keys "
                            "label, bbox [x,y,w,h], mask (RLE or null).",
                        },
                        {"type": "image_url", "image_url": {"url": data_url(image_b64, mime)}},
                    ],
                }
            ],
        )
        raw = json.loads(resp.choices[0].message.content or "{}")
    except (OpenAIError, json.JSONDecodeError, IndexError) as exc:
        print(f"[warn] segmentation failed ({exc}); continuing without it")
        raw = {}
    return {
        "label": raw.get("label", "unknown"),
        "bbox": raw.get("bbox"),
        "mask": raw.get("mask"),
    }


# ---------------------------------------------------------------------------
# Step 2: structured diagnosis
# ---------------------------------------------------------------------------
def diagnose(client, image_b64, mime, segmentation, system_prompt, schema):
    seg_summary = json.dumps(
        {"label": segmentation["label"], "bbox": segmentation["bbox"],
         "has_mask": segmentation["mask"] is not None}
    )
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Segmentation summary: {seg_summary}\nDiagnose this."},
                    {"type": "image_url", "image_url": {"url": data_url(image_b64, mime)}},
                ],
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "diagnosis", "strict": True, "schema": schema},
        },
    )
    content = resp.choices[0].message.content or ""
    try:
        diagnosis = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Diagnosis was not valid JSON: {exc}\n{content[:500]}") from exc
    missing = [k for k in schema.get("required", []) if k not in diagnosis]
    if missing:
        raise ValueError(f"Diagnosis missing required fields: {missing}")
    return diagnosis


# ---------------------------------------------------------------------------
# Step 3: work-order agent loop
# ---------------------------------------------------------------------------
WORK_ORDER_TOOL = {
    "type": "function",
    "function": {
        "name": "create_work_order",
        "description": "Create a maintenance/field work order from a diagnosis.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "title": {"type": "string"},
                "asset": {"type": "string"},
                "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "priority": {"type": "string", "enum": ["immediate", "soon", "routine"]},
                "actions": {"type": "array", "items": {"type": "string"}},
                "parts_needed": {"type": "array", "items": {"type": "string"}},
                "estimated_hours": {"type": "number"},
                "notes": {"type": "string"},
            },
            "required": ["title", "asset", "severity", "priority", "actions",
                         "parts_needed", "estimated_hours", "notes"],
        },
    },
}


def create_work_order(**kwargs):
    """Execute the tool locally: write work_order_<timestamp>.json."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    order = {"id": f"WO-{ts}", "created_at": ts, **kwargs}
    path = OUTPUT_DIR / f"work_order_{ts}.json"
    path.write_text(json.dumps(order, indent=2), encoding="utf-8")
    return {"status": "created", "id": order["id"], "path": str(path)}


TOOLS_IMPL = {"create_work_order": create_work_order}


def run_work_order_agent(client, diagnosis):
    messages = [
        {"role": "system", "content": "You are a field operations agent. Use the "
         "create_work_order tool exactly once to turn the diagnosis into a work order, "
         "then reply with a one-paragraph summary. Never invent part numbers."},
        {"role": "user", "content": "Diagnosis:\n" + json.dumps(diagnosis, indent=2)},
    ]
    results = []
    for _ in range(MAX_AGENT_TURNS):
        resp = client.chat.completions.create(
            model=LLM_MODEL, messages=messages, tools=[WORK_ORDER_TOOL]
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return {"summary": msg.content or "", "tool_results": results}
        messages.append(msg.model_dump(exclude_none=True))
        for call in msg.tool_calls:
            fn = TOOLS_IMPL.get(call.function.name)
            try:
                args = json.loads(call.function.arguments or "{}")
                result = fn(**args) if fn else {"error": f"unknown tool {call.function.name}"}
            except (json.JSONDecodeError, TypeError, OSError) as exc:
                result = {"error": str(exc)}
            results.append(result)
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)}
            )
    return {"summary": "Agent stopped: max turns reached.", "tool_results": results}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    try:
        client = get_client()
        system_prompt, schema = load_prompt_and_schema()
        image_b64, mime = load_image_b64(IMAGE_PATH)

        print("== Step 1: segmentation ==")
        seg = segment_object(client, image_b64, mime)
        print(json.dumps({k: v for k, v in seg.items() if k != "mask"}, indent=2))

        print("\n== Step 2: diagnosis ==")
        diagnosis = diagnose(client, image_b64, mime, seg, system_prompt, schema)
        print(json.dumps(diagnosis, indent=2))

        print("\n== Step 3: work order ==")
        outcome = run_work_order_agent(client, diagnosis)
        for r in outcome["tool_results"]:
            print(json.dumps(r, indent=2))
        print("\n" + outcome["summary"])
        return 0
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
    except OpenAIError as exc:
        print(f"Model API error: {exc}", file=sys.stderr)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
