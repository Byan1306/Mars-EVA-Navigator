# Mars EVA Navigator 🚀

### Every Step Matters

**NASA Space Apps Challenge 2026 | Interplanetary Survival Guide: Martian Map**

**Mars EVA Navigator** is an interactive prototype for planning exploration routes on Mars. It uses actual Martian elevation data to compare possible paths, examine slopes, and explore what could happen during an extravehicular activity (EVA).

We started with a simple question: **How do you choose the best route on a planet you've never walked on?**

We didn't want to build just another map of Mars. We wanted to use NASA's scientific data to help people understand *why* one route might be preferable to another.

## 🎥 Watch the project video

[![Watch Mars EVA Navigator on YouTube](https://img.youtube.com/vi/syIeHq7CK50/hqdefault.jpg)](https://youtu.be/syIeHq7CK50)

**[Watch our Mars EVA Navigator presentation](https://youtu.be/syIeHq7CK50)**

## What does it do?

- **Compare three route options:** green (safety-oriented), blue (balanced), and red (speed-oriented).
- **Use real elevations:** a Jezero Crater digital elevation model (DEM) supplies terrain heights to the route planner.
- **Explore the surface:** interactive maps and a 3D terrain view provide geographical context.
- **Consider emergencies:** simulate return-route planning when a mission does not go as expected.
- **Discover scientific context:** explore points of interest, Mars missions, and rover imagery.

The project is a **hackathon prototype**, not a certified system for astronaut navigation or safety.

## Why it matters

On Mars, the shortest route is not necessarily the safest or most useful. The terrain might be steep, information could be missing, or another route might make more sense for a particular mission. Our goal is to make those differences visible and help people think about the trade-offs before choosing where to go.

With further validation, the same approach could eventually help research and planning for exploration of Mars and other worlds.

## NASA resources

| Resource | Purpose |
| --- | --- |
| [HiRISE Digital Terrain Models](https://hirise.lpl.arizona.edu/dtm/) | Elevation data for Jezero terrain analysis and route planning. |
| [NASA Mars Trek](https://trek.nasa.gov/mars/) | Martian mapping and geographical context. |
| [NASA Perseverance images](https://mars.nasa.gov/mars2020/multimedia/raw-images/) | Mission imagery and context for Jezero Crater. |
| [NASA Curiosity images](https://mars.nasa.gov/msl/multimedia/raw-images/) | Additional imagery from the surface of Mars. |

Our local terrain service reads a compatible **GeoTIFF DEM** and produces elevation grids with geographic bounds, coverage, and cell-size information.

**The large GeoTIFF is not in this repository.** A compatible Jezero dataset must be obtained separately from its original source.

## Technologies

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python, FastAPI, Uvicorn
- **Terrain processing:** Rasterio, NumPy, pyproj
- **Local catalog:** SQLite
- **HTTP:** httpx
- **Optional integration:** Meteomatics for Earth-weather analog information when configured. This is not real-time Martian weather.

Python dependencies are specified in [requirements.txt](requirements.txt).

## Run locally

### 1. Download the code and install Python dependencies

Python 3.12 or another compatible Python version is recommended.

```powershell
git clone https://github.com/Byan1306/Mars-EVA-Navigator.git
cd Mars-EVA-Navigator
python -m pip install -r requirements.txt
```

### 2. Download and configure the real Jezero CTX DEM

The checked-in `jezero_dem_precomputed.json` contains a real USGS CTX crop for the static app. For the Python backend, download and validate the native 20 m/pixel product and set its path in PowerShell:

```powershell
python scripts/prepare_dem.py --download ctx --export-json
$env:MARS_DEM_PATH = (Resolve-Path ./jezero_ctx_dtm_20m.tif).Path
```

On Bash, use `export MARS_DEM_PATH="$PWD/jezero_ctx_dtm_20m.tif"`. [.env.example](.env.example) documents the same setting; Python does not automatically load dotenv files. Keep the downloaded `.tif.provenance.json` next to the GeoTIFF. The downloader first tries the requested USGS host, then the public mirror linked by USGS, and pins the reviewed CTX SHA-256.

### 3. Start the server

```powershell
python mars_dem_server.py
```

### 4. Open Mars EVA Navigator

Open **http://127.0.0.1:8000/** in your browser. Keep PowerShell running while using the application.

You can also check:

- [Server status](http://127.0.0.1:8000/api/status)
- [Processed elevation grid](http://127.0.0.1:8000/api/dem/jezero?size=40)

`/api/status` now validates the raster, scans its physical elevations, checks provenance when present and processes a grid. Check both `dem_validated` and `provenance_verified`; an arbitrary local file is not labelled as verified USGS data.

## Static GitHub Pages deployment

The root [index.html](index.html) redirects to the interactive application. GitHub Pages serves the frontend only; it does not execute the Python backend. A real terrain-dependent route requires a loaded Mars DEM. The app does not substitute invented heights when DEM coverage is unavailable.

The existing science-release workflow builds a separate 440×440 regional export for deployment. Enable **Settings → Pages → Source: GitHub Actions**; see the release workflow and `docs/SCIENTIFIC_EVIDENCE.md`. The checked-in 220×220 study crop remains available for direct static hosting and regression tests.

## Mission GENESIS — verified science release

The project now includes a **repeatable USGS Jezero DEM deployment pipeline** and
**immersive navigation between documented Curiosity photo stations**. The original
2D EVA planner, three route profiles, NASA Mars Trek maps, evidence panels,
emergency-return models and local DEM backend remain intact.

- **Scientifically sourced:** download the official USGS Mars 2020 CTX DTM
  (20 m/pixel) or its public PDS S3 mirror and retain SHA-256/provenance.
- **Public site:** automatically build a reviewed Jezero 440×440 precomputed
  elevation JSON (real DEM, coarser resampling) and deploy with GitHub Actions.
- **Curiosity viewer:** Next/Previous documented panoramas, keyboard arrows and
  full screen, with explicit labeling of gaps between photographic stations.
- **Scientific exports:** GeoJSON includes the source DEM identity, original
  source resolution, checksum when available, validity fraction and limitations.
- **Safety:** invalid/missing DEM is reported, never replaced silently with
  fabricated elevations for Jezero mission.

**Portable fallback if GitHub Pages has not been enabled:** open the most recent
**Publish Mars EVA Navigator with verified Jezero DEM** workflow in Actions,
download the `mars-eva-verified-web-demo` artifact from its Artifacts section
and extract the ZIP. From the extracted directory run `python -m http.server
8080`, then open `http://127.0.0.1:8080/`. The package contains the authentic
validated DEM JSON; map tiles and NASA imagery still require Internet access.

**One-time site setup:** repository **Settings → Pages → Source → GitHub Actions**.
The workflow `Publish Mars EVA Navigator with verified Jezero DEM` downloads
and validates data before publishing. Do not claim the Pages release has real
terrain until this workflow completes successfully. No credentials are needed
for the public USGS CTX data.

See [Scientific evidence, limitations, deployment and demo checklist](docs/SCIENTIFIC_EVIDENCE.md).

### Reproducible Jezero elevations

After installing Python dependencies, obtain a suitable Jezero GeoTIFF from the official USGS Mars 2020 mapping products (CTX or HiRISE). The repository does not include these large source datasets.

```powershell
# Use a previously downloaded Mars GeoTIFF (recommended for reliable sourcing)
python scripts/prepare_dem.py --input 'C:\path\to\jezero_dem.tif' --export-json

# Alternatively request a USGS CTX product automatically (remote URL may change)
python scripts/prepare_dem.py --download ctx --export-json
```

The utility validates the Martian CRS and exports `jezero_dem_precomputed.json` from **actual sampled elevations** using the Python DEM endpoint's processing logic. The committed 220×220 crop covers 77.390–77.475°E, 18.425–18.475°N, with 48,400 valid heights and retained USGS/NASA attribution. NoData is represented as JSON `null`, never a fabricated zero or filled plateau. Cropped static data cannot claim the full GeoTIFF's coverage.

The original CTX spacing is **20×20 m in the map projection**. The static grid samples approximately **21.72×13.47 m on the Mars sphere**; interpolation does not create finer scientific detail. For the local backend, set `MARS_DEM_PATH` and run `python mars_dem_server.py`. See [Jezero DEM validation, sources and HiRISE evaluation](docs/jezero-dem.md) and the [recorded HTTP verification](docs/jezero-dem-verification.json).

With the server running, independently compare the HTTP result with native GeoTIFF pixels and the static export:

```sh
python scripts/verify_dem.py
```

## Automated regression tests

Isolated error/NoData tests use tiny **synthetic test-only rasters** in temporary directories. The JavaScript routing suite also loads the committed **real CTX export**, runs the actual EVA planner and makes any procedural terrain call fail the test. An optional Python integration test reads the downloaded real source. Test fixtures are never installed as application data.

```powershell
python -m unittest discover -s tests -v
node --test tests/*.test.cjs
# Optional real GeoTIFF test (PowerShell)
$env:MARS_DEM_TEST_PATH = (Resolve-Path ./jezero_ctx_dtm_20m.tif).Path
python -m unittest discover -s tests -v
```

[GitHub Actions](.github/workflows/verify.yml) runs tests on pushes and pull requests. Passing these checks does not certify EVA safety.

## Licensing

See [LICENSE](LICENSE). The repository is public but not open-source licensed; rights for third-party imagery, terrain datasets, dependencies and other external materials remain with their respective owners.

## Repository files

| File | Description |
| --- | --- |
| `mars_eva_navigator_guia_de_supervivencia_interplanetaria_nasa_space_apps_2026.html` | Main interactive app |
| `mars_dem_server.py` | Backend server and terrain API |
| `catalog_store.py` | Local mission-evidence catalog logic |
| `catalog.sqlite` | Included local catalog database |
| `requirements.txt` | Python packages needed to run the backend |
| `index.html` | Static GitHub Pages entry point |
| `scripts/prepare_dem.py` | Local official DEM preparation/export |
| `tests/test_project.py` | Regression tests |
| `.github/workflows/verify.yml` | Automated verification |
| `LICENSE` | Copyright notice |
| `curiosity_explorer.js` | Curiosity timeline, full track loader, NASA photo viewer |
| `curiosity_explorer.css` | Responsive mission explorer styles |
| `tests/curiosity.test.cjs` | JavaScript and mission-data regression tests |
| `curiosity_pro.css` | Mission-control visual redesign |
| `curiosity_360_renderer.js` | WebGL cylindrical panorama projection |
| `scripts/stitch_curiosity_panorama.py` | Optional OpenCV real-photography stitch tool |
| `tests/curiosity-mission-control.test.cjs` | High-resolution map and NASA photo archive tests |

The local catalog database is included. If that database is removed, the server may require a separate `catalog_seed.json` file to rebuild the catalog; that seed file is not currently published in this repository.

## Curiosity Mission Explorer — full historical traverse and 360° panoramas

Choose **Ruta Curiosity · 360°** in the top navigation. This independent view does not change Jezero EVA simulation data or replace them with Curiosity's route.

- **Entire available rover track:** the browser loads the [Curiosity traverse compilation](https://azmth.space/data/mars-traverses/curiosity.json), based on NASA/JPL-Caltech MMGIS MSL traverse and waypoint layers. The geometrical path has more than 20,000 vertices as of November 2026. The dataset is fetched at runtime and is *not* copied into this repository.
- **Time controls:** scrub by Mars sol, jump to a sol, replay the historic route, inspect locations, and fit all published geometry.
- **NASA panorama gallery:** ten curated, NASA-documented 360° horizontal panoramas (Navcam and Mastcam) spanning the 2012–2026 mission. Where a resized image is available, you can pan and zoom it locally. Very large panoramas link to NASA without automatically loading gigabytes of image data.
- **Inspect/export:** each selected sol links to NASA's raw-image index, and the route can be exported as GeoJSON with its source/limitations.
- **Offline or blocked sources:** if the full traverse cannot be fetched, the UI attempts to load the [NASA MMGIS waypoint dataset](https://mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json). These waypoints are connected with a **dashed approximation**—NOT falsely presented as exact wheel tracks. If neither source can be obtained, the UI displays an error and **does not draw fictional history**.

### Scientific provenance and limitations

**NASA/JPL-Caltech** owns the mission geometry; [azmth.space](https://azmth.space/mars/data) distributes its compilation under **CC BY 4.0**. The original NASA MMGIS traverse has no per-vertex time labels; the compiler assigns exact sols to NASA waypoints and interpolates between them. Panoramas are associated with the path by documented **sol**, not independently verified camera coordinates. The rendered path is not a certified EVA route. The redesigned Curiosity viewer now uses actual NASA HiRISE/CTX mosaics where each has coverage, backed by the coarse Viking global mosaic. The displayed geometric trail length is not NASA rover odometry.

All panoramas link to NASA Science original resource pages and retain NASA/JPL-Caltech camera credits. Images are fetched as needed rather than bundled, and third-party rights remain unchanged.

Verification: `node --test tests/curiosity.test.cjs` and `node --check curiosity_explorer.js`, in addition to the existing Python tests.

## Curiosity Mission Control — high-resolution Gale imagery and NASA photo explorer

The Curiosity tab is now a **map-first mission control** with a redesigned interface. It layers three official [NASA Mars Trek WMTS](https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=mars) products: 

- **HiRISE rover-site mosaic:** `curiosity_hirise_mosaic` — highest-detail NASA Trek product available for the original roving-site mosaic footprint (roughly 137.122–137.730°E, 4.925–4.249°S).
- **MRO CTX Gale crater mosaic:** `Gale_CTX_BlockAdj_dd` — wider regional coverage (roughly 135.184–139.241°E, 6.573–2.808°S), visible under HiRISE or as a standalone choice.
- **Viking global mosaic:** fallback outside regional coverage; its native resolution is about 232 m/pixel and should never be mistaken for a sharp local orbiter view.

The map is rendered with actual NASA WMTS tiles rather than upscaled screenshots. WMTS availability, coverage and maximum *native* zoom depend on the server and are not guaranteed to match this app's zoom level. High-resolution tiles are not universally available for all Mars coordinates. See [USGS 25 cm/pixel Gale mosaic](https://astrogeology.usgs.gov/search/map/mars_msl_gale_merged_orthophoto_mosaic_25cm) (23 GB lossless scientific source, **not embedded or served from the browser**).

### NASA original-image browser

For any selected mission sol, choose a camera and click **Cargar fotos reales**. The app queries the [NASA Mars Curiosity raw image API](https://mars.nasa.gov/msl/multimedia/raw-images/), 24 results per page, and shows original image links. NASA currently lists hundreds of thousands of Curiosity frames. If the API or image host blocks a browser request, the direct NASA archive link remains available; an API outage is not shown as an empty scientific record.

Individual photos are **not** classified as 360 panoramas. Published, documented cylindrical NASA panoramas also have a 360° horizontal WebGL perspective mode. This is a projection of genuine NASA panoramic pixels, not generated 3D geometry or a 360×180 spherical recording. WebGL2 and image-host CORS are needed; otherwise the accessible draggable image view remains.

### Experimental stitching of multiple NASA photos

Download a small set (3–30) of **original overlapping frames from the same stationary camera sequence and sol**, preserving the NASA URL, source camera and timestamp for each. To attempt a panorama locally:

```powershell
python -m pip install opencv-python-headless
python scripts/stitch_curiosity_panorama.py --input-dir .\raw_nasa_frames --sol 4287 --output curiosity_panorama_experimental.jpg
```

Open the Curiosity tab, under **Laboratorio fotográfico** select the new JPEG. It will display locally, and if its aspect ratio allows it can be explored as a cylinder. Successful stitching depends on the images having sufficient matching features and camera overlap. A single day often contains photos from **several locations and camera directions**, so selecting the same sol alone does not guarantee a coherent panorama. The generated `.provenance.json` includes SHA-256 hashes and explicitly marks full 360° coverage, camera geolocation, and 3D depth as **unverified**; add each photo's original official NASA URL before publishing.

**This release is not a continuous Mars Street View.** No verified complete 360° spherical image exists for every point along Curiosity's driven route. Building an interpolated free-roam 3D environment would require a separate photogrammetry/NeRF/3D Gaussian Splatting pipeline with camera calibration, pose estimation, a DEM, provenance, error estimates and explicit labels for reconstructed or missing areas.

### Verification

```powershell
node --check curiosity_explorer.js
node --check curiosity_360_renderer.js
node --test tests/curiosity.test.cjs tests/curiosity-mission-control.test.cjs
python -m unittest discover -s tests -v
```

All photos and map tiles are loaded on demand and are not redistributed as part of the source repository. Original data and image use/attribution terms apply.

## Scientific limitations

Our planner works with real topography, but the routes are **not guaranteed safe**. A high-resolution DEM can be resampled to a much coarser planning grid, leaving smaller hazards unresolved. Missing coverage, environmental risks, and operational constraints also need more testing. The three colors represent experimental route priorities, not certified safety levels.

## Team and responsible AI use

Built by **Ronald López and Brayan Barrera** for **NASA Space Apps Challenge 2026**.

We used ChatGPT as a development assistant for coding, debugging, interface improvements, research, and documentation. Our team directed the project, connected the terrain data, and tested the prototype. AI assistance does not substitute for scientific verification.

## Acknowledgments

Thanks to NASA and the teams behind HiRISE, Mars Trek, Perseverance, and Curiosity for making planetary science information accessible. External data, images, and software remain subject to their original terms and licenses.

---

**We don't just want to see Mars. We want to understand how to explore it.**
