"""Offline checks for bounded URL planning with no website fetching."""
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from raw_collector.plan import candidate_urls, official_schedule_path

class BoundedPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        p=official_schedule_path(self.root,"20261012")
        p.parent.mkdir(parents=True)
        p.write_text("race_id,deadline\n20261012-22-12,16:40\n20261012-22-11,16:05\n20261012-22-10,15:40\n20261012-02-12,16:30\n",encoding="utf-8")
    def tearDown(self):
        self.tmp.cleanup()
    def test_actual_known_race_time_maps_to_valid_official_beforeinfo_url(self):
        now=datetime.fromisoformat("2026-10-12T16:25:00+09:00")
        rows=candidate_urls(self.root,"20261012",now,venues={"22"})
        self.assertEqual(rows[0]["race_id"],"20261012-22-12")
        self.assertEqual(rows[0]["source_kind"],"beforeinfo")
        self.assertIn("jcd=22", rows[0]["url"])
        self.assertIn("rno=12", rows[0]["url"])
    def test_never_plan_late_race_as_predeadline(self):
        now=datetime.fromisoformat("2026-10-12T16:41:00+09:00")
        self.assertEqual(candidate_urls(self.root,"20261012",now,venues={"22"}),[])
    def test_plan_is_bounded_and_favors_near_cutoffs(self):
        now=datetime.fromisoformat("2026-10-12T16:15:00+09:00")
        rows=candidate_urls(self.root,"20261012",now,max_requests=1)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["source_kind"],"beforeinfo")
        self.assertEqual(rows[0]["race_id"],"20261012-02-12")
    def test_refuse_naive_timezone_and_zero_limit(self):
        with self.assertRaises(ValueError):
            candidate_urls(self.root,"20261012",datetime(2026,10,12,16,25))
        with self.assertRaises(ValueError):
            candidate_urls(self.root,"20261012",datetime.fromisoformat("2026-10-12T16:25:00+09:00"),max_requests=0)
if __name__=="__main__":
    unittest.main()
