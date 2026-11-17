"""DEM contract tests. Generated rasters exist ONLY in temporary test directories.

Opt-in tests use MARS_DEM_TEST_PATH for the actual downloaded USGS CTX product;
they never substitute generated heights for a missing scientific dataset.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from fastapi import HTTPException
from fastapi.testclient import TestClient

from mars_dem_server import (app, MARS_LONLAT_CRS, OFFICIAL_DEM_PATHS,
                             USGS_BASE, USGS_MIRROR_BASE, obtener_dem)

BBOX = (77.390, 18.425, 77.475, 18.475)
CTX_SHA256 = '16a1aa66c3f48c1bca252795827db7b417876217aff0f5e1aff18027fab2327b'


def fixture_raster(path, values=None, crs=MARS_LONLAT_CRS, dtype='float32', count=1,
                   nodata=-9999, mask=None, scale=1, units='m'):
    """Test fixture, deliberately not a real Martian elevation product."""
    if values is None:
        values = np.arange(1600, dtype=dtype).reshape(40, 40)-3000
    with rasterio.open(path, 'w', driver='GTiff', width=40, height=40, count=count,
                       crs=crs, transform=from_bounds(*BBOX, 40, 40),
                       dtype=dtype, nodata=nodata) as dst:
        for band in range(1, count+1):
            dst.write(values.astype(dtype), band)
        dst.scales = (scale,)*count
        if units:
            dst.set_band_unit(1, units)
        if mask is not None:
            dst.write_mask(mask)


class DEMContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)/'test_fixture_not_scientific_data.tif'
        fixture_raster(self.path)
        self.env = patch.dict(os.environ, {'MARS_DEM_PATH': str(self.path)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_status_validates_raster_and_distinguishes_unverified_provenance(self):
        status = self.client.get('/api/status').json()
        self.assertEqual(status['status'], 'activo')
        self.assertTrue(status['dem_validated'])
        self.assertFalse(status['provenance_verified'])
        self.assertFalse(status['provenance']['verified'])
        self.assertIsNone(status['provenance']['source_url'])
        self.assertEqual(status['source_elevation_stats']['valid_cells'], 1600)

    def test_existing_non_tiff_never_reports_active(self):
        self.path.write_text('not a raster')
        status = self.client.get('/api/status').json()
        self.assertEqual(status['status'], 'dem_invalido')
        self.assertFalse(status['dem_validated'])
        self.assertEqual(self.client.get('/api/dem/jezero').status_code, 422)

    def test_missing_file_never_returns_elevations(self):
        self.path.unlink()
        self.assertEqual(self.client.get('/api/status').json()['status'], 'sin_dem')
        self.assertEqual(self.client.get('/api/dem/jezero').status_code, 404)

    def test_legacy_manifest_keeps_unknown_download_time_and_requires_ctx_pin(self):
        record = {'dataset': 'ctx', 'origin_url': USGS_BASE + OFFICIAL_DEM_PATHS['usgs_ctx'],
                  'download_url': USGS_MIRROR_BASE + OFFICIAL_DEM_PATHS['usgs_ctx'],
                  'source_institution': 'USGS Astrogeology Science Center', 'sha256': CTX_SHA256}
        manifest = Path(str(self.path) + '.provenance.json')
        manifest.write_text(json.dumps(record))
        # Isolate manifest migration; an actual fixture cannot match the CTX pin.
        with patch('mars_dem_server._sha256', return_value=CTX_SHA256):
            status = self.client.get('/api/status').json()
        self.assertTrue(status['provenance_verified'])
        self.assertIsNone(status['provenance']['downloaded_at'])
        self.assertFalse(status['provenance']['download_time_recorded'])
        self.assertEqual(self.client.get('/api/dem/jezero').status_code, 422)

    def test_real_numeric_bands_mars_crs_and_physical_units_required(self):
        cases = ({'crs': 'EPSG:4326'}, {'count': 3}, {'scale': 0.5}, {'units': 'ft'},
                 {'dtype': 'uint8', 'values': np.ones((40, 40)), 'nodata': 255},
                 {'dtype': 'complex64', 'values': np.ones((40, 40)), 'nodata': None})
        for arguments in cases:
            with self.subTest(arguments=arguments.keys()):
                fixture_raster(self.path, **arguments)
                self.assertEqual(self.client.get('/api/status').json()['status'], 'dem_invalido')
                self.assertEqual(self.client.get('/api/dem/jezero').status_code, 422)

    def test_undeclared_sentinel_rejected_before_interpolation(self):
        for bad_value in (float('inf'), float('nan'), -3.4028226550889045e38, 999999):
            with self.subTest(value=bad_value):
                values = np.full((40, 40), -2500, dtype='float32')
                values[17, 17] = bad_value
                fixture_raster(self.path, values)
                result = self.client.get('/api/dem/jezero?size=80')
                self.assertEqual(result.status_code, 422)
                self.assertIn('NoData', result.json()['detail'])

    def test_nodata_is_null_and_cannot_contaminate_neighbors(self):
        values = np.full((40, 40), -2500, dtype='float32')
        values[10:20, 10:20] = -9999
        fixture_raster(self.path, values)
        result = self.client.get('/api/dem/jezero?size=80')
        self.assertEqual(result.status_code, 200, result.text)
        data = result.json()
        self.assertEqual(data['nodata_cells'], 400)
        self.assertEqual(data['elevations'].count(None), 400)
        self.assertAlmostEqual(data['valid_fraction'], 0.9375)
        self.assertEqual(set(v for v in data['elevations'] if v is not None), {-2500})
        self.assertEqual(data['nodata_representation'], 'null')
        json.dumps(data, allow_nan=False)

    def test_dataset_mask_hole_remains_nodata(self):
        values = np.full((40, 40), -2500, dtype='float32')
        values[10:20, 10:20] = 500000
        mask = np.full((40, 40), 255, dtype='uint8')
        mask[10:20, 10:20] = 0
        fixture_raster(self.path, values, nodata=None, mask=mask)
        response = self.client.get('/api/dem/jezero?size=80')
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['nodata_cells'], 400)
        self.assertEqual(set(v for v in data['elevations'] if v is not None), {-2500})

    def test_all_nodata_is_an_error(self):
        fixture_raster(self.path, np.full((40, 40), -9999, dtype='float32'))
        self.assertEqual(self.client.get('/api/status').json()['status'], 'dem_invalido')
        self.assertEqual(self.client.get('/api/dem/jezero').status_code, 422)

    def test_coordinate_registration_and_row_order_match_source(self):
        data = obtener_dem(size=40)
        self.assertEqual(data['row_order'], 'north_to_south')
        self.assertEqual(data['coordinate_order'], 'longitude, latitude')
        self.assertEqual(data['pixel_registration'], 'area')
        self.assertEqual(data['bbox'], list(BBOX))
        self.assertAlmostEqual(data['elevations'][0], -3000)
        self.assertAlmostEqual(data['elevations'][-1], -1401)
        self.assertGreater(data['grid_transform'][0], 0)
        self.assertLess(data['grid_transform'][4], 0)

    def test_clipping_is_explicit_and_no_intersection_is_rejected(self):
        data = obtener_dem(min_lon=77.38, min_lat=18.42, max_lon=77.47, max_lat=18.47, size=40)
        self.assertFalse(data['requested_bbox_fully_covered'])
        self.assertEqual(data['bbox'][:2], list(BBOX)[:2])
        self.assertEqual(data['requested_bbox'], [77.38, 18.42, 77.47, 18.47])
        for url in ('?min_lon=1&min_lat=1&max_lon=2&max_lat=2',
                    '?min_lon=77', '?size=0', '?size=441',
                    '?min_lon=78&min_lat=18&max_lon=77&max_lat=19'):
            self.assertEqual(self.client.get('/api/dem/jezero'+url).status_code, 422)
        with self.assertRaises(HTTPException):
            obtener_dem(size=0)

    def test_manifest_integrity_and_official_source_are_both_required(self):
        product = OFFICIAL_DEM_PATHS['usgs_ctx']
        record = {'source_url': USGS_BASE+product,
                  'retrieved_url': USGS_MIRROR_BASE+product,
                  'source_product': 'usgs_ctx', 'attribution': 'TEST MANIFEST ONLY',
                  'downloaded_at': '2026-01-01T00:00:00Z',
                  'sha256': hashlib.sha256(self.path.read_bytes()).hexdigest()}
        manifest = self.path.with_suffix('.tif.provenance.json')
        manifest.write_text(json.dumps(record))
        # A self-authored manifest cannot turn this fixture into official CTX data.
        self.assertEqual(self.client.get('/api/dem/jezero').status_code, 422)
        record['sha256'] = CTX_SHA256
        record['doi'] = 'https://doi.org/10.5066/P9P2SP9T'
        manifest.write_text(json.dumps(record))
        with patch('mars_dem_server._sha256', return_value=CTX_SHA256):
            data = obtener_dem(size=40)
            self.assertTrue(data['provenance']['verified'])
            self.assertTrue(data['provenance']['content_pinned'])
            self.assertEqual(data['provenance']['doi'], record['doi'])
            self.assertEqual(data['provenance']['retrieved_url'], USGS_MIRROR_BASE+product)
        # The actual fixture hash fails even with an official-looking pinned manifest.
        self.assertEqual(self.client.get('/api/dem/jezero').status_code, 422)
        record['source_url'] = 'https://example.com/fake.tif'
        manifest.write_text(json.dumps(record))
        self.assertEqual(self.client.get('/api/dem/jezero').status_code, 422)
        record['source_url'] = USGS_BASE+product
        record['sha256'] = '0'*64
        manifest.write_text(json.dumps(record))
        self.assertEqual(self.client.get('/api/status').json()['status'], 'dem_invalido')


@unittest.skipUnless(os.environ.get('MARS_DEM_TEST_PATH'),
                     'Set MARS_DEM_TEST_PATH to run against the actual USGS CTX GeoTIFF')
class OfficialCTXIntegrationTests(unittest.TestCase):
    def test_actual_ctx_hash_resolution_coverage_and_heights(self):
        path = Path(os.environ['MARS_DEM_TEST_PATH'])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), CTX_SHA256)
        with patch.dict(os.environ, {'MARS_DEM_PATH': str(path)}):
            with TestClient(app) as client:
                response = client.get('/api/dem/jezero', params=dict(
                    min_lon=BBOX[0], min_lat=BBOX[1], max_lon=BBOX[2], max_lat=BBOX[3], size=220))
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                self.assertTrue(data['requested_bbox_fully_covered'])
                self.assertEqual(data['valid_fraction'], 1)
                self.assertEqual(data['source_resolution_m'], [20, 20])
                self.assertEqual((data['source_width'], data['source_height']), (1596, 1512))
                self.assertTrue(data['upsampled'])
                self.assertAlmostEqual(data['source_resolution_m_approx'][0], 18.972, places=2)
                self.assertAlmostEqual(data['cell_size_x_m'], 21.72445, places=4)
                self.assertAlmostEqual(data['cell_size_y_m'], 13.47152, places=4)
                self.assertLess(data['elevation_max_m'], -2400)
                self.assertGreater(data['elevation_min_m'], -2700)
                self.assertEqual(client.get('/api/status').json()['status'], 'activo')
                # Independent nearest source-cell comparison bounds the interpolated
                # result to the four source neighbors at each output cell center.
                with rasterio.open(path) as src:
                    for row, col in ((0, 0), (45, 80), (110, 110), (219, 219)):
                        lon = BBOX[0]+(col+0.5)*(BBOX[2]-BBOX[0])/220
                        lat = BBOX[3]-(row+0.5)*(BBOX[3]-BBOX[1])/220
                        x, y = rasterio.warp.transform(MARS_LONLAT_CRS, src.crs, [lon], [lat])
                        u, v = ~src.transform*(x[0], y[0])
                        cell_col, cell_row = int(np.floor(u-0.5)), int(np.floor(v-0.5))
                        neighbors = src.read(1, window=rasterio.windows.Window(cell_col, cell_row, 2, 2))
                        elevation = data['elevations'][row*220+col]
                        self.assertGreaterEqual(elevation, float(neighbors.min())-0.1)
                        self.assertLessEqual(elevation, float(neighbors.max())+0.1)


if __name__ == '__main__':
    unittest.main()
