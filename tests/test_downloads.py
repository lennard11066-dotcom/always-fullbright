"""Failures here could otherwise silently produce a corrupt or stale build."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from build_universal import download


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.target = Path(self.directory.name) / "dependency.jar"
        self.payload = b"verified dependency"
        self.checksum = hashlib.sha256(self.payload).hexdigest()

    def test_valid_cache_works_without_network(self):
        self.target.write_bytes(self.payload)
        with patch("urllib.request.urlopen", side_effect=AssertionError("Network used")):
            self.assertEqual(download("https://example.invalid/dependency", self.target, self.checksum), self.target)

    def test_corrupt_cache_fails_offline(self):
        self.target.write_bytes(b"broken")
        with self.assertRaisesRegex(RuntimeError, "corrupt offline"):
            download("https://example.invalid/dependency", self.target, self.checksum, offline=True)

    def test_verified_download_repairs_corrupt_cache(self):
        self.target.write_bytes(b"broken")
        with patch("urllib.request.urlopen", return_value=io.BytesIO(self.payload)):
            download("https://example.invalid/dependency", self.target, self.checksum)
        self.assertEqual(self.target.read_bytes(), self.payload)
        self.assertFalse(self.target.with_suffix(".jar.part").exists())

    def test_bad_download_never_replaces_cache(self):
        self.target.write_bytes(b"previous")
        with patch("urllib.request.urlopen", return_value=io.BytesIO(b"tampered")):
            with self.assertRaisesRegex(RuntimeError, "Checksum mismatch"):
                download("https://example.invalid/dependency", self.target, self.checksum)
        self.assertEqual(self.target.read_bytes(), b"previous")
        self.assertFalse(self.target.with_suffix(".jar.part").exists())

    def test_interrupted_download_cannot_be_used_as_a_valid_cache(self):
        class InterruptedResponse(io.BytesIO):
            def read(self, *args):
                raise OSError("Connection interrupted")
        with patch("urllib.request.urlopen", side_effect=lambda *a, **k: InterruptedResponse(b"partial")), \
                patch("time.sleep"):
            with self.assertRaises(OSError):
                download("https://example.invalid/dependency", self.target, self.checksum)
        self.assertFalse(self.target.exists())
        self.assertFalse(self.target.with_suffix(".jar.part").exists())


if __name__ == "__main__":
    unittest.main()
