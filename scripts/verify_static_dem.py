#!/usr/bin/env python3
"""Fail closed if a GitHub Pages Jezero DEM is absent, incomplete or synthetic.

This check validates the public interchange format and declared provenance.
The upstream GeoTIFF is independently checked for Mars CRS by prepare_dem.py.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

EXPECTED_FILE = "jezero_ctx_dtm_20m.tif"
EXPECTED_ORIGIN = "https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/"


def verify(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("source_file") != EXPECTED_FILE:
        raise ValueError("Expected the official Mars 2020 USGS CTX DEM, not a test or mock raster")
    if not str(data.get("source_url") or "").startswith(EXPECTED_ORIGIN):
        raise ValueError("Missing original USGS product provenance")
    digest = str(data.get("source_sha256") or "")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Missing valid source GeoTIFF SHA-256")
    if data.get("elevation_units") != "m" or data.get("coordinate_order") != "longitude, latitude":
        raise ValueError("Invalid elevation units or coordinate order")
    w, h = data.get("width"), data.get("height")
    if type(w) is not int or type(h) is not int or not (40 <= w <= 440 and 40 <= h <= 440):
        raise ValueError("Invalid export dimensions")
    values = data.get("elevations")
    if not isinstance(values, list) or len(values) != w * h:
        raise ValueError("DEM array does not match its dimensions")
    valid = sum(type(v) in (float, int) and math.isfinite(v) for v in values)
    if any(v is not None and (type(v) not in (int, float) or not math.isfinite(v)) for v in values):
        raise ValueError("DEM contains invalid elevation values")
    ratio = valid / len(values)
    if ratio < .70 or abs(ratio - float(data.get("valid_fraction", -1))) > .00001:
        raise ValueError("Insufficient scientific coverage or inconsistent mask")
    bbox = data.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4 or not all(type(v) in (float,int) and math.isfinite(v) for v in bbox):
        raise ValueError("Missing finite Jezero geographic bounds")
    west,south,east,north = bbox
    if not (76 < west < east < 79 and 17.5 < south < north < 19.5):
        raise ValueError("Requested bounds are outside Jezero")
    resolution = data.get("source_resolution_m_approx")
    if not isinstance(resolution, list) or len(resolution) != 2 or not all(type(v) in (int,float) and 10 <= v <= 35 for v in resolution):
        raise ValueError("Input data must have actual CTX-scale resolution; interpolation is not a substitute")
    if "DEM" not in str(data.get("scientific_limitations") or "") and not data.get("scientific_limitations"):
        raise ValueError("Missing limitations label")
    return {"size": (w, h), "valid_fraction": ratio, "bbox": bbox,
            "source_sha256": digest, "source_resolution_m": resolution}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    print("Validated real Jezero DEM:", json.dumps(verify(args.path), ensure_ascii=False))


if __name__ == "__main__":
    main()
