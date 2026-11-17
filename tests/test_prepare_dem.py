"""Downloader failures must never install an unverified DEM or replace an export."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from scripts.prepare_dem import download_dataset, export_json, USGS_DATASETS


class Response(io.BytesIO):
    def __init__(self, content, length=None):
        super().__init__(content)
        self.headers = {"Content-Length": str(len(content) if length is None else length)}


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "dem.tif"

    def test_blocked_primary_uses_only_documented_official_mirror(self):
        blocked = HTTPError(USGS_DATASETS["ctx"]["url"], 403, "Forbidden", {}, io.BytesIO(b"Your request was blocked."))
        with patch("scripts.prepare_dem.urlopen", side_effect=[blocked, Response(b"test-only bytes")]) as open_url, patch("scripts.prepare_dem.check_product", return_value="a" * 64):
            download_dataset("ctx", self.path)
        urls = [call.args[0].full_url for call in open_url.call_args_list]
        self.assertEqual(urls, [USGS_DATASETS["ctx"]["url"], USGS_DATASETS["ctx"]["mirror"]])
        manifest = json.loads(Path(str(self.path) + ".provenance.json").read_text())
        self.assertEqual(manifest["retrieved_url"], urls[1])
        self.assertEqual(manifest["source_url"], urls[0])
        self.assertEqual(manifest["sha256"], "a" * 64)
        self.assertFalse(self.path.with_suffix(".tif.part").exists())

    def test_truncated_download_cannot_become_dem(self):
        with patch("scripts.prepare_dem.urlopen", side_effect=[Response(b"incomplete", 500), Response(b"incomplete", 500)]):
            with self.assertRaisesRegex(OSError, "incomplete"):
                download_dataset("ctx", self.path)
        self.assertFalse(self.path.exists())
        self.assertFalse(self.path.with_suffix(".tif.part").exists())

    def test_200_html_and_changed_product_fail_pinned_checksum(self):
        with patch("scripts.prepare_dem.urlopen", return_value=Response(b"<html>not a DEM</html>")):
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                download_dataset("ctx", self.path)
        self.assertFalse(self.path.exists())
        self.assertFalse(self.path.with_suffix(".tif.part").exists())

    def test_cached_wrong_file_is_never_silently_accepted(self):
        self.path.write_bytes(b"invalid existing file")
        with patch("scripts.prepare_dem.urlopen") as open_url:
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                download_dataset("ctx", self.path)
            open_url.assert_not_called()

    def test_clipped_study_area_preserves_previous_export(self):
        output = self.path.with_suffix(".json")
        output.write_text('{"previous":true}')
        with patch("mars_dem_server.obtener_dem", return_value={"bbox": [77.4, 18.43, 77.47, 18.47]}):
            with self.assertRaisesRegex(ValueError, "complete study bbox"):
                export_json(self.path, output, (77.39, 18.425, 77.475, 18.475), 40)
        self.assertEqual(json.loads(output.read_text()), {"previous": True})


if __name__ == "__main__":
    unittest.main()
