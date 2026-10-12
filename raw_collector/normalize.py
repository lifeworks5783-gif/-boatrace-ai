"""Make small normalized research JSON from a verified private raw ZIP.

HTML stays in private Google Drive; parse failure remains a visible status.
"""
from __future__ import annotations
import csv
import gzip
import json
import sys
import zipfile
from pathlib import Path
from raw_collector.drive_bundle import validate_bundle
from raw_collector.archive import source_identity
from raw_collector.parser_audit import audit_parsed_beforeinfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"collectors"))
from today_beforeinfo import parse_beforeinfo

PARSER_ID="today_beforeinfo_parse_beforeinfo_v1"
RACE_FIELDS=("weather","air_temperature_c","water_temperature_c",
             "wind_speed_mps","wind_direction_code","wind_direction",
             "wave_height_cm","stabilizer","fixed_course")
ENTRY_FIELDS=("boat","registration_no","racer_name","weight_kg",
              "exhibition_time","tilt","exhibition_course",
              "exhibition_st_raw","exhibition_st_seconds","exhibition_st_flag",
              "change_parts","is_miss")

def base_schedule(root:Path,day:str)->dict:
    path=root/"daily_inputs"/day[:4]/day[4:6]/day[6:8]/"base"/f"program_races_{day}.csv"
    if not path.exists():
        raise FileNotFoundError("race_schedule_missing")
    with path.open(encoding="utf-8-sig",newline="") as stream:
        return {str(row["race_id"]):row for row in csv.DictReader(stream)}

def program_registration_map(root:Path,day:str)->dict:
    path=root/"daily_inputs"/day[:4]/day[4:6]/day[6:8]/"base"/f"program_entries_{day}.csv"
    if not path.exists():
        return {}
    found={}
    with path.open(encoding="utf-8-sig",newline="") as fh:
        for row in csv.DictReader(fh):
            race_id=str(row.get("race_id",""))
            if not race_id: continue
            found.setdefault(race_id,{})[str(row.get("boat",""))]=str(row.get("registration_no",""))
    return found

def normalize_verified_bundle(bundle:Path, *, root:Path,
                              transfer_status:str)->dict:
    """Production: allow normalizing for GitHub only after confirmed Drive transfer."""
    if transfer_status not in ("verified_uploaded","verified_existing"):
        raise RuntimeError("raw_bundle_not_verified_in_private_drive")
    return _normalize_bundle(bundle,root=root,drive_verified=True)

def preview_local_bundle(bundle:Path, *, root:Path)->dict:
    """Research-only: inspect a local archive before OAuth without claiming Drive storage.

    Never pass this result to write_summary() or publish it as a durable forecast.
    """
    return _normalize_bundle(bundle,root=root,drive_verified=False)

def _normalize_bundle(bundle:Path, *, root:Path,drive_verified:bool)->dict:
    manifest=validate_bundle(bundle)
    day=manifest["date"]
    schedules=base_schedule(root,day)
    registration=program_registration_map(root,day)
    per_race={}
    with zipfile.ZipFile(bundle) as files:
        for entry in manifest["entries"]:
            date,kind,venue,rno=source_identity(entry["source_url"])
            if kind!="beforeinfo":
                continue
            rid=f"{date}-{venue}-{rno}"
            base=schedules.get(rid)
            provenance={
                "source_url":entry["source_url"],
                "raw_sha256":entry["sha256"],
                "collected_at":entry["received_at"],
                "drive_raw_verified":drive_verified,
                "parser":PARSER_ID
            }
            summary={"race_id":rid,"source":provenance,"parse_status":"unparsed",
                     "race":None,"boats":[],
                     "diagnostics":{"schema":"boatrace-parser-audit-v1",
                         "ready_live_inputs":False,"parser_learning_required":True,
                         "issues":[{"code":"parser_not_yet_run","field":"beforeinfo"}]}}
            if base:
                context={"date":date,"venue_code":venue,
                         "venue_name":base.get("venue_name",""),
                         "race":int(rno),"race_id":rid,
                         "deadline":base.get("deadline","")}
                try:
                    original=gzip.decompress(files.read(entry["path"]))
                    parsed=parse_beforeinfo(original.decode("utf-8",errors="replace"),
                                            context,requested_at=entry["requested_at"] or "")
                    if parsed:
                        weather,boats=parsed
                        summary["race"]={k:weather.get(k) for k in RACE_FIELDS}
                        summary["boats"]=[{k:row.get(k) for k in ENTRY_FIELDS} for row in boats]
                        expected=registration.get(rid,{})
                        audit=audit_parsed_beforeinfo(boats,weather,expected)
                        summary["diagnostics"]=audit
                        identity_issues={"program_registration_mismatch",
                                         "program_six_registrations_not_verified",
                                         "missing_registration","duplicate_registration"}
                        mismatch=any(x["code"] in identity_issues
                                     for x in audit["issues"])
                        summary["parse_status"]=(
                            "ready_live_inputs" if audit["ready_live_inputs"] else
                            "participant_identity_not_verified" if mismatch else
                            "incomplete_live_inputs")
                    else:
                        summary["diagnostics"]["issues"]=[
                            {"code":"parser_no_exhibition_data","field":"beforeinfo"}]
                except Exception:
                    summary["parse_status"]="unparsed"
                    summary["diagnostics"]["issues"]=[
                        {"code":"parser_unhandled_exception","field":"beforeinfo"}]
            else:
                summary["parse_status"]="schedule_missing"
                summary["diagnostics"]["issues"]=[
                    {"code":"schedule_missing","field":"program_races"}]
            prev=per_race.get(rid)
            if not prev or str(summary["source"]["collected_at"])>=str(prev["source"]["collected_at"]):
                per_race[rid]=summary
    return {"schema":"boatrace-normalized-v1","date":day,
            "source_archive":"private_google_drive_verified" if drive_verified else "local_ephemeral_unarchived",
            "races":[per_race[k] for k in sorted(per_race)]}

def merge_daily_summary(existing:dict | None,new:dict)->dict:
    if not existing:return new
    if existing.get("date")!=new.get("date") or existing.get("schema")!=new.get("schema"):
        raise ValueError("incompatible_normalized_schema")
    byid={r["race_id"]:r for r in existing.get("races",[])}
    for r in new.get("races",[]):
        old=byid.get(r["race_id"])
        if old is None or str(r["source"]["collected_at"])>=str(old["source"]["collected_at"]):
            if old and old.get("parse_status")=="ready_live_inputs" and r.get("parse_status")!="ready_live_inputs":
                # Hold the previous complete observation separately; never pretend it
                # describes the new HTML, and never erase its validated values.
                r["last_ready"]={k:old.get(k) for k in ("source","race","boats")}
            elif old and old.get("last_ready") and r.get("parse_status")!="ready_live_inputs":
                r["last_ready"]=old["last_ready"]
            byid[r["race_id"]]=r
    return {**new,"races":[byid[k] for k in sorted(byid)]}

def write_summary(payload:dict,*,repo_root:Path)->Path:
    if (payload.get("source_archive")!="private_google_drive_verified" or
        any(not race.get("source",{}).get("drive_raw_verified")
            for race in payload.get("races",[]))):
        raise RuntimeError("local_ephemeral_preview_cannot_be_committed")
    day=payload["date"]
    path=repo_root/"normalized"/day[:4]/day[4:6]/day[6:8]/"races.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    old=json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    combined=merge_daily_summary(old,payload)
    path.write_text(json.dumps(combined,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return path
