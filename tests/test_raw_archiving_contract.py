"""Checks that raw capture does not require parsing or valid exhibition values."""
import gzip
import tempfile
import unittest
from pathlib import Path
from raw_collector.archive import source_identity, source_url, record_response, load_raw, capture_one

class RawCaptureContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.url = source_url("20261012", "beforeinfo", "02", 3)
    def tearDown(self):
        self.tmp.cleanup()
    def test_official_only(self):
        self.assertEqual(source_identity(self.url), ("20261012", "beforeinfo", "02", "03"))
        with self.assertRaises(ValueError):
            source_identity("https://example.com/owpc/pc/race/beforeinfo?hd=20261012&jcd=02&rno=3")
    def test_unknown_html_is_still_saved(self):
        original = b"<html>\xff\x00<unrecognized-ST>?</unrecognized-ST></html>"
        result = record_response(self.root, url=self.url, payload=original,
                                 requested_at="1", received_at="2")
        self.assertEqual(load_raw(Path(result["path"])), original)
    def test_dedup_and_changed_versions(self):
        a = record_response(self.root, url=self.url, payload=b"A", requested_at="1", received_at="2")
        b = record_response(self.root, url=self.url, payload=b"A", requested_at="3", received_at="4")
        c = record_response(self.root, url=self.url, payload=b"B", requested_at="5", received_at="6")
        self.assertEqual(a["path"], b["path"])
        self.assertNotEqual(a["path"], c["path"])
        self.assertEqual(len(list(self.root.rglob("*.html.gz"))), 2)
    def test_corrupt_bytes_detected(self):
        a = record_response(self.root, url=self.url, payload=b"first", requested_at="1", received_at="2")
        with gzip.open(a["path"], "wb") as f:
            f.write(b"corrupted")
        with self.assertRaises(ValueError):
            load_raw(Path(a["path"]))
    def test_failed_request_cannot_fabricate_data(self):
        def fail(*args, **kwargs):
            raise TimeoutError("offline")
        self.assertEqual(capture_one(self.url, self.root, opener=fail, retries=0)["status"], "failed")
        self.assertEqual(list(self.root.rglob("*.html.gz")), [])
if __name__ == "__main__":
    unittest.main()
