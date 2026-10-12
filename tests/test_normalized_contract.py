"""Only compact, verified, parser-versioned data belongs in public Git."""
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from raw_collector.archive import record_response
from raw_collector.drive_bundle import bundle_batch
from raw_collector.normalize import normalize_verified_bundle,preview_local_bundle,merge_daily_summary,write_summary

class NormalizedContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        p=self.root/"daily_inputs/2026/10/12/base/program_races_20261012.csv"
        p.parent.mkdir(parents=True)
        p.write_text("race_id,date,venue_code,venue_name,race,deadline\n20261012-22-12,20261012,22,福岡,12,16:40\n",encoding="utf-8")
        url="https://www.boatrace.jp/owpc/pc/race/beforeinfo?hd=20261012&jcd=22&rno=12"
        raw=self.root/"private_raw_official"
        record_response(raw,url=url,payload=b"<html>unknown-layout</html>",
                        requested_at="2026-10-12T15:00:00+09:00",
                        received_at="2026-10-12T15:00:01+09:00")
        self.zip,_=bundle_batch(raw,self.root/"out","20261012")
    def tearDown(self):
        self.tmp.cleanup()
    def test_never_publish_summary_before_private_archive_verified(self):
        with self.assertRaisesRegex(RuntimeError,"not_verified"):
            normalize_verified_bundle(self.zip,root=self.root,transfer_status="failed")
    def test_failed_parser_still_has_evidence_pointer_without_html(self):
        payload=normalize_verified_bundle(self.zip,root=self.root,transfer_status="verified_uploaded")
        self.assertEqual(payload["races"][0]["parse_status"],"unparsed")
        self.assertTrue(payload["races"][0]["source"]["drive_raw_verified"])
        self.assertNotIn("<html>",str(payload))
        written=write_summary(payload,repo_root=self.root)
        self.assertIn("20261012-22-12",written.read_text(encoding="utf-8"))
    def test_drive_auth_free_preview_is_explicitly_non_durable(self):
        preview=preview_local_bundle(self.zip,root=self.root)
        self.assertEqual(preview["source_archive"],"local_ephemeral_unarchived")
        self.assertEqual(preview["races"][0]["parse_status"],"unparsed")
        self.assertFalse(preview["races"][0]["source"]["drive_raw_verified"])
        with self.assertRaisesRegex(RuntimeError,"cannot_be_committed"):
            write_summary(preview,repo_root=self.root)
        self.assertFalse((self.root/"normalized").exists())

    def test_same_zip_keeps_prior_good_observation_when_new_html_unreadable(self):
        # Later pages can break the parser; their raw hash must remain current,
        # while the last *complete* read remains available for comparisons.
        p=self.root/"daily_inputs/2026/10/12/base/program_entries_20261012.csv"
        lines=["race_id,boat,registration_no"]
        lines.extend(f"20261012-22-12,{n},{4000+n}" for n in range(1,7))
        p.write_text("\n".join(lines)+"\n",encoding="utf-8")
        url="https://www.boatrace.jp/owpc/pc/race/beforeinfo?hd=20261012&jcd=22&rno=12"
        raw=self.root/"private_raw_official"
        record_response(raw,url=url,payload=b"<html>readable</html>",
            requested_at="2026-10-12T15:01:00+09:00",
            received_at="2026-10-12T15:01:01+09:00")
        record_response(raw,url=url,payload=b"<html>new-layout-unreadable</html>",
            requested_at="2026-10-12T15:02:00+09:00",
            received_at="2026-10-12T15:02:01+09:00")
        archived,_=bundle_batch(raw,self.root/"all", "20261012")
        rows=[{"boat":n,"registration_no":str(4000+n),
               "exhibition_course":n,"exhibition_st_raw":f".0{n}",
               "exhibition_st_seconds":0.01*n,"exhibition_st_flag":"",
               "exhibition_time":6.6+0.01*n,"is_miss":False}
              for n in range(1,7)]
        weather={"air_temperature_c":26.0,"water_temperature_c":24.0,
                 "wind_speed_mps":4.0,"wave_height_cm":4.0}
        def parse(html,base,requested_at=""):
            return (weather,rows) if ">readable<" in html else None
        with patch("raw_collector.normalize.parse_beforeinfo",side_effect=parse):
            result=preview_local_bundle(archived,root=self.root)
        current=result["races"][0]
        self.assertEqual(current["parse_status"],"unparsed")
        self.assertEqual(current["last_ready"]["boats"][0]["exhibition_st_raw"],".01")
        self.assertFalse(current["source"]["drive_raw_verified"])
        self.assertEqual(current["last_ready"]["source"]["collected_at"],
                         "2026-10-12T15:01:01+09:00")

    def test_daily_merge_preserves_other_races(self):
        a={"schema":"boatrace-normalized-v1","date":"20261012","races":[
            {"race_id":"20261012-22-01","source":{"collected_at":"1"}}]}
        b={"schema":"boatrace-normalized-v1","date":"20261012","races":[
            {"race_id":"20261012-22-12","source":{"collected_at":"2"}}]}
        x=merge_daily_summary(a,b)
        self.assertEqual([v["race_id"] for v in x["races"]],
                         ["20261012-22-01","20261012-22-12"])
    def test_bad_new_parser_result_does_not_erase_last_valid_snapshot(self):
        old={"schema":"boatrace-normalized-v1","date":"20261012","races":[{
            "race_id":"20261012-22-12","parse_status":"ready_live_inputs",
            "source":{"collected_at":"2026-10-12T15:00:00+09:00","raw_sha256":"old"},
            "race":{"wind_speed_mps":4.0},"boats":[{"boat":1,"exhibition_st_raw":".03"}]}]}
        new={"schema":"boatrace-normalized-v1","date":"20261012","races":[{
            "race_id":"20261012-22-12","parse_status":"unparsed",
            "source":{"collected_at":"2026-10-12T15:01:00+09:00","raw_sha256":"new"},
            "race":None,"boats":[]}]}
        row=merge_daily_summary(old,new)["races"][0]
        self.assertEqual(row["parse_status"],"unparsed")
        self.assertEqual(row["source"]["raw_sha256"],"new")
        self.assertEqual(row["last_ready"]["source"]["raw_sha256"],"old")
        self.assertEqual(row["last_ready"]["boats"][0]["exhibition_st_raw"],".03")

if __name__=="__main__":
    unittest.main()
