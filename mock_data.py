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


def _pick(image_data_url: str, *hints: str) -> str:
    for h in hints:  # earlier hints (e.g. filename) win over later ones (notes)
        h = (h or "").lower()
        for key, words in KEYWORDS:
            if any(w in h for w in words):
                return key
    digest = hashlib.sha256((image_data_url or "").encode()).digest()
    return list(SCENARIOS)[digest[0] % len(SCENARIOS)]


def mock_segment(prompt: str = "object") -> dict:
    return {"mock": True, "label": prompt, "bbox": [0.18, 0.22, 0.64, 0.56],
            "mask": None, "note": "Mock segmentation; real SAM 3.1 output shape unverified."}


def mock_diagnose(image_data_url: str, user_note: str = "", domain: str = "", hint: str = "") -> dict:
    key = _pick(image_data_url, hint, user_note)
    d = copy.deepcopy(SCENARIOS[key])
    if not any(k in (domain or "").lower() for k in ("oil", "gas", "wellsite", "pipeline")):
        for k in OIL_GAS_EXTRA_KEYS:
            d.pop(k, None)
    return d


def _title(text: str, limit: int = 70) -> str:
    t = text.split(";")[0].split(":")[0].strip().rstrip(".")
    if len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0] + "..."
    return t


def mock_work_order(diagnosis: dict) -> dict:
    return {
        "title": _title(diagnosis.get("work_order_draft") or "Field inspection follow-up"),
        "priority": diagnosis.get("severity", "Medium"),
        "description": diagnosis.get("issue_summary", ""),
        "immediate_actions": list(diagnosis.get("immediate_actions", [])),
        "recommended_next_steps": list(diagnosis.get("recommended_next_steps", [])),
        "safety_notes": list(diagnosis.get("safety_notes", [])),
    }


# ---------------------------------------------------------------------------
# Satellite + drone mock data
# ---------------------------------------------------------------------------
import json as _json
from pathlib import Path as _Path

_ROOT = _Path(__file__).resolve().parent
SEVERITY_RANK = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}


def mock_satellite(notes: str = "") -> dict:
    """Demo AOIs hand-placed on the bundled Sentinel-2 clip. NOT detected leaks."""
    p = _ROOT / "samples" / "satellite" / "demo_aoi.json"
    demo = _json.loads(p.read_text()) if p.is_file() else {"aois": []}
    aois = []
    for a in demo.get("aois", []):
        a = dict(a)
        a["description"] = "DEMO EXAMPLE: " + a["description"]
        a["next_level"] = "none" if a["type"] == "seasonal_false_positive" else "drone"
        aois.append(a)
    return {
        "demo": True,
        "summary": ("DEMO OUTPUT. Example areas of interest placed by hand on visible features of a real "
                    "Sentinel-2 clip near Dawson Creek/Fort St. John. They illustrate the workflow and are "
                    "NOT detected leaks or confirmed problems."),
        "aois": aois,
        "limitations": [
            "~10 m pixels: valves, gauges, signage and small stains are not visible",
            "Most NDVI drop in this pair is harvest/seasonal change (Aug 2018 vs Sep 2021)",
            "Satellite imagery cannot detect gas, H2S or methane",
        ],
    }


_DRONE_BASE = {"gauge_reading": "not resolvable from the air", "regulatory_note": REG_NOTE,
               "additional_issues": [], "requires_gas_detection": True}

DRONE_SCENARIOS = {
    "leak": dict(_DRONE_BASE, **{
        "issue_summary": "Well pad with visible disturbance and dark ground patches consistent with an active incident response.",
        "severity": "Critical", "confidence": 0.66, "asset_type": "lease_pad",
        "observed_conditions": ["Dark, irregular patches on the pad surface", "Equipment and response activity on site",
                                "Vegetation discolouration downslope of the pad"],
        "likely_causes": ["Loss of containment at the wellhead or connected equipment"],
        "immediate_actions": ["Do not approach without the site's emergency/H2S procedures and gas monitoring",
                              "Notify the operator's control room or emergency line"],
        "recommended_next_steps": ["Ground close-up of the wellhead and the downslope edge", "Delineate the affected area"],
        "safety_notes": ["An image cannot detect gas; confirm with calibrated detection", "Stay upwind"],
        "work_order_draft": "Respond to suspected release at the well pad; ground inspection; contain and report.",
        "hazard_flags": ["leak_or_stain", "containment_breach"],
        "needs_ground_closeup": True,
        "ground_photo_request": "Close-up of the wellhead base and the darkest downslope patch, with a scale reference"}),
    "row": dict(_DRONE_BASE, **{
        "issue_summary": "Pipeline right-of-way in good overall condition; check one crossing area for erosion/encroachment.",
        "severity": "Medium", "confidence": 0.58, "asset_type": "right_of_way",
        "observed_conditions": ["Cleared corridor with intersecting cutlines/roads", "Snow cover limits ground visibility",
                                "No exposed pipe visible at this altitude"],
        "likely_causes": ["Vehicle crossings and freeze-thaw may cause rutting or erosion at intersections"],
        "immediate_actions": ["Log the crossing location for follow-up"],
        "recommended_next_steps": ["Ground check at the intersection after snowmelt", "Confirm the crossing is authorized"],
        "safety_notes": ["Call before you dig; never excavate near a pipeline without a locate",
                         "An image cannot detect gas"],
        "work_order_draft": "RoW patrol follow-up: inspect the crossing for erosion, depth of cover and authorization.",
        "hazard_flags": ["other"], "requires_gas_detection": False,
        "needs_ground_closeup": True,
        "ground_photo_request": "Ground photos of the crossing from both sides, with any markers visible"}),
    "construction": dict(_DRONE_BASE, **{
        "issue_summary": "Active well pad construction: lease footprint change explains the satellite flag.",
        "severity": "Low", "confidence": 0.7, "asset_type": "lease_pad",
        "observed_conditions": ["Fresh earthworks and cleared pad", "Rig/construction equipment staged", "Snow-covered access"],
        "likely_causes": ["Planned development (consistent with a 'new disturbance' AOI)"],
        "immediate_actions": ["Confirm with the operator that the activity is planned"],
        "recommended_next_steps": ["Close the AOI as explained if confirmed", "Re-check erosion and sediment controls after thaw"],
        "safety_notes": ["Active construction: stay clear of equipment; site orientation required"],
        "work_order_draft": "Verify planned construction at the flagged lease; close the AOI if confirmed.",
        "hazard_flags": ["other"], "requires_gas_detection": False,
        "needs_ground_closeup": False, "ground_photo_request": ""}),
    "pad": dict(_DRONE_BASE, **{
        "issue_summary": "Operating well pad with tanks and facilities; containment looks intact from the air, minor housekeeping.",
        "severity": "Low", "confidence": 0.6, "asset_type": "lease_pad",
        "observed_conditions": ["Facilities and piping visible", "Containment berm outline visible", "No obvious staining at this resolution"],
        "likely_causes": ["Normal operating condition"],
        "immediate_actions": ["None urgent"],
        "recommended_next_steps": ["Routine ground inspection of the tank containment and wellheads"],
        "safety_notes": ["An image cannot detect gas; follow site entry and gas monitoring procedures"],
        "work_order_draft": "Routine lease inspection; verify containment and housekeeping.",
        "hazard_flags": [], "requires_gas_detection": True,
        "needs_ground_closeup": False, "ground_photo_request": ""}),
}
_DRONE_KEYS = [("leak", ("leak", "aliso", "stain", "spill")), ("row", ("row", "right", "pipeline", "corridor")),
               ("construction", ("construct", "build", "new")), ("pad", ("pad", "sagd", "well", "tank"))]


def mock_drone_finding(image_data_url: str, filename: str = "", notes: str = "") -> dict:
    h = (filename or "").lower()
    for key, words in _DRONE_KEYS:
        if any(w in h for w in words):
            return copy.deepcopy(DRONE_SCENARIOS[key])
    digest = hashlib.sha256((image_data_url or "").encode()).digest()
    return copy.deepcopy(list(DRONE_SCENARIOS.values())[digest[0] % len(DRONE_SCENARIOS)])
