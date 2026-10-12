"""Publisher integration without changing existing family four-tab UI."""
import json
import tempfile
import unittest
from pathlib import Path
from raw_collector.stage_family_diagnostics import stage

class StageResearchDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.site=self.root/"site"
        self.site.mkdir()
        self.original='<html><body><nav class="family-nav"><a href="index.html">最新予想</a><a href="analysis.html">AI分析</a></nav><h1>AI分析</h1></body></html>'
        (self.site/"analysis.html").write_text(self.original,encoding="utf-8")
        self.output=self.root/"normalized"/"2026"/"10"/"12"/"races.json"
    def tearDown(self): self.temp.cleanup()
    def put(self,verified):
        self.output.parent.mkdir(parents=True,exist_ok=True)
        data={"schema":"boatrace-normalized-v1","date":"20261012",
              "source_archive":"private_google_drive_verified" if verified else "local_ephemeral_unarchived",
              "races":[{"race_id":"20261012-22-12","parse_status":"unparsed","boats":[],
                        "source":{"source_url":"https://www.boatrace.jp/owpc/pc/race/beforeinfo",
                                  "raw_sha256":"f"*64,"drive_raw_verified":verified},
                        "diagnostics":{"issues":[{"code":"unknown_st_notation",
                                                  "field":"exhibition_st_raw","boat":3}]}}]}
        self.output.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
    def test_missing_normalized_never_adds_broken_link(self):
        self.assertEqual(stage(self.root,self.site,"20261012")["status"],"skipped_no_saved_research_data")
        self.assertEqual((self.site/"analysis.html").read_text(encoding="utf-8"),self.original)
        self.assertFalse((self.site/"raw_diagnostics.html").exists())
    def test_unarchived_dev_preview_never_appears_on_family_site(self):
        self.put(False)
        self.assertEqual(stage(self.root,self.site,"20261012")["status"],"skipped_no_saved_research_data")
        self.assertFalse((self.site/"raw_diagnostics.html").exists())
    def test_existing_program_adds_live_save_diagnostics_without_drive_oauth(self):
        base=self.root/"daily_inputs/2026/10/12/base"
        base.mkdir(parents=True)
        (base/"program_races_20261012.csv").write_text(
            "race_id,deadline\n20261012-22-12,16:40\n",encoding="utf-8")
        (base/"program_entries_20261012.csv").write_text(
            "race_id,boat,registration_no\n"+
            "".join(f"20261012-22-12,{i},{4000+i}\n" for i in range(1,7)),
            encoding="utf-8")
        self.put(False)  # Local preview cannot claim verified Drive raw archive.
        result=stage(self.root,self.site,"20261012")
        self.assertEqual(result["status"],"staged_saved_research_diagnostics")
        self.assertEqual(result["count"],1)
        report=(self.site/"raw_diagnostics.html").read_text(encoding="utf-8")
        self.assertIn("朝番組6艇",report)
        self.assertIn("原本",report)
        self.assertIn("結果後に復旧したデータを当時の直前取得",report)
        analysis=(self.site/"analysis.html").read_text(encoding="utf-8")
        self.assertIn("研究用・保存データ診断を見る",analysis)
        self.assertEqual(analysis.count('<nav'),1)

    def test_verified_research_data_adds_optional_link_and_page(self):
        self.put(True)
        r=stage(self.root,self.site,"20261012")
        self.assertEqual(r["status"],"staged_verified_research_diagnostics")
        self.assertEqual(r["needs_review"],1)
        self.assertTrue((self.site/"raw_diagnostics.html").is_file())
        edited=(self.site/"analysis.html").read_text(encoding="utf-8")
        self.assertIn('href="raw_diagnostics.html"',edited)
        self.assertEqual(edited.count("<nav"),1)
        self.assertEqual(edited.count('href="index.html"'),1)
        self.assertIn("3号艇・展示STの未知の表記",
                       (self.site/"raw_diagnostics.html").read_text(encoding="utf-8"))
    def test_publisher_wires_diagnostics_without_expanding_four_main_tabs(self):
        workflow=(Path(__file__).resolve().parents[1]/".github/workflows/family_prediction_page.yml").read_text(encoding="utf-8")
        navigation=(Path(__file__).resolve().parents[1]/"collectors/add_family_navigation.py").read_text(encoding="utf-8")
        self.assertIn("python -m raw_collector.stage_family_diagnostics",workflow)
        self.assertIn('if test -s _family_site/raw_diagnostics.html; then',workflow)
        self.assertIn('git add raw_diagnostics.html raw_diagnostics_summary.json',workflow)
        self.assertIn('"analysis.html": "analysis"',navigation)
        self.assertNotIn('"raw_diagnostics.html": "raw_diagnostics"',navigation)

    def test_repeat_staging_is_rejected_instead_of_duplicate_link(self):
        self.put(True)
        stage(self.root,self.site,"20261012")
        with self.assertRaisesRegex(ValueError,"already_exists"):
            stage(self.root,self.site,"20261012")
if __name__=="__main__":unittest.main()
