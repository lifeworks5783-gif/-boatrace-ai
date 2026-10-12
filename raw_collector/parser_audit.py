"""Read-side quality checks: never part of official HTTP capture or raw archive.

The checker produces knowledge about unrecognized/insufficient formats.
It cannot overwrite originals, infer missing values or fabricate live predictions.
Keep it separate from the normal-score and Fujin/Raijin calculation code.
"""
from __future__ import annotations
import math
import re

# Recognized *observational* ST notation, not racer-average ST or F-holdings.
# L starts are observed but not usable as a positive ST score in live models.
ST_VALUE = re.compile(r"^(?:F)?(?:0?\.\d{1,2}|1\.00)$", re.IGNORECASE)
ST_LATE = re.compile(r"^L(?:0?\.\d{1,2}|1\.00)$", re.IGNORECASE)
AIR_LIMITS = (-20.0, 50.0)
WATER_LIMITS = (-5.0, 45.0)
WIND_LIMITS = (0.0, 45.0)
WAVE_LIMITS = (0.0, 200.0)

def as_finite(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result=float(value)
    except (TypeError,ValueError):
        return None
    return result if math.isfinite(result) else None

def st_semantics(raw):
    """Classify known formats; unknown strings are *never* accepted as seconds."""
    s=str(raw or "").strip().replace(" ","").upper()
    if ST_LATE.fullmatch(s):
        return "late_observation_unusable"
    if ST_VALUE.fullmatch(s):
        return "exhibition_false_start" if s.startswith("F") else "valid"
    return "missing" if not s else "unknown"

def audit_parsed_beforeinfo(rows,context,expected=None):
    """Diagnostic audit, not a collector and not a scoring algorithm.

    Returns non-guessing issues and readiness to normalize, *not* an AI forecast.
    Missing course/duplicate courses/unknown ST and identity conflicts are
    explicit, so the original response remains available for parser repair.
    """
    issues=[]
    def issue(code,field,boat=None):
        record={"code":code,"field":field}
        if boat is not None:record["boat"]=boat
        issues.append(record)
    expected=expected or {}
    if len(rows)!=6:
        issue("boat_count_incomplete","boats")
    lanes=[]
    courses=[]
    ids=[]
    for row in rows:
        boat=row.get("boat")
        if boat not in range(1,7):
            issue("invalid_boat_number","boat",boat)
        lanes.append(boat)
        reg=str(row.get("registration_no") or "").strip()
        ids.append(reg)
        if not re.fullmatch(r"\d{4}",reg):
            issue("missing_registration","registration_no",boat)
        if expected and expected.get(str(boat))!=reg:
            issue("program_registration_mismatch","registration_no",boat)
        if row.get("is_miss"):
            issue("official_scratch_requires_special_handling","is_miss",boat)
        course=row.get("exhibition_course")
        courses.append(course)
        if course not in range(1,7):
            issue("invalid_exhibition_course","exhibition_course",boat)
        ex_time=as_finite(row.get("exhibition_time"))
        if ex_time is None or not 5.0<=ex_time<=10.0:
            issue("invalid_exhibition_time","exhibition_time",boat)
        raw=row.get("exhibition_st_raw")
        meaning=st_semantics(raw)
        if meaning=="late_observation_unusable":
            issue("late_st_not_usable_in_live_score","exhibition_st_raw",boat)
        elif meaning=="unknown":
            issue("unknown_st_notation","exhibition_st_raw",boat)
        elif meaning=="missing":
            issue("missing_exhibition_st","exhibition_st_raw",boat)
        else:
            observed=as_finite(row.get("exhibition_st_seconds"))
            token=str(raw).strip().replace(" ","").upper()
            target=float(token.lstrip("F").replace(".","0.",1)) if token.lstrip("F").startswith(".") else float(token.lstrip("F"))
            if meaning=="exhibition_false_start":target=-abs(target)
            if observed is None or abs(observed-target)>0.000001:
                issue("st_seconds_mismatch","exhibition_st_seconds",boat)
            flag=str(row.get("exhibition_st_flag") or "")
            if meaning=="exhibition_false_start" and flag.upper()!="F":
                issue("false_start_flag_mismatch","exhibition_st_flag",boat)
            if meaning=="valid" and flag.upper()=="F":
                issue("false_start_flag_mismatch","exhibition_st_flag",boat)

    if len(set(lanes))!=len(lanes):
        issue("duplicate_boat_number","boat")
    if len(set(courses))!=len(courses):
        issue("duplicate_exhibition_course","exhibition_course")
    if len(set(ids))!=len(ids):
        issue("duplicate_registration","registration_no")
    if len(expected)!=6:
        issue("program_six_registrations_not_verified","registration_no")
    if not isinstance(context,dict):
        context={}
    for field,limits in {
        "air_temperature_c":AIR_LIMITS,
        "water_temperature_c":WATER_LIMITS,
        "wind_speed_mps":WIND_LIMITS,
        "wave_height_cm":WAVE_LIMITS,
    }.items():
        value=as_finite(context.get(field))
        if value is None:
            issue("weather_field_missing",field)
        elif not limits[0]<=value<=limits[1]:
            issue("weather_value_outside_plausible_bounds",field)
    return {
        "schema":"boatrace-parser-audit-v1",
        "ready_live_inputs": not issues,
        "issues":issues,
        "checked_boats":len(rows),
        "parser_learning_required":bool(issues),
    }
