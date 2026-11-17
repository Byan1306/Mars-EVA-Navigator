"""Schema and offline safety tests. All data constructed here is synthetic TEST-ONLY."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from fastapi.testclient import TestClient

from mars_dem_server import app
from scripts.prepare_dem import download_dataset, sha256_file
from scripts.verify_static_dem import verify
from scripts.build_static_site import build, PUBLIC_FILES


def fake_schema_data():
    # Invented values ONLY for an isolated schema test; never included in release.
    return {
        "source_file": "jezero_ctx_dtm_20m.tif",
        "source_url": "https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/example-test-only.tif",
        "source_sha256": "a" * 64,
        "elevation_units": "m",
        "coordinate_order": "longitude, latitude",
        "width": 40, "height": 40,
        "elevations": [-2600.0] * 1600,
        "valid_fraction": 1.0,
        "bbox": [77.30, 18.30, 77.40, 18.40],
        "source_resolution_m_approx": [20.0, 20.0],
        "scientific_limitations": "DEM test fixture: no science data",
    }


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.dataset = self.folder / "dem.json"
        self.dataset.write_text(json.dumps(fake_schema_data()), encoding="utf-8")

    def test_release_schema_validation_and_missing_provenance(self):
        self.assertEqual(verify(self.dataset)["size"], (40, 40))
        data = fake_schema_data()
        del data["source_sha256"]
        self.dataset.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            verify(self.dataset)

    def test_release_rejects_fabricated_coverage(self):
        data = fake_schema_data()
        data["elevations"] = [None] * 500 + data["elevations"][500:]
        data["valid_fraction"] = 1100 / 1600
        self.dataset.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "coverage"):
            verify(self.dataset)

    def test_site_build_only_exposes_approved_public_assets(self):
        target = self.folder / "_site"
        build(target, self.dataset)
        self.assertEqual(
            {p.name for p in target.iterdir()},
            set(PUBLIC_FILES) | {"jezero_dem_precomputed.json", "vendor"} |
            ({"assets"} if (target / "assets").exists() else set())
        )
        self.assertFalse((target / "catalog.sqlite").exists())
        self.assertFalse((target / "mars_dem_server.py").exists())

    def test_official_fallback_and_checksum_provenance(self):
        destination = self.folder / "jezero_ctx_dtm_20m.tif"
        calls = []

        def mocked_urlopen(request, timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise HTTPError(request.full_url, 403, "blocked", {}, None)
            output = io.BytesIO(b"TEST-ONLY-NOT-A-REAL-TIFF" * 150)
            output.headers = {"Content-Length": str(len(output.getvalue()))}
            return output

        # This is a transport/provenance unit test, not a scientific raster.
        # Keep production checksum/GeoTIFF validation strict; the separate real
        # CTX test exercises it against the downloaded official bytes.
        with patch("scripts.prepare_dem.urlopen", mocked_urlopen), patch(
            "scripts.prepare_dem.check_product", side_effect=lambda path, source: sha256_file(path)
        ):
            path = download_dataset("ctx", destination)
        self.assertEqual(path, destination)
        self.assertEqual(len(calls), 2)
        self.assertIn("asc-pds-services.s3.us-west-2.amazonaws.com", calls[1])
        provenance = json.loads((self.folder / "jezero_ctx_dtm_20m.tif.provenance.json").read_text())
        self.assertEqual(provenance["sha256"], sha256_file(path))
        self.assertEqual(provenance["download_url"], calls[1])

    def test_invalid_file_does_not_report_active_dem(self):
        invalid = self.folder / "broken.tif"
        invalid.write_bytes(b"TEST ONLY, NOT A TIFF")
        with patch.dict(os.environ, {"MARS_DEM_PATH": str(invalid)}):
            with TestClient(app) as client:
                status = client.get("/api/status")
                self.assertEqual(status.status_code, 200)
                self.assertEqual(status.json()["status"], "dem_invalido")
                self.assertNotEqual(client.get("/api/dem/jezero").status_code, 200)


if __name__ == "__main__":
    unittest.main()
