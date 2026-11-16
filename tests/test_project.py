"""Regression tests using generated test rasters only; no invented Martian science data."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from fastapi.testclient import TestClient
from pyproj import CRS

from mars_dem_server import app, encontrar_tif, validar_raster, obtener_dem
from catalog_store import Catalog, validate_record

MARS_CRS = CRS.from_proj4("+proj=longlat +R=3396190 +no_defs")


def write_dem(path: Path, crs=MARS_CRS):
    with rasterio.open(
        path, "w", driver="GTiff", height=4, width=4, count=1,
        dtype="float32", crs=crs,
        transform=from_bounds(77.40, 18.43, 77.47, 18.47, 4, 4),
        nodata=-9999.0,
    ) as dst:
        elevations = np.array([
            [100, 101, 102, 103],
            [104, 105, 106, 107],
            [108, 109, -9999, 111],
            [112, 113, 114, 115],
        ], dtype=np.float32)
        dst.write(elevations, 1)


class DEMTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "mock_mars_dem.tif"
        write_dem(self.path)

    def test_missing_dem_returns_status_not_fake_elevation(self):
        with patch.dict(os.environ, {"MARS_DEM_PATH": str(self.path) + ".missing"}):
            with TestClient(app) as client:
                response = client.get("/api/status")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "sin_dem")
                self.assertEqual(client.get("/api/dem/jezero").status_code, 404)

    def test_valid_mars_dem_and_nodata(self):
        with patch.dict(os.environ, {"MARS_DEM_PATH": str(self.path)}):
            with TestClient(app) as client:
                response = client.get("/api/dem/jezero?size=40")
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                self.assertEqual(data["width"], 40)
                self.assertEqual(data["height"], 40)
                self.assertGreater(data["valid_fraction"], 0)
                self.assertLess(data["valid_fraction"], 1)
                self.assertGreater(data["nodata_cells"], 0)
                self.assertEqual(len(data["elevations"]), 1600)
                self.assertEqual(data["elevation_units"], "m")
                self.assertTrue(any(x is None for x in data["elevations"]))

    def test_bad_bbox_and_no_overlap(self):
        with patch.dict(os.environ, {"MARS_DEM_PATH": str(self.path)}):
            with TestClient(app) as client:
                self.assertEqual(client.get("/api/dem/jezero?min_lon=78&max_lon=77&min_lat=18&max_lat=19").status_code, 422)
                self.assertEqual(client.get("/api/dem/jezero?min_lon=0&max_lon=1&min_lat=0&max_lat=1").status_code, 422)

    def test_reject_earth_dem(self):
        other = Path(self.tmp.name) / "earth.tif"
        write_dem(other, CRS.from_epsg(4326))
        with rasterio.open(other) as src:
            with self.assertRaises(Exception):
                validar_raster(src)


class WebTests(unittest.TestCase):
    def test_open_world_routes_keep_app_and_vendor_explicit(self):
        with TestClient(app) as client:
            self.assertIn('open_world.mjs', client.get('/').text)
            self.assertEqual(client.get('/open_world.html').status_code, 200)
            self.assertIn('text/css', client.get('/open_world.css').headers.get('content-type',''))
            self.assertIn('javascript', client.get('/open_world_core.js').headers.get('content-type',''))
            self.assertEqual(client.get('/vendor/three.module.js').status_code, 200)
            self.assertEqual(client.get('/vendor/three.core.js').status_code, 200)
            self.assertEqual(client.get('/node_modules/three/build/three.module.js').status_code, 404)
            self.assertEqual(client.get('/jezero_ortho.jpg').status_code, 404)

    def test_github_pages_entry(self):
        root = Path(__file__).resolve().parents[1]
        index = (root / "index.html").read_text(encoding="utf-8")
        target = "mars_eva_navigator_guia_de_supervivencia_interplanetaria_nasa_space_apps_2026.html"
        self.assertIn(target, index)
        self.assertTrue((root / target).is_file())

    def test_mission_control_assets_are_accessible_locally(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/curiosity_pro.css').status_code, 200)
            self.assertIn('text/css', client.get('/curiosity_pro.css').headers.get('content-type', ''))
            self.assertEqual(client.get('/curiosity_360_renderer.js').status_code, 200)
            self.assertIn('javascript', client.get('/curiosity_360_renderer.js').headers.get('content-type', ''))
            self.assertEqual(client.get('/scripts/stitch_curiosity_panorama.py').status_code, 404)

    def test_stitching_manifest_never_claims_native_3d_or_verified_360(self):
        from scripts.stitch_curiosity_panorama import find_images, make_manifest
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            for i in range(3):
                (directory / f'NASA_{i}.jpg').write_bytes(f'FAKE_UNIT_TEST_{i}'.encode())
            paths = find_images(directory, 30)
            data = make_manifest(paths, directory / 'stitch.jpg', 1200, (500, 2000, 3))
            self.assertEqual(len(data['sources']), 3)
            self.assertEqual(data['coverage_360_degrees'], 'NOT VERIFIED')
            self.assertFalse(data['native_3d_depth'])
            self.assertEqual(data['sol'], 1200)

    def test_curiosity_assets_available_without_exposing_private_files(self):
        with TestClient(app) as client:
            javascript = client.get('/curiosity_explorer.js')
            stylesheet = client.get('/curiosity_explorer.css')
            self.assertEqual(javascript.status_code, 200)
            self.assertIn('javascript', javascript.headers.get('content-type',''))
            self.assertIn('CuriosityData', javascript.text)
            self.assertEqual(stylesheet.status_code, 200)
            self.assertIn('text/css', stylesheet.headers.get('content-type',''))
            self.assertIn('#curiosity-explorer', stylesheet.text)
            self.assertEqual(client.get('/catalog.sqlite').status_code, 404)
    def test_real_elevation_export_support(self):
        root = Path(__file__).resolve().parents[1]
        code = (root / "scripts/prepare_dem.py").read_text(encoding="utf-8")
        self.assertIn("export_json(", code)
        self.assertIn("obtener_dem(", code)
        self.assertNotIn("np.random", code)


class CatalogTests(unittest.TestCase):
    def test_catalog_starts_empty_without_pretending_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            cat = Catalog(Path(d) / "catalog.sqlite")
            self.assertEqual(cat.list(), [])
            self.assertEqual(cat.nearby("Perseverance", 18.4, 77.4, 500), [])

    def test_reject_unofficial_source(self):
        record = dict(id="x", mission="Perseverance", region="Jezero", kind="photo",
                      title="test", category="B", source="https://example.org/foo")
        with self.assertRaises(ValueError):
            validate_record(record)


if __name__ == "__main__":
    unittest.main()
