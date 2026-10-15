"""Fetch free Sentinel-2 L2A clips (Element84 earth-search STAC, AWS COGs; no auth).

Writes a true-colour clip plus before/after NDVI and an NDVI-change view to samples/satellite/.
Contains modified Copernicus Sentinel data (2018, 2021).
Usage: python tools/fetch_sentinel.py   (needs: rasterio numpy pillow pyproj)
"""
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.windows import from_bounds

OUT = Path(__file__).resolve().parent.parent / "samples" / "satellite"
BASE = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/10/V/FH"
CENTER = (-120.45, 55.95)  # lon, lat: Montney play area between Dawson Creek and Fort St. John, NE BC
HALF = 4000  # metres → ~8 km × 8 km clip
SCENES = {"before": f"{BASE}/2018/8/S2A_10VFH_20180802_0_L2A",
          "after": f"{BASE}/2021/9/S2A_10VFH_20210902_0_L2A"}


def read(scene, band, bounds):
    with rasterio.open(f"{scene}/{band}.tif") as src:
        return src.read(1, window=from_bounds(*bounds, transform=src.transform)).astype("float32")


def stretch(a, lo=0, hi=2500):
    return (np.clip((a - lo) / (hi - lo), 0, 1) ** 0.8 * 255).astype("uint8")


def ndvi_rgb(n):
    # brown (bare) -> yellow -> green (vigorous)
    t = np.clip((n + 0.1) / 0.9, 0, 1)
    r = np.where(t < .5, 140 + t * 2 * 100, 240 - (t - .5) * 2 * 200)
    g = np.where(t < .5, 90 + t * 2 * 140, 230 - (t - .5) * 2 * 90)
    b = np.full_like(t, 40)
    return np.dstack([r, g, b]).astype("uint8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    x, y = Transformer.from_crs(4326, 32610, always_xy=True).transform(*CENTER)
    bounds = (x - HALF, y - HALF, x + HALF, y + HALF)
    nd = {}
    for k, s in SCENES.items():
        r, g, b, n = (read(s, band, bounds) for band in ("B04", "B03", "B02", "B08"))
        Image.fromarray(np.dstack([stretch(r), stretch(g), stretch(b)])).save(OUT / f"truecolor_{k}.jpg", quality=90)
        nd[k] = (n - r) / np.maximum(n + r, 1)
        Image.fromarray(ndvi_rgb(nd[k])).save(OUT / f"ndvi_{k}.png")
    d = nd["after"] - nd["before"]
    rgb = np.full(d.shape + (3,), 60, "uint8")
    rgb[d < -0.15] = (255, 106, 0)   # NDVI drop (orange): vegetation loss/stress or new clearing
    rgb[d > 0.15] = (60, 160, 90)    # NDVI gain (green)
    Image.fromarray(rgb).save(OUT / "ndvi_change.png")
    inv = Transformer.from_crs(32610, 4326, always_xy=True)
    meta = {"center_lonlat": CENTER, "bbox_utm10n": bounds,
            "bbox_lonlat": [*inv.transform(bounds[0], bounds[1]), *inv.transform(bounds[2], bounds[3])],
            "scenes": SCENES, "pixel_m": 10, "size_px": list(d.shape[::-1]),
            "ndvi_drop_fraction": float((d < -0.15).mean())}
    (OUT / "scene.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
