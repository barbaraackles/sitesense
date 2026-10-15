"""Emberline wildfire layer: historical fire risk around a point (wellsite, AOI, lease).

Data: data/bc_fires.geojson, exported from Emberline (BC Wildfire Service Historical Fire
Incident Locations 2015-2025, Open Government Licence - British Columbia).

The rating mirrors Emberline's per-town ("City") logic: mapped fires (>= 1 ha) and burned
hectares inside 10 / 25 / 50 km rings, cause mix, nearest large fire, and a 0-100 score
banded into watch / moderate / high / very-high / extreme. Emberline's scores are computed
offline; the weights below were least-squares calibrated against its 63 published town
scores (mean absolute error about 6 points) so the two tools agree on the same place.

This is a HISTORICAL exposure indicator, not a fire-danger forecast. Always check current
BC Wildfire Service danger ratings, bans and evacuation orders.
"""
import json
import math
from datetime import date
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "bc_fires.geojson"
RINGS_KM = (10, 25, 50)
BIG_FIRE_HA = 1000
# Score bands taken from Emberline's town ratings.
BANDS = ((87, "extreme"), (75, "very-high"), (56, "high"), (38, "moderate"), (0, "watch"))
# Fire season used for drone ranking (BC Wildfire Service season is roughly April-October).
FIRE_SEASON_MONTHS = range(4, 11)
# Calibrated weights (see module docstring).
W = {"c": -3.62, "n10": 14.9, "ha10": 1.21, "n25": 0.86, "ha25": 2.22}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@lru_cache(maxsize=1)
def load(path: str = str(DATA)):
    fc = json.loads(Path(path).read_text())
    fires, cells = [], []
    for f in fc["features"]:
        lon, lat = f["geometry"]["coordinates"]
        p = dict(f["properties"], lat=lat, lon=lon)
        (fires if p["kind"] == "fire" else cells).append(p)
    return fires, cells, fc.get("metadata", {})


def score_from_rings(n10, ha10, n25, ha25) -> float:
    s = (W["c"] + W["n10"] * math.log1p(n10) + W["ha10"] * math.log1p(ha10)
         + W["n25"] * math.log1p(n25) + W["ha25"] * math.log1p(ha25))
    return round(min(100.0, max(0.0, s)), 1)


def rating_for(score: float) -> str:
    return next(name for floor, name in BANDS if score >= floor)


def risk_at(lat: float, lon: float) -> dict:
    """Historical wildfire exposure around (lat, lon). Works anywhere; data covers BC only."""
    fires, cells, meta = load()
    near = []
    for f in fires:
        if abs(f["lat"] - lat) > 0.5 or abs(f["lon"] - lon) > 0.9:  # cheap box prefilter (> 50 km)
            continue
        d = haversine_km(lat, lon, f["lat"], f["lon"])
        if d <= RINGS_KM[-1]:
            near.append((d, f))
    rings = {}
    for km in RINGS_KM:
        inside = [f for d, f in near if d <= km]
        rings[f"{km}km"] = {"fires": len(inside), "ha": round(sum(f["ha"] for f in inside), 1)}
    mix_src = [f for d, f in near if d <= 25]
    n = len(mix_src)
    counts = {c: sum(f["cause"] == c for f in mix_src) for c in ("human", "lightning", "unknown")}
    pct = {c: (round(100 * v / n) if n else 0) for c, v in counts.items()}
    big = sorted(((d, f) for d, f in near if f["ha"] >= BIG_FIRE_HA), key=lambda x: x[0])
    largest = max(near, key=lambda x: x[1]["ha"], default=None)

    def fire_out(x):
        if not x:
            return None
        d, f = x
        return {"id": f["id"], "name": f["name"], "year": f["year"], "ha": f["ha"], "cause": f["cause"],
                "km": round(d, 1), "lat": f["lat"], "lon": f["lon"]}

    starts = [c for c in cells if haversine_km(lat, lon, c["lat"], c["lon"]) <= 10]
    score = score_from_rings(rings["10km"]["fires"], rings["10km"]["ha"],
                             rings["25km"]["fires"], rings["25km"]["ha"])
    return {
        "lat": lat, "lon": lon, "rings": rings,
        "cause_mix": {"radius_km": 25, "fires": n, "counts": counts, "percent": pct},
        "ignition_hotspot_starts_10km": sum(c["starts"] for c in starts),
        "nearest_big_fire": fire_out(big[0] if big else None),
        "largest_within_50km": fire_out(largest),
        "score": score, "rating": rating_for(score),
        "years": meta.get("years"), "source": meta.get("source"),
        "note": "Historical 2015-2025 exposure, not a forecast. Check current BC Wildfire Service danger ratings and bans.",
    }


def burn_scar_check(lat: float, lon: float, after_year: int | None = None, radius_km: float = 0) -> dict | None:
    """Is there a known fire whose (circular) footprint overlaps or sits near this point?

    Fire points have no perimeter, so the footprint is approximated as a circle of the
    fire's area centred on its origin, plus a 3 km margin (origins are not centroids).
    Only fires up to `after_year` (the later image) can explain a vegetation drop.
    """
    fires, _, _ = load()
    best = None
    for f in fires:
        if after_year and f["year"] > after_year:
            continue
        reach = math.sqrt(f["ha"] * 10000 / math.pi) / 1000 + 3 + radius_km
        if abs(f["lat"] - lat) > reach / 111 + 0.05:
            continue
        d = haversine_km(lat, lon, f["lat"], f["lon"])
        if d <= reach and (best is None or f["ha"] > best[1]["ha"]):
            best = (d, f)
    if not best:
        return None
    d, f = best
    return {"id": f["id"], "name": f["name"], "year": f["year"], "ha": f["ha"], "km": round(d, 1)}


def in_fire_season(today: date | None = None) -> bool:
    return (today or date.today()).month in FIRE_SEASON_MONTHS


RATING_RANK = {"watch": 0, "moderate": 1, "high": 2, "very-high": 3, "extreme": 4}


def firesmart_section(risk: dict | None = None) -> dict:
    """Generic lease FireSmart checklist for work orders (no regulation numbers invented)."""
    rating = (risk or {}).get("rating")
    head = (f"Historical wildfire exposure around this lease: {rating} (score {risk['score']}). "
            if risk else "") + "Generic lease FireSmart checks; follow the operator's procedures and applicable rules."
    return {
        "title": "Lease FireSmart",
        "summary": head,
        "rating": rating,
        "items": [
            "Vegetation clearance: keep grass, brush and deadfall cut back around the wellhead, separators, "
            "tanks and the flare stack, to the distance in the operator's procedures and permit conditions.",
            "Flare and hot work: check the flare area is clear of cured grass and debris; follow the hot-work "
            "permit and any fire bans or restrictions in force.",
            "Pipeline right-of-way: maintain mowed or bladed firebreaks along the ROW and lease edge; note "
            "slash piles or encroaching fuel for follow-up.",
            "Overwintering fires: after a fire season nearby, watch for smoke or hot spots from holdover fires "
            "in peat and organic soils in spring; report to the BC Wildfire Service.",
            "Evacuation and H2S muster: confirm the muster point and a second egress route still work if a fire "
            "blocks the main access; wildfire smoke and H2S are both reasons to move upwind.",
            "Check current BC Wildfire Service fire danger, bans and evacuation orders before field work.",
        ],
    }


# --------------------------------------------------------------------------- AOIs + drone
# AOI types whose signal is a vegetation drop / dark patch that a burn could also explain.
DROP_TYPES = {"vegetation_stress", "possible_staining", "new_disturbance", "other"}
BURN_LABEL = "possible burn scar / fire recovery"


def compact(risk: dict) -> dict:
    return {"score": risk["score"], "rating": risk["rating"], "rings": risk["rings"],
            "cause_mix": risk["cause_mix"]["percent"], "nearest_big_fire": risk["nearest_big_fire"]}


def annotate_aoi(aoi: dict, after_year: int | None = None) -> dict:
    """Add a wildfire-risk badge and, for vegetation-drop AOIs over/near a known fire,
    relabel them as a possible burn scar instead of a possible spill."""
    a = dict(aoi)
    if a.get("lat") is None or a.get("lon") is None:
        return a
    a["fire_risk"] = compact(risk_at(a["lat"], a["lon"]))
    scar = burn_scar_check(a["lat"], a["lon"], after_year) if a.get("type") in DROP_TYPES else None
    if scar:
        a["burn_scar"] = scar
        a["interpretation"] = BURN_LABEL
        a["description"] = (f"{BURN_LABEL.capitalize()}: the vegetation drop is within the footprint of the "
                            f"{scar['year']} {scar['name']} fire ({scar['ha']:,.0f} ha, origin {scar['km']} km away). "
                            f"Original flag: {a.get('description', '')}")
    return a


def fire_relevant(finding: dict) -> bool:
    """Findings that add fuel or ignition to a lease: weighted up in fire season."""
    flags = set(finding.get("hazard_flags") or [])
    text = " ".join([finding.get("issue_summary", "")] + list(finding.get("observed_conditions") or [])).lower()
    return bool(flags & {"leak_or_stain", "hot_work", "ignition_source", "containment_breach"}) or any(
        w in text for w in ("flare", "vegetation", "grass", "brush", "slash", "debris", "hydrocarbon"))


def drone_fire_bonus(finding: dict, risk: dict | None, today: date | None = None) -> float:
    """Ranking bonus in fire season (Apr-Oct): +0.5 at high+ exposure, +0.25 at moderate,
    only for fire-relevant findings. Smaller than one severity step, so a Critical is never
    out-ranked by a High; it reorders within a severity level and breaks near-ties."""
    if not risk or not in_fire_season(today) or not fire_relevant(finding):
        return 0.0
    r = RATING_RANK.get(risk["rating"], 0)
    return 0.5 if r >= 2 else 0.25 if r == 1 else 0.0
