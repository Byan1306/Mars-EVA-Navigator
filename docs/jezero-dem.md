# Jezero: real CTX DEM integration

The static app includes `jezero_dem_precomputed.json`, derived from the official USGS CTX Mars 2020 Terrain Relative Navigation product. The local Python backend uses the downloaded GeoTIFF through `MARS_DEM_PATH`. No synthetic elevation raster is installed. Jezero routing stops when coverage is missing, and NoData cells remain impassable.

## Source and attribution

- [USGS CTX product page](https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_ctx_dtm_mosaic), [DOI 10.5066/P906QQT8](https://doi.org/10.5066/P906QQT8).
- [Original GeoTIFF requested](https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.tif).
- [Official public mirror linked by USGS](https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/mars2020_trn/CTX/index.html); same product filename and path, downloaded over verified HTTPS.
- USGS Astrogeology Science Center; NASA/JPL-Caltech/MSSS (CTX); NASA/JPL-Caltech/University of Arizona (HiRISE). Product authors: R. L. Fergason, D. M. Galuszka, T. M. Hare, D. M. Mayer, B. L. Redding and E. D. Smith (2020). Third-party data terms remain applicable; the repository's code license does not replace them.

The original `planetarymaps.usgs.gov` request returned **HTTP 403**, body `Your request was blocked.`, with Cloudflare response markers. The environment reported an enforced **unrestricted HTTP** policy. The exact upstream blocking rule was not disclosed; there is no evidence of an environment domain-allowlist denial. The USGS-linked `asc-pds-services.s3.us-west-2.amazonaws.com` mirror returned **HTTP 200** and the complete 9,662,387-byte GeoTIFF. No TLS checks or access controls were disabled.

Observed CTX SHA-256 (pinned in downloader and backend):

```text
16a1aa66c3f48c1bca252795827db7b417876217aff0f5e1aff18027fab2327b
```

This is a locally computed checksum of the official download, not a publisher signature. The adjacent `.tif.provenance.json` records canonical URL, actual retrieval URL, hash, download time, citation and attribution. A manually supplied compatible raster without this manifest remains explicitly unverified. Reusing an existing file does not invent download history.

## Measured dataset and output

| Property | Verified value |
| --- | --- |
| Native raster | GeoTIFF, one `float32` band, 1596 × 1512 pixels |
| CRS | Equirectangular Mars 2000 Sphere IAU, radius 3,396,190 m; standard parallel 0°, central meridian 0° |
| Native spacing | 20 × 20 m in projection; about 18.97 × 20 m ground spacing near the study area |
| Full extent (W,S,E,N) | 77.1604654592, 18.2110273910, 77.6989751663, 18.7211944819 degrees |
| Native valid heights | 2,413,152; −2710.6958 to −1515.5396 m |
| Native NoData sentinel | −3.4028226550889045e38; no invalid native cells in this CTX product |
| Export study area (W,S,E,N) | 77.390, 18.425, 77.475, 18.475 degrees; fully inside coverage |
| Export | 220 × 220, 48,400 valid cells, 0 NoData; −2611.7813 to −2441.7583 m |
| Export sampling | 21.72445 × 13.47152 m on the Mars sphere; bilinear resampling |

The product name retains `MOLAtopography_DeltaGeoid`. Elevations are in metres according to the source documentation; the TIFF does not set a band-unit tag, so the API preserves `units_assumed: true`. The software does not derive a vertical datum from the horizontal CRS, transform these heights to Earth sea level, or claim an independently verified vertical accuracy.

The 13.47 m north–south grid spacing is **upsampling of a 20 m product**, not new 13.47 m observations. Planning grids may resample it again. The interface distinguishes native resolution, loaded sampling and route-grid spacing. None establishes the absence of smaller obstacles.

JSON uses longitude/latitude in degrees on the Mars sphere, area-registered pixels, row-major north-to-south storage and explicit `grid_transform`. Pixel centres are `(W+(column+0.5)*(E-W)/width, N-(row+0.5)*(N-S)/height)`. NoData becomes `null`; masked cells are not filled or traversed. Entirely invalid rasters, undeclared invalid heights, incompatible CRS/units and invalid provenance are rejected.

## Reproduce and verify

```sh
python -m pip install -r requirements.txt
python scripts/prepare_dem.py --download ctx --export-json
export MARS_DEM_PATH="$PWD/jezero_ctx_dtm_20m.tif"
python mars_dem_server.py
```

In another terminal:

```sh
python scripts/verify_dem.py --report docs/jezero-dem-verification.json
MARS_DEM_TEST_PATH="$PWD/jezero_ctx_dtm_20m.tif" python -m unittest discover -s tests -v
node --test tests/*.test.cjs
```

PowerShell: use `$env:MARS_DEM_PATH = (Resolve-Path ./jezero_ctx_dtm_20m.tif).Path` and the equivalent assignment for `MARS_DEM_TEST_PATH`. `.env.example` is a configuration template; the server does not read it implicitly.

Recorded validation: `/api/status` and the study-area `/api/dem/jezero` both returned HTTP 200; `dem_validated` and `provenance_verified` were true. The HTTP crop equals the static JSON. A separate 40×40 crop aligned to native pixels matches **all 1,600 independently read native heights exactly (0 m maximum error)**. An out-of-coverage request returns 422, and the raw TIFF is not publicly served. See [machine-readable evidence](jezero-dem-verification.json).

The JavaScript tests execute the actual application's sampler, grid builder and EVA path planner. They verify route elevations equal loaded DEM cells, height changes affect route elevations, and NoData/steep barriers reject paths. The real CTX default mission produces an executable route while the procedural terrain generator is replaced with a function that throws. DOM/map rendering is stubbed in these numerical tests; they do not certify astronaut safety.

## HiRISE evaluation

[USGS HiRISE product](https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_hirise_dtm_mosaic), [DOI 10.5066/P9REJ9JN](https://doi.org/10.5066/P9REJ9JN), and [official mirror index](https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/mars2020_trn/HiRISE/index.html) identify a 1 m/pixel, one-band float32 mosaic of 21,400 × 21,488 pixels (1,839,545,409 bytes). The published extent is approximately 77.2229–77.5840°E, 18.3068–18.6693°N, containing the study rectangle.

Product metadata, HTTP HEAD and the TIFF header were inspected. The attempted bounded native-pixel coverage audit then failed with HTTP 503 from the mirror/proxy path (`upstream connect error ... remote connection failure`). The exact failing upstream component was not identified. **Complete valid-mask coverage was not verified; HiRISE is not enabled or blended into this release.** Being inside the rectangular extent does not prove valid elevation coverage.

Next integration should download or tile the real HiRISE data, validate its masks and vertical registration against CTX, then select HiRISE only where valid. Preserve CTX elsewhere with explicit per-cell/source provenance, and assess transitions across mosaic seams. USGS describes a median vertical offset of roughly 0.4 m between HiRISE and CTX; this is not a claim of absolute vertical accuracy. A 220×220 grid spanning the full study area would still sample about 13–22 m, so it cannot be marketed as a 1 m route grid. CTX remains the verified baseline.
