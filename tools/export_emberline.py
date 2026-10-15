"""Export Emberline's BC Wildfire Service catalog to data/bc_fires.geojson.

Usage: python tools/export_emberline.py /path/to/emberline/src/data/catalog.json

Source data: BC Wildfire Service, Historical Fire Incident Locations (2015-2025),
Open Government Licence - British Columbia. Only fire points (>= 1 ha) and the
pre-aggregated ignition hotspot cells are exported; no Emberline code is copied.
"""
import json
import sys
from pathlib import Path

CAUSE = {"h": "human", "l": "lightning", "u": "unknown"}
OUT = Path(__file__).resolve().parent.parent / "data" / "bc_fires.geojson"


def export(catalog_path: str, out: Path = OUT) -> dict:
    cat = json.loads(Path(catalog_path).read_text())
    meta = cat["meta"]
    feats = []
    for f in cat["fires"]:
        feats.append({"type": "Feature",
                      "geometry": {"type": "Point", "coordinates": [round(f["lng"], 4), round(f["lat"], 4)]},
                      "properties": {"kind": "fire", "id": f["id"], "name": f.get("name") or f["id"],
                                     "year": f["y"], "month": f.get("m"), "ha": f["ha"],
                                     "cause": CAUSE.get(f.get("cause"), "unknown")}})
    for h in cat["hotspots"]:
        feats.append({"type": "Feature",
                      "geometry": {"type": "Point", "coordinates": [h["lng"], h["lat"]]},
                      "properties": {"kind": "hotspot", "starts": h["n"], "ha": h["ha"], "human": h["human"],
                                     "lightning": h["lightning"],
                                     "unknown": max(0, h["n"] - h["human"] - h["lightning"]),
                                     "score": h["score"], "top_year": h.get("topYear")}})
    fc = {"type": "FeatureCollection",
          "metadata": {"source": meta["source"], "source_url": meta["sourceUrl"],
                       "licence": "Open Government Licence - British Columbia",
                       "licence_url": "https://www2.gov.bc.ca/gov/content/data/open-data/open-government-licence-bc",
                       "years": meta["years"], "retrieved": meta["retrieved"],
                       "note": ("Fire points are incidents >= 1 ha at their reported origin (not perimeters). "
                                "Hotspot cells aggregate all recorded starts on a ~0.1 degree grid. "
                                "Exported from the Emberline catalog."),
                       "fires": len(cat["fires"]), "hotspot_cells": len(cat["hotspots"])},
          "features": feats}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fc, separators=(",", ":")))
    return fc["metadata"]


if __name__ == "__main__":
    print(export(sys.argv[1]))
