"""Full-day RESEARCH dry-run of existing saved data + bounded official missing pages.

No race results as predictors, no raw HTML publication, no production commits.
Official website fetch only for gaps lacking any saved decoded beforeinfo;
postdeadline observations are NEVER credited as historic live predictions.
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlencode

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"collectors"))
from raw_collector.saved_research_adapter import diagnose_saved_day
from collectors.official_race_conditions import classify_race
from collectors import race_prediction_store as store
from collectors import build_latest_prediction_view as latest
from collectors import today_beforeinfo as beforeinfo

JST=timezone(timedelta(hours=9))
def load_rows(path):
    if not path.exists():return []
    with path.open(encoding="utf-8-sig",newline="") as stream:
        return list(csv.DictReader(stream))
def as_cutoff(date,row):
    try:return datetime.strptime(date+" "+row["deadline"],"%Y%m%d %H:%M").replace(tzinfo=JST)
    except (KeyError,TypeError,ValueError):return None

def replay_predictions(day,root):
    report={"schema":"boatrace-research-replay-v1","date":day,"mode":"research_only",
            "no_retroactive_live_claim":True,"count":{},"details":[]}
    canon=store.load_canonical(day,root=root/"predictions")
    records=canon["races"]
    config=latest.load_signal_ai_config()
    stats=Counter()
    for race in records:
        rid=str(race.get("race_id") or "")
        stat={"race_id":rid,"result_as_input":False}
        boats=latest.ranked_boats(race)
        stat["score_count"]=len(boats)
        quality=race.get("prediction_quality") or {}
        stat["verified_scratches"]=quality.get("verified_scratched_boats") or []
        actual=(race.get("up_signal") or {},race.get("down_signal") or {})
        if len(boats)>=3 and all(
          latest.to_float(row.get("score")) is not None for row in boats
        ):
            stats["normal_scoring_present"]+=1
            stat["normal"]="score_available"
        else:
            stat["normal"]="scores_missing_or_field_below_three"
            stats["normal_not_ready"]+=1
        try:
            up=latest.build_up_signal(boats,quality)
            down=latest.build_down_signal(boats,quality)
            stat["replayed_ability"]={
                "raijin_available":bool(up.get("available")),
                "fujin_available":bool(down.get("available")),
                "raijin_level":int(up.get("level") or 0),
                "fujin_level":int(down.get("level") or 0)
            }
            if not up.get("available") or not down.get("available"):
                stats["signal_requires_condition_or_verified_scores"]+=1
            else:
                stats["detector_executed"]+=1
            if int(up.get("level") or 0) or int(down.get("level") or 0):
                stats["replayed_triggered"]+=1
                signal=latest.build_signal_ai_prediction(boats,up,down,config)
                if signal is None:
                    stats["signal_ai_missing"]+=1
                    stat["signal_ai_error"]="not_generated"
                else:
                    buys=signal.get("combinations") or []
                    stat["signal_ai_points"]=len(buys)
                    stat["signal_ai_valid_universe"]=len(signal.get("all_120_combinations") or [])
                    if len(buys)==24 and len({x.get("combination") for x in buys})==24:
                        stats["signal_ai_24_valid"]+=1
                    else:
                        stats["signal_ai_incomplete"]+=1
                    stat["normal_unchanged"]=bool(signal.get("normal_prediction_unchanged"))
            else:
                stat["signal_ai_status"]="not_applicable_no_trigger"
                stats["signal_untriggered"]+=1
        except Exception as e:
            stat["replay_error"]=type(e).__name__+":"+str(e)[:140]
            stats["replay_error"]+=1
        stat["stored_signal_audit"]=store.audit_race(race)
        if stat["stored_signal_audit"]["signal_ai_status"]=="missing_or_invalid_signal_24":
            stats["stored_signal_24_invalid"]+=1
        report["details"].append(stat)
    stats["canonical_races"]=len(records)
    report["count"]=dict(stats)
    return report

def survey_gaps(day,root,clock,max_fetch):
    base=root/"daily_inputs"/day[:4]/day[4:6]/day[6:8]/"base"
    races=load_rows(base/f"program_races_{day}.csv")
    known=diagnose_saved_day(root,day)
    byid={x["race_id"]:x for x in known["races"]}
    choices=[]
    for row in races:
        rid=row.get("race_id")
        deadline=as_cutoff(day,row)
        if rid not in byid or deadline is None or deadline>clock:continue
        if byid[rid]["beforeinfo_state"]!="no_saved_beforeinfo":continue
        choices.append((deadline,rid,row))
    choices.sort()
    out={"as_of":clock.isoformat(),"eligible_missing":len(choices),
         "official_attempted":0,"retrieved_now":0,
         "official_page_no_useable_beforeinfo":0,"official_connection_failed":0,
         "not_attempted_due_to_bound":max(0,len(choices)-max_fetch),
         "retrospective_only":True,"results":[]}
    for index,(_,rid,row) in enumerate(choices[:max_fetch],1):
        if index>1:time.sleep(1.1)
        url=(f"https://www.boatrace.jp/owpc/pc/race/beforeinfo?"+
             urlencode({"hd":day,"jcd":row["venue_code"],"rno":row["race"]}))
        entry={"race_id":rid,"source_url":url,
               "acquisition":"after_original_deadline_retrospective_only"}
        out["official_attempted"]+=1
        try:
            import requests
            response=requests.get(url,headers={"User-Agent":"BoatRaceResearchAudit/1.0",
                         "Accept":"text/html"},timeout=12)
            entry["http_status"]=response.status_code
            entry["retrieved_at"]=datetime.now(JST).isoformat()
            response.raise_for_status()
            if len(response.content)>1_500_000:raise ValueError("response_oversized")
            start=datetime.now(JST).isoformat()
            base_info={
                "date":day,"venue_code":row["venue_code"],
                "venue_name":row["venue_name"],"race":int(row["race"]),
                "race_id":rid,"deadline":row["deadline"]
            }
            parsed=beforeinfo.parse_beforeinfo(response.text,base_info,start)
            if parsed:
                context,entries=parsed
                info=classify_race(entries=entries)
                entry["row_count"]=len(entries)
                entry["active_count"]=len(info["active_lanes"])
                entry["events"]=info["events"]
                entry["has_weather"]=any(context.get(k) is not None for k in
                                            ("air_temperature_c","wind_speed_mps","water_temperature_c"))
                entry["status"]="retrospective_decoded"
                # Data values only. Raw HTML must not go to a public repo.
                entry["decoded_entries"]=[{k:e.get(k) for k in (
                    "boat","registration_no","racer_name","is_miss",
                    "exhibition_time","exhibition_st_raw","exhibition_st_seconds",
                    "exhibition_st_flag","exhibition_course")} for e in entries]
                entry["decoded_weather"]={k:context.get(k) for k in (
                    "air_temperature_c","water_temperature_c","wind_speed_mps",
                    "wave_height_cm","wind_direction")}
                out["retrieved_now"]+=1
            else:
                entry["status"]="official_page_unavailable_or_no_exhibition"
                out["official_page_no_useable_beforeinfo"]+=1
        except Exception as e:
            out["official_connection_failed"]+=1
            entry["status"]="request_failed"
            entry["error"]=type(e).__name__+":"+str(e)[:160]
        out["results"].append(entry)
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True)
    p.add_argument("--as-of",default=None)
    p.add_argument("--max-official-gap-requests",type=int,default=15)
    p.add_argument("--output-dir",type=Path,default=Path("_research_probe"))
    x=p.parse_args()
    if x.date!="20261012":raise ValueError("this test scoped to the observed 20261012 day")
    if not 0<=x.max_official_gap_requests<=20:raise ValueError("official_fetch_limit")
    now=datetime.fromisoformat(x.as_of).astimezone(JST) if x.as_of else datetime.now(JST)
    before=diagnose_saved_day(ROOT,x.date)
    replay=replay_predictions(x.date,ROOT)
    gap=survey_gaps(x.date,ROOT,now,x.max_official_gap_requests)
    x.output_dir.mkdir(parents=True,exist_ok=True)
    report={"schema":"boatrace-full-day-research-audit-v1","date":x.date,
            "as_of_jst":now.isoformat(),"saved_research":before["summary"],
            "replay":replay,"gap_official":gap,
            "result_as_prediction_input":False,
            "research_only_retroactive_not_predeadline":True}
    (x.output_dir/"full_day_audit.json").write_text(json.dumps(report,ensure_ascii=False,
                                                  indent=2)+"\n",encoding="utf-8")
    summary={
      "as_of":now.isoformat(),
      "saved":before["summary"],"replay":replay["count"],
      "official_gaps":{k:v for k,v in gap.items() if k!="results"}
    }
    print("FULL_DAY_RESEARCH_AUDIT_SUMMARY="+json.dumps(summary,ensure_ascii=False))
    if replay["count"].get("canonical_races",0)!=before["summary"].get("total"):
        raise RuntimeError("canonical_and_saved_program_races_count_differ")
if __name__=="__main__":main()
