# Mars EVA Navigator — Scientific provenance and Mission Evidence

**NASA Space Apps Challenge 2026 — Interplanetary Survival Guide**

This project is an **independent educational/research prototype**, not a NASA/JPL
flight system, EVA safety certification, or instrument telemetry feed.

## 1. Data classification (mandatory for demonstrations)

| Layer / output | Evidence category | What is actually supported |
| --- | --- | --- |
| Jezero CTX terrain GeoTIFF | **OBSERVED / DERIVED by USGS** | USGS Mars 2020 Terrain Relative Navigation CTX DTM; 20 m source sampling, georeferenced to Mars |
| Jezero JSON terrain grid | **RESAMPLED from observed data** | Original CTX heights processed by Rasterio; grid spacing depends on geographic window and output resolution; no new spatial detail |
| Curiosity HiRISE / CTX orbital maps | **OBSERVED** | NASA Mars Trek map tiles, with explicitly limited source footprints and native zoom |
| Curiosity traverse | **PUBLISHED / COMPILED** | NASA/JPL rover geometry or waypoint fallback; gaps, temporal interpolation and approximate positions disclosed in interface |
| Curiosity NASA panoramas | **OBSERVED / NASA MOSAIC** | Official NASA photo pages with panorama sources; locations matched approximately to rover sol, *not* verified camera pose |
| Local stitched panorama | **USER-DERIVED / EXPERIMENTAL** | Panorama from user-supplied overlapping frames; neither complete 360° nor 3D depth certified |
| EVA route profiles, resource consumption, radiation scenarios, emergency return, science utility | **MODEL / SCENARIO** | Exploration algorithms and assumptions. Not a validated EVA safety standard |
| Synthetic terrain mode | **DEMONSTRATION ONLY** | Never presented as Jezero or Gale measurements; disabled for Jezero planning |

**Do not describe an interpolated point as an observed rover pose.** The navigation
between photo stations jumps to *documented* panoramas and does not simulate
unphotographed viewpoints as real imagery. A continuous verified Street View at
every meter is not currently possible with these sources.

## 2. Authoritative terrain sources

- USGS Astrogeology, *Mars 2020 Terrain Relative Navigation CTX DTM Mosaic*,
  https://www.usgs.gov/data/mars-2020-terrain-relative-navigation-ctx-dtm-mosaic
  DOI [10.5066/P906QQT8](https://doi.org/10.5066/P906QQT8) (20 m/pixel).
- USGS Astrogeology, *Mars 2020 Terrain Relative Navigation HiRISE DTM Mosaic*,
  https://www.usgs.gov/data/mars-2020-terrain-relative-navigation-hirise-dtm-mosaic
  DOI [10.5066/P9REJ9JN](https://doi.org/10.5066/P9REJ9JN) (higher resolution; partial coverage).
- Additional HiRISE extension, USGS 2025:
  https://www.usgs.gov/data/mars-sample-return-hirise-mosaics-terrain-relative-navigation
- NASA Mars Trek orbital tiles:
  https://trek.nasa.gov/mars/
- NASA Curiosity mission location, images and official imagery:
  https://science.nasa.gov/mission/msl-curiosity/
- NASA raw images archive:
  https://mars.nasa.gov/msl/multimedia/raw-images/

**Gale ≠ Jezero.** Curiosity's Gale/Mount Sharp scene needs its *own* terrain
models. Never overlay Jezero heights beneath Gale photographs or routes.

## 3. Repeatable release of authentic Jezero terrain

Running `python scripts/prepare_dem.py --download ctx --export-json` downloads
the official USGS GeoTIFF. If the primary USGS site blocks requests, the
script tries its public PDS S3 mirror (not a scraped or user-submitted dataset).
The script records SHA-256, original source URL, actual download URL and file size
in a local `.tif.provenance.json` sidecar. The Rasterio pipeline rejects
incompatible Earth CRS, NoData contamination, missing or malformed raster bands.

For publishing, GitHub Actions runs:

```bash
python scripts/prepare_dem.py --download ctx --export-json \
  --bbox 77.1605 18.2111 77.6989 18.7211 --size 440 \
  --output jezero_dem_precomputed.json
python scripts/verify_static_dem.py jezero_dem_precomputed.json
python scripts/build_static_site.py --dem jezero_dem_precomputed.json --output _site
```

The *precomputed* JSON includes measured elevations, source metadata, sample
cell size, original source resolution and original TIFF SHA-256. A scientific
validator **fails the deployment** if provenance, Jezero bounds, original CTX
resolution, coverage or numerical values do not pass. It does **not** silently
substitute invented heights. The raw GeoTIFF, database and local secrets are
never part of the public site.

### Enable GitHub Pages

In the repository, open **Settings → Pages → Build and deployment → Source:
GitHub Actions**. After merging, the workflow **Publish Mars EVA Navigator with
verified Jezero DEM** runs on `main`, or can be started via **Actions →
Run workflow**. The static site loads `jezero_dem_precomputed.json` using the
existing **Conectar .TIF** flow automatically. A failed workflow means no newly
verified site has been deployed; investigate its logs rather than inventing
science outputs.

### Local live backend

```powershell
python -m pip install -r requirements.txt
python scripts/prepare_dem.py --download ctx --export-json
$env:MARS_DEM_PATH = (Resolve-Path '.\jezero_ctx_dtm_20m.tif').Path
python mars_dem_server.py
```

Open `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/api/status`.
Use **Misión Jezero · 2D → Conectar .TIF**, then choose two points inside the
cyan coverage boundary. Export GeoJSON; it now carries DEM provenance, actual
grid resolution and explicit prototype limitations. For a local-only
demonstration, bring your GeoTIFF or precomputed JSON with you.

## 4. Photo-based exploration and 3D limitations

The **Curiosity / 360°** mode provides NASA HiRISE and CTX map layers, a
published traverse where accessible, documented NASA panorama stations, WebGL
cylindrical viewing, raw photo search and optional local panorama stitching.
Fullscreen and previous/next navigation move between *actual documented photo
stations*. They cannot reconstruct camera viewpoints between those stations.

The **Mission Evidence Mode** terrain canvas derives 3D relief from the DEM
grid. It is terrain visualization, not ground-level photogrammetry.

To responsibly add real scene reconstruction in a future dataset:

1. Obtain calibrated, overlapping frames and their camera models/poses from
   official rover science archives; retain instrument IDs, sol and provenance.
2. Run feature matching and structure-from-motion / multiview stereo using
   sufficient parallax and image overlap; estimate scale and uncertainty.
3. Georegister into the correct Mars planetocentric coordinate system using
   independently validated rover poses or ground controls.
4. Compare reconstructed elevations against existing Gale/HiRISE/CTX DEM where
   coverage overlaps. Mark gaps and uncertainties; never inpaint them as truth.
5. Clearly label rendered mesh or Gaussian splat as **RECONSTRUCTED**, not an
   original NASA panoramic photograph.

No currently implemented module claims to have completed these stages.

## 5. Reviewer checklist

- Open Jezero planner and show **DEM REAL** plus the cyan coverage outline.
- Call `/api/status` and `/api/dem/jezero?size=40` to confirm georeferenced
  numeric elevations (no fake terrain in Jezero mode).
- Compare three EVA profiles and inspect constraints and return calculations.
- Export GeoJSON and inspect `dem_provenance` and
  `model_status: exploratory_not_validated`.
- Open Curiosity 360°, switch HiRISE / CTX / Viking; inspect NASA source links.
- Navigate between documented panoramas using the new station controls.
- Do not promise uninterrupted 360° imagery everywhere along the traverse.
- Be transparent if remote NASA services or tile servers are unavailable.
