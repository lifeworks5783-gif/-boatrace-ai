"""Drive archive handoff: only verified copies may be marked transferred."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from raw_collector.archive import record_response
from raw_collector.drive_bundle import bundle_batch, validate_bundle
from raw_collector.drive_upload import upload_private_bundle, DriveTransferError

class _Reply:
    def __init__(self,obj):
        self.content=json.dumps(obj).encode("utf-8")
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,size=-1): return self.content[:size] if size>=0 else self.content

class DriveArchiveContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)
        self.raw=self.base/"private"
        self.out=self.base/"bundles"
        url="https://www.boatrace.jp/owpc/pc/race/beforeinfo?hd=20261012&jcd=22&rno=12"
        record_response(self.raw,url=url,payload=b"<html>unknown-layout</html>",
                        requested_at="2026-10-12T15:45:00+09:00",
                        received_at="2026-10-12T15:45:02+09:00")
        self.bundle,self.manifest=bundle_batch(self.raw,self.out,"20261012")
        self.payload=self.bundle.read_bytes()

    def tearDown(self):
        self.tmp.cleanup()

    def fake_api(self, *, corrupted=False, existing=False):
        events=[]
        md5=hashlib.md5(self.payload).hexdigest()
        sha=hashlib.sha256(self.payload).hexdigest()
        def opener(request,timeout=30):
            url=request.full_url
            events.append((url,request.get_method()))
            if "uploadType=multipart" in url:
                return _Reply({"id":"file-123"})
            if "files/file-123?" in url:
                return _Reply({"id":"file-123","md5Checksum":"0"*32 if corrupted else md5,
                               "sha256Checksum":sha,"size":str(len(self.payload))})
            if "drive/v3/files?" in url:
                return _Reply({"files":[{"id":"file-123"}] if existing else []})
            raise AssertionError(url)
        return opener,events

    def test_bundle_round_trip_and_manifest(self):
        self.assertEqual(validate_bundle(self.bundle)["entries"][0]["bytes"],len(b"<html>unknown-layout</html>"))
        self.assertEqual(self.bundle,bundle_batch(self.raw,self.out,"20261012")[0])

    def test_new_drive_upload_requires_server_verified_checksum(self):
        opener,calls=self.fake_api()
        result=upload_private_bundle(self.bundle,folder_id="private-folder-123",
                                     token="test-token",opener=opener)
        self.assertEqual(result["status"],"verified_uploaded")
        self.assertEqual(len([u for u,m in calls if "uploadType=multipart" in u]),1)

    def test_existing_bundle_reused_no_duplicate_upload(self):
        opener,calls=self.fake_api(existing=True)
        result=upload_private_bundle(self.bundle,folder_id="private-folder-123",
                                     token="test-token",opener=opener)
        self.assertEqual(result["status"],"verified_existing")
        self.assertFalse(any("uploadType=multipart" in u for u,m in calls))

    def test_corrupt_remote_upload_fails_closed(self):
        opener,calls=self.fake_api(corrupted=True)
        with self.assertRaisesRegex(DriveTransferError,"checksum_or_size"):
            upload_private_bundle(self.bundle,folder_id="private-folder-123",
                                  token="test-token",opener=opener)

    def test_folder_missing_refused(self):
        with self.assertRaisesRegex(DriveTransferError,"invalid_drive_folder"):
            upload_private_bundle(self.bundle,folder_id="",token="test-token")

if __name__=="__main__":
    unittest.main()
