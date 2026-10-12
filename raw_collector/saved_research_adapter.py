"""Audit ALREADY-SAVED research data without calling official sites or Drive.

These files are decoded snapshots, NOT immutable official HTML.  Do not
reclassify post-result recovery as a genuine predeadline observation or signal.
Read-only and independent of AI scoring.
"""
from __future__ import annotations
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

def _csv(path):
    if not path.is_file(): return []
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def _norm_id(x):
    m=re.fullmatch(r"(\d{8})[-_](\d{1,2})[-_](\d{1,2})",str(x or "").strip())
    if not m or not 1<=int(m[3])<=12 or not 1<=int(m[2])<=24:
        return None
    return f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}"

def _yes(x):
    return str(x or "").strip().lower() in {"1","true","yes"}

def _float(x):
    try: return float(x) if str(x or "").strip() else None
    except (ValueError,TypeError):return None

def _snapshot_sources(root,day):
    date_dir=root/"daily_inputs"/day[:4]/day[4:6]/day[6:8]
    recover=root/"evaluations"/day[:4]/day[4:6]/day[6:8]/"recovery"
    sources=[]
    def add(glob_root,pattern,provenance):
        if glob_root.exists():
            for p in sorted(glob_root.glob(pattern)):
                if p.is_file() and p.name.startswith("beforeinfo_entries_"):
                    sources.append((p,provenance))
    add(date_dir/"live"/"raw","*/beforeinfo_entries_*.csv","original_folder")
    add(date_dir/"live"/"retry_after_results","**/beforeinfo_entries_*.csv","retrieved_after_result")
    add(date_dir/"live"/"backfill","**/beforeinfo_entries_*.csv","retrieved_after_result")
    path=recover/f"official_retry_beforeinfo_entries_{day}.csv"
    if path.is_file():sources.append((path,"retrieved_after_result"))
    # Legacy structure: skip known retry/backfill descendants and already listed paths.
    other=date_dir/"live"
    found={p for p,_ in sources}
    if other.exists():
        for p in sorted(other.glob("**/beforeinfo_entries_*.csv")):
            if p in found or "retry_after_results" in p.parts or "backfill" in p.parts:
                continue
            sources.append((p,"legacy_unverified_capture_time"))
    return sources

def _load_prediction_ids(path,day):
    if not path.is_file() or not path.stat().st_size:
        return None
    try:
        obj=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj,dict) or str(obj.get("target_date"))!=day or not isinstance(obj.get("races"),list):
            return None
        return {_norm_id(r.get("race_id")) for r in obj["races"] if isinstance(r,dict)}-{None}
    except (ValueError,TypeError,OSError):
        return None

def diagnose_saved_day(root:Path,day:str)->dict:
    if not re.fullmatch(r"\d{8}",day):raise ValueError("invalid_date")
    folder=root/"daily_inputs"/day[:4]/day[4:6]/day[6:8]/"base"
    race_rows=_csv(folder/f"program_races_{day}.csv")
    entry_rows=_csv(folder/f"program_entries_{day}.csv")
    if not race_rows:race_rows=_csv(root/"data"/f"program_races_{day}.csv")
    if not entry_rows:entry_rows=_csv(root/"data"/f"program_entries_{day}.csv")
    if not race_rows:
        return {"schema":"boatrace-saved-diagnostics-v1","date":day,"status":"schedule_not_saved",
                "source_kind":"decoded_research_files_not_official_html",
                "coverage":None,"races":[],"summary":{"total":0,"morning_six":0,
                    "predeadline_live_six":0,"recovered_only":0,"no_live_saved":0}}
    grouped=defaultdict(list)
    for row in entry_rows:
        rid=_norm_id(row.get("race_id"))
        if rid and rid[:8]==day:grouped[rid].append(row)
    snapshots=defaultdict(lambda:{"original_folder":[],"retrieved_after_result":[],
                                   "legacy_unverified_capture_time":[]})
    for path,provenance in _snapshot_sources(root,day):
        for row in _csv(path):
            rid=_norm_id(row.get("race_id"))
            if rid and rid[:8]==day:
                snapshots[rid][provenance].append(row)
    base=root/"predictions"/day[:4]/day[4:6]/day[6:8]
    morning=_load_prediction_ids(base/f"morning_predictions_{day}.json",day)
    live=_load_prediction_ids(base/"live"/f"live_predictions_final_{day}.json",day)
    canonical=_load_prediction_ids(base/"live"/f"formation_predictions_final_{day}.json",day)
    expected_ids={_norm_id(x.get("race_id")) for x in race_rows}
    expected_ids.discard(None)
    out=[]
    for rid in sorted(expected_ids):
        entrants=grouped.get(rid,[])
        identities={str(row.get("boat") or ""):str(row.get("registration_no") or "")
                    for row in entrants if str(row.get("boat") or "") in {"1","2","3","4","5","6"}}
        six=(len(entrants)==6 and len(identities)==6 and
             all(re.fullmatch(r"\d{4}",v) for v in identities.values()) and
             len(set(identities.values()))==6)
        sets=snapshots.get(rid,{})
        def distinct_count(ctype):
            rows=sets.get(ctype,[])
            return len({str(x.get("boat") or "") for x in rows
                        if str(x.get("boat") or "") in {"1","2","3","4","5","6"}})
        current=distinct_count("original_folder")
        retry=distinct_count("retrieved_after_result")
        unknown=distinct_count("legacy_unverified_capture_time")
        # No recovered row may raise the observed predeadline count.
        if current:
            observation="original_folder_saved_unverified_time"
        elif retry:
            observation="post_result_recovery_only"
        elif unknown:
            observation="historical_capture_time_unverified"
        else:
            observation="no_saved_beforeinfo"
        # Do not call this true parsing readiness: weather lives in a different CSV
        # and not all original official fields are necessarily retained.
        issues=[]
        if not six:issues.append({"code":"saved_program_entries_not_six","field":"program_entries","observed":len(entrants)})
        if current and current<6:issues.append({"code":"saved_live_entries_incomplete","field":"beforeinfo_entries","observed":current})
        if current:issues.append({"code":"predeadline_capture_time_not_independently_verified","field":"provenance"})
        if not current and retry:issues.append({"code":"only_reconstructed_after_result","field":"provenance"})
        if not current and not retry:issues.append({"code":"predeadline_capture_not_confirmed","field":"provenance"})
        if morning is None:issues.append({"code":"morning_prediction_file_unreadable_or_missing","field":"morning_prediction"})
        elif rid not in morning:issues.append({"code":"morning_prediction_not_saved_for_race","field":"morning_prediction"})
        if live is None:issues.append({"code":"live_prediction_file_unreadable_or_missing","field":"live_prediction"})
        elif rid not in live:issues.append({"code":"live_prediction_not_saved_for_race","field":"live_prediction"})
        if canonical is None:issues.append({"code":"canonical_file_unreadable_or_missing","field":"canonical_prediction"})
        elif rid not in canonical:issues.append({"code":"canonical_prediction_not_saved_for_race","field":"canonical_prediction"})
        out.append({
            "race_id":rid,"morning_entry_count":len(entrants),
            "morning_six_identity_verified":bool(six),
            "original_folder_boats":current,
            "saved_predeadline_boats":0, # verified with collected_at + cutoff in future stage
            "reconstructed_after_result_boats":retry,
            "legacy_time_unverified_boats":unknown,
            "beforeinfo_state":observation,
            "morning_prediction_saved":morning is not None and rid in morning,
            "live_prediction_saved":live is not None and rid in live,
            "canonical_prediction_saved":canonical is not None and rid in canonical,
            "official_html_original_archived":False,
            "issues":issues
        })
    counts=Counter(x["beforeinfo_state"] for x in out)
    return {"schema":"boatrace-saved-diagnostics-v1","date":day,
        "status":"saved_research_files_audited","source_kind":"decoded_research_files_not_official_html",
        "coverage":{"expected_from_saved_program":len(expected_ids),
                    "has_saved_program":True,"raw_html_archive_verified":False},
        "races":out,
        "summary":{"total":len(out),"morning_six":sum(x["morning_six_identity_verified"] for x in out),
                   "predeadline_live_six":0,
                   "original_folder_six":sum(x["original_folder_boats"]==6 for x in out),
                   "recovered_only":counts["post_result_recovery_only"],
                   "no_live_saved":counts["no_saved_beforeinfo"],
                   "unknown_time":counts["historical_capture_time_unverified"],
                   "morning_prediction_saved":sum(x["morning_prediction_saved"] for x in out),
                   "live_prediction_saved":sum(x["live_prediction_saved"] for x in out),
                   "canonical_prediction_saved":sum(x["canonical_prediction_saved"] for x in out)}}
