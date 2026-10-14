# SiteSense

Multimodal agentic field assistant for the **Meta Global AI Developer Hackathon** (Oct 26–Nov 4, 2026).

Uses the Meta Model API:
- **SAM 3.1** — object segmentation
- **Muse Spark 1.3** — structured diagnosis + tool-calling agent loop

## What it does
Point a camera at equipment, a crop, or a defect → get a structured diagnosis, severity rating, immediate actions, and a ready-to-use work order.

## Quick start
1. Get a key from [dev.meta.ai](https://dev.meta.ai) and export it:
   ```bash
   export MODEL_API_KEY="your_key_here"
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run:
   ```bash
   python sitesense.py
   ```
   (Update `IMAGE_PATH` inside the script first.)

## Demo flow
1. SAM 3.1 segments the object of interest  
2. Muse Spark returns a structured JSON diagnosis  
3. Second agent call finalizes a work order via tool calling  

## Hackathon fit
- Theme: “Build for Your World” + “Push the Frontier”
- Uses Muse Spark 1.3 + SAM 3.1
- $150 Meta Model API credits for accepted participants
