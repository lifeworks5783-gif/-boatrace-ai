"""V4: raw-first, deadline window, independent decode, no fake historic signal."""
from __future__ import annotations
import csv
import gzip
import hashlib
import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
from collectors.v4_pipeline import plan_live,fetch_one,decode_manifest,capture_morning,JST,exhibition_is_complete

class FakeReply:
    status_code=200
    encoding="utf-8"
    content=b"<html><body><div>official irregular</div></body></html>"
class FakeClient:
    def get(self,url,timeout=None,headers=None):return FakeReply()

class V4ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.day="20261012"
        b=self.root/"daily_inputs/2026/10/12/base"
        b.mkdir(parents=True)
        (b/"program_races_20261012.csv").write_text(
            "race_id,date,venue_code,venue_name,race,deadline\n"
            "20261012-22-11,20261012,22,福岡,11,20:20\n"
            "20261012-22-12,20261012,22,福岡,12,20:45\n"
            "20261012-19-12,20261012,19,下関,12,21:10\n",
            encoding="utf-8")
        (b/"program_entries_20261012.csv").write_text(
            "race_id,boat,registration_no\n"+
            "".join(f"20261012-22-12,{n},{4000+n}\n" for n in range(1,7)),
            encoding="utf-8")
    def tearDown(self):self.tmp.cleanup()
    def test_only_upcoming_deadlines_and_deterministic_order(self):
        now=datetime(2026,10,12,20,25,tzinfo=JST)
        planned=plan_live(self.root,self.day,now)
        self.assertEqual([x["race_id"] for x in planned],["20261012-22-12"])
        self.assertTrue(planned[0]["source_url"].endswith("hd=20261012&jcd=22&rno=12"))
    def test_raw_http_stored_even_if_parser_cannot_understand_html(self):
        entry=plan_live(self.root,self.day,datetime(2026,10,12,20,25,tzinfo=JST))[0]
        record=fetch_one(entry,self.root/"input"/"raw",client=FakeClient())
        self.assertEqual(record["status"],"http_received")
        raw=self.root/"input"/"raw"/record["raw_path"]
        self.assertEqual(gzip.decompress(raw.read_bytes()),FakeReply.content)
        self.assertEqual(hashlib.sha256(FakeReply.content).hexdigest(),record["sha256"])
        (self.root/"input"/"manifest.json").write_text(json.dumps({
            "schema":"boatrace-v4-capture-v1","mode":"live","date":self.day,
            "records":[record]}),encoding="utf-8")
        result=decode_manifest(self.root/"input",self.root/"decoded",self.root)
        self.assertEqual(result["decoded_races"],0)
        self.assertEqual(len(result["unparsed_races"]),1)
        self.assertTrue(raw.exists())
        self.assertFalse((self.root/"decoded"/"raw").exists())
    def test_checksum_tamper_fails_without_misleading_saved_data(self):
        entry=plan_live(self.root,self.day,datetime(2026,10,12,20,25,tzinfo=JST))[0]
        record=fetch_one(entry,self.root/"input"/"raw",client=FakeClient())
        record["sha256"]="f"*64
        (self.root/"input"/"manifest.json").write_text(json.dumps({
            "schema":"boatrace-v4-capture-v1","mode":"live","date":self.day,
            "records":[record]}),encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError,"checksum_mismatch"):
            decode_manifest(self.root/"input",self.root/"decoded",self.root)
    def test_morning_reuses_existing_program_without_external_connection(self):
        out=capture_morning(self.root,self.day,self.root/"morning")
        self.assertEqual(out["mode"],"morning")
        self.assertIn("program_races_20261012.csv",out["base_files"])
        self.assertTrue((self.root/"morning/base/program_entries_20261012.csv").exists())
    def test_future_schedule_cannot_be_captured_as_late_live(self):
        now=datetime(2026,10,12,21,30,tzinfo=JST)
        self.assertEqual(plan_live(self.root,self.day,now),[])
    def test_3stage_files_exist_and_late_predictions_are_guarded(self):
        root=Path(__file__).resolve().parents[1]
        names=("v4_stage1_capture.yml","v4_stage2_decode.yml","v4_stage3_predict.yml")
        files=[(root/".github/workflows"/name).read_text(encoding="utf-8") for name in names]
        self.assertIn("actions/upload-artifact",files[0])
        self.assertIn('gh run download "$SOURCE_RUN"',files[1])
        self.assertIn('gh run download "$SOURCE_RUN"',files[2])
        self.assertIn('--now "$NOW"',files[2])
        self.assertIn('python -u collectors/build_latest_prediction_view.py',files[2])
        # V4 must publish index via the light path; heavy PDCA is independent.
        self.assertIn('run fast_family_prediction_page.yml',files[2])
        self.assertNotIn('run family_prediction_page.yml',files[2])
        self.assertTrue((root/".github/workflows/fast_family_prediction_page.yml").is_file())
        self.assertIn('live/v4_decoded',files[1])
        self.assertIn('live/v4_decoded',files[2])
        self.assertIn("v4-stage2-receipt-v1",files[1])
        self.assertIn("v4-stage3-receipt-v1",files[2])
        self.assertNotIn('sleep "$DELAY"',files[0])
    def test_http_200_without_exhibition_is_not_ready_for_scoring(self):
        rows=[{"boat":n,"registration_no":str(4000+n),
               "exhibition_course":None,"exhibition_time":None,
               "exhibition_st_raw":None,"is_miss":False} for n in range(1,7)]
        self.assertFalse(exhibition_is_complete(rows))
        for row in rows:
            row["exhibition_course"]=int(row["boat"])
            row["exhibition_time"]=6.8
            row["exhibition_st_raw"]=".00"
        self.assertTrue(exhibition_is_complete(rows))
        rows[5]["exhibition_time"]=None
        self.assertFalse(exhibition_is_complete(rows))
        rows[5]["is_miss"]=True
        self.assertTrue(exhibition_is_complete(rows))
        rows.pop(4)
        self.assertFalse(exhibition_is_complete(rows))  # missing boat is not an inferred scratch
        self.assertFalse(exhibition_is_complete(rows+[rows[0]]))  # duplicate boat identity

    def test_unready_automatically_dispatches_missing_only_bounded_collector(self):
        root=Path(__file__).resolve().parents[1]
        decode=(root/"collectors/v4_pipeline.py").read_text(encoding="utf-8")
        stage2=(root/".github/workflows/v4_stage2_decode.yml").read_text(encoding="utf-8")
        collector=(root/".github/workflows/fast_live_collection_v3.yml").read_text(encoding="utf-8")
        self.assertIn('"official_exhibition_not_ready"',decode)
        self.assertIn('"after_deadline_observation"',decode)
        self.assertIn('if not exhibition_is_complete(bb):',decode)
        self.assertIn('gh workflow run fast_live_collection_v3.yml',stage2)
        self.assertIn("30 < (cutoff-now).total_seconds() <= 25*60",stage2)
        self.assertIn('V4_RETRY_ALREADY_QUEUED_OR_RECENT',stage2)
        self.assertIn('cloudflare_button_fallback',collector)
        self.assertIn('RETRIES=2',collector)

    def test_beforeinfo_recording_timestamp_is_not_decode_timestamp(self):
        code=(Path(__file__).resolve().parents[1]/"collectors/v4_pipeline.py").read_text(encoding="utf-8")
        self.assertIn('"collected_at":x["received_at"]',code)
        self.assertIn('result["decoded_races"]+=1',code)
if __name__=="__main__":unittest.main()
