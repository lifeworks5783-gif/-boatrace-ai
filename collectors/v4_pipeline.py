"""V4 ingestion contract. Three Actions: capture -> interpret -> calculate.

Capture never calls a parser. Every HTTP response body is stored as gzip and SHA256
in an artifact before downstream interpretation. Artifacts are temporary until the
private Drive archive is authenticated; don't describe them as durable storage.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

JST=timezone(timedelta(hours=9))
FIELDS_RACE=("date","venue_code","venue_name","race","race_id","deadline",
 "weather","air_temperature_c","water_temperature_c","wind_speed_mps",
 "wind_direction_code","wind_direction","wave_height_cm","stabilizer",
 "fixed_course","source_url","requested_at","collected_at")
FIELDS_BOAT=("date","venue_code","venue_name","race","race_id","boat",
 "registration_no","racer_name","weight_kg","exhibition_time","tilt",
 "exhibition_course","exhibition_st_raw","exhibition_st_seconds",
 "exhibition_st_flag","change_parts","is_miss","source_url",
 "requested_at","collected_at")
def dump(path,object):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(object,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def day_path(root,day):
    return Path(root)/"daily_inputs"/day[:4]/day[4:6]/day[6:8]
def read_csv(path):
    if not Path(path).is_file():return []
    with Path(path).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def parse_clock(day,clock):
    try:return datetime.strptime(day+" "+clock,"%Y%m%d %H:%M").replace(tzinfo=JST)
    except (ValueError,TypeError):return None
def parse_now(value):
    x=datetime.fromisoformat(value) if value else datetime.now(JST)
    if x.tzinfo is None:raise ValueError("expected_offset_aware_clock")
    return x.astimezone(JST)
def plan_live(root,day,now,horizon_minutes=32,max_races=24):
    if not re.fullmatch(r"\d{8}",day):raise ValueError("invalid_day")
    rows=read_csv(day_path(root,day)/"base"/f"program_races_{day}.csv")
    found={}
    for r in rows:
        rid=r.get("race_id")
        deadline=parse_clock(day,r.get("deadline"))
        if not rid or not deadline:continue
        remaining=(deadline-now).total_seconds()
        if not 0<remaining<=horizon_minutes*60:continue
        try:
            venue=int(r["venue_code"]);race=int(r["race"])
            if not 1<=venue<=24 or not 1<=race<=12:continue
        except (ValueError,TypeError,KeyError):continue
        url="https://www.boatrace.jp/owpc/pc/race/beforeinfo?"+urlencode({
            "hd":day,"jcd":f"{venue:02d}","rno":race})
        found[rid]={"race_id":rid,"source_url":url,"date":day,
                    "venue_code":f"{venue:02d}","venue_name":r.get("venue_name",""),
                    "race":race,"deadline":r.get("deadline","")}
    return sorted(found.values(),key=lambda r:(r["deadline"],r["race_id"]))[:max_races]

def fetch_one(entry,raw_dir,now=None,client=None):
    """No parser; preserve binary body even for unusual official HTML/status."""
    import requests
    url=entry["source_url"]
    requested=datetime.now(JST).isoformat() if now is None else now.isoformat()
    try:
        response=(client or requests).get(url,timeout=(5,12),headers={
            "User-Agent":"Mozilla/5.0 (compatible; BoatraceResearchCollector/4)",
            "Accept":"text/html"})
        body=response.content
        status=int(response.status_code)
        charset=response.encoding or "utf-8"
    except Exception as error:
        return {**entry,"requested_at":requested,"received_at":datetime.now(JST).isoformat(),
                "status":"transport_error","error":type(error).__name__}
    received=datetime.now(JST).isoformat()
    if len(body)>2_000_000:
        return {**entry,"requested_at":requested,"received_at":received,
                "status":"oversize_response","bytes":len(body)}
    h=hashlib.sha256(body).hexdigest()
    name=f"{entry['race_id']}_{h[:16]}.html.gz"
    raw_dir=Path(raw_dir)
    raw_dir.mkdir(parents=True,exist_ok=True)
    with gzip.open(raw_dir/name,"wb") as f:f.write(body)
    return {**entry,"requested_at":requested,"received_at":received,
            "status":"http_received","http_status":status,"sha256":h,
            "bytes":len(body),"charset":charset,"raw_path":name}
def capture_live(root,day,out,now=None,workers=6):
    now=parse_now(now)
    planned=plan_live(root,day,now)
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    rows=[]
    with ThreadPoolExecutor(max_workers=min(max(workers,1),8)) as pool:
        futures=[pool.submit(fetch_one,x,out/"raw") for x in planned]
        for f in as_completed(futures):rows.append(f.result())
    manifest={"schema":"boatrace-v4-capture-v1","mode":"live","date":day,
       "started_at":now.isoformat(),"capture_count":len(rows),
       "successful_http":sum(x.get("http_status")==200 for x in rows),
       "capture_status":"empty_window" if not rows else "attempted",
       "records":sorted(rows,key=lambda x:x["race_id"])}
    dump(out/"manifest.json",manifest)
    return manifest
def capture_morning(root,day,out):
    """If uncached, fetch official LZH once, archive it, then decode existing logic."""
    root=Path(root);out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    existing=day_path(root,day)/"base"
    reused=all((existing/f"{name}_{day}.csv").is_file() for name in
           ("program_races","program_entries"))
    source=existing
    raw_evidence=None
    if not reused:
        sys.path.insert(0,str(root/"collectors"))
        import today_basic
        url=today_basic.build_source_url(day)
        binary=today_basic.download_file(url,retries=2)
        if not binary:raise RuntimeError("morning_empty_raw_official_archive")
        name=f"program_{day}.lzh"
        raw_file=out/"raw"/name
        raw_file.parent.mkdir(parents=True,exist_ok=True)
        raw_file.write_bytes(binary)
        raw_evidence={"path":"raw/"+name,"url":url,"sha256":hashlib.sha256(binary).hexdigest(),
                      "bytes":len(binary),"capture_at":datetime.now(JST).isoformat()}
        script=root/"collectors"/"today_basic.py"
        subprocess.run([sys.executable,str(script),"--date",day,
                        "--archive-input",str(raw_file.resolve())],
                       cwd=root,check=True,timeout=120)
        source=root/"data"
    target=out/"base"
    target.mkdir(exist_ok=True)
    import shutil
    copied=[]
    for src in source.glob(f"*{day}*"):
        if src.is_file():
            shutil.copy2(src,target/src.name);copied.append(src.name)
    if not {"program_races_"+day+".csv","program_entries_"+day+".csv"}<=set(copied):
        raise RuntimeError("morning_program_not_available")
    manifest={"schema":"boatrace-v4-capture-v1","mode":"morning","date":day,
        "capture_count":len(copied),"records":[],"base_files":sorted(copied),
        "raw_archive":raw_evidence,
        "source_type":"cached_existing_program_no_binary" if reused else "official_LZH_original_before_parse"}
    dump(out/"manifest.json",manifest)
    return manifest

def exhibition_is_complete(entries):
    """HTTP 200 is not a finished exhibition: all active starters need fields.

    Never infer official scratches from absent boat rows; preserve incomplete
    exact-source captures for retry rather than scoring neutral placeholders.
    """
    # Six boat identities are mandatory; a five-starter race needs an
    # explicit sixth is_miss row, never an inferred scratch.
    if len(entries) != 6:
        return False
    numbers=[str(row.get("boat") or "") for row in entries]
    if len(set(numbers)) != len(numbers) or any(x not in {"1","2","3","4","5","6"} for x in numbers):
        return False
    for row in entries:
        if not str(row.get("registration_no") or "").strip():
            return False
        scratched=str(row.get("is_miss") or "").lower() in {"true","1","yes"}
        if not scratched and any(row.get(k) is None or not str(row.get(k)).strip()
                   for k in ("exhibition_course","exhibition_time","exhibition_st_raw")):
            return False
    return sum(str(x.get("is_miss") or "").lower() not in {"true","1","yes"} for x in entries) >= 3

def decode_manifest(source,out,root):
    """Interpret AFTER capture artifact exists, never discard immutable raw body."""
    source=Path(source);out=Path(out);root=Path(root)
    manifest=json.loads((source/"manifest.json").read_text(encoding="utf-8"))
    day=manifest["date"];mode=manifest["mode"]
    result={"schema":"boatrace-v4-decoded-v1","date":day,"mode":mode,
            "observed_races":0,"decoded_races":0,"unparsed_races":[],
            "unready_races":[], "snapshot_path":None,
            "raw_storage":"temporary_github_actions_artifact_only"}
    if mode=="morning":
        raw=manifest.get("raw_archive")
        if raw:
            evidence=source/raw["path"]
            if (not evidence.is_file() or
                hashlib.sha256(evidence.read_bytes()).hexdigest()!=raw["sha256"]):
                raise RuntimeError("morning_raw_lzh_checksum_mismatch")
        import shutil
        tgt=out/"base";tgt.mkdir(parents=True,exist_ok=True)
        for p in (source/"base").glob("*"):
            if p.is_file():shutil.copy2(p,tgt/p.name)
        result["decoded_races"]=len(read_csv(tgt/f"program_races_{day}.csv"))
        dump(out/"status.json",result)
        return result
    if mode!="live":raise ValueError("unsupported_mode")
    # Keep all parse failures in status.json, don't re-write the raw HTTP body.
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from bs4 import BeautifulSoup
    import today_beforeinfo as legacy
    races=[];boats=[]
    for x in manifest["records"]:
        if x.get("status")!="http_received" or x.get("http_status")!=200:
            result["unparsed_races"].append({"race_id":x["race_id"],"reason":x.get("status"),
              "http_status":x.get("http_status")})
            continue
        p=source/"raw"/x["raw_path"]
        body=gzip.decompress(p.read_bytes())
        if hashlib.sha256(body).hexdigest()!=x["sha256"]:
            raise RuntimeError("raw_capture_checksum_mismatch:"+x["race_id"])
        # HTML can change declared charset; use BeautifulSoup's byte-aware detector.
        from bs4 import UnicodeDammit
        detected=UnicodeDammit(body,is_html=True).unicode_markup
        html=detected if detected is not None else body.decode("utf-8",errors="replace")
        base={k:x.get(k) for k in ("date","venue_code","venue_name","race","race_id","deadline")}
        try:
            parsed=legacy.parse_beforeinfo(html,base,x["requested_at"])
            if parsed:
                r,bb=parsed
            else:
                soup=BeautifulSoup(html,"html.parser")
                bb=legacy.parse_entry_table(soup)
                if not bb:raise ValueError("no_decrypted_boat_rows")
                weather=legacy.parse_weather(soup)
                r={**base,**weather,**legacy.parse_flags(soup),
                   "source_url":x["source_url"],
                   "requested_at":x["requested_at"],
                   "collected_at":x["received_at"]}
                bb=[{**base,**b,"source_url":x["source_url"],
                     "requested_at":x["requested_at"],
                     "collected_at":x["received_at"]} for b in bb]
            # Use the actual HTTP timestamps, never the later parser-runtime
            # timestamp (which may occur after the racing deadline).
            r.update({"requested_at":x["requested_at"],"collected_at":x["received_at"],
                      "source_url":x["source_url"]})
            for entry in bb:
                entry.update({"requested_at":x["requested_at"],
                              "collected_at":x["received_at"],
                              "source_url":x["source_url"]})
            # An official HTTP response with six names but blank ST/exhibition
            # is valid evidence, not a usable pre-deadline LIVE prediction.
            if not exhibition_is_complete(bb):
                result["unready_races"].append({
                    "race_id":x["race_id"],"deadline":x.get("deadline"),
                    "reason":"official_exhibition_not_ready",
                    "collected_at":x["received_at"],"source_sha256":x["sha256"]
                })
                continue
            # Decoding is not proof of being timely. A source received after
            # deadline is retained only in the raw archive (research replay).
            cutoff=parse_clock(day,x.get("deadline"))
            received=parse_now(x["received_at"])
            if cutoff is None or received >= cutoff:
                result["unparsed_races"].append({
                    "race_id":x["race_id"],"reason":"after_deadline_observation",
                    "collected_at":x["received_at"],"source_sha256":x["sha256"]
                })
                continue
            races.append(r);boats.extend(bb)
            result["decoded_races"]+=1
        except Exception as exc:
            result["unparsed_races"].append({"race_id":x["race_id"],
                 "reason":"parse_error","error_type":type(exc).__name__,
                 "source_sha256":x["sha256"]})
    result["observed_races"]=len(manifest["records"])
    if races:
        snap=out/"raw"/datetime.now(JST).strftime("%Y%m%d_%H%M%S")
        snap.mkdir(parents=True,exist_ok=True)
        for path,rows,fields in [
            (snap/f"beforeinfo_races_{day}.csv",races,FIELDS_RACE),
            (snap/f"beforeinfo_entries_{day}.csv",boats,FIELDS_BOAT)]:
            with path.open("w",encoding="utf-8",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
                writer.writeheader();writer.writerows(rows)
        result["snapshot_path"]=str(snap.relative_to(out))
    dump(out/"status.json",result)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("stage",choices=["capture","decode"])
    p.add_argument("--mode",choices=["morning","live"],default="live")
    p.add_argument("--day",required=True)
    p.add_argument("--root",type=Path,default=Path("."))
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--in-dir",type=Path)
    p.add_argument("--now")
    x=p.parse_args()
    if x.stage=="capture":
        result=capture_morning(x.root,x.day,x.out) if x.mode=="morning" else capture_live(
            x.root,x.day,x.out,x.now)
    else:
        if x.in_dir is None:raise ValueError("decode_needs_in_dir")
        result=decode_manifest(x.in_dir,x.out,x.root)
    print("V4_STAGE_RESULT="+json.dumps({k:v for k,v in result.items() if k!="records"},ensure_ascii=False))
if __name__=="__main__":main()
