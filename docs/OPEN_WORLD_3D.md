# Jezero Open World — scientific architecture and verification

## Status of the implementation

The first exploratory 3D viewer is implemented separately from the pre-existing
EVA planner. **This is an educational prototype, not a certified Mars navigation
system and not yet a fully validated 3D game.** The major missing components are
full-resolution regional streaming, rover-local geometric registration, and
tested high-fidelity global rendering. Gale/Curiosity DEM is **not** loaded in the
Jezero viewer.

### What is actually 3D?

The application creates indexed triangular THREE.BufferGeometry from numerical
Martian elevation samples. Each vertex is positioned in metres according to the
actual DEM grid. It is not a cylindrical panorama or a flat photo. Missing DEM
cells are excluded before any triangle is rendered; coarse LOD quads crossing
a missing source cell are also excluded. A map is only a navigation aid.

First/third-person movement, flight, orbit, top-down camera, simulated Mars
gravity (3.71 m/s² when jumping), ground collision and an optional 25° walking
slope restriction are included. The locomotion speed is **accelerated for
exploration** and must not be treated as realistic EVA walking speed. Collision
samples are interpolated from the raster cells and **cannot detect rocks,
ditches, ledges, or slopes finer than the source resolution**. Vertical scale
is 1:1 (no vertical exaggeration).

Tiles are chunked in 32-cell patches, with decimated level-of-detail 1/2/4
based on distance. Native Three.js frustum culling, GPU buffer disposal,
quality presets, browser resize, and error feedback are provided. This is
regional LOD, **not yet a quadtree with remote tile streaming**.

## Authoritative source inventory

| Product | Source and citation | Native sampling | Use | Limits |
| --- | --- | --- | --- | --- |
| Mars 2020 TRN CTX DTM Mosaic | USGS; DOI [10.5066/P906QQT8](https://doi.org/10.5066/P906QQT8); `JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.tif` | ~20 m/post; 32-bit, 1 band | **Integrated** via `prepare_dem.py` | Interpolated to a 440×440 web grid, not 20-m detail at all locations |
| Mars 2020 TRN CTX Orthorectified Image Mosaic | USGS; DOI [10.5066/P9GV1ND3](https://doi.org/10.5066/P9GV1ND3); `JEZ_ctx_B_soc_008_orthoMosaic_6m_Eqc_latTs0_lon0.tif` | ~6 m/pixel imagery | **Optional** real texture via `prepare_ortho.py` | Does not imply 6-m geometric terrain; may be unavailable or insufficiently covered |
| Mars 2020 HiRISE DTM Mosaic | USGS; DOI [10.5066/P9REJ9JN](https://doi.org/10.5066/P9REJ9JN) | ~1 m/post in supported areas | **Candidate**, not yet integrated | Coverage limited; larger raw downloads |
| Mars Sample Return HiRISE extended mosaics | [USGS 2025 release](https://www.usgs.gov/data/mars-sample-return-hirise-mosaics-terrain-relative-navigation) | Varies by product | Candidate | Research and registration pending |
| Perseverance Navcam, Hazcam, Mastcam-Z operational terrain meshes | NASA PDS: [Navcam](https://pds.nasa.gov/ds-view/pds/viewCollection.jsp?identifier=urn:nasa:pds:mars2020_navcam_ops_mesh:data), [Hazcam](https://pds.nasa.gov/ds-view/pds/viewCollection.jsp?identifier=urn:nasa:pds:mars2020_hazcam_ops_mesh:data), [Mastcam-Z](https://pds.nasa.gov/ds-view/pds/viewCollection.jsp?identifier=urn:nasa:pds:mars2020_mastcamz_ops_mesh:data) | Rover-local, varies | Candidate | Requires PDS label, camera frame, scale, sol, pose and georegistration |
| Curiosity / Gale regional and local DEM | Mission data selection pending | Not selected | **Not loaded** | Never present Jezero geometry as Gale |

USGS 2020 CTX metadata lists footprint 77.1605°–77.699° E and
18.211°–18.7212° N, 20-m raster sampling, planetocentric latitude,
positive-east longitude, 3,396,190-m spherical radius, equirectangular
projection, and metres for vertical units. USGS reports 9.6-m mean
image registration displacement and 3.8-m relative vertical registration
between CTX DTM strips, **not a general absolute altitude error bound**.
See [USGS archival metadata](https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_ctx_dtm_mosaic).
The source data release is CC0 1.0.

The optional orthomosaic is a photogrammetrically orthorectified IMAGE, not
terrain heights. It is reprojected to the *same rectangular Jezero bbox*,
processed with a disclosed 1st–99th percentile display stretch and published
only when >=95% covered. The JPEG is shown only if metadata bbox and official
source URL match the DEM. Otherwise the viewer displays **analytical
hypsometric shading**, explicitly identified as illustrative rather than
NASA imagery.

## Coordinate and fidelity contract

- Geographic DEM input is longitude E / latitude N in degrees, translated
  to a local tangent approximation with Mars radius **3,396,190 metres**.
- X increases east; Z increases south; Y is DEM elevation relative to a
  valid reference sample, without changing vertical scaling. Rendered camera
  positions and collisions are in metres.
- Raster first row is northernmost. Pixel centres are used for georeferencing.
- Bilinear collision/interpolation is used only if all four source samples are
  valid. Neither masking nor LOD may bridge NoData.
- The published JSON has a SHA-256 of the underlying USGS source, recorded by
  the existing reproducible `prepare_dem.py` pipeline and checked by
  `verify_static_dem.py`.
- Elevation is relative to the DTM's declared topographic reference, not
  "height above nearest crater floor" or verified astronaut altitude.
- A 440×440 grid over ~30×30 km has output samples roughly 69 m apart,
  even though the original CTX DEM is ~20 m/post; the viewer must disclose
  both. This first viewer is regional, **not physically detailed every metre**.
- Lighting, sky/fog, color stretches, avatar and speed are interface/render
  choices, not NASA measurements.

## Repeatable local run (Windows 11 PowerShell)

```powershell
git clone https://github.com/Byan1306/Mars-EVA-Navigator.git
cd Mars-EVA-Navigator
git switch feature/jezero-open-world-3d
python -m pip install -r requirements.txt
npm install
python scripts/prepare_dem.py --download ctx --export-json --bbox 77.1605 18.211 77.699 18.7212 --size 440
# Optional, source GeoTIFF may be much larger:
python scripts/prepare_ortho.py --download --dem jezero_dem_precomputed.json
python mars_dem_server.py
```

Open http://127.0.0.1:8000/ to explore. The original EVA planner is at the
link in the header. The viewer tries the verified static JSON first and then
the local `/api/dem/jezero` backend. Missing/unreadable data produce an error
and retry button, **not invented terrain**.

For a portable ZIP/web artifact (after downloading DEM):

```powershell
python scripts/verify_static_dem.py jezero_dem_precomputed.json
python scripts/build_static_site.py --dem jezero_dem_precomputed.json --output _site
```

Upload/zip the generated `_site/` directory; it includes a *locally bundled*
Three.js module. GitHub Actions also publishes a portable build artifact.
GitHub Pages deployment is optional and requires enabling Pages on GitHub.

## Controls and limitations

- Mouse click to capture; ESC to release. WASD moves, Shift speeds up,
  Space jumps (or rises in flight), C crouches (or descends in flight).
- F toggles flight, V toggles first/third person, R restores a valid
  DEM position. Orbital and top views use camera buttons and wheel zoom.
- Minimap click teleports to a valid sampled location. Toggle walking
  slope restriction in the scientific panel.
- The minimap is a measured-height visualization, **not an orbital photo**.
- No claim is made of documented Perseverance positions being present in
  this first visitor-accessible demo. Those require mission pose archives.

### Evidence required before claiming a verified release

1. Python and Node regression test suites succeed.
2. GitHub Actions successfully downloads and checks the authentic USGS DEM.
3. Browser successfully loads the locally bundled Three.js module.
4. Human or automated GPU/WebGL test confirms real triangles, view movement,
   collisions, NoData and controls in a Windows browser.
5. Any optional CTX imagery must pass registration and declared mask tests.
6. A realistic video/screenshot cannot be claimed if GPU browser execution
   was not possible in the verification environment.
7. High-resolution rover mesh integration requires separately verified
   PDS products, registration and pose accuracy.

### Design decision

Three.js was chosen over CesiumJS for the first Jezero patch because it is
lighter to embed in the existing static frontend and permits a Mars-specific
local metric coordinate system without inherited Earth ellipsoid assumptions.
A different planetary global engine can be evaluated separately.
