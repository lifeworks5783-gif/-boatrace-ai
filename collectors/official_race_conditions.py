"""Stage-aware BOAT RACE exception ontology: preserve observations, never gate fetch.

Collector must archive every valid HTTP response regardless of 6-boat/readiness.
This module only interprets decoded records with evidence of the condition.
Do not change AI scoring or classify actual-result F/L as exhibition ST.
"""
from __future__ import annotations
import re

SCHEMA="boatrace-official-condition-v1"
EVENTS={
 "normal_entry":"通常出走",
 "scratch":"欠場・出走取消",
 "fewer_starters":"出走艇数減少",
 "course_change":"展示進入変更",
 "exhibition_false_start":"展示F（展示スタート）",
 "exhibition_late_start":"展示L（展示スタート）",
 "exhibition_unknown":"展示ST未解読",
 "race_cancelled":"レース中止・不成立",
 "race_abandoned":"競走不成立・打切り",
 "race_disqualification":"競走中の失格",
 "race_flying_start":"本番スタートF",
 "race_late_start":"本番スタートL",
 "race_nonfinish":"転覆・落水・沈没・エンストなど",
 "weather_or_equipment_change":"気象・安定板・部品交換",
 "missing_observation":"未取得または項目不足",
}
# Official result expressions vary; collect unknown text instead of guessing.
RESULT_PATTERNS=[
 ("race_cancelled",re.compile(r"中止|開催中止|レース中止|欠航")),
 ("race_abandoned",re.compile(r"不成立|打切|競走不成立")),
 ("race_disqualification",re.compile(r"失格|妨害|不良航法|待機行動違反")),
 ("race_nonfinish",re.compile(r"転覆|落水|沈没|エンスト|不完走")),
 ("race_flying_start",re.compile(r"(?<![A-Za-z])F\\d*|フライング",re.I)),
 ("race_late_start",re.compile(r"(?<![A-Za-z])L\\d*|出遅れ",re.I)),
]
def _boat_id(x):
    try:
        n=int(x)
        return n if 1<=n<=6 else None
    except (TypeError,ValueError):return None

def classify_race(*,entries:list[dict],morning_entries:list[dict]|None=None,
                  actual_results:list[dict]|None=None, official_status:str|None=None)->dict:
    """Classification and calculation capability are separate decisions.

    "official confirmed" is not assumed for an absent row. If a boat is missing
    without an explicit scratch, collector preserves partial data and marks
    ambiguity rather than rejecting/constructing a sixth boat.
    """
    events=[]
    def event(code,stage,boat=None,evidence=None):
        x={"code":code,"label":EVENTS[code],"stage":stage}
        if boat is not None:x["boat"]=boat
        if evidence is not None:x["evidence"]=str(evidence)[:150]
        events.append(x)
    by={_boat_id(r.get("boat")):r for r in entries if _boat_id(r.get("boat"))}
    before={_boat_id(r.get("boat")):r for r in (morning_entries or []) if _boat_id(r.get("boat"))}
    scratch=[]
    active=[]
    for b,r in sorted(by.items()):
        missing=str(r.get("is_miss") or "").lower() in ("true","yes","1") or r.get("is_miss") is True
        if missing:
            scratch.append(b);event("scratch","before_start",b,"is_miss")
        else:
            active.append(b)
            value=str(r.get("exhibition_st_raw") or "").strip().upper()
            if value.startswith("F"):event("exhibition_false_start","before_start",b,value)
            elif value.startswith("L"):event("exhibition_late_start","before_start",b,value)
            elif value and not re.fullmatch(r"(?:0?\\.)?\\d{1,2}|1\\.00",value):
                event("exhibition_unknown","before_start",b,value)
            old=before.get(b)
            if old and r.get("exhibition_course") not in (None,"","-"):
                try:
                    if int(r["exhibition_course"])!=b:
                        event("course_change","before_start",b,r.get("exhibition_course"))
                except (TypeError,ValueError):
                    event("missing_observation","before_start",b,"invalid_exhibition_course")
    unknown_missing=sorted(set(range(1,7))-set(by))
    # Missing entrants aren't inferred to have scratched, not even with 5 entries.
    if unknown_missing:event("missing_observation","before_start",evidence=f"missing_rows:{unknown_missing}")
    if scratch or len(active)<6:event("fewer_starters","before_start",evidence=f"active={len(active)}")
    if any(r.get("change_parts") for r in entries):event("weather_or_equipment_change","before_start","", "parts")
    if official_status:
        for typ,pattern in RESULT_PATTERNS:
            if pattern.search(str(official_status)):
                event(typ,"after_start",evidence=official_status)
    for row in actual_results or []:
        raw=" ".join(str(row.get(k) or "") for k in ("finish_status","result_status","remark","note","rank","arrival","status"))
        for typ,pattern in RESULT_PATTERNS:
            if pattern.search(raw):
                event(typ,"after_start",_boat_id(row.get("boat")),raw)
    active_count=len(active)
    # 3P3 6 tickets, 4P3 24; product is nominal 24 ONLY for 4-6
    # starters when scratches are verified. A raw row omitted is NOT evidence.
    confirmed=len(by)==6 and not unknown_missing and len(scratch)==6-active_count
    signal_24_possible=(4<=active_count<=6 and
                        (active_count==6 or confirmed))
    return {
        "schema":SCHEMA,"observed_rows":len(entries),"active_lanes":active,
        "verified_scratches":scratch,"unresolved_missing_lanes":unknown_missing,
        "events":events,
        "collection_accept":True, # never reject evidence on interpretation
        "can_compute_normal_if_features_exist":active_count>=3,
        "can_compute_signal_if_scores_exist":signal_24_possible,
        "signal_24_product_possible":signal_24_possible,
        "calculation_context":"after_start_outcomes_not_prediction_inputs",
    }
