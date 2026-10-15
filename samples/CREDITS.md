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

## Drone / aerial (samples/drone/)

These are openly licensed **aerial** photos from Wikimedia Commons, mostly taken from crewed aircraft rather than drones, used as stand-ins until Barbara's own drone photos are added. Licenses were checked on each file page on 2026-10-14. Images are downscaled to 1280 px wide and not otherwise modified. CC BY / CC BY-SA require attribution (given here). CC BY-SA also requires sharing adaptations of those images under the same license.

| File | Subject | Source | License | Author |
|---|---|---|---|---|
| `well_pad_gas_leak_aliso.jpg` | Aliso Canyon gas leak well pad (California), two months after the leak began | https://commons.wikimedia.org/wiki/File:Aliso_Canyon_leak_well_pad_1_Credit-_Earthworks_(23594167450).jpg | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0) | EARTHWORKS |
| `pipeline_row.jpg` | Pipeline right-of-way through boreal forest | https://commons.wikimedia.org/wiki/File:Pipeline_right_of_ways_(25224881585).jpg | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0) | jasonwoodhead23 (Flickr) |
| `well_pad_construction.jpg` | Well pad under construction (ConocoPhillips) | https://commons.wikimedia.org/wiki/File:Conoco_Phillips_(25712193905).jpg | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0) | jasonwoodhead23 (Flickr) |
| `sagd_well_pad.jpg` | SAGD well pad, Long Lake (Alberta) | https://commons.wikimedia.org/wiki/File:Nexion_long_lake_2016_(25653392922).jpg | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0) | jasonwoodhead23 (Flickr) |
| `oil_well_site_yawthorpe.jpg` | Oil well site at Yawthorpe (UK), aerial 2022 | https://commons.wikimedia.org/wiki/File:Oil_well_at_Yawthorpe,_aerial_2022_-_geograph.org.uk_-_7162660.jpg | [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0) | Simon Tomson |

Not used: pumpjack and tank-battery aerials, because no clearly licensed relevant image came up. Unsplash and Pexels were not used, because their custom licenses can't be checked as reliably as CC files.
