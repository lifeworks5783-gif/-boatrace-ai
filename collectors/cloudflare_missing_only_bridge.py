"""Isolated Cloudflare D1 fallback bridge. Never edits existing canonical predictions.

Run after the independent Cloudflare Worker has captured verified, complete
official beforeinfo *before the deadline*. Only races missing from the
research-side official decoded snapshots are requested. Output is staged under
live/cloudflare_bridge and is NOT automatically labelled as a prediction.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

JST = timezone(timedelta(hours=9))
BRIDGE_URL = "https://boatrace-v2-collector.life-works5782.workers.dev/admin/research-beforeinfo"
RACE_FIELDS = ("date","venue_code","venue_name","race","race_id","deadline",
    "weather","air_temperature_c","water_temperature_c","wind_speed_mps",
    "wind_direction_code","wind_direction","wave_height_cm","stabilizer",
    "fixed_course","source_url","requested_at","collected_at")
BOAT_FIELDS = ("date","venue_code","venue_name","race","race_id","boat",
    "registration_no","racer_name","weight_kg","exhibition_time","tilt",
    "exhibition_course","exhibition_st_raw","exhibition_st_seconds",
    "exhibition_st_flag","change_parts","is_miss","source_url",
    "requested_at","collected_at")

def read_csv(file):
    if not file.exists(): return []
    with file.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))

def jst_now():
    return datetime.now(JST)

def source_complete(day_dir, day, race_id):
    """Ignore superficial HTTP success: six exhibition times/ST are needed."""
    files=list((day_dir/"live"/"v4_decoded").glob("*/beforeinfo_entries_"+day+".csv"))
    files+=list((day_dir/"live"/"cloudflare_bridge").glob("*/beforeinfo_entries_"+day+".csv"))
    for file in files:
        rows=[r for r in read_csv(file) if r.get("race_id")==race_id]
        if len(rows)==6 and len({r.get("boat") for r in rows})==6 and all(
                r.get("exhibition_time") and r.get("exhibition_course") and
                r.get("exhibition_st_raw") for r in rows if r.get("is_miss","False").lower()!="true"):
            return True
    return False

def plan(root: Path, day: str, now: datetime, horizon_minutes=28):
    day_dir=root/"daily_inputs"/day[:4]/day[4:6]/day[6:]
    base=read_csv(day_dir/"base"/("program_races_"+day+".csv"))
    canonical=read_csv(root/"predictions"/day[:4]/day[4:6]/day[6:]/
                       "live"/("formation_predictions_final_"+day+".csv"))
    live_done={r["race_id"] for r in canonical if r.get("prediction_type")=="直前"}
    selected=[]
    for row in base:
        race_id=row.get("race_id","")
        if not re.fullmatch(day+r"-\d{2}-(0[1-9]|1[0-2])",race_id): continue
        if race_id in live_done or source_complete(day_dir,day,race_id): continue
        try:
            cutoff=datetime.strptime(day+" "+row["deadline"],"%Y%m%d %H:%M").replace(tzinfo=JST)
            remaining=(cutoff-now).total_seconds()
        except (ValueError,KeyError): continue
        if 0<remaining<=horizon_minutes*60:
            selected.append(row)
    return sorted(selected,key=lambda x:(x["deadline"],x["race_id"]))

def iso(ms):
    return datetime.fromtimestamp(ms/1000,JST).isoformat()

def validate(item, expected, day, now):
    """Verify original bytes digest, six identities and both official timestamps."""
    raw=item.get("snapshot_json")
    if not isinstance(raw,str) or len(raw)>200000: raise ValueError("snapshot_absent_or_oversized")
    if hashlib.sha256(raw.encode("utf-8")).hexdigest()!=item.get("snapshot_sha256"):
        raise ValueError("raw_snapshot_sha256_mismatch")
    s=json.loads(raw)
    rid=expected["race_id"]
    venue=int(expected["venue_code"])
    num=int(expected["race"])
    deadline=datetime.strptime(day+" "+expected["deadline"],"%Y%m%d %H:%M").replace(tzinfo=JST)
    ms=int(deadline.timestamp()*1000)
    if item.get("race_id")!=rid or s.get("race_id")!=rid or s.get("race_date")!=day:
        raise ValueError("race_identity_mismatch")
    if s.get("deadline_ms")!=ms or s.get("provenance")!="official_observed_before_deadline":
        raise ValueError("source_provenance_invalid")
    requested=s.get("requested_ms")
    collected=s.get("collected_ms")
    if not all(isinstance(x,int) and not isinstance(x,bool) for x in (requested,collected)) or not requested<=collected<ms:
        raise ValueError("not_observed_before_deadline")
    # Never make an after-cutoff import appear to be a live prediction.
    if not now<deadline: raise ValueError("race_deadline_passed")
    source=s.get("source_url","")
    if not source.startswith("https://www.boatrace.jp/owpc/pc/race/beforeinfo?"):
        raise ValueError("not_official_source")
    from urllib.parse import urlparse,parse_qs
    q=parse_qs(urlparse(source).query)
    if q.get("hd")!=[day] or q.get("jcd")!=[f"{venue:02d}"] or q.get("rno")!=[str(num)]:
        raise ValueError("official_source_race_mismatch")
    boats=s.get("entries")
    if not isinstance(boats,list) or len(boats)!=6 or {b.get("boat") for b in boats}!={1,2,3,4,5,6}:
        raise ValueError("missing_six_boats")
    if any(not str(b.get("registration_no","")).isdigit() or not b.get("racer_name") or
           (not b.get("is_miss") and (b.get("exhibition_time") is None or
             b.get("exhibition_course") not in (1,2,3,4,5,6) or
             not b.get("exhibition_st_raw"))) for b in boats):
        raise ValueError("unready_exhibition")
    env=s.get("environment") or {}
    if any(env.get(k) is None for k in ("air_temperature_c","water_temperature_c","wind_speed_mps","wave_height_cm")):
        raise ValueError("weather_incomplete")
    return s

def make_rows(s, row):
    day=s["race_date"];rid=s["race_id"];p=s["source_url"]
    common={"date":day,"venue_code":row["venue_code"],"venue_name":row["venue_name"],
       "race":row["race"],"race_id":rid,"source_url":p,
       "requested_at":iso(s["requested_ms"]),"collected_at":iso(s["collected_ms"])}
    e=s["environment"]
    a={**common,"deadline":row["deadline"],**e}
    return a,[{**common,**b} for b in s["entries"]]

def fetch_batch(url,token,day,ids):
    query=urlencode({"date":day,"race_ids":",".join(ids)})
    request=Request(url+"?"+query,headers={"Authorization":"Bearer "+token,
        "Accept":"application/json","User-Agent":"BoatraceMissingOnlyBridge/1"})
    with urlopen(request,timeout=12) as reply: raw=reply.read(650000)
    if len(raw)>640000: raise RuntimeError("response_too_large")
    data=json.loads(raw)
    if data.get("schema")!="boatrace-research-beforeinfo-bridge-v1" or data.get("date")!=day:
        raise RuntimeError("unexpected_backup_response")
    if data.get("status") not in ("up","degraded"): raise RuntimeError("backup_status_invalid")
    return data

def write_csv(path,rows,fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as out:
        writer=csv.DictWriter(out,fieldnames=fields,extrasaction="ignore")
        writer.writeheader();writer.writerows(rows)

def run(root,day,now,token,url=BRIDGE_URL):
    if not re.fullmatch(r"\d{8}",day) or now.strftime("%Y%m%d")!=day:
        raise ValueError("bridge_only_current_jst_day")
    candidates=plan(root,day,now)
    if not candidates:return {"status":"nothing_missing_in_window","selected":0,"imported":0}
    if not token: raise RuntimeError("CLOUDFLARE_BACKUP_TOKEN not configured; no backup import attempted")
    by_id={r["race_id"]:r for r in candidates}
    received={}
    not_available=[];rejected=[]
    for offset in range(0,len(candidates),8):
        ids=[r["race_id"] for r in candidates[offset:offset+8]]
        data=fetch_batch(url,token,day,ids)
        not_available.extend(data.get("missing_ids",[]))
        rejected.extend(data.get("rejected",[]))
        for item in data.get("snapshots",[]):
            rid=item.get("race_id")
            if rid not in ids or rid in received: raise RuntimeError("unrequested_or_duplicate_backup_race")
            # Re-evaluate deadline now, not when the request was planned.
            received[rid]=validate(item,by_id[rid],day,jst_now())
    if not received:
        return {"status":"waiting_verified_cloudflare_snapshot","selected":len(candidates),
            "imported":0,"not_available":not_available,"rejected":rejected}
    stamp=jst_now().strftime("%Y%m%d_%H%M%S")
    dest=root/"daily_inputs"/day[:4]/day[4:6]/day[6:]/"live"/"cloudflare_bridge"/stamp
    races=[];boats=[]
    for rid in sorted(received):
        a,b=make_rows(received[rid],by_id[rid]);races.append(a);boats.extend(b)
    write_csv(dest/("beforeinfo_races_"+day+".csv"),races,RACE_FIELDS)
    write_csv(dest/("beforeinfo_entries_"+day+".csv"),boats,BOAT_FIELDS)
    receipt={"schema":"research-cloudflare-missing-only-v1","date":day,"status":"staged_only",
       "selected":len(candidates),"imported":len(races),"race_ids":sorted(received),
       "not_available":not_available,"rejected":rejected,
       "prediction_generated":False,"canonical_modified":False}
    (dest/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {**receipt,"staged_path":str(dest.relative_to(root))}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=".")
    p.add_argument("--date",default=jst_now().strftime("%Y%m%d"))
    p.add_argument("--url",default=BRIDGE_URL)
    args=p.parse_args()
    result=run(Path(args.root),args.date,jst_now(),os.getenv("CLOUDFLARE_BACKUP_TOKEN"),args.url)
    print(json.dumps(result,ensure_ascii=False))

if __name__=="__main__": main()
