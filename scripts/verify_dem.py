#!/usr/bin/env python3
"""Verify a running HTTP backend against the reviewed, downloaded CTX bytes.

Run after prepare_dem.py and starting mars_dem_server.py with MARS_DEM_PATH.
This check does not create a raster and cannot pass using test-only fixtures.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

import httpx
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import Window, bounds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_dem import USGS_DATASETS, sha256_file, write_json_atomic, DEFAULT_BBOX
from mars_dem_server import MARS_LONLAT_CRS


def verify(path: Path, base_url: str) -> dict:
    digest = sha256_file(path)
    assert digest == USGS_DATASETS['ctx']['sha256'], 'Requires the reviewed authentic CTX product'
    with httpx.Client(base_url=base_url, timeout=60) as client:
        status_response = client.get('/api/status')
        status_response.raise_for_status()
        status = status_response.json()
        assert status['status'] == 'activo' and status['dem_validated']
        assert status['provenance_verified']
        assert status['provenance']['sha256'] == digest
        params = dict(zip(('min_lon', 'min_lat', 'max_lon', 'max_lat'), DEFAULT_BBOX)) | {'size': 220}
        response = client.get('/api/dem/jezero', params=params)
        response.raise_for_status()
        data = response.json()
        assert data == json.loads((ROOT / 'jezero_dem_precomputed.json').read_text()), 'HTTP/export mismatch'
        assert data['requested_bbox_fully_covered']
        assert len(data['elevations']) == 48400
        assert data['nodata_cells'] == sum(v is None for v in data['elevations'])
        assert all(v is None or np.isfinite(v) for v in data['elevations'])
        assert data['source_resolution_m'] == [20.0, 20.0]
        assert data['coordinate_order'] == 'longitude, latitude'
        # Select native pixel edges: this reprojection is affine on the Mars
        # equirectangular sphere, so each output centre matches a native centre.
        # Compare independently read native pixels, not an API-generated oracle.
        with rasterio.open(path) as src:
            window = Window(800, 700, 40, 40)
            bbox = transform_bounds(src.crs, MARS_LONLAT_CRS, *bounds(window, src.transform))
            native = src.read(1, window=window)
        native_params = dict(zip(('min_lon', 'min_lat', 'max_lon', 'max_lat'), bbox)) | {'size': 40}
        sampled = client.get('/api/dem/jezero', params=native_params)
        sampled.raise_for_status()
        actual = np.array(sampled.json()['elevations'], dtype=np.float32).reshape(40, 40)
        np.testing.assert_array_equal(actual, native)
        outside = client.get('/api/dem/jezero', params={'min_lon': 0, 'min_lat': 0, 'max_lon': 1, 'max_lat': 1})
        assert outside.status_code == 422
        assert client.get('/jezero_ctx_dtm_20m.tif').status_code == 404
    return {
        'verified_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_sha256': digest, 'provenance': data['provenance'],
        'status_http': status_response.status_code, 'dem_http': response.status_code,
        'native_resolution_m': data['source_resolution_m'],
        'source_size_pixels': [data['source_width'], data['source_height']],
        'source_elevation_stats': data['source_elevation_stats'],
        'study_bbox': data['bbox'], 'grid_size': [data['width'], data['height']],
        'sampling_xy_m': [data['cell_size_x_m'], data['cell_size_y_m']],
        'valid_fraction': data['valid_fraction'], 'nodata_cells': data['nodata_cells'],
        'elevation_range_m': [data['elevation_min_m'], data['elevation_max_m']],
        'http_equals_static_export': True,
        'native_window': [800, 700, 40, 40], 'native_pixels_compared_exactly': 1600,
        'native_comparison_max_error_m': float(np.max(np.abs(actual - native))),
        'outside_coverage_http': outside.status_code,
        'route_verification_command': 'node --test tests/dem-routing.test.cjs',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path(os.environ.get('MARS_DEM_PATH', ROOT / 'jezero_ctx_dtm_20m.tif')))
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = verify(args.input, args.base_url)
    if args.report:
        write_json_atomic(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
