"""No fake predeadline successes; quality page never damages four-tab navigation."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from raw_collector.saved_research_adapter import diagnose_saved_day
from raw_collector.stage_saved_quality_page import stage

class PublicQualityGateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.site=self.root/"site"
        self.site.mkdir()
        self.html='<html><body><nav class="family-nav"><a href="index.html">最新予想</a><a href="analysis.html">AI分析</a></nav><h1>AI分析</h1></body></html>'
        (self.site/"analysis.html").write_text(self.html,encoding="utf-8")
        self.base=self.root/"daily_inputs/2026/10/12/base"
        self.base.mkdir(parents=True)
        (self.base/"program_races_20261012.csv").write_text(
            "race_id,deadline\n20261012-22-11,16:05\n20261012-22-12,16:40\n",encoding="utf-8")
        (self.base/"program_entries_20261012.csv").write_text(
            "race_id,boat,registration_no\n"+
            "".join(f"20261012-22-12,{n},{4000+n}\n" for n in range(1,7)),encoding="utf-8")

    def tearDown(self):self.temp.cleanup()

    def snapshot(self,folder,*,received,requested="2026-10-12T16:20:00+09:00",
                 race_id="20261012-22-12"):
        p=self.root/f"daily_inputs/2026/10/12/live/raw/{folder}/beforeinfo_entries_20261012.csv"
        p.parent.mkdir(parents=True,exist_ok=True)
        venue=race_id.split("-")[1];rno=str(int(race_id.split("-")[2]))
        source=f"https://www.boatrace.jp/owpc/pc/race/beforeinfo?hd=20261012&jcd={venue}&rno={rno}"
        p.write_text("race_id,boat,registration_no,requested_at,collected_at,source_url\n"+
            "".join(f"{race_id},{n},{4000+n},{requested},{received},{source}\n" for n in range(1,7)),
            encoding="utf-8")

    def test_predeadline_clocks_consistent_but_never_claim_independent_proof(self):
        self.snapshot("20261012_162202",received="2026-10-12T16:21:33+09:00")
        x=diagnose_saved_day(self.root,"20261012")
        y=next(r for r in x["races"] if r["race_id"]=="20261012-22-12")
        self.assertEqual(y["beforeinfo_state"],"original_folder_time_consistent_not_proven")
        self.assertEqual(y["clock_consistent_snapshot_count"],1)
        self.assertEqual(y["saved_predeadline_boats"],0)
        self.assertFalse(y["official_html_original_archived"])

    def test_copied_old_clock_cannot_count_as_late_new_live_capture(self):
        self.snapshot("20261012_163100",received="2026-10-12T16:21:33+09:00")
        x=diagnose_saved_day(self.root,"20261012")
        y=next(r for r in x["races"] if r["race_id"]=="20261012-22-12")
        self.assertEqual(y["beforeinfo_state"],"original_folder_saved_unverified_time")
        self.assertEqual(y["clock_consistent_snapshot_count"],0)

    def test_postdeadline_cannot_be_labelled_predeadline(self):
        self.snapshot("20261012_164200",requested="2026-10-12T16:40:10+09:00",
                      received="2026-10-12T16:41:10+09:00")
        x=diagnose_saved_day(self.root,"20261012")
        y=next(r for r in x["races"] if r["race_id"]=="20261012-22-12")
        self.assertEqual(y["clock_consistent_snapshot_count"],0)

    def test_missing_schedule_skips_site_without_broken_link(self):
        (self.base/"program_races_20261012.csv").unlink()
        r=stage(self.root,self.site,"20261012")
        self.assertEqual(r["status"],"skipped_no_saved_program")
        self.assertEqual((self.site/"analysis.html").read_text(encoding="utf-8"),self.html)

    def test_existing_research_page_appends_only_quality_link(self):
        r=stage(self.root,self.site,"20261012")
        self.assertEqual(r["status"],"generated")
        self.assertEqual(r["races"],2)
        a=(self.site/"analysis.html").read_text(encoding="utf-8")
        self.assertEqual(a.count("<nav"),1)
        self.assertIn('href="raw_diagnostics.html"',a)
        page=(self.site/"raw_diagnostics.html").read_text(encoding="utf-8")
        self.assertIn("独立証明",page)
        self.assertIn("結果後に復旧",page)
        self.assertTrue((self.site/"raw_diagnostics_summary.json").is_file())
        with self.assertRaisesRegex(ValueError,"already_inserted"):
            stage(self.root,self.site,"20261012")

if __name__=="__main__":unittest.main()
