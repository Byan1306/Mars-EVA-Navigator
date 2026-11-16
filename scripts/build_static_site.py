#!/usr/bin/env python3
"""Publish only public application assets and the validated real Jezero DEM.

Never publish a local database, .env file, raw GeoTIFF, or repo internals.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil

try:
    from .verify_static_dem import verify
except ImportError:  # direct invocation: python scripts/build_static_site.py
    from verify_static_dem import verify

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = (
    "index.html",
    "mars_eva_navigator_guia_de_supervivencia_interplanetaria_nasa_space_apps_2026.html",
    "curiosity_explorer.js",
    "curiosity_explorer.css",
    "curiosity_pro.css",
    "curiosity_360_renderer.js",
)


def build(output: Path, dem: Path) -> None:
    source = dem.resolve()
    metadata = verify(source)
    output = output.resolve()
    if output == ROOT or ROOT in output.parents and output == source.parent:
        raise ValueError("Output must be a dedicated publish directory, never the repository root")
    output.mkdir(parents=True, exist_ok=True)
    for name in PUBLIC_FILES:
        path = ROOT / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing public asset: {name}")
        shutil.copy2(path, output / name)
    shutil.copy2(source, output / "jezero_dem_precomputed.json")
    print(f"Static NASA science build ready: {output} ({metadata['valid_fraction']:.1%} valid cells)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dem", required=True, type=Path, help="Validated JSON generated from USGS")
    parser.add_argument("--output", default=ROOT / "_site", type=Path)
    args = parser.parse_args()
    build(args.output, args.dem)


if __name__ == "__main__":
    main()
