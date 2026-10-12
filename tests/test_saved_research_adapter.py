"""Tests existing research storage audit with separated recovery provenance."""
import json
import tempfile
import unittest
from pathlib import Path
from raw_collector.saved_research_adapter import diagnose_saved_day
from raw_collector.saved_research_view import make_html,write_saved_diagnostics

class ExistingResearchAdapterContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        base=self.root/"daily_inputs"/"2026"/"10"/"12"/"base"
        base.mkdir(parents=True)
        (base/"program_races_20261012.csv").write_text(
            "race_id,deadline\n20261012-22-11,16:05\n20261012-22-12,16:40\n",
            encoding="utf-8")
        (base/"program_entries_20261012.csv").write_text(
            "race_id,boat,registration_no\n"+
            "".join(f"20261012-22-11,{i},{4000+i}\n" for i in range(1,7))+
            "".join(f"20261012-22-12,{i},{4100+i}\n" for i in range(1,7)),
            encoding="utf-8")
    def tearDown(self):self.temp.cleanup()
    def live(self,path,race_id,count):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text("race_id,boat,exhibition_time,exhibition_st_raw\n"+
            "".join(f"{race_id},{i},6.8,.03\n" for i in range(1,count+1)),encoding="utf-8")
    def forecast(self,filename,ids):
        base=self.root/"predictions/2026/10/12"
        file=base/filename
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps({"target_date":"20261012",
            "races":[{"race_id":i} for i in ids]}),encoding="utf-8")

    def test_recovered_only_must_never_count_as_original(self):
        p=self.root/"evaluations/2026/10/12/recovery/official_retry_beforeinfo_entries_20261012.csv"
        self.live(p,"20261012-22-12",6)
        self.forecast("morning_predictions_20261012.json",
                      ["20261012-22-11","20261012-22-12"])
        self.forecast("live/live_predictions_final_20261012.json",["20261012-22-11"])
        self.forecast("live/formation_predictions_final_20261012.json",
                      ["20261012-22-11","20261012-22-12"])
        report=diagnose_saved_day(self.root,"20261012")
        self.assertEqual(report["summary"]["total"],2)
        self.assertEqual(report["summary"]["recovered_only"],1)
        self.assertEqual(report["summary"]["predeadline_live_six"],0)
        race=next(x for x in report["races"] if x["race_id"].endswith("-12"))
        self.assertEqual(race["beforeinfo_state"],"post_result_recovery_only")
        self.assertEqual(race["reconstructed_after_result_boats"],6)
        self.assertEqual(race["saved_predeadline_boats"],0)
        self.assertFalse(race["live_prediction_saved"])
        self.assertTrue(race["canonical_prediction_saved"])
        self.assertFalse(race["official_html_original_archived"])
        html=make_html(report)
        self.assertIn("結果後の復旧のみ",html)
        self.assertIn("原本の保存確認では",html) if "原本の保存確認では" in html else self.assertIn("公式ページの生HTML原本は検証できておらず",html)

    def test_original_folder_alone_does_not_prove_predeadline_clock(self):
        p=self.root/"daily_inputs/2026/10/12/live/raw/1200/beforeinfo_entries_20261012.csv"
        self.live(p,"20261012-22-11",6)
        report=diagnose_saved_day(self.root,"20261012")
        row=next(x for x in report["races"] if x["race_id"].endswith("-11"))
        self.assertEqual(row["beforeinfo_state"],"original_folder_saved_unverified_time")
        self.assertEqual(row["original_folder_boats"],6)
        self.assertEqual(row["saved_predeadline_boats"],0)
        self.assertIn("predeadline_capture_time_not_independently_verified",
                      [i["code"] for i in row["issues"]])

    def test_missing_source_files_are_missing_not_complete(self):
        report=diagnose_saved_day(self.root,"20261012")
        self.assertEqual(report["summary"]["total"],2)
        self.assertEqual(report["summary"]["no_live_saved"],2)
        self.assertEqual(report["summary"]["morning_six"],2)
        self.assertEqual(report["summary"]["live_prediction_saved"],0)
        self.assertNotIn("全レース正常",make_html(report))
        written=write_saved_diagnostics(self.root,"20261012",self.root/"preview")
        self.assertEqual(written["source_kind"],"decoded_research_files_not_official_html")
        self.assertTrue((self.root/"preview"/"raw_diagnostics.html").is_file())

    def test_no_saved_program_does_not_fabricate_coverage(self):
        report=diagnose_saved_day(self.root,"20261013")
        self.assertEqual(report["status"],"schedule_not_saved")
        self.assertIsNone(report["coverage"])
        self.assertEqual(report["races"],[])

    def test_invalid_date_rejected(self):
        with self.assertRaises(ValueError):
            diagnose_saved_day(self.root,"2026-10-12")

if __name__=="__main__":
    unittest.main()
