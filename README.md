# SiteSense

Multimodal agentic field assistant built for the Meta Global AI Developer Hackathon (Oct 26–Nov 4, 2026).

Uses Meta Model API:
- SAM 3.1 for object segmentation
- Muse Spark 1.3 for structured diagnosis + tool-calling agent loop

## What it does
Point a phone/camera at equipment, crops, or a defect → get a structured diagnosis, severity, actions, and a ready-to-use work order.

## Quick start
1. Set `MODEL_API_KEY` from https://dev.meta.ai
2. `pip install -r requirements.txt`
3. `python sitesense.py` (update IMAGE_PATH inside)

## Demo flow
1. SAM 3.1 segments the object
2. Muse Spark returns structured JSON diagnosis
3. Second agent call finalizes a work order via tool calling

## Hackathon notes
Fits both "Build for Your World" and "Push the Frontier" themes.
$150 Meta Model API credits included for accepted participants.
