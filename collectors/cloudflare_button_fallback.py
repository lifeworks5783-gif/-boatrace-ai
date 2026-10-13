"""Button-only secondary official source. Never recalculates scores or signals.

After the existing official live collector, ask Cloudflare for immutable, already
captured official exhibitions only when six complete primary boats are absent.
Keep original timestamps and source evidence; no after-deadline retroactive scoring.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collectors import cloudflare_missing_only_bridge as bridge
from collectors import today_beforeinfo as official

JST=timezone(timedelta(hours=9))
URL="https://boatrace-v2-collector.life-works5782.workers.dev/public/official-beforeinfo"
def complete(entries,rid):
    a=[x for x in entries if x.get("race_id")==rid]
    if len(a)!=6 or {str(x.get("boat")) for x in a}!={"1","2","3","4","5","6"}:return False
    return all(x.get("registration_no") and (
      str(x.get("is_miss","")).lower() in ("true","1","yes") or all(
        str(x.get(k,"")).strip() for k in ("exhibition_course","exhibition_time","exhibition_st_raw")
      )) for x in a)
def import_missing_only(root,day,now,endpoint=URL,fetch=bridge.fetch_batch):
    if not re.fullmatch(r"\d{8}",day) or day!=now.strftime("%Y%m%d"):
        raise ValueError("current_jst_day_only")
    data=root/"data"
    program=bridge.read_csv(data/("program_races_"+day+".csv"))
    if not program:
        program=bridge.read_csv(root/"daily_inputs"/day[:4]/day[4:6]/day[6:]/"base"/("program_races_"+day+".csv"))
    current_races=bridge.read_csv(data/("beforeinfo_races_"+day+".csv"))
    current_entries=bridge.read_csv(data/("beforeinfo_entries_"+day+".csv"))
    known_races={r.get("race_id") for r in current_races}
    canonical=bridge.read_csv(root/"predictions"/day[:4]/day[4:6]/day[6:]/
       "live"/("formation_predictions_final_"+day+".csv"))
    predicted={r.get("race_id") for r in canonical if r.get("prediction_type")=="直前"}
    base_boats=bridge.read_csv(data/("program_entries_"+day+".csv"))
    registrations={(r.get("race_id"),str(r.get("boat"))):str(r.get("registration_no")) for r in base_boats}
    missing=[]
    for r in program:
        rid=r.get("race_id","")
        if not re.fullmatch(day+r"-\d{2}-(0[1-9]|1[0-2])",rid):continue
        if rid in predicted or (rid in known_races and complete(current_entries,rid)):continue
        try:
            cutoff=datetime.strptime(day+" "+r["deadline"],"%Y%m%d %H:%M").replace(tzinfo=JST)
        except (KeyError,ValueError):continue
        if 10<(cutoff-now).total_seconds()<=28*60:
            missing.append(r)
    missing.sort(key=lambda r:(r["deadline"],r["race_id"]))
    if not missing:
        return {"status":"no_current_missing","selected":0,"imported":0}
    imported_races=[];imported_entries=[];not_saved=[];not_eligible=[];rejected=[]
    for i in range(0,len(missing),4):
        subset=missing[i:i+4]
        response=fetch(endpoint,None,day,[r["race_id"] for r in subset])
        if response.get("schema")!="boatrace-public-official-beforeinfo-v1" or response.get("date")!=day:
            raise ValueError("unexpected_public_official_response")
        byid={r["race_id"]:r for r in subset}
        not_saved.extend(response.get("missing_ids",[]))
        not_eligible.extend(response.get("not_eligible_ids",[]))
        rejected.extend(response.get("rejected",[]))
        got=set()
        for item in response.get("snapshots",[]):
            rid=item.get("race_id")
            if rid not in byid or rid in got:raise ValueError("unexpected_or_duplicate_public_race")
            got.add(rid)
            # Use current wall-clock, never the workflow's earlier timestamp.
            snap=bridge.validate(item,byid[rid],day,bridge.jst_now())
            for e in snap["entries"]:
                expected=registrations.get((rid,str(e["boat"])))
                if expected and expected!=str(e["registration_no"]):
                    raise ValueError("official_program_identity_mismatch:"+rid)
            a,b=bridge.make_rows(snap,byid[rid])
            imported_races.append(a);imported_entries.extend(b)
    if not imported_races:
        return {"status":"cloudflare_not_ready","selected":len(missing),"imported":0,
          "missing_ids":not_saved,"not_eligible_ids":not_eligible,"rejected":rejected}
    new_races=official.merge_rows(current_races,imported_races,("race_id",))
    new_entries=official.merge_official_beforeinfo_entries(current_entries,imported_entries)
    check=official.validate(new_races,new_entries)
    if check["status"]!="PASS":raise ValueError("merged_official_validation_failed:"+str(check["errors"]))
    for race in imported_races:
        if not complete(new_entries,race["race_id"]):
            raise ValueError("merged_backup_no_longer_complete:"+race["race_id"])
    # Existing scorer reads these exact original data/ files. Preserve the
    # existing source if it was complete, and never modify model config.
    official.write_csv(data/("beforeinfo_races_"+day+".csv"),new_races,official.RACE_FIELDS)
    official.write_csv(data/("beforeinfo_entries_"+day+".csv"),new_entries,official.ENTRY_FIELDS)
    valpath=data/("beforeinfo_validation_"+day+".json")
    validation=json.loads(valpath.read_text()) if valpath.exists() else {}
    validation.update({k:v for k,v in check.items() if k in ("status","stored_races","stored_entries","errors")})
    validation["new_ready_races"]=int(validation.get("new_ready_races",0))+len(imported_races)
    unready=set(validation.get("unready_new_races") or [])-{r["race_id"] for r in imported_races}
    validation["unready_new_races"]=sorted(unready)
    validation["unready_new_count"]=len(unready)
    validation["cloudflare_backup_imported"]=len(imported_races)
    validation["cloudflare_backup_source"]="stored_official_predeadline_only"
    valpath.write_text(json.dumps(validation,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    stamp=bridge.jst_now().strftime("%Y%m%d_%H%M%S")
    archive=root/"daily_inputs"/day[:4]/day[4:6]/day[6:]/"live"/"cloudflare_bridge"/stamp
    archive.mkdir(parents=True,exist_ok=True)
    bridge.write_csv(archive/("beforeinfo_races_"+day+".csv"),imported_races,bridge.RACE_FIELDS)
    bridge.write_csv(archive/("beforeinfo_entries_"+day+".csv"),imported_entries,bridge.BOAT_FIELDS)
    receipt={"schema":"button-cloudflare-missing-only-v1","date":day,"status":"input_merged",
      "selected":len(missing),"imported":len(imported_races),
      "race_ids":[r["race_id"] for r in imported_races],
      "missing_ids":not_saved,"not_eligible_ids":not_eligible,"rejected":rejected,
      "existing_primary_complete_preserved":True,"no_score_formula_change":True}
    (archive/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return receipt

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",default=bridge.jst_now().strftime("%Y%m%d"))
    p.add_argument("--root",default=".")
    a=p.parse_args()
    print(json.dumps(import_missing_only(Path(a.root),a.date,bridge.jst_now()),ensure_ascii=False))

if __name__=="__main__": main()
