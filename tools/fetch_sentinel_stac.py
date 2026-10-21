"""Fetch real Sentinel-2 L2A before/after clips for Peace Region oil & gas sites.

Queries the free Element84 Earth Search STAC API (collection sentinel-2-l2a; no auth)
for the most recent low-cloud scene at each site plus a same-season scene from about a
year earlier, then clips true-colour + NDVI views from the AWS COGs into
samples/satellite/sites/<slug>/ and writes per-site site.json plus a combined
samples/satellite/sites.json summary.

Honesty rules (same as the rest of SiteSense): Sentinel-2 is 10 m/px — site-level
change triage only. These clips cannot resolve individual equipment and cannot detect
leaks or gas; they flag where a drone or ground crew should look next.

Usage: python tools/fetch_sentinel_stac.py [--max-cloud 20] [--half-m 4000]
       (needs: rasterio numpy pillow pyproj; requests not required)
Exit code is non-zero if any site fails, with a clear error on stderr.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.windows import from_bounds

STAC_SEARCH = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-l2a"
OUT_ROOT = Path(__file__).resolve().parent.parent / "samples" / "satellite" / "sites"

# Peace Region oil & gas target sites (lat, lon are town/plant-area centres).
SITES = [
    {"slug": "dawson-creek", "name": "Dawson Creek, BC", "lat": 55.76, "lon": -120.23,
     "note": "Wellsite area south of Dawson Creek; Montney play."},
    {"slug": "taylor", "name": "Taylor, BC", "lat": 56.16, "lon": -120.69,
     "note": "Gas plants / refinery area (Taylor refinery and gas processing)."},
    {"slug": "fort-st-john", "name": "Fort St. John, BC", "lat": 56.25, "lon": -120.85,
     "note": "Major Peace Region oil & gas hub."},
]

def load_extra_sites():
    """Optional extra sites from samples/satellite/sites/extra_sites.json.

    Lets private/local watch sites (e.g. a landowner's own property) join the
    demo without putting their coordinates in this source file — the config
    lives inside the samples/satellite/sites/ output tree alongside results.
    """
    path = OUT_ROOT / "extra_sites.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


LIMITATIONS = [
    "10 m/px Sentinel-2: site-level change triage only — pads, clearings, vegetation "
    "change. Cannot resolve individual equipment, valves or fittings.",
    "Cannot detect leaks or gas. A dark patch or NDVI drop is a reason to escalate to "
    "drone/ground inspection, never a leak conclusion.",
    "Before/after pairs are same-season by design, but harvest, weather and phenology "
    "still cause NDVI change unrelated to any site activity.",
]

BANDS = {"red": "red", "green": "green", "blue": "blue", "nir": "nir"}


class FetchError(RuntimeError):
    pass


def stac_search(lat, lon, start, end, max_cloud, limit=40):
    """POST a STAC search; returns feature dicts sorted newest-first."""
    body = {
        "collections": [COLLECTION],
        "intersects": {"type": "Point", "coordinates": [lon, lat]},
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": max_cloud}},
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        "limit": limit,
    }
    req = urllib.request.Request(STAC_SEARCH, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.load(resp).get("features", [])
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise FetchError(f"STAC search failed ({start}..{end}): {exc}") from exc


def scene_brief(feature):
    p = feature["properties"]
    return {"id": feature["id"], "datetime": p.get("datetime"),
            "date": (p.get("datetime") or "")[:10],
            "cloud_cover_pct": round(float(p.get("eo:cloud_cover", -1)), 2),
            "tile": p.get("grid:code")}


def pick_pair(site, max_cloud):
    """Most recent clear scene + a same-season scene ~1 year earlier, same tile if possible."""
    today = date.today()
    recent_start = today - timedelta(days=120)
    after_feats = (stac_search(site["lat"], site["lon"], str(recent_start), str(today), max_cloud)
                   or stac_search(site["lat"], site["lon"], str(today - timedelta(days=365)),
                                  str(today), 60))
    if not after_feats:
        raise FetchError("no usable recent scene found")
    after = after_feats[0]
    after_date = date.fromisoformat(scene_brief(after)["date"])
    before_start = after_date - timedelta(days=365 + 60)
    before_end = after_date - timedelta(days=365 - 60)
    before_feats = (stac_search(site["lat"], site["lon"], str(before_start), str(before_end), max_cloud)
                    or stac_search(site["lat"], site["lon"], str(before_start), str(before_end), 60))
    if not before_feats:
        raise FetchError("no usable ~1-year-earlier scene found")
    tile = scene_brief(after)["tile"]
    same_tile = [f for f in before_feats if scene_brief(f)["tile"] == tile] or before_feats
    target_doy = (after_date - timedelta(days=365)).timetuple().tm_yday
    before = min(same_tile,
                 key=lambda f: abs(date.fromisoformat(scene_brief(f)["date"]).timetuple().tm_yday - target_doy))
    return before, after


def stretch(a, lo=0, hi=2500):
    return (np.clip((a - lo) / (hi - lo), 0, 1) ** 0.8 * 255).astype("uint8")


def ndvi_rgb(n):
    # brown (bare) -> yellow -> green (vigorous); same ramp as tools/fetch_sentinel.py
    t = np.clip((n + 0.1) / 0.9, 0, 1)
    r = np.where(t < .5, 140 + t * 2 * 100, 240 - (t - .5) * 2 * 200)
    g = np.where(t < .5, 90 + t * 2 * 140, 230 - (t - .5) * 2 * 90)
    b = np.full_like(t, 40)
    return np.dstack([r, g, b]).astype("uint8")


def read_window(href, bounds):
    with rasterio.open(href) as src:
        return src.read(1, window=from_bounds(*bounds, transform=src.transform)).astype("float32")


def clip_scene(feature, lat, lon, half_m):
    """Read an ~2*half_m square clip of red/green/blue/nir around (lat, lon)."""
    assets = feature["assets"]
    hrefs = {}
    for key, asset_key in BANDS.items():
        asset = assets.get(asset_key) or assets.get(asset_key.upper())
        if not asset:
            raise FetchError(f"scene {feature['id']} is missing asset '{asset_key}'")
        hrefs[key] = asset["href"]
    with rasterio.open(hrefs["red"]) as src:
        crs = src.crs
    x, y = Transformer.from_crs(4326, crs, always_xy=True).transform(lon, lat)
    bounds = (x - half_m, y - half_m, x + half_m, y + half_m)
    bands = {k: read_window(h, bounds) for k, h in hrefs.items()}
    if any(b.size == 0 for b in bands.values()):
        raise FetchError(f"scene {feature['id']} does not cover the site centre")
    inv = Transformer.from_crs(crs, 4326, always_xy=True)
    bbox_lonlat = [*inv.transform(bounds[0], bounds[1]), *inv.transform(bounds[2], bounds[3])]
    return bands, bbox_lonlat


def fetch_site(site, max_cloud, half_m):
    before_f, after_f = pick_pair(site, max_cloud)
    out = OUT_ROOT / site["slug"]
    out.mkdir(parents=True, exist_ok=True)
    nd, files = {}, {}
    for label, feature in (("before", before_f), ("after", after_f)):
        bands, bbox = clip_scene(feature, site["lat"], site["lon"], half_m)
        rgb = np.dstack([stretch(bands["red"]), stretch(bands["green"]), stretch(bands["blue"])])
        tc = out / f"truecolor_{label}.jpg"
        Image.fromarray(rgb).save(tc, quality=90)
        nd[label] = (bands["nir"] - bands["red"]) / np.maximum(bands["nir"] + bands["red"], 1)
        nv = out / f"ndvi_{label}.png"
        Image.fromarray(ndvi_rgb(nd[label])).save(nv)
        files[label] = (tc, nv)
    h = min(nd["before"].shape[0], nd["after"].shape[0])
    w = min(nd["before"].shape[1], nd["after"].shape[1])
    d = nd["after"][:h, :w] - nd["before"][:h, :w]
    change = np.full(d.shape + (3,), 60, "uint8")
    change[d < -0.15] = (255, 106, 0)   # NDVI drop: vegetation loss/stress or new clearing
    change[d > 0.15] = (60, 160, 90)    # NDVI gain
    Image.fromarray(change).save(out / "ndvi_change.png")
    for label in ("before", "after"):  # verify every written image actually opens
        for path in files[label]:
            with Image.open(path) as im:
                im.verify()
    meta = {
        "site": site["name"], "slug": site["slug"], "note": site["note"],
        "center": {"lat": site["lat"], "lon": site["lon"]},
        "clip": {"size_m": 2 * half_m, "pixel_m": 10,
                 "size_px": [int(w), int(h)], "bbox_lonlat": bbox},
        "scenes": {"before": scene_brief(before_f), "after": scene_brief(after_f)},
        "images": {"truecolor_before": "truecolor_before.jpg",
                   "truecolor_after": "truecolor_after.jpg",
                   "ndvi_before": "ndvi_before.png", "ndvi_after": "ndvi_after.png",
                   "ndvi_change": "ndvi_change.png"},
        "ndvi_drop_fraction": round(float((d < -0.15).mean()), 4),
        "source": f"Element84 Earth Search STAC ({STAC_SEARCH}), collection {COLLECTION}, "
                  "AWS COGs; free, no auth",
        "attribution": "Contains modified Copernicus Sentinel data "
                       f"({scene_brief(before_f)['date'][:4]}, {scene_brief(after_f)['date'][:4]})",
        "limitations": LIMITATIONS,
    }
    (out / "site.json").write_text(json.dumps(meta, indent=2))
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max-cloud", type=float, default=20.0,
                    help="maximum scene cloud cover %% for the primary search (default 20)")
    ap.add_argument("--half-m", type=int, default=4000,
                    help="clip half-size in metres (default 4000 -> 8 km x 8 km)")
    args = ap.parse_args(argv)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    sites = SITES + load_extra_sites()
    summary, failures = [], 0
    for site in sites:
        try:
            meta = fetch_site(site, args.max_cloud, args.half_m)
            entry = dict(meta)
            entry["images"] = {k: f"sites/{site['slug']}/{v}" for k, v in meta["images"].items()}
            summary.append(entry)
            print(f"OK  {site['name']}: after {meta['scenes']['after']['id']} "
                  f"({meta['scenes']['after']['cloud_cover_pct']}% cloud), "
                  f"before {meta['scenes']['before']['id']} "
                  f"({meta['scenes']['before']['cloud_cover_pct']}% cloud)", file=sys.stderr)
        except (FetchError, rasterio.errors.RasterioError, OSError, ValueError) as exc:
            failures += 1
            print(f"ERROR {site['name']}: {exc}", file=sys.stderr)
            summary.append({"site": site["name"], "slug": site["slug"],
                            "center": {"lat": site["lat"], "lon": site["lon"]},
                            "error": str(exc)})
    combined = {"collection": COLLECTION, "source": STAC_SEARCH,
                "limitations": LIMITATIONS, "sites": summary}
    summary_path = OUT_ROOT.parent / "sites.json"
    summary_path.write_text(json.dumps(combined, indent=2))
    print(json.dumps(combined, indent=2))
    if failures:
        print(f"FAILED: {failures}/{len(sites)} site(s) could not be fetched", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
