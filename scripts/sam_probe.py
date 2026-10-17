"""Print the raw sam-3.1 Responses API output for one image.

Run: MODEL_API_KEY=... python scripts/sam_probe.py [image] [prompt]
Confirms the live output contract so segment_image()'s parser can be locked in.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sitesense  # noqa: E402

image = sys.argv[1] if len(sys.argv) > 1 else "samples/corroded_pipe.jpg"
prompt = sys.argv[2] if len(sys.argv) > 2 else "corroded pipe"

os.environ.pop("SITESENSE_MOCK", None)
if not os.environ.get("MODEL_API_KEY"):
    sys.exit("Set MODEL_API_KEY first.")

url = sitesense.image_to_data_url(image)
resp = sitesense.client.responses.create(
    model=sitesense.SEG_MODEL,
    input=[{"role": "user", "content": [
        {"type": "input_text", "text": f"Locate every instance of: {prompt}. Reply with ONLY JSON."},
        {"type": "input_image", "image_url": url},
    ]}],
)
print("=== output_text ===")
print(sitesense._responses_text(resp))
print("=== parsed by segment_image ===")
import json
print(json.dumps(sitesense.segment_image(url, prompt), indent=2)[:2000])
