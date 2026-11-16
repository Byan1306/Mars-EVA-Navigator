#!/usr/bin/env python3
"""Download an official Jezero DEM and optionally export a real-elevation JSON.

No synthetic elevations are generated. Source GeoTIFF files remain local; a small
precomputed JSON can be published on a static site after scientific review.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# NASA Mars 2020 Terrain Relative Navigation products published by USGS Astrogeology.
# CTX: 20 m/pixel; HiRISE: 1 m/pixel (about 1.8 GB).
USGS_DATASETS = {
    "ctx": {
        "file": "jezero_ctx_dtm_20m.tif",
        "url": "https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.tif",
    },
    "hirise": {
        "file": "jezero_hirise_dtm_1m.tif",
        "url": "https://planetarymaps.usgs.gov/mosaic/mars2020_trn/HiRISE/JEZ_hirise_soc_006_DTM_MOLAtopography_DeltaGeoid_1m_Eqc_latTs0_lon0_blend40.tif",
    },
}

# Small Jezero exploration area surrounding the app's default origin/destination.
# Box order: western lon, southern lat, eastern lon, northern lat.
DEFAULT_BBOX = (77.390, 18.425, 77.475, 18.475)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(2 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_dataset(source: str, destination: Path) -> Path:
    """Official USGS host first; use its public PDS S3 mirror after HTTP blocking."""
    info = USGS_DATASETS[source]
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        print(f"Using existing file: {destination}")
        return destination
    partial = destination.with_suffix(destination.suffix + ".part")
    mirror = info["url"].replace(
        "https://planetarymaps.usgs.gov/",
        "https://asc-pds-services.s3.us-west-2.amazonaws.com/",
        1,
    )
    attempts = [info["url"], mirror]
    errors = []
    for url in attempts:
        print(f"Requesting official USGS {source.upper()} DEM: {url}")
        request = Request(url, headers={"User-Agent": "Mars-EVA-Navigator/2026"})
        try:
            with urlopen(request, timeout=90) as response, partial.open("wb") as out:
                total = response.headers.get("Content-Length")
                expected = int(total) if total and total.isdigit() else None
                received = 0
                while True:
                    chunk = response.read(2 * 1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    received += len(chunk)
                if expected is not None and received != expected:
                    raise OSError(f"Incomplete download: {received} of {expected} bytes")
            if partial.stat().st_size < 1024:
                raise OSError("Download is too small to be a valid GeoTIFF.")
            partial.replace(destination)
            provenance = {
                "dataset": source,
                "origin_url": info["url"],
                "download_url": url,
                "sha256": sha256_file(destination),
                "size_bytes": destination.stat().st_size,
                "source_institution": "USGS Astrogeology Science Center",
            }
            destination.with_suffix(destination.suffix + ".provenance.json").write_text(
                json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
            )
            print(f"Downloaded: {destination} ({destination.stat().st_size / 1024**2:.1f} MiB)")
            return destination
        except (OSError, TimeoutError, ValueError) as exc:
            partial.unlink(missing_ok=True)
            errors.append(f"{url}: {exc}")
            print(f"Source unavailable: {exc}")
    raise OSError("Could not download a real DEM.\n" + "\n".join(errors))

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
    provenance_path = path.with_suffix(path.suffix + ".provenance.json")
    if provenance_path.is_file():
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        if provenance.get("sha256") != sha256_file(path):
            raise ValueError("DEM checksum differs from recorded USGS download.")
        data["source_url"] = provenance["origin_url"]
        data["download_url"] = provenance["download_url"]
        data["source_sha256"] = provenance["sha256"]
        data["source_institution"] = provenance["source_institution"]
    else:
        data["source_url"] = None
        data["source_institution"] = "Not independently verified; inspect this input GeoTIFF."
    data["scientific_limitations"] = (
        "Measured surface heights resampled to a grid; not rover-verified walking "
        "safety, real-time weather, or subcell obstacle detection."
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".part")
    try:
        with partial.open("w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)
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
    if args.export_json:
        export_json(path, args.output, tuple(args.bbox), args.size)
    else:
        print("To enable GitHub Pages with real elevations, repeat with --export-json.")


if __name__ == "__main__":
    main()
