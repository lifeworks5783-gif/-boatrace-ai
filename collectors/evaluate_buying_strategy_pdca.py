from __future__ import annotations
import csv, json, math
from collections import defaultdict
from pathlib import Path

OUT=Path("evaluations/pdca_buying_strategy/latest")
Q=[.25,.40,.50,.60,.75,.85]

def f(v):
    try:return float(v)
    except:return None

def read_csv(p):
    with Path(p).open(encoding="utf-8-sig",newline="") as h:return list(csv.DictReader(h))

def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))

def available_ai_dates():
    out=[]
    for p in Path("evaluations/2026/10").glob("*/ai_score_simulation_*.json"):
        d=p.stem.split("_")[-1]
        form=Path(f"predictions/{d[:4]}/{d[4:6]}/{d[6:8]}/live/formation_predictions_final_{d}.json")
        if form.exists(): out.append(d)
    return sorted(set(out))

def base_records(d):
    form=load_json(f"predictions/{d[:4]}/{d[4:6]}/{d[6:8]}/live/formation_predictions_final_{d}.json")
    ev=load_json(f"evaluations/{d[:4]}/{d[4:6]}/{d[6:8]}/ai_score_simulation_{d}.json")
    truth={x["race_id"]:x for x in ev.get("details",[])}
    out=[]
    for race in form.get("races",[]):
        ap=race.get("ai_score_prediction") or {}
        det=truth.get(race.get("race_id"))
        if not det: continue
        base=ap.get("base_120_combinations") or ap.get("all_120_combinations") or []
        if len(base)<13: continue
        out.append({
            "date":d,"race_id":race["race_id"],"actual":det.get("actual_trifecta"),
            "pay":int(det.get("trifecta_payout_100yen") or 0),
            "base":[{"combination":x["combination"],"score":float(x["score"])} for x in base]
        })
    return out

def exact_signal_records(d):
    base=base_records(d)
    livep=Path(f"predictions/{d[:4]}/{d[4:6]}/{d[6:8]}/live/live_predictions_final_{d}.csv")
    if not livep.exists(): return []
    live=defaultdict(list)
    for r in read_csv(livep):live[r["race_id"]].append(r)
    out=[]
    for rec in base:
        rr=sorted(live.get(rec["race_id"],[]),key=lambda x:int(float(x.get("rank") or 99)))
        if len(rr)<5: continue
        scores={}
        ok=True
        for r in rr:
            boat=int(float(r["boat"]))
            lv=f(r.get("score")); mo=f(r.get("morning_score_reference")); rk=int(float(r.get("rank") or 99))
            if lv is None or mo is None: ok=False;break
            scores[boat]={"live":lv,"morning":mo,"rank":rk}
        if not ok or len(scores)<5: continue
        rec=dict(rec);rec["scores"]=scores;out.append(rec)
    return out

def legacy_v1_rank(rec,weight=.40):
    boats=sorted(rec["scores"])
    raw={b:math.log(max(rec["scores"][b]["live"],1e-9)/max(rec["scores"][b]["morning"],1e-9)) for b in boats}
    avg=sum(raw.values())/len(raw)
    mom={b:raw[b]-avg for b in boats}
    scale=max([abs(x) for x in mom.values()] or [1.0])
    if scale<1e-9:scale=1.0
    sig={b:mom[b]/scale for b in boats}
    arr=[]
    for i,x in enumerate(rec["base"]):
        a,b,c=map(int,x["combination"].split("-"))
        boost=math.exp(weight*(.25*sig.get(a,0)+.85*sig.get(b,0)+.70*sig.get(c,0)))
        arr.append((x["score"]*boost,i,x["combination"]))
    arr.sort(key=lambda z:(-z[0],z[1]))
    return [x[2] for x in arr]

def v2_rank(rec):
    signals={}
    for b,s in rec["scores"].items():
        rise=s["live"]-s["morning"]
        if s["rank"]>3 and rise>=10.0:signals[b]={"rise":rise,"rank":s["rank"]}
    arr=[]
    for i,x in enumerate(rec["base"]):
        parts=list(map(int,x["combination"].split("-")));bonus=0.0
        for pos,b in enumerate(parts):
            s=signals.get(b)
            if not s:continue
            att=1.0 if s["rank"]<=4 else .7 if s["rank"]==5 else 1.0
            bonus+=1.5*s["rise"]*(0.0,.6,.4)[pos]*att
        arr.append((x["score"]+bonus,i,x["combination"]))
    arr.sort(key=lambda z:(-z[0],z[1]))
    return [x[2] for x in arr],signals

def agg_rank(records,method,points,signal_only=False):
    n=hits=ret=manshu=0
    bydate=defaultdict(lambda:{"races":0,"hits":0,"return":0})
    for r in records:
        base=[x["combination"] for x in r["base"]]
        if method=="base":ranking=base;signals={}
        elif method=="v1":ranking=legacy_v1_rank(r);signals=v2_rank(r)[1]
        else:ranking,signals=v2_rank(r)
        if signal_only and not signals:continue
        n+=1;bydate[r["date"]]["races"]+=1
        hit=r["actual"] in ranking[:points]
        if hit:
            hits+=1;ret+=r["pay"];manshu+=r["pay"]>=10000
            bydate[r["date"]]["hits"]+=1;bydate[r["date"]]["return"]+=r["pay"]
    inv=n*points*100
    bd={}
    for d,z in sorted(bydate.items()):
        dinv=z["races"]*points*100
        bd[d]={"races":z["races"],"hits":z["hits"],"hit_rate_pct":round(100*z["hits"]/z["races"],2) if z["races"] else None,
               "roi_pct":round(100*z["return"]/dinv,2) if dinv else None}
    return {"races":n,"hits":hits,"hit_rate_pct":round(100*hits/n,2) if n else None,"points_per_race":points,
            "investment":inv,"return":ret,"profit":ret-inv,"roi_pct":round(100*ret/inv,2) if inv else None,
            "manshu_hits":manshu,"by_date":bd}

def formation_compare():
    rows=[]
    latest_version=None
    for p in sorted(Path("evaluations/2026/10").glob("*/prediction_evaluation_*.json")):
        j=load_json(p); fs=j.get("formation_simulation") or {}; v=fs.get("model_version")
        if v:latest_version=v
        rows.append((p,j))
    agg=defaultdict(lambda:{"races":0,"hits":0,"points":0,"investment":0,"return":0})
    used=[]
    for p,j in rows:
        fs=j.get("formation_simulation") or {}
        if fs.get("model_version")!=latest_version:continue
        d=(j.get("target_date") or p.stem.split("_")[-1]);used.append(d)
        for k,v in (fs.get("by_formation_type") or {}).items():
            a=agg[k]
            for x in ["races","hits","points","investment","return"]:a[x]+=v.get(x) or 0
    out={}
    for k,a in agg.items():
        n=a["races"];inv=a["investment"]
        out[k]={**a,"hit_rate_pct":round(100*a["hits"]/n,2) if n else None,
                "avg_points":round(a["points"]/n,2) if n else None,
                "profit":a["return"]-inv,"roi_pct":round(100*a["return"]/inv,2) if inv else None}
    return {"model_version":latest_version,"dates":sorted(used),"by_formation_type":out}

def quantiles(records,key):
    a=sorted(r[key] for r in records)
    return [a[int(q*(len(a)-1))] for q in Q] if a else []

def enrich_gaps(records):
    out=[]
    for r in records:
        s=[x["score"] for x in r["base"]]
        if len(s)<13:continue
        z=dict(r);z.update({"g6":s[5]-s[6],"g8":s[7]-s[8],"g10":s[9]-s[10]})
        out.append(z)
    return out

def point_eval(records,t6=None,t8=None,t10=None,fixed=None):
    hits=ret=pts=0;counts={6:0,8:0,10:0,12:0}
    for r in records:
        if fixed is not None:p=fixed
        else:
            p=12
            if r["g6"]>=t6:p=6
            elif r["g8"]>=t8:p=8
            elif r["g10"]>=t10:p=10
        counts[p]+=1;pts+=p
        if r["actual"] in [x["combination"] for x in r["base"][:p]]:
            hits+=1;ret+=r["pay"]
    inv=pts*100;n=len(records)
    return {"races":n,"hits":hits,"hit_rate_pct":round(100*hits/n,2) if n else None,
            "avg_points":round(pts/n,2) if n else None,"investment":inv,"return":ret,"profit":ret-inv,
            "roi_pct":round(100*ret/inv,2) if inv else None,"point_counts":counts}

def point_compare(all_by_date):
    dates=sorted(all_by_date)
    if len(dates)<2:return {"status":"insufficient_dates","dates":dates}
    train_dates=dates[:-1];test_date=dates[-1]
    train=enrich_gaps([r for d in train_dates for r in all_by_date[d]])
    test=enrich_gaps(all_by_date[test_date])
    fixed={str(p):{"train":point_eval(train,fixed=p),"test":point_eval(test,fixed=p)} for p in (6,8,10,12)}
    base8=fixed["8"]["train"]
    cand=[]
    for t6 in quantiles(train,"g6"):
      for t8 in quantiles(train,"g8"):
       for t10 in quantiles(train,"g10"):
        tr=point_eval(train,t6,t8,t10)
        if tr["hit_rate_pct"]>=base8["hit_rate_pct"] and tr["avg_points"]<=10:
            cand.append((tr["roi_pct"],t6,t8,t10,tr))
    cand.sort(reverse=True,key=lambda x:x[0])
    if not cand:return {"status":"no_candidate","dates":dates,"fixed":fixed}
    _,t6,t8,t10,tr=cand[0]
    te=point_eval(test,t6,t8,t10)
    pooled=enrich_gaps(train+test)
    po=point_eval(pooled,t6,t8,t10)
    return {"status":"ok","train_dates":train_dates,"test_date":test_date,"selection_rule":"train ROI max subject to train hit-rate >= fixed8 and avg_points <=10",
            "thresholds":{"gap6":t6,"gap8":t8,"gap10":t10},"fixed":fixed,
            "selected":{"train":tr,"test":te,"pooled":po}}

def main():
    dates=available_ai_dates()
    allbase={d:base_records(d) for d in dates}
    exact=[]
    for d in dates:exact+=exact_signal_records(d)
    signal={
      "definition_note":"V1 here is legacy relative-momentum overlay transplanted onto the same current AI base ranking for apples-to-apples comparison; it is not the original reconstructed V1 base model.",
      "exact_dates":sorted(set(r["date"] for r in exact)),
      "records":len(exact),"signal_races":sum(1 for r in exact if v2_rank(r)[1]),
      "all_races":{},"signal_races_only":{}
    }
    for p in (8,10,12):
        signal["all_races"][str(p)]={m:agg_rank(exact,m,p,False) for m in ("base","v1","v2")}
        signal["signal_races_only"][str(p)]={m:agg_rank(exact,m,p,True) for m in ("base","v1","v2")}
    out={"production_changed":False,"generated_from_saved_data":True,"pdca_targets":["1_signal_v1_v2_none","2_formation_type_roi","3_dynamic_ai_points"],
         "signal_comparison":signal,"formation_comparison":formation_compare(),"dynamic_points":point_compare(allbase)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    md=["# 買い方PDCA 1・2・3 継続比較","",f"- exact signal records: {signal['records']}","- production changed: false","",
        "## 1 シグナル V1/V2/なし","同一current AI base上で比較。V1は旧相対モメンタム補正を移植した比較用。","",
        "## 2 フォーメーション別ROI",f"model: {out['formation_comparison']['model_version']}","",
        "## 3 AI点数6/8/10/12・条件分岐","最新日をholdoutにして閾値ルールを比較。"]
    (OUT/"README.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
