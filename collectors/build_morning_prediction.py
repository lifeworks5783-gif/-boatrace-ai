from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
MODEL_VERSION = "provisional_v4_20261006_morning_traceable_inputs"

# 暫定ロジックVer.1（2026-10-04固定）
MORNING_WEIGHTS = {
    "racer_course": 40.0,
    "grade": 20.0,
    "motor": 20.0,
    "boat": 5.0,
    "national_top2": 15.0,
}
# build_live_prediction.py との互換用。直前側の本番配点は同ファイルで 80/6/14。
UNIFIED_WEIGHTS = {
    "racer_course": 40.0, "grade": 20.0, "motor": 20.0,
    "boat": 5.0, "national_top2": 15.0,
    "exTime": 6.0, "exST": 14.0,
}
GRADE_PRIOR = {"A1": 1.00, "A2": 0.75, "B1": 0.45, "B2": 0.25}
FORBIDDEN_CURRENT_RESULT_KEYS = {"finish","result","race_time","actual_st","actual_course"}

def parse_args():
    p=argparse.ArgumentParser(description="暫定ロジックVer.1で朝予測を生成")
    p.add_argument("--date",required=True)
    p.add_argument("--input",default=None)
    p.add_argument("--output-dir",default="data")
    # 旧workflow/手動実行とのCLI互換のみ。外部CSVは読まない。
    p.add_argument("--public-source-dir",default=None)
    return p.parse_args()

def text(v): return "" if v is None else str(v).strip()
def to_float(v):
    if v is None or isinstance(v,bool): return None
    try: n=float(str(v).replace(",","").strip())
    except (TypeError,ValueError): return None
    return n if math.isfinite(n) else None
def to_int(v):
    n=to_float(v); return None if n is None else int(n)
def clamp(v,lo=0.0,hi=1.0): return max(lo,min(hi,float(v)))
def canonical_race_code(v): return "".join(re.findall(r"\d",text(v)))

def rank_lower_is_better(values):
    valid=[(k,v) for k,v in values.items() if v is not None]
    valid.sort(key=lambda x:(x[1],x[0]))
    if len(valid)==1: return {valid[0][0]:0.5}
    if not valid: return {}
    return {k:1.0-i/(len(valid)-1) for i,(k,_) in enumerate(valid)}

def _rank6(values,lower=False):
    # 履歴が無い艇だけ中立0.5で補完。配点自体は変更しない。
    valid=[(k,v) for k,v in values.items() if v is not None]
    if not valid: return {}
    valid.sort(key=lambda x:((x[1] if lower else -x[1]),x[0]))
    if len(valid)==1:
        ranked={valid[0][0]:0.5}
    else:
        ranked={k:1.0-i/(len(valid)-1) for i,(k,_) in enumerate(valid)}
    for k,v in values.items():
        if v is None: ranked[k]=0.5
    return ranked

def _feature_rows(path):
    p=Path(path)
    if not p.exists(): return []
    with p.open(encoding="utf-8-sig",newline="") as h: return list(csv.DictReader(h))
def _keynum(v):
    try: return str(int(float(v)))
    except (TypeError,ValueError): return ""
def _rate(v):
    n=to_float(v)
    if n is None: return None
    return clamp(n/100.0 if n>1 else n)

_FEATURE_CACHE=None
def _feature_maps():
    global _FEATURE_CACHE
    if _FEATURE_CACHE is not None: return _FEATURE_CACHE
    rc={}; rf={}; mf={}; bf={}
    for r in _feature_rows("features/racer_course_features.csv"):
        rc[(_keynum(r.get("registration_no")),_keynum(r.get("course")))]=r
    for r in _feature_rows("features/racer_features.csv"):
        rf[_keynum(r.get("registration_no"))]=r
    for r in _feature_rows("features/motor_features.csv"):
        mf[(str(r.get("venue_code","")).zfill(2),_keynum(r.get("motor_no")))]=r
    for r in _feature_rows("features/boat_features.csv"):
        bf[(str(r.get("venue_code","")).zfill(2),_keynum(r.get("boat_no")))]=r
    _FEATURE_CACHE=(rc,rf,mf,bf)
    return _FEATURE_CACHE

def _raw_race_features(race,course_overrides=None):
    rc,rf,mf,bf=_feature_maps()
    boats=race.get("boats") or []
    venue=str(race.get("venue_code") or race.get("stadium_code") or "").zfill(2)
    raw={}
    # 朝は枠番=想定コース、直前は展示進入コースを使う。
    # enriched入力に履歴が入っていても、計算元は同一feature snapshotに固定して
    # 朝/直前で参照日がずれないようにする。
    for boat in boats:
        lane=to_int(boat.get("boat"))
        racer=boat.get("racer") or {}; motor=boat.get("motor") or {}; bm=boat.get("boat_machine") or {}
        reg=_keynum(racer.get("registration_no"))
        course=(course_overrides or {}).get(lane,lane)
        cr=rc.get((reg,str(course)),{}); rr=rf.get(reg,{})
        mm=mf.get((venue,_keynum(motor.get("motor_no"))),{})
        bb=bf.get((venue,_keynum(bm.get("boat_no"))),{})
        raw[lane]={
            "course_win":_rate(cr.get("d90_win_rate")),
            "course_top2":_rate(cr.get("d90_top2_rate")),
            "course_top3":_rate(cr.get("d90_top3_rate")),
            "course_avg_st":to_float(cr.get("d90_avg_st")),
            "grade":GRADE_PRIOR.get(text(racer.get("grade")).upper()),
            "national_top2":_rate(rr.get("d90_top2_rate")),
            "motor_win":_rate(mm.get("d90_win_rate")),
            "motor_top3":_rate(mm.get("d90_top3_rate")),
            "boat_top2":_rate(bb.get("d90_top2_rate")),
            "boat_top3":_rate(bb.get("d90_top3_rate")),
        }
    return raw

def provisional_details(race,public_store=None,course_overrides=None):
    raw=_raw_race_features(race,course_overrides)
    keys=["course_win","course_top2","course_top3","course_avg_st","grade","national_top2","motor_win","motor_top3","boat_top2","boat_top3"]
    ranks={k:_rank6({b:v[k] for b,v in raw.items()},lower=(k=="course_avg_st")) for k in keys}
    missing=[k for k,v in ranks.items() if len(v)!=6]
    if missing: return {},missing
    # 6艇すべてについて基礎5要素の計算材料が揃った場合だけ予測を生成する。
    # 欠損を0点扱いして順位を歪めることは禁止。
    for b, values in raw.items():
        required = ("course_win","course_top2","course_top3","course_avg_st","grade","national_top2","motor_win","motor_top3","boat_top2","boat_top3")
        if any(values.get(k) is None for k in required):
            return {}, [f"{b}号艇:{k}" for k in required if values.get(k) is None]
    out={}
    for b in raw:
        racer_course=(.40*ranks["course_win"][b]+.20*ranks["course_top2"][b]+.30*ranks["course_top3"][b]+.10*ranks["course_avg_st"][b])
        motor=.40*ranks["motor_win"][b]+.60*ranks["motor_top3"][b]
        boat=.50*ranks["boat_top2"][b]+.50*ranks["boat_top3"][b]
        score=100*(.40*racer_course+.20*ranks["grade"][b]+.20*motor+.05*boat+.15*ranks["national_top2"][b])
        out[b]={
            "score":score,
            "racer_course":racer_course,
            "grade":ranks["grade"][b],
            "motor":motor,
            "boat":boat,
            "national_top2":ranks["national_top2"][b],
            "course":(course_overrides or {}).get(b,b),
        }
    return out,[]

def provisional_scores(race,public_store=None,course_overrides=None):
    details,missing=provisional_details(race,public_store,course_overrides)
    if missing: return {}
    return {b:d["score"] for b,d in details.items()}

def score_boat(race,boat,public_store=None,course_override=None):
    lane=to_int(boat.get("boat"))
    if lane not in {1,2,3,4,5,6}: raise RuntimeError(f"艇番異常: {race.get('race_id')} {boat.get('boat')}")
    overrides={lane:to_int(course_override)} if course_override is not None else None
    details,missing=provisional_details(race,None,overrides)
    if missing: raise RuntimeError(f"履歴特徴量不足 {race.get('race_id')}: {','.join(missing)}")
    d=details[lane]; racer=boat.get("racer") or {}; motor=boat.get("motor") or {}; bm=boat.get("boat_machine") or {}
    comps={
        "racer_course":{"weight":40.0,"raw_score_0_1":round(d["racer_course"],6),"available":True},
        "grade":{"weight":20.0,"raw_score_0_1":round(d["grade"],6),"available":True},
        "motor":{"weight":20.0,"raw_score_0_1":round(d["motor"],6),"available":True},
        "boat":{"weight":5.0,"raw_score_0_1":round(d["boat"],6),"available":True},
        "national_top2":{"weight":15.0,"raw_score_0_1":round(d["national_top2"],6),"available":True},
    }
    return {"boat":lane,"registration_no":racer.get("registration_no"),"racer_name":racer.get("name"),"grade":racer.get("grade"),"motor_no":motor.get("motor_no"),"boat_no":bm.get("boat_no"),"score":round(d["score"],2),"base_score":round(d["score"],2),"trend_adjustment_points":0.0,"f_l_penalty_points":0.0,"data_coverage_pct":100.0,"components":comps,"note":"暫定ロジックVer.1: 選手×想定コース40/級別20/モーター20/ボート5/全国2連対15"}

def validate_current_day_no_results(payload):
    violations=[]
    races=payload.get("races")
    if not isinstance(races,list): return ["racesがlistではありません"]
    for race in races:
        for boat in race.get("boats") or []:
            for key in FORBIDDEN_CURRENT_RESULT_KEYS & set(boat.keys()):
                violations.append(f"{race.get('race_id')} {boat.get('boat')}号艇: 当日結果キー {key}")
    return violations

def prediction_strength(ranked):
    if len(ranked)<2:return {"top1_top2_gap":None,"top1_top3_gap":None}
    return {"top1_top2_gap":round(ranked[0]["score"]-ranked[1]["score"],2),"top1_top3_gap":round(ranked[0]["score"]-ranked[2]["score"],2) if len(ranked)>=3 else None}

def write_csv(path,rows):
    fields=["target_date","venue_code","venue_name","race","race_id","rank","boat","registration_no","racer_name","grade","motor_no","boat_no","score","base_score","trend_adjustment_points","f_l_penalty_points","data_coverage_pct"]
    with Path(path).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)

def main():
    args=parse_args(); target_date=args.date
    try: datetime.strptime(target_date,"%Y%m%d")
    except ValueError: print("ERROR: --dateはYYYYMMDD形式です",file=sys.stderr); return 1
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    inp=Path(args.input) if args.input else out/f"prediction_input_enriched_morning_{target_date}.json"
    oj=out/f"morning_predictions_{target_date}.json"; oc=out/f"morning_predictions_{target_date}.csv"; vj=out/f"morning_predictions_validation_{target_date}.json"
    if not inp.exists(): print(f"ERROR: 入力ファイルがありません: {inp}",file=sys.stderr); return 1
    try:
        payload=json.loads(inp.read_text(encoding="utf-8"))
        if text(payload.get("target_date"))!=target_date: raise RuntimeError("target_date不一致")
        if text(payload.get("prediction_stage"))!="morning": raise RuntimeError("朝予測以外のprediction_inputです")
        violations=validate_current_day_no_results(payload)
        if violations: raise RuntimeError(f"当日結果データ混入: {violations[:5]}")
        races=payload.get("races")
        if not isinstance(races,list): raise RuntimeError("racesが不正です")
        prediction_races=[]; rows=[]; scores=[]
        for race in races:
            boats=race.get("boats")
            if not isinstance(boats,list) or len(boats)!=6: raise RuntimeError(f"6艇ではないレース: {race.get('race_id')}")
            details,missing=provisional_details(race)
            if missing: raise RuntimeError(f"履歴特徴量不足 {race.get('race_id')}: {','.join(missing)}")
            scored=[]
            for boat in boats:
                lane=to_int(boat.get("boat")); d=details[lane]; racer=boat.get("racer") or {}; motor=boat.get("motor") or {}; bm=boat.get("boat_machine") or {}
                history=boat.get("history") or {}
                row={"boat":lane,"registration_no":racer.get("registration_no"),"racer_name":racer.get("name"),"grade":racer.get("grade"),"motor_no":motor.get("motor_no"),"boat_no":bm.get("boat_no"),"score":round(d["score"],2),"base_score":round(d["score"],2),"trend_adjustment_points":0.0,"f_l_penalty_points":0.0,"data_coverage_pct":100.0,"components":{"racer_course":{"weight":40.0,"raw_score_0_1":round(d["racer_course"],6)},"grade":{"weight":20.0,"raw_score_0_1":round(d["grade"],6)},"motor":{"weight":20.0,"raw_score_0_1":round(d["motor"],6)},"boat":{"weight":5.0,"raw_score_0_1":round(d["boat"],6)},"national_top2":{"weight":15.0,"raw_score_0_1":round(d["national_top2"],6)}},"input_trace":{"history_feature_manifest":payload.get("history_feature_manifest"),"racer_30d":history.get("racer_30d"),"racer_90d":history.get("racer_90d"),"motor_30d":history.get("motor_30d"),"motor_90d":history.get("motor_90d"),"boat_30d":history.get("boat_30d"),"boat_90d":history.get("boat_90d"),"racer_venue":history.get("racer_venue"),"course_used":d.get("course"),"official_f_count":racer.get("official_f_count"),"official_l_count":racer.get("official_l_count"),"official_avg_st":racer.get("official_avg_st"),"official_fl_available":racer.get("official_fl_available",False),"candidate_components":{"f_l_holdings":{"available":racer.get("official_fl_available",False),"f_count":racer.get("official_f_count"),"l_count":racer.get("official_l_count"),"active_in_score":False},"motor_30d":{"available":history.get("motor_30d_available",False),"features":history.get("motor_30d"),"active_in_score":False},"parts_exchange":{"available":False,"value":"","active_in_score":False},"weather_water":{"available":False,"value":{},"active_in_score":False}}}}
                scored.append(row)
            scored.sort(key=lambda x:(-x["score"],x["boat"]))
            for rank,row in enumerate(scored,1):
                row["rank"]=rank; scores.append(row["score"])
                rows.append({"target_date":target_date,"venue_code":race.get("venue_code"),"venue_name":race.get("venue_name"),"race":race.get("race"),"race_id":race.get("race_id"),"rank":rank,**{k:row[k] for k in ["boat","registration_no","racer_name","grade","motor_no","boat_no","score","base_score","trend_adjustment_points","f_l_penalty_points","data_coverage_pct"]}})
            prediction_races.append({"race_id":race.get("race_id"),"date":race.get("date"),"venue_code":race.get("venue_code"),"venue_name":race.get("venue_name"),"race":race.get("race"),"race_name":race.get("race_name"),"deadline":race.get("deadline"),"morning_order":[x["boat"] for x in scored],"top3_boats":[x["boat"] for x in scored[:3]],"strength":prediction_strength(scored),"boats":scored})
        result={"schema_version":"1.0","model_version":MODEL_VERSION,"target_date":target_date,"prediction_stage":"morning","generated_at":datetime.now(JST).isoformat(),"score_note":"現行本番配点は維持。入力追跡情報として30/90日履歴・場適性等を保存し、未検証要素は勝手に加点しない。対象日結果は不使用。","weights":MORNING_WEIGHTS,"race_count":len(prediction_races),"boat_count":len(rows),"races":prediction_races}
        oj.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); write_csv(oc,rows)
        if len(prediction_races)!=len(races) or len(rows)!=len(races)*6: raise RuntimeError("予測件数不一致")
        validation={"status":"PASS","model_version":MODEL_VERSION,"target_date":target_date,"prediction_stage":"morning","race_count":len(prediction_races),"boat_count":len(rows),"score_min":round(min(scores),2),"score_max":round(max(scores),2),"score_average":round(sum(scores)/len(scores),2),"average_data_coverage_pct":100.0,"current_day_result_leakage":0,"course_used":False,"exhibition_used":False,"weights":MORNING_WEIGHTS,"external_public_csv_used":False}
        vj.write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding="utf-8")
        print("朝予測生成: PASS",len(prediction_races),"R",len(rows),"艇"); return 0
    except Exception as exc:
        vj.write_text(json.dumps({"status":"FAIL","model_version":MODEL_VERSION,"target_date":target_date,"error":str(exc),"generated_at":datetime.now(JST).isoformat()},ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"ERROR: {exc}",file=sys.stderr); return 1

if __name__=="__main__": sys.exit(main())
