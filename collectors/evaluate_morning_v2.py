#!/usr/bin/env python3
import csv, json, math, re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "features"
DAILY = ROOT / "daily_inputs" / "2026" / "09" / "30"
ARCHIVE = ROOT / "archive" / "2026" / "09" / "30"
CONFIG_PATH = ROOT / "config" / "morning_v2_config.json"
OUT = ROOT / "evaluations" / "2026" / "09" / "30"

def f(v, default=None):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default

def keynum(v):
    try: return str(int(float(v)))
    except: return str(v or "").strip()

def norm_race_id(v):
    # entries = 20260930-02-01, results = 20260930_02_01
    return str(v or "").strip().replace("_", "-")

def clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))

def load_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as h:
        return list(csv.DictReader(h))

def index(rows, fn):
    return {fn(r): r for r in rows}

def rate(v, default=.5):
    x=f(v)
    if x is None: return default
    return x/100.0 if x > 1.0 else x

def inv_st(v, default=.5):
    x=f(v)
    if x is None: return default
    return clip(1.0-x/.35)

def finish_score(v, default=.5):
    x=f(v)
    if x is None: return default
    return clip((6.0-x)/5.0)

def trend_score(v, scale=1.0):
    x=f(v,0.0)
    return clip(.5+x/scale)

def smooth(value,n,prior,k):
    value=f(value); n=f(n,0.0)
    if value is None: return prior
    return (n*value+k*prior)/(n+k)

def series_score(raw):
    vals=[int(x) for x in re.findall(r"[1-6]",str(raw or ""))]
    if not vals: return .5
    ws=list(range(1,len(vals)+1))
    return sum(((7-v)/6)*w for v,w in zip(vals,ws))/sum(ws)

def within_race_rank(rows,field):
    ordered=sorted(rows,key=lambda r:(r[field],-r["boat"]),reverse=True)
    n=max(1,len(ordered)-1)
    return {r["boat"]:1.0-i/n for i,r in enumerate(ordered)}

def main():
    cfg=json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    W=cfg["outer_weights"]; IW=cfg["inner_weights"]; K=cfg["shrinkage"]

    racer=load_csv(FEATURES/"racer_features.csv")
    rc=load_csv(FEATURES/"racer_course_features.csv")
    rv=load_csv(FEATURES/"racer_venue_features.csv")
    vc=load_csv(FEATURES/"venue_course_features.csv")
    motor=load_csv(FEATURES/"motor_features.csv")
    boat=load_csv(FEATURES/"boat_features.csv")
    entries=load_csv(DAILY/"program_entries_20260930.csv")
    results=load_csv(ARCHIVE/"boat_results_20260930_all.csv")

    IR=index(racer,lambda r:keynum(r["registration_no"]))
    IRC=index(rc,lambda r:keynum(r["registration_no"])+"|"+keynum(r["course"]))
    IRV=index(rv,lambda r:keynum(r["registration_no"])+"|"+keynum(r["venue_code"]))
    IVC=index(vc,lambda r:keynum(r["venue_code"])+"|"+keynum(r["course"]))
    IM=index(motor,lambda r:keynum(r["venue_code"])+"|"+keynum(r["motor_no"]))
    IB=index(boat,lambda r:keynum(r["venue_code"])+"|"+keynum(r["boat_no"]))
    IRES=index(results,lambda r:norm_race_id(r["race_id"])+"|"+keynum(r["boat"]))

    grades={"A1":1.0,"A2":.75,"B1":.45,"B2":.25}
    groups=defaultdict(list)

    for e in entries:
        reg=keynum(e["registration_no"]); venue=keynum(e["venue_code"]); lane=int(float(e["boat"]))
        r=IR.get(reg,{}); c=IRC.get(reg+"|"+str(lane),{}); v=IRV.get(reg+"|"+venue,{})
        vcx=IVC.get(venue+"|"+str(lane),{})
        m=IM.get(venue+"|"+keynum(e["motor_no"]),{})
        b=IB.get(venue+"|"+keynum(e["boat_no"]),{})

        wi=IW["venue_course"]
        venue_course=(wi["win_rate"]*rate(vcx.get("d90_win_rate"))+
                      wi["top2_rate"]*rate(vcx.get("d90_top2_rate"))+
                      wi["top3_rate"]*rate(vcx.get("d90_top3_rate"))+
                      wi["avg_st"]*inv_st(vcx.get("d90_avg_st")))

        n=f(c.get("d90_starts"),0)
        wr=smooth(rate(c.get("d90_win_rate")),n,rate(vcx.get("d90_win_rate")),K["racer_course_k"])
        t2=smooth(rate(c.get("d90_top2_rate")),n,rate(vcx.get("d90_top2_rate")),K["racer_course_k"])
        t3=smooth(rate(c.get("d90_top3_rate")),n,rate(vcx.get("d90_top3_rate")),K["racer_course_k"])
        cst=smooth(f(c.get("d90_avg_st")),n,f(vcx.get("d90_avg_st"),.20),K["racer_course_k"])
        wi=IW["racer_course"]
        racer_course=wi["win_rate"]*wr+wi["top2_rate"]*t2+wi["top3_rate"]*t3+wi["avg_st"]*inv_st(cst)

        wi=IW["base_ability"]
        base_ability=(wi["national_win_rate"]*clip(f(e.get("national_win_rate"),5)/10)+
                      wi["national_top2_rate"]*rate(e.get("national_top2_rate"))+
                      wi["history_d90_top3_rate"]*rate(r.get("d90_top3_rate")))

        wi=IW["recent_form"]
        recent=(wi["last5_top3"]*rate(r.get("last5_top3_rate"))+
                wi["last10_top3"]*rate(r.get("last10_top3_rate"))+
                wi["d30_top3"]*rate(r.get("d30_top3_rate"))+
                wi["last10_avg_finish"]*finish_score(r.get("last10_avg_finish"))+
                wi["top3_trend"]*trend_score(r.get("trend_top3_rate_30v90"),.5))

        def block(row,name):
            z=IW[name]
            return (z["d90_top3"]*rate(row.get("d90_top3_rate"))+
                    z["d30_top3"]*rate(row.get("d30_top3_rate"))+
                    z["top3_trend"]*trend_score(row.get("trend_top3_rate_30v90"),.5))
        venue_fit=block(v,"venue_fit"); motor_s=block(m,"motor"); boat_s=block(b,"boat")

        wi=IW["st_stability"]
        st=(wi["d90_avg_st"]*inv_st(r.get("d90_avg_st"))+
            wi["d30_avg_st"]*inv_st(r.get("d30_avg_st"))+
            wi["course_d90_avg_st"]*inv_st(c.get("d90_avg_st"))+
            wi["st_trend"]*trend_score(f(r.get("d90_avg_st"),.20)-f(r.get("d30_avg_st"),.20),.10))

        groups[norm_race_id(e["race_id"])].append({
            "date":e["date"],"venue_code":venue,"venue_name":e.get("venue_name",""),
            "race":int(float(e["race"])),"race_id":norm_race_id(e["race_id"]),"boat":lane,
            "registration_no":reg,"racer_name":e.get("racer_name",""),
            "venue_course":venue_course,"racer_course":racer_course,"base_ability":base_ability,
            "recent_form":recent,"venue_fit":venue_fit,"motor":motor_s,
            "current_series":series_score(e.get("series_results_raw")),"st_stability":st,
            "boat_component":boat_s,"grade":grades.get(e.get("grade"),.4),
            "weight":clip((60-f(e.get("weight_kg"),52))/15)
        })

    expected=sum(len(rows) for rows in groups.values())
    matched=sum(1 for rid,rows in groups.items() for r in rows if IRES.get(rid+"|"+str(r["boat"])))
    if matched != expected:
        raise RuntimeError(f"結果結合不足: {matched}/{expected}艇")

    detail=[]; summary=[]; hits=exact=0
    venue_stats=defaultdict(lambda:{"races":0,"hits":0,"exact":0})
    fields=["venue_course","racer_course","base_ability","recent_form","venue_fit","motor",
            "current_series","st_stability","boat_component","grade","weight"]
    weight_key={"boat_component":"boat"}

    for race_id,rows in sorted(groups.items()):
        ranks={x:within_race_rank(rows,x) for x in fields}
        for r in rows:
            total=0.0
            for x in fields:
                r[x+"_rank"]=ranks[x][r["boat"]]
                total+=W[weight_key.get(x,x)]*r[x+"_rank"]
            r["score"]=total
            res=IRES[race_id+"|"+str(r["boat"])]
            fv=f(res.get("finish"))
            r["finish"]=int(fv) if fv is not None else None
            detail.append(r)

        pred=[r["boat"] for r in sorted(rows,key=lambda x:x["score"],reverse=True)[:3]]
        finish_top=sorted((r["finish"],r["boat"]) for r in rows if r["finish"] in (1,2,3))
        if len(finish_top)!=3 or [x[0] for x in finish_top] != [1,2,3]:
            raise RuntimeError(f"{race_id}: 1〜3着結果異常 {finish_top}")
        actual=[boat_no for _,boat_no in finish_top]
        hit=set(pred)==set(actual); ex=pred==actual
        hits+=int(hit); exact+=int(ex)
        vs=venue_stats[rows[0]["venue_code"]]; vs["races"]+=1; vs["hits"]+=int(hit); vs["exact"]+=int(ex)
        summary.append({"race_id":race_id,"venue_code":rows[0]["venue_code"],"venue_name":rows[0]["venue_name"],
                        "race":rows[0]["race"],"predicted_top3":"-".join(map(str,pred)),
                        "actual_top3":"-".join(map(str,actual)),"top3_hit":int(hit),"exact_hit":int(ex)})

    OUT.mkdir(parents=True,exist_ok=True)
    def write(name,rows):
        with (OUT/name).open("w",encoding="utf-8-sig",newline="") as h:
            w=csv.DictWriter(h,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    write("morning_v2_race_results_20260930.csv",summary)
    write("morning_v2_boat_scores_20260930.csv",detail)

    n=len(summary)
    report={"model":cfg["model_name"],"target_date":cfg["target_date"],"races":n,
            "result_joined_boats":matched,
            "top3_hits":hits,"top3_hit_rate_pct":round(hits/n*100,2),
            "exact_hits":exact,"exact_hit_rate_pct":round(exact/n*100,2),
            "outer_weights":W,"inner_weights":IW,
            "venue_results":{k:{**v,"top3_hit_rate_pct":round(v["hits"]/v["races"]*100,2),
                                "exact_rate_pct":round(v["exact"]/v["races"]*100,2)}
                             for k,v in sorted(venue_stats.items())}}
    (OUT/"morning_v2_report_20260930.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"morning_v2_config_snapshot_20260930.json").write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
