#!/usr/bin/env python3
"""Download an official Jezero DEM and optionally export a real-elevation JSON.

No synthetic elevations are generated. Source GeoTIFF files remain local; a small
precomputed JSON can be published on a static site after scientific review.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# NASA Mars 2020 Terrain Relative Navigation products published by USGS Astrogeology.
# CTX: 20 m/pixel; HiRISE: 1 m/pixel (about 1.8 GB).
USGS_DATASETS = {
    "ctx": {
        "file": "jezero_ctx_dtm_20m.tif",
        "url": "https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.tif",
        "sha256": "16a1aa66c3f48c1bca252795827db7b417876217aff0f5e1aff18027fab2327b",
        "resolution_m": 20,
        "doi": "https://doi.org/10.5066/P906QQT8",
    },
    "hirise": {
        "file": "jezero_hirise_dtm_1m.tif",
        "url": "https://planetarymaps.usgs.gov/mosaic/mars2020_trn/HiRISE/JEZ_hirise_soc_006_DTM_MOLAtopography_DeltaGeoid_1m_Eqc_latTs0_lon0_blend40.tif",
        "resolution_m": 1,
        "doi": "https://doi.org/10.5066/P9REJ9JN",
    },
}

# These public mirrors are linked by the corresponding USGS product pages.
# Keep the canonical URL as scientific provenance, and record the retrieval URL.
for product, info in USGS_DATASETS.items():
    info["mirror"] = info["url"].replace(
        "https://planetarymaps.usgs.gov/",
        "https://asc-pds-services.s3.us-west-2.amazonaws.com/",
    )
    info["product_page"] = (
        "https://astrogeology.usgs.gov/search/map/"
        f"mars_2020_terrain_relative_navigation_{product}_dtm_mosaic"
    )


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    try:
        with partial.open("w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            out.write("\n")
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


def check_product(path: Path, source: str) -> str:
    """Validate bytes and raster before installing a downloaded product."""
    info = USGS_DATASETS[source]
    digest = sha256_file(path)
    if info.get("sha256") and digest != info["sha256"]:
        raise ValueError("CTX SHA-256 does not match the reviewed USGS product; refusing replacement.")
    validate_dataset(path)
    import rasterio
    with rasterio.open(path) as src:
        if not src.crs.is_projected or any(abs(r - info["resolution_m"]) > 1e-6 for r in src.res):
            raise ValueError("The downloaded product does not have its documented native resolution.")
    return digest

# Small Jezero exploration area surrounding the app's default origin/destination.
# Box order: western lon, southern lat, eastern lon, northern lat.
DEFAULT_BBOX = (77.390, 18.425, 77.475, 18.475)


def download_dataset(source: str, destination: Path) -> Path:
    info = USGS_DATASETS[source]
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        check_product(destination, source)
        print(f"Using existing file: {destination}")
        return destination
    partial = destination.with_suffix(destination.suffix + ".part")
    failures = []
    for url in (info["url"], info["mirror"]):
        print(f"Downloading official USGS {source.upper()} DEM from:\n{url}")
        request = Request(url, headers={"User-Agent": "Mars-EVA-Navigator/2026"})
        try:
            with urlopen(request, timeout=90) as response, partial.open("wb") as out:
                total = response.headers.get("Content-Length")
                expected = int(total) if total and total.isdigit() else None
                received = 0
                while chunk := response.read(2 * 1024 * 1024):
                    out.write(chunk)
                    received += len(chunk)
                if expected is not None and received != expected:
                    raise OSError(f"Download incomplete: got {received} of {expected} bytes")
            digest = check_product(partial, source)
            manifest = {
                "source_product": f"usgs_{source}", "source_url": info["url"],
                "retrieved_url": url, "product_page": info["product_page"], "doi": info["doi"],
                "sha256": digest, "downloaded_at": datetime.now(timezone.utc).isoformat(),
                "attribution": "USGS Astrogeology Science Center; NASA/JPL-Caltech/MSSS (CTX); NASA/JPL-Caltech/University of Arizona (HiRISE)",
                "authors": "R. L. Fergason, D. M. Galuszka, T. M. Hare, D. M. Mayer, B. L. Redding, E. D. Smith (2020)",
                "native_resolution_m": info["resolution_m"],
                "vertical_reference": "USGS MOLA topography / DeltaGeoid product; heights in metres, not Earth sea level",
                "checksum_note": "Locally calculated SHA-256 of official downloaded bytes; not a publisher signature",
            }
            partial.replace(destination)
            write_json_atomic(Path(str(destination) + ".provenance.json"), manifest)
            break
        except (HTTPError, URLError, OSError) as exc:
            if isinstance(exc, HTTPError):
                detail = f"HTTP {exc.code}: {exc.read(512).decode('utf-8', errors='replace').strip()}"
            else:
                detail = str(exc)
            failure = f"{urlparse(url).hostname}: {detail}"
            failures.append(failure)
            print(f"Download failed: {failure}", file=sys.stderr)
        finally:
            partial.unlink(missing_ok=True)
    else:
        raise OSError("Official DEM download failed. " + " | ".join(failures))
    print(f"Downloaded: {destination} ({destination.stat().st_size / 1024**2:.1f} MiB)")
    return destination


def validate_dataset(path: Path) -> None:
    import rasterio
    from mars_dem_server import bounds_marcianos, validar_raster
    with rasterio.open(path) as src:
        validar_raster(src)
        bbox = bounds_marcianos(src)
        print(f"Validated Mars DEM: {src.width} x {src.height}; lon/lat bounds {bbox}")


def export_json(path: Path, output: Path, bbox: tuple, size: int) -> None:
    from mars_dem_server import obtener_dem
    # Call the same validated raster-processing code that the live API uses.
    previous = os.environ.get("MARS_DEM_PATH")
    os.environ["MARS_DEM_PATH"] = str(path.resolve())
    try:
        data = obtener_dem(
            min_lon=bbox[0], min_lat=bbox[1],
            max_lon=bbox[2], max_lat=bbox[3], size=size,
        )
    finally:
        if previous is None:
            os.environ.pop("MARS_DEM_PATH", None)
        else:
            os.environ["MARS_DEM_PATH"] = previous
    if any(abs(actual - wanted) > 1e-8 for actual, wanted in zip(data['bbox'], bbox)):
        raise ValueError("The DEM does not cover the complete study bbox; no partial export was published.")
    write_json_atomic(output, data)
    print(f"Real DEM export: {output} ({len(data['elevations'])} cells, "
          f"{data['valid_fraction'] * 100:.1f}% valid)")
    print("Review the source/bounds/resolution before committing the JSON to a public site.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--download", choices=sorted(USGS_DATASETS), help="USGS DEM to download")
    inputs.add_argument("--input", type=Path, help="Existing Mars DEM GeoTIFF")
    parser.add_argument("--export-json", action="store_true",
                        help="Generate real elevations for the static GitHub Pages app")
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"),
                        default=DEFAULT_BBOX, help="Desired Mars lon/lat window")
    parser.add_argument("--size", type=int, default=220, help="Grid cells per side (40–440)")
    parser.add_argument("--output", type=Path, default=ROOT / "jezero_dem_precomputed.json")
    args = parser.parse_args()
    if not 40 <= args.size <= 440:
        parser.error("--size must be between 40 and 440")
    w, s, e, n = args.bbox
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        parser.error("--bbox must be valid west south east north bounds")

    if args.download:
        info = USGS_DATASETS[args.download]
        path = download_dataset(args.download, ROOT / info["file"])
    else:
        path = args.input.expanduser().resolve()
    if not path.is_file():
        parser.error(f"Missing DEM file: {path}")

    validate_dataset(path)
    print(f"PowerShell for the live server:\n$env:MARS_DEM_PATH = '{path.resolve()}'")
    print(f"Bash for the live server:\nexport MARS_DEM_PATH='{path.resolve()}'")
    if args.export_json:
        export_json(path, args.output, tuple(args.bbox), args.size)
    else:
        print("To enable GitHub Pages with real elevations, repeat with --export-json.")


if __name__ == "__main__":
    main()
