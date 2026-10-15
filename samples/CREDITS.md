# Sample image credits

All samples come from Wikimedia Commons, and each is marked **public domain** on its file page. They were checked on 2026-10-14. Images are downscaled copies (1024 px wide) and were not otherwise edited.

| File | Subject | Source | License | Author / credit |
|---|---|---|---|---|
| `corroded_pipe.jpg` | Corroded pipe | https://commons.wikimedia.org/wiki/File:Corroded_pipe.jpg | Public domain (US Government work) | NIOSH (CDC) |
| `wellhead.jpg` | Wellhead with plunger-lift catcher, Northern BC, Canada | https://commons.wikimedia.org/wiki/File:Wellhead-plunger_lift.jpg | Public domain (released by author) | Dexcel at English Wikipedia |
| `pressure_gauge.jpg` | Glycerine-filled Bourdon-tube pressure gauge | https://commons.wikimedia.org/wiki/File:Druck_Manometer.jpg | Public domain (released by author) | ADwarf |
| `leak_stain_soil.jpg` | Oil-contaminated soil, crew in PPE (2010 Enbridge Kalamazoo River spill response) | https://commons.wikimedia.org/wiki/File:Contaminated_soil_(4888593988).jpg | Public domain (US Government work) | U.S. EPA |

No pumpjack, valve or tank-berm image was added, because no relevant one with a clearly verifiable CC0/PD license came up in this pass.

## Satellite (samples/satellite/)

| File | Content | Source | License |
|---|---|---|---|
| `truecolor_before.jpg`, `ndvi_before.png` | Sentinel-2 L2A scene S2A_10VFH_20180802_0_L2A, ~8×8 km clip centred at 55.95°N, 120.45°W (Montney area between Dawson Creek and Fort St. John, NE BC) | Element84 Earth Search STAC (`sentinel-2-l2a`), AWS Open Data COGs: https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/10/V/FH/2018/8/S2A_10VFH_20180802_0_L2A/ | Copernicus Sentinel data, free and open ([Sentinel data legal notice](https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice)) |
| `truecolor_after.jpg`, `ndvi_after.png` | Same area, scene S2A_10VFH_20210902_0_L2A | https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/10/V/FH/2021/9/S2A_10VFH_20210902_0_L2A/ | As above |
| `ndvi_change.png` | NDVI(after) − NDVI(before); orange = drop > 0.15, green = gain > 0.15 | Derived (`tools/fetch_sentinel.py`) | As above |

Attribution: **Contains modified Copernicus Sentinel data [2018, 2021].**

Note: most of the NDVI drop in this pair is farm harvest and seasonal difference (early Aug vs early Sep), not industrial impact. This shows why satellite change needs drone and ground follow-up. `demo_aoi.json` areas of interest are **hand-placed demo examples**, not detected leaks.
