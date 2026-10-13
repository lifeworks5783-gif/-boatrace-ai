import csv
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collectors import cloudflare_missing_only_bridge as bridge

JST=timezone(timedelta(hours=9))
DAY="20261013"
RID=DAY+"-14-02"
NOW=datetime(2026,10,13,8,48,tzinfo=JST)
DEADLINE=datetime(2026,10,13,9,1,tzinfo=JST)
def seed(root):
    d=root/"daily_inputs"/"2026"/"10"/"13"/"base"
    d.mkdir(parents=True)
    with (d/("program_races_"+DAY+".csv")).open("w",newline="",encoding="utf-8") as out:
        w=csv.DictWriter(out,fieldnames=["race_id","venue_code","venue_name","race","deadline"])
        w.writeheader()
        w.writerow({"race_id":RID,"venue_code":"14","venue_name":"鳴門","race":"2","deadline":"09:01"})

def backup_item(**overrides):
    stamp=int(datetime(2026,10,13,8,45,tzinfo=JST).timestamp()*1000)
    snap={"race_id":RID,"race_date":DAY,"deadline_ms":int(DEADLINE.timestamp()*1000),
          "requested_ms":stamp,"collected_ms":stamp+12000,
          "source_url":"https://www.boatrace.jp/owpc/pc/race/beforeinfo?hd=20261013&jcd=14&rno=2",
          "provenance":"official_observed_before_deadline",
          "environment":{"weather":"晴","air_temperature_c":20,"water_temperature_c":24,"wind_speed_mps":1,"wave_height_cm":1},
          "entries":[{"boat":i,"registration_no":str(5000+i),"racer_name":"R"+str(i),
               "exhibition_time":6.8,"exhibition_course":i,"exhibition_st_raw":".12",
               "exhibition_st_seconds":.12,"is_miss":False} for i in range(1,7)]}
    snap.update(overrides)
    raw=json.dumps(snap,ensure_ascii=False,separators=(",",":"))
    return {"race_id":RID,"snapshot_json":raw,"snapshot_sha256":hashlib.sha256(raw.encode()).hexdigest()}

class CloudflareBridgeTests(unittest.TestCase):
    def test_missing_only_window(self):
        with tempfile.TemporaryDirectory() as x:
            root=Path(x);seed(root)
            self.assertEqual([x["race_id"] for x in bridge.plan(root,DAY,NOW)],[RID])
            self.assertEqual(bridge.plan(root,DAY,DEADLINE),[])

    def test_known_live_prediction_not_retrieved_again(self):
        with tempfile.TemporaryDirectory() as x:
            root=Path(x);seed(root)
            p=root/"predictions"/"2026"/"10"/"13"/"live"/("formation_predictions_final_"+DAY+".csv")
            p.parent.mkdir(parents=True)
            p.write_text("race_id,prediction_type\n"+RID+",直前\n",encoding="utf-8")
            self.assertEqual(bridge.plan(root,DAY,NOW),[])

    def test_complete_primary_snapshot_not_retrieved_again(self):
        with tempfile.TemporaryDirectory() as x:
            root=Path(x);seed(root)
            p=root/"daily_inputs"/"2026"/"10"/"13"/"live"/"v4_decoded"/"test"/("beforeinfo_entries_"+DAY+".csv")
            p.parent.mkdir(parents=True)
            with p.open("w",newline="",encoding="utf-8") as out:
                w=csv.DictWriter(out,fieldnames=["race_id","boat","exhibition_time","exhibition_course","exhibition_st_raw","is_miss"])
                w.writeheader()
                for boat in range(1,7):w.writerow({"race_id":RID,"boat":boat,"exhibition_time":"6.81","exhibition_course":boat,"exhibition_st_raw":".12","is_miss":"False"})
            self.assertEqual(bridge.plan(root,DAY,NOW),[])

    def test_verified_input_and_integrity_fail_closed(self):
        good=backup_item()
        expected={"race_id":RID,"venue_code":"14","venue_name":"鳴門","race":"2","deadline":"09:01"}
        result=bridge.validate(good,expected,DAY,NOW)
        self.assertEqual(len(result["entries"]),6)
        tampered=dict(good)
        tampered["snapshot_json"]+= " "
        with self.assertRaisesRegex(ValueError,"sha256"): bridge.validate(tampered,expected,DAY,NOW)
        with self.assertRaisesRegex(ValueError,"deadline"):bridge.validate(good,expected,DAY,DEADLINE)
        late=backup_item(collected_ms=int(DEADLINE.timestamp()*1000)+100)
        with self.assertRaisesRegex(ValueError,"not_observed"):bridge.validate(late,expected,DAY,NOW)

    def test_staged_only_does_not_modify_canonical(self):
        with tempfile.TemporaryDirectory() as x:
            root=Path(x);seed(root)
            old=bridge.fetch_batch
            try:
                bridge.fetch_batch=lambda *args:{"schema":"boatrace-research-beforeinfo-bridge-v1",
                    "date":DAY,"status":"up","snapshots":[backup_item()],"missing_ids":[],"rejected":[]}
                # Runtime cutoff should be checked using the injected value for this fixed test.
                old_now=bridge.jst_now
                bridge.jst_now=lambda:NOW
                try: r=bridge.run(root,DAY,NOW,"secret")
                finally:bridge.jst_now=old_now
                self.assertEqual(r["imported"],1)
                self.assertFalse(r["canonical_modified"])
                self.assertEqual(len(list((root/"daily_inputs").rglob("beforeinfo_entries_"+DAY+".csv"))),1)
                self.assertFalse((root/"predictions").exists())
            finally: bridge.fetch_batch=old

if __name__=="__main__":unittest.main()
