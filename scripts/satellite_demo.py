"""Run the Sentinel-2 multi-site demo fetch for the SiteSense satellite layer.

Fetches real Sentinel-2 before/after clips (Peace Region sites) via the free,
no-auth Element84 Earth Search STAC API and writes images + JSON summaries into
samples/satellite/sites/. Prints the combined summary; exits non-zero if any
site fails.

Run: python scripts/satellite_demo.py [--max-cloud 20] [--half-m 4000]
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_fetcher():
    spec = importlib.util.spec_from_file_location(
        "fetch_sentinel_stac", ROOT / "tools" / "fetch_sentinel_stac.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


if __name__ == "__main__":
    fetcher = load_fetcher()
    sys.exit(fetcher.main(sys.argv[1:]))
