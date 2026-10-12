"""Standalone research diagnostics: no live UI, no raw HTML in report."""
import json
import tempfile
import unittest
from pathlib import Path
from raw_collector.diagnostics_view import build_page, render_dashboard, summarize_quality

def payload(*,archive="local_ephemeral_unarchived",date="20261012",rows=None):
    return {"schema":"boatrace-normalized-v1","date":date,
            "source_archive":archive,"races":rows if rows is not None else []}

def race(rid,st,issues=None,verified=False,boats=6):
    return {"race_id":rid,"parse_status":st,
            "boats":[{"boat":i+1} for i in range(boats)],
            "source":{"source_url":"https://www.boatrace.jp/owpc/pc/race/beforeinfo",
                      "raw_sha256":"a"*64,"collected_at":"2026-10-12T15:32:00+09:00",
                      "parser":"today_beforeinfo_parse_beforeinfo_v1",
                      "drive_raw_verified":verified},
            "diagnostics":{"schema":"boatrace-parser-audit-v1",
                           "ready_live_inputs":st=="ready_live_inputs",
                           "issues":issues or []}}

class ResearchDiagnosticViewTests(unittest.TestCase):
    def test_no_rows_cannot_be_called_all_good(self):
        body=render_dashboard(payload())
        self.assertIn("診断対象データがありません",body)
        self.assertIn("公式開催レース全体の取得率ではありません",body)
        self.assertNotIn("全レース正常です",body)

    def test_distinct_good_error_missing_and_archive_state(self):
        rows=[
            race("20261012-22-10","ready_live_inputs",verified=True),
            race("20261012-22-11","unparsed",
                 issues=[{"code":"unknown_st_notation","field":"exhibition_st_raw","boat":3}]),
            race("20261012-22-12","schedule_missing",
                 issues=[{"code":"schedule_missing","field":"program_races"}],boats=0),
        ]
        x=payload(rows=rows)
        summary=summarize_quality(x)
        self.assertEqual((summary["total"],summary["ready"],summary["needs_review"]),(3,1,2))
        self.assertEqual(summary["drive_verified_count"],1)
        self.assertIsNone(summary["not_collected_count"])
        html=render_dashboard(x)
        for phrase in ("読取正常","読取不能","朝番組不足","3号艇・展示STの未知の表記",
                       "Drive照合済み","永続保存未確認","【検証専用】"):
            self.assertIn(phrase,html)

    def test_last_ready_separate_from_new_unparsed_observation(self):
        row=race("20261012-22-12","unparsed",
                 issues=[{"code":"parser_unhandled_exception","field":"beforeinfo"}])
        row["last_ready"]={"source":{"collected_at":"2026-10-12T15:20:00+09:00"},
                           "race":{"wind_speed_mps":4},"boats":[{"boat":1}]}
        html=render_dashboard(payload(rows=[row]))
        self.assertIn("最後の正常読取",html)
        self.assertIn("15:20:00",html)
        self.assertIn("以前の観測であり、現在の表示値ではありません",html)
        self.assertIn("読取不能",html)

    def test_html_is_escaped_in_every_free_text_field(self):
        row=race("20261012-22-12","unparsed",
                 issues=[{"code":"<script>alert(1)</script>","field":"x"}])
        row["source"]["parser"]='"><img src=x onerror=alert(1)>'
        result=render_dashboard(payload(rows=[row]))
        self.assertNotIn("<script>alert(1)</script>",result)
        self.assertNotIn('<img src=x onerror=alert(1)>',result)
        self.assertIn("&lt;script&gt;",result)
        self.assertIn("&lt;img",result)

    def test_build_page_writes_small_html_and_json_only(self):
        with tempfile.TemporaryDirectory() as work:
            root=Path(work)
            source=root/"snapshot.json"
            x=payload(rows=[race("20261012-22-12","ready_live_inputs")])
            source.write_text(json.dumps(x,ensure_ascii=False),encoding="utf-8")
            output=build_page(source,root/"display")
            self.assertEqual((output["ready"],output["total"]),(1,1))
            self.assertTrue((root/"display"/"raw_diagnostics.html").is_file())
            public=(root/"display"/"raw_diagnostics_summary.json").read_text(encoding="utf-8")
            self.assertNotIn("original_html",public)
            self.assertIn("needs_review",public)

    def test_incorrect_schema_or_invalid_race_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"unsupported"):
            summarize_quality({"schema":"unknown","date":"20261012","races":[]})
        with self.assertRaisesRegex(ValueError,"invalid_quality_race_id"):
            summarize_quality(payload(rows=[race("20261012-22-99","ready_live_inputs")]))

if __name__=="__main__":unittest.main()
