"""Canned, realistic responses for MOCK mode (no MODEL_API_KEY needed).

Scenario choice: keywords in the user's note/filename take priority. Otherwise
the choice is stable, based on a hash of the image bytes, so a demo is repeatable.
"""

import copy
import hashlib

OIL_GAS_EXTRA_KEYS = ("asset_type", "hazard_flags", "gauge_reading",
                      "requires_gas_detection", "regulatory_note")

REG_NOTE = ("Follow your company's procedures and applicable BC Energy Regulator "
            "requirements for inspection, repair and any release reporting.")

SCENARIOS = {
    "corrosion": {
        "issue_summary": "External corrosion with pitting on an above-ground pipe section near a support.",
        "severity": "High",
        "confidence": 0.78,
        "observed_conditions": [
            "Heavy orange/brown rust scale over most of the visible pipe surface",
            "Apparent pitting and flaking where the coating has failed",
            "Corrosion concentrated at the support/contact point",
            "No active liquid release visible in the image",
        ],
        "likely_causes": [
            "Coating breakdown allowing atmospheric corrosion",
            "Moisture trapped at the pipe support (crevice corrosion)",
            "Freeze-thaw cycling and condensation",
        ],
        "immediate_actions": [
            "Notify the supervisor/control room and record the location",
            "Keep ignition sources away and do not strike or scrape the pipe while it is in service",
            "Schedule wall-thickness (UT) measurement by a qualified inspector",
        ],
        "recommended_next_steps": [
            "Assess remaining wall thickness and fitness for service before deciding to repair or replace",
            "Clean, prime and recoat the section and add a wear pad at the support",
            "Add the line to the corrosion monitoring program",
        ],
        "safety_notes": [
            "Treat the line as pressurized until it is confirmed isolated",
            "Gas presence cannot be determined from an image; use calibrated gas detection",
        ],
        "work_order_draft": "Inspect and assess external corrosion/pitting on the pipe at the support; UT thickness survey; recoat or repair per the engineering assessment.",
        "additional_issues": ["Coating degradation likely on adjacent sections"],
        "asset_type": "pipeline",
        "hazard_flags": ["corrosion", "pressure"],
        "gauge_reading": "no gauge",
        "requires_gas_detection": True,
        "regulatory_note": REG_NOTE,
    },
    "wellhead": {
        "issue_summary": "Producing gas wellhead with plunger lift; minor staining at a lower connection needs follow-up.",
        "severity": "Medium",
        "confidence": 0.64,
        "observed_conditions": [
            "Wellhead/christmas tree with plunger-lift catcher on top",
            "Dark discolouration below a lower flanged connection (possible weep)",
            "Paint wear and light surface rust on the valve bodies",
            "Gauge present but the dial is not legible at this resolution",
        ],
        "likely_causes": [
            "Minor packing or gasket weep at a flanged/threaded connection",
            "Normal weathering of the coating",
        ],
        "immediate_actions": [
            "Approach from upwind wearing a calibrated personal H2S/LEL monitor",
            "Check the stained connection with a gas detector and leak-detection solution",
            "Report the finding to the lease operator/supervisor",
        ],
        "recommended_next_steps": [
            "If a leak is confirmed, schedule repair under isolation and a permit",
            "Get a close-up photo of the gauge to record a legible reading",
            "Touch up the coating at the next maintenance window",
        ],
        "safety_notes": [
            "Wellheads are under pressure: no work without isolation and a permit",
            "Sour gas may be present in this region; an image cannot detect H2S. Follow the site's H2S procedures",
        ],
        "work_order_draft": "Investigate possible weep at the lower wellhead connection; leak check; repair if confirmed; record the gauge reading.",
        "additional_issues": ["Gauge not legible in the photo"],
        "asset_type": "wellhead",
        "hazard_flags": ["leak_or_stain", "pressure", "h2s_sour_cue"],
        "gauge_reading": "not legible",
        "requires_gas_detection": True,
        "regulatory_note": REG_NOTE,
    },
    "gauge": {
        "issue_summary": "Glycerine-filled pressure gauge in readable condition; verify it is suitable and calibrated for the service.",
        "severity": "Low",
        "confidence": 0.7,
        "observed_conditions": [
            "Bourdon-tube gauge with an intact lens and liquid fill",
            "Needle at or near zero on the visible dial",
            "No visible leak at the gauge connection",
        ],
        "likely_causes": [
            "Gauge isolated or reading a depressurized line, OR a stuck needle",
        ],
        "immediate_actions": [
            "Compare the reading against a known reference or redundant gauge",
            "Confirm the gauge isolation valve position",
        ],
        "recommended_next_steps": [
            "Add the gauge to the calibration schedule if it is not already there",
            "Replace it if the needle is stuck or the fill is cloudy or leaking",
        ],
        "safety_notes": [
            "A zero reading does not prove the line is depressurized; verify isolation per procedure",
        ],
        "work_order_draft": "Verify the pressure gauge reading and calibration; replace if faulty.",
        "additional_issues": [],
        "asset_type": "pressure_gauge",
        "hazard_flags": ["pressure"],
        "gauge_reading": "approximately 0 on the visible scale (units not legible)",
        "requires_gas_detection": False,
        "regulatory_note": REG_NOTE,
    },
    "leak": {
        "issue_summary": "Hydrocarbon-stained soil indicating a release; containment and reporting assessment required.",
        "severity": "Critical",
        "confidence": 0.72,
        "observed_conditions": [
            "Dark, saturated-looking soil consistent with hydrocarbon staining",
            "Workers in protective equipment handling contaminated material",
            "Proximity to surface water/vegetation",
        ],
        "likely_causes": [
            "Loss of containment from a nearby line, tank or fitting",
        ],
        "immediate_actions": [
            "Stop work if the source is still active and keep people upwind",
            "Notify the supervisor and emergency contact and start the spill response procedure",
            "Control ignition sources and confirm the atmosphere with calibrated gas detection",
            "Contain the spread (booms, berms, absorbent) per the spill plan",
        ],
        "recommended_next_steps": [
            "Identify and isolate the source",
            "Delineate the impacted area and plan remediation",
            "Complete internal and regulatory reporting as required",
        ],
        "safety_notes": [
            "Wear the required PPE; avoid skin contact with hydrocarbons",
            "Gas or vapour presence cannot be determined from an image",
        ],
        "work_order_draft": "Spill response: isolate the source, contain, clean up impacted soil, and complete reporting.",
        "additional_issues": ["Possible impact to nearby water"],
        "asset_type": "site_general",
        "hazard_flags": ["leak_or_stain", "containment_breach", "ignition_source"],
        "gauge_reading": "no gauge",
        "requires_gas_detection": True,
        "regulatory_note": REG_NOTE,
    },
}

KEYWORDS = [
    ("leak", ("leak", "stain", "spill", "soil", "sheen")),
    ("gauge", ("gauge", "manometer", "psi", "kpa")),
    ("wellhead", ("wellhead", "well head", "christmas", "plunger", "tree")),
    ("corrosion", ("corro", "rust", "pit", "pipe")),
]


def _pick(image_data_url: str, hint: str) -> str:
    h = (hint or "").lower()
    for key, words in KEYWORDS:
        if any(w in h for w in words):
            return key
    digest = hashlib.sha256((image_data_url or "").encode()).digest()
    return list(SCENARIOS)[digest[0] % len(SCENARIOS)]


def mock_segment(prompt: str = "object") -> dict:
    return {"mock": True, "label": prompt, "bbox": [0.18, 0.22, 0.64, 0.56],
            "mask": None, "note": "Mock segmentation; real SAM 3.1 output shape unverified."}


def mock_diagnose(image_data_url: str, user_note: str = "", domain: str = "", hint: str = "") -> dict:
    key = _pick(image_data_url, f"{hint} {user_note}")
    d = copy.deepcopy(SCENARIOS[key])
    if not any(k in (domain or "").lower() for k in ("oil", "gas", "wellsite", "pipeline")):
        for k in OIL_GAS_EXTRA_KEYS:
            d.pop(k, None)
    return d


def mock_work_order(diagnosis: dict) -> dict:
    return {
        "title": diagnosis.get("work_order_draft", "Field inspection follow-up")[:80],
        "priority": diagnosis.get("severity", "Medium"),
        "description": diagnosis.get("issue_summary", ""),
        "immediate_actions": list(diagnosis.get("immediate_actions", [])),
        "recommended_next_steps": list(diagnosis.get("recommended_next_steps", [])),
        "safety_notes": list(diagnosis.get("safety_notes", [])),
    }
