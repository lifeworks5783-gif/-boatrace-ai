import csv
import hashlib
import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from collectors import cloudflare_button_fallback as m
from collectors import cloudflare_missing_only_bridge as bridge

JST=timezone(timedelta(hours=9));DAY="20261013"
NOW=datetime(2026,10,13,8,48,tzinfo=JST)
RID=DAY+"-14-02";CUTOFF=datetime(2026,10,13,9,1,tzinfo=JST)

def write(path,fields,rows):
  path.parent.mkdir(parents=True,exist_ok=True)
  with path.open("w",encoding="utf-8",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def seed(root,complete_primary=False):
  d=root/"data"
  write(d/("program_races_"+DAY+".csv"),["race_id","venue_code","venue_name","race","deadline"],
    [{"race_id":RID,"venue_code":"14","venue_name":"鳴門","race":"2","deadline":"09:01"}])
  write(d/("program_entries_"+DAY+".csv"),["race_id","boat","registration_no"],
    [{"race_id":RID,"boat":i,"registration_no":str(5000+i)} for i in range(1,7)])
  if complete_primary:
    write(d/("beforeinfo_races_"+DAY+".csv"),bridge.RACE_FIELDS,
       [{"date":DAY,"venue_code":"14","venue_name":"鳴門","race":"2","race_id":RID,"deadline":"09:01",
         "requested_at":NOW.isoformat(),"collected_at":NOW.isoformat()}])
    write(d/("beforeinfo_entries_"+DAY+".csv"),bridge.BOAT_FIELDS,
      [{"race_id":RID,"boat":i,"registration_no":str(5000+i),"racer_name":str(i),"exhibition_time":6.81,
        "exhibition_st_raw":".13","exhibition_course":i} for i in range(1,7)])
  (d/("beforeinfo_validation_"+DAY+".json")).write_text(json.dumps({
    "status":"PASS","new_ready_races":1 if complete_primary else 0,
    "unready_new_races":[] if complete_primary else [RID],
    "unready_new_count":0 if complete_primary else 1
  }),encoding="utf-8")
def official():
  cutoff_ms=int(CUTOFF.timestamp()*1000)
  first_ms=int((NOW-timedelta(minutes=3)).timestamp()*1000)
  body={"race_id":RID,"race_date":DAY,"deadline_ms":cutoff_ms,"requested_ms":first_ms,
    "collected_ms":first_ms+3000,"source_url":
    "https://www.boatrace.jp/owpc/pc/race/beforeinfo?hd=20261013&jcd=14&rno=2",
    "provenance":"official_observed_before_deadline",
    "environment":{"weather":"晴","air_temperature_c":20,"water_temperature_c":24,"wind_speed_mps":1,
      "wave_height_cm":1,"stabilizer":False,"fixed_course":False},
    "entries":[{"boat":i,"registration_no":str(5000+i),"racer_name":"Name"+str(i),"exhibition_time":6.8,
      "exhibition_course":i,"exhibition_st_raw":".11","exhibition_st_seconds":0.11,"is_miss":False}
       for i in range(1,7)]}
  raw=json.dumps(body,ensure_ascii=False,separators=(",",":"))
  return {"race_id":RID,"snapshot_json":raw,"snapshot_sha256":hashlib.sha256(raw.encode()).hexdigest()}
def response(url,token,day,ids):
  assert url.startswith("https://") and token is None and ids==[RID]
  return {"schema":"boatrace-public-official-beforeinfo-v1","date":DAY,"status":"up",
          "snapshots":[official()],"missing_ids":[],"not_eligible_ids":[],"rejected":[]}

class ButtonFallbackTests(unittest.TestCase):
  def test_primary_complete_never_overwritten_or_network_requested(self):
    with tempfile.TemporaryDirectory() as d:
      root=Path(d);seed(root,True)
      before=(root/"data"/("beforeinfo_entries_"+DAY+".csv")).read_bytes()
      result=m.import_missing_only(root,DAY,NOW,fetch=lambda *_: self.fail("must not query backup"))
      self.assertEqual(result["selected"],0)
      self.assertEqual((root/"data"/("beforeinfo_entries_"+DAY+".csv")).read_bytes(),before)

  def test_missing_primary_gets_verified_official_staging_and_raw_for_prediction(self):
    with tempfile.TemporaryDirectory() as d:
      root=Path(d);seed(root)
      orig=bridge.jst_now;bridge.jst_now=lambda:NOW
      try:result=m.import_missing_only(root,DAY,NOW,fetch=response)
      finally:bridge.jst_now=orig
      self.assertEqual(result["status"],"input_merged")
      self.assertEqual(result["imported"],1)
      rows=bridge.read_csv(root/"data"/("beforeinfo_entries_"+DAY+".csv"))
      self.assertEqual(len(rows),6)
      self.assertEqual({r["race_id"] for r in rows},{RID})
      self.assertEqual(rows[0]["exhibition_time"],"6.8")
      validation=json.loads((root/"data"/("beforeinfo_validation_"+DAY+".json")).read_text())
      self.assertEqual(validation["new_ready_races"],1)
      self.assertEqual(validation["unready_new_count"],0)
      self.assertFalse((root/"predictions").exists())
      self.assertEqual(len(list((root/"daily_inputs").rglob("receipt.json"))),1)

  def test_missing_cloudflare_data_never_changes_primary_files(self):
    with tempfile.TemporaryDirectory() as d:
      root=Path(d);seed(root)
      empty=lambda *_:{"schema":"boatrace-public-official-beforeinfo-v1","date":DAY,
        "status":"up","snapshots":[],"missing_ids":[RID],"not_eligible_ids":[],"rejected":[]}
      r=m.import_missing_only(root,DAY,NOW,fetch=empty)
      self.assertEqual(r["imported"],0)
      self.assertFalse((root/"data"/("beforeinfo_entries_"+DAY+".csv")).exists())

  def test_invalid_hash_never_produces_prediction_input(self):
    with tempfile.TemporaryDirectory() as d:
      root=Path(d);seed(root)
      item=official();item["snapshot_sha256"]="f"*64
      bad=lambda *_:{"schema":"boatrace-public-official-beforeinfo-v1","date":DAY,
        "status":"up","snapshots":[item],"missing_ids":[],"not_eligible_ids":[],"rejected":[]}
      with self.assertRaisesRegex(ValueError,"sha256"):
        m.import_missing_only(root,DAY,NOW,fetch=bad)
      self.assertFalse((root/"data"/("beforeinfo_entries_"+DAY+".csv")).exists())

if __name__=="__main__":unittest.main()
