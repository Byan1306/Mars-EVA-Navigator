#!/usr/bin/env python3
"""Prepare an optional, georeferenced CTX orthoimage matching a verified Jezero DEM.

The source is the genuine USGS Mars 2020 CTX orthomosaic (~6 m/pixel).
This script *never* generates texture from synthetic data or fills missing pixels.
The image is for visualization, not centimeter-scale terrain measurement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image
import rasterio
from rasterio.transform import from_bounds
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from pyproj import CRS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mars_dem_server import MARS_LONLAT_CRS
try:
    from scripts.verify_static_dem import verify
except ImportError:
    from verify_static_dem import verify

BASE_URL = "https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/"
PRODUCT = "JEZ_ctx_B_soc_008_orthoMosaic_6m_Eqc_latTs0_lon0.tif"
SOURCE_URL = BASE_URL + PRODUCT
MIRROR_URL = "https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/mars2020_trn/CTX/" + PRODUCT


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(2 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(destination: Path) -> Path:
    if destination.is_file() and destination.stat().st_size > 1024:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(".part")
    failures = []
    for address in (SOURCE_URL, MIRROR_URL):
        try:
            with urlopen(Request(address, headers={"User-Agent": "Mars-EVA-Navigator/2026"}),
                         timeout=120) as stream, partial.open("wb") as out:
                while True:
                    block = stream.read(2 * 1024 * 1024)
                    if not block:
                        break
                    out.write(block)
            if partial.stat().st_size < 1024:
                raise ValueError("El archivo no parece un GeoTIFF.")
            partial.replace(destination)
            return destination
        except (OSError, TimeoutError, ValueError) as exc:
            failures.append(f"{address}: {exc}")
            partial.unlink(missing_ok=True)
    raise OSError("Ortofoto USGS no disponible. " + " | ".join(failures))


def generate(source: Path, dem_file: Path, output: Path, size: int = 2048) -> dict:
    """Output JPEG + metadata only when source and Jezero bbox are georegistered."""
    verify(dem_file)
    meta = json.loads(dem_file.read_text(encoding="utf-8"))
    bbox = meta["bbox"]
    if not (256 <= size <= 4096):
        raise ValueError("Image size must be 256–4096.")
    with rasterio.open(source) as src:
        if src.crs is None or src.count < 1:
            raise ValueError("Fuente sin CRS o imagen.")
        radius = CRS.from_wkt(src.crs.to_wkt()).ellipsoid.semi_major_metre
        if not (3_300_000 < radius < 3_500_000):
            raise ValueError("La imagen no tiene sistema de coordenadas marciano.")
        transform = from_bounds(*bbox, size, size)
        with WarpedVRT(src, crs=MARS_LONLAT_CRS, transform=transform,
                       width=size, height=size, resampling=Resampling.bilinear) as view:
            values = view.read(1, masked=True)
        mask = ~np.ma.getmaskarray(values) & np.isfinite(values.data)
        fraction = float(mask.mean())
        if fraction < 0.95:
            raise ValueError(f"La ortofoto cubre solo {fraction:.1%} del DEM (se exige 95%).")
        levels = values.data[mask].astype(np.float64)
        lo, hi = [float(x) for x in np.percentile(levels, (1, 99))]
        if not lo < hi:
            raise ValueError("Ortofoto sin contraste válido.")
        # Recorded contrast stretch only: no added geological detail or inpainting.
        gray = np.clip((values.data.astype(np.float64)-lo)/(hi-lo)*255,0,255)
        gray[~mask]=0
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(gray.astype("uint8"), mode="L").convert("RGB").save(
            output, format="JPEG", quality=89, optimize=True, subsampling=0)
        description = {
            "product": PRODUCT,
            "instrument": "MRO Context Camera (CTX)",
            "producer": "USGS Astrogeology Science Center",
            "source_url": SOURCE_URL,
            "source_sha256": checksum(source),
            "bbox": bbox,
            "coordinate_order": "longitude, latitude",
            "width": size, "height": size, "valid_fraction": fraction,
            "source_crs": src.crs.to_string(),
            "source_pixel_spacing": list(src.res),
            "display_stretch_percentiles": [1, 99],
            "missing_pixels": "Rendered black; not invented or inpainted.",
            "scientific_limitations": "Approx 6 m image sampling; registered to Mars. Image detail is not terrain elevation."
        }
        output.with_name("jezero_ortho_meta.json").write_text(
            json.dumps(description, indent=2)+"\n", encoding="utf-8")
    return description


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--input", type=Path, default=ROOT / "jezero_ctx_ortho_6m.tif")
    parser.add_argument("--dem", type=Path, default=ROOT / "jezero_dem_precomputed.json")
    parser.add_argument("--output", type=Path, default=ROOT / "jezero_ortho.jpg")
    parser.add_argument("--size", type=int, default=2048)
    args = parser.parse_args()
    path = download(args.input) if args.download else args.input
    if not path.is_file():
        parser.error("Missing official CTX orthomosaic. Use --download or --input.")
    print(json.dumps(generate(path,args.dem,args.output,args.size),indent=2))


if __name__ == "__main__":
    main()
