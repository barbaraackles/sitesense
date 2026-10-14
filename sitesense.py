import os
import json
import base64
from openai import OpenAI

client = OpenAI(
    base_url="https://api.meta.ai/v1",
    api_key=os.environ["MODEL_API_KEY"],
)

def image_to_data_url(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/jpeg;base64,{b64}"

def segment_image(image_data_url: str, prompt: str = "pipe"):
    response = client.responses.create(
        model="sam-3.1",
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

def diagnose(image_data_url: str, user_note: str = "", domain: str = "industrial maintenance") -> dict:
    response = client.chat.completions.create(
        model="muse-spark-1.3",
        messages=[
            {"role": "system", "content": DIAGNOSIS_SYSTEM},
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
            "json_schema": DIAGNOSIS_SCHEMA,
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
    response = client.chat.completions.create(
        model="muse-spark-1.3",
        messages=[
            {"role": "system", "content": WORK_ORDER_SYSTEM},
            {"role": "user", "content": f"Here is the SiteSense diagnosis JSON:\n{json.dumps(diagnosis, indent=2)}\n\nPlease create a finalized work order."},
        ],
        tools=tools,
        tool_choice={"type": "function", "function": {"name": "create_work_order"}},
    )
    tool_call = response.choices[0].message.tool_calls[0]
    return json.loads(tool_call.function.arguments)

if __name__ == "__main__":
    IMAGE_PATH = "sample_pipe.jpg"  # ← change this
    image_url = image_to_data_url(IMAGE_PATH)

    print("1. SAM 3.1 segmentation...")
    segment_image(image_url, prompt="pipe")

    print("2. Muse Spark diagnosis...")
    diagnosis = diagnose(image_url, user_note="noticed this on the main supply line yesterday")
    print(json.dumps(diagnosis, indent=2))

    print("3. Finalizing work order...")
    work_order = create_work_order(diagnosis)
    print(json.dumps(work_order, indent=2))
