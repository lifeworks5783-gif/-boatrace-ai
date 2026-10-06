from __future__ import annotations
import csv, json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path("evaluations/live_logic_combination_20260930_20261003")
GRADE = {"A1":1.00,"A2":0.75,"B1":0.45,"B2":0.25}

def F(v):
    try: return float(v)
    except (TypeError,ValueError): return None

def I(v):
    try: return int(float(v))
    except (TypeError,ValueError): return None

def DT(v): return datetime.strptime(v,"%Y%m%d").date()
def nid(v): return "".join(c for c in str(v or "") if c.isdigit())

def read(p):
    with open(p,encoding="utf-8-sig",newline="") as h:
        return list(csv.DictReader(h))

def archive_rows():
    rows=[]
    for p in Path("archive").glob("*/*/*/boat_results_*_all.csv"):
        rows += read(p)
    return rows

def candidate_dates():
    out=[]
    for p in Path("daily_inputs").glob("*/*/*/base/program_entries_*.csv"):
        d=p.stem.split("_")[-1]
        if len(d)!=8 or not d.isdigit(): continue
        live=Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/live")
        arc=Path(f"archive/{d[:4]}/{d[4:6]}/{d[6:8]}/boat_results_{d}_all.csv")
        if live.exists() and arc.exists(): out.append(d)
    return sorted(set(out))[-7:]

def program(d):
    ps=[
        Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/base/program_entries_{d}.csv"),
        Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/program_entries_{d}.csv"),
        Path(f"data/program_entries_{d}.csv"),
    ]
    for p in ps:
        if p.exists():
            return {(nid(r.get("race_id")),I(r.get("boat"))):r for r in read(p)}
    return {}

def live_entries(d):
    root=Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/live")
    ps=list(root.glob(f"backfill/beforeinfo_entries_{d}.csv"))
    if not ps:
        ps=sorted(root.glob(f"snapshots/*/beforeinfo_entries_{d}.csv"))
    best={}
    for p in ps:
        for r in read(p):
            k=(nid(r.get("race_id")),I(r.get("boat")))
            if k[0] and k[1] in range(1,7): best[k]=r
    return best

def stat(rs):
    fs=[I(r.get("finish")) for r in rs if I(r.get("finish")) in range(1,7)]
    sts=[F(r.get("st")) for r in rs if F(r.get("st")) is not None]
    if not fs: return {}
    return {
        "win":sum(x==1 for x in fs)/len(fs),
        "top2":sum(x<=2 for x in fs)/len(fs),
        "top3":sum(x<=3 for x in fs)/len(fs),
        "avg_st":sum(sts)/len(sts) if sts else None,
        "st_samples":len(sts),
    }

def rankmap(bs,key,lower=False):
    if len(bs)<3: return None
    if any(b.get(key) is None for b in bs): return None
    o=sorted(bs,key=lambda b:((b[key] if lower else -b[key]),b["boat"]))
    if len(o)==1: return {o[0]["boat"]:0.5}
    return {b["boat"]:1-i/(len(o)-1) for i,b in enumerate(o)}

def personal_st_score(b):
    if b.get("is_f"): return 0.4
    st=b.get("est"); avg=b.get("racer_avg_st"); n=b.get("racer_st_samples") or 0
    if st is None or avg is None or n<10: return 0.5
    return max(0.0,min(1.0,0.5-(st-avg)/0.12))

def build_races(rows,dates):
    bydate=defaultdict(list)
    for r in rows: bydate[str(r.get("date") or "")].append(r)
    allr={}
    for d in dates:
        td=DT(d)
        prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=DT(r["date"])<td]
        pg=program(d); lv=live_entries(d)
        rg=defaultdict(list); rc=defaultdict(list); mg=defaultdict(list); bg=defaultdict(list)
        for r in prior:
            reg=str(r.get("registration_no") or "")
            c=I(r.get("course")); v=str(r.get("venue_code") or "").zfill(2)
            m=I(r.get("motor_no")); bn=I(r.get("boat_no"))
            if reg: rg[reg].append(r)
            if reg and c: rc[(reg,c)].append(r)
            if m is not None: mg[(v,m)].append(r)
            if bn is not None: bg[(v,bn)].append(r)
        rr=defaultdict(list)
        for r in bydate[d]:
            bo=I(r.get("boat")); fi=I(r.get("finish")); rid=nid(r.get("race_id"))
            if bo not in range(1,7) or fi not in range(1,7): continue
            P=pg.get((rid,bo),{}); Q=lv.get((rid,bo))
            if not Q: continue
            v=str(r.get("venue_code") or "").zfill(2); reg=str(r.get("registration_no") or "")
            rs=stat(rg[reg])
            entry=I(Q.get("exhibition_course")) or bo
            cs=stat(rc[(reg,entry)])
            if not cs: cs=rs
            m=I(r.get("motor_no")); m=m if m is not None else I(P.get("motor_no"))
            bn=I(r.get("boat_no")); bn=bn if bn is not None else I(P.get("boat_no"))
            ms=stat(mg[(v,m)]) if m is not None else {}
            bs=stat(bg[(v,bn)]) if bn is not None else {}
            official_m2=F(P.get("motor_top2_rate") or P.get("official_motor_top2_rate") or P.get("motor_2rate"))
            if official_m2 is not None and official_m2>1: official_m2/=100.0
            mw=ms.get("win"); m3=ms.get("top3")
            if mw is None: mw=official_m2
            if m3 is None: m3=official_m2
            est=F(Q.get("exhibition_st_seconds") or Q.get("exhibition_st"))
            flag=str(Q.get("exhibition_st_flag") or "").strip().upper()
            rr[rid].append({
                "boat":bo,"finish":fi,
                "lw":cs.get("win"),"l2":cs.get("top2"),"l3":cs.get("top3"),"lst":cs.get("avg_st"),
                "grade":GRADE.get(str(P.get("grade") or "").strip().upper()),
                "nat2":rs.get("top2"),"mw":mw,"m3":m3,"b2":bs.get("top2"),"b3":bs.get("top3"),
                "etime":F(Q.get("exhibition_time")),"est":est,"is_f":flag=="F" or (est is not None and est<0),
                "racer_avg_st":rs.get("avg_st"),"racer_st_samples":rs.get("st_samples",0),
            })
        for rid,bs0 in rr.items():
            bs=sorted(bs0,key=lambda x:x["boat"])
            if len(bs)<3: continue
            maps={}
            for key,lower in [("lw",False),("l2",False),("l3",False),("lst",True),("grade",False),("nat2",False),("mw",False),("m3",False),("b2",False),("b3",False),("etime",True)]:
                maps[key]=rankmap(bs,key,lower)
            if any(v is None for v in maps.values()): continue
            structural={}
            for b in bs:
                lane=b["boat"]
                racer=.40*maps["lw"][lane]+.20*maps["l2"][lane]+.30*maps["l3"][lane]+.10*maps["lst"][lane]
                motor=.40*maps["mw"][lane]+.60*maps["m3"][lane]
                boat=.50*maps["b2"][lane]+.50*maps["b3"][lane]
                structural[lane]=.40*racer+.20*maps["grade"][lane]+.20*motor+.05*boat+.15*maps["nat2"][lane]
                b["time_score"]=maps["etime"][lane]
                b["st_score"]=personal_st_score(b)
            actual=sorted(bs,key=lambda x:(x["finish"],x["boat"]))
            allr[(d,rid)]={"date":d,"race_id":rid,"boats":bs,"structural":structural,"actual":[x["boat"] for x in actual]}
    return allr

def order(rec,time_w,st_w):
    sw=1-time_w-st_w
    return sorted(rec["boats"],key=lambda b:(-(sw*rec["structural"][b["boat"]]+time_w*b["time_score"]+st_w*b["st_score"]),b["boat"]))

def evaluate(records,time_w,st_w,current_orders):
    bydate={}
    totals={"n":0,"top1":0,"winner_top3":0,"top3_set":0,"exact3":0,"rank_sum":0.0,"top1_gain":0,"top1_loss":0,"top3_gain":0,"top3_loss":0}
    for d in sorted({r["date"] for r in records.values()}):
        z={k:0 for k in ["n","top1","winner_top3","top3_set","exact3","rank_sum"]}
        for k,r in records.items():
            if r["date"]!=d: continue
            pred=[x["boat"] for x in order(r,time_w,st_w)]
            act=r["actual"]; winner=act[0]; rank=pred.index(winner)+1
            z["n"]+=1; z["rank_sum"]+=rank; z["top1"]+=rank==1; z["winner_top3"]+=rank<=3
            hit3=set(pred[:3])==set(act[:3]); ex=pred[:3]==act[:3]
            z["top3_set"]+=hit3; z["exact3"]+=ex
            cur=current_orders[k]; cur_rank=cur.index(winner)+1; cur3=set(cur[:3])==set(act[:3])
            totals["top1_gain"]+=(cur_rank!=1 and rank==1); totals["top1_loss"]+=(cur_rank==1 and rank!=1)
            totals["top3_gain"]+=(not cur3 and hit3); totals["top3_loss"]+=(cur3 and not hit3)
        if z["n"]:
            bydate[d]={
                "n":z["n"],"top1_pct":round(100*z["top1"]/z["n"],2),
                "winner_top3_pct":round(100*z["winner_top3"]/z["n"],2),
                "top3_set_pct":round(100*z["top3_set"]/z["n"],2),
                "exact3_pct":round(100*z["exact3"]/z["n"],2),
                "avg_winner_rank":round(z["rank_sum"]/z["n"],3),
            }
            for key in ["n","top1","winner_top3","top3_set","exact3","rank_sum"]: totals[key]+=z[key]
    n=totals["n"]
    vals=[v["top3_set_pct"] for v in bydate.values()]
    pooled={
        "n":n,"top1_pct":round(100*totals["top1"]/n,2),"winner_top3_pct":round(100*totals["winner_top3"]/n,2),
        "top3_set_pct":round(100*totals["top3_set"]/n,2),"exact3_pct":round(100*totals["exact3"]/n,2),
        "avg_winner_rank":round(totals["rank_sum"]/n,3),
        "top1_gain":totals["top1_gain"],"top1_loss":totals["top1_loss"],"top1_net":totals["top1_gain"]-totals["top1_loss"],
        "top3_gain":totals["top3_gain"],"top3_loss":totals["top3_loss"],"top3_net":totals["top3_gain"]-totals["top3_loss"],
        "daily_top3_spread_pt":round(max(vals)-min(vals),2) if vals else None,
    }
    return bydate,pooled

def main():
    dates=candidate_dates()
    if not dates: raise RuntimeError("検証可能日がありません")
    rows=archive_rows(); records=build_races(rows,dates)
    if not records: raise RuntimeError("検証レースがありません")
    current_orders={k:[x["boat"] for x in order(r,.06,.14)] for k,r in records.items()}
    combos=[]
    for tp in [0,2,4,6,8]:
        for sp in [0,4,6,8,10,12,14]:
            tw=tp/100; sw=sp/100
            if tw+sw>=1: continue
            bd,p=evaluate(records,tw,sw,current_orders)
            combos.append({"structural_pct":100-tp-sp,"time_pct":tp,"st_pct":sp,"by_date":bd,"pooled":p})
    combos.sort(key=lambda x:(-x["pooled"]["top3_set_pct"],-x["pooled"]["top1_pct"],x["pooled"]["daily_top3_spread_pt"],x["pooled"]["avg_winner_rank"]))
    current=next(x for x in combos if x["time_pct"]==6 and x["st_pct"]==14)
    OUT.mkdir(parents=True,exist_ok=True)
    payload={
        "logic":"current live structure + exhibition time rank + personal d90 ST delta",
        "production_weights":{"structural_pct":80,"time_pct":6,"st_pct":14},
        "dates":dates,"race_records":len(records),"current":current,"ranked_candidates":combos,
        "note":"検証専用。production code/weights are not modified."
    }
    (OUT/"current_summary.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    flat=[]
    for x in combos:
        p=x["pooled"]
        flat.append({"structural_pct":x["structural_pct"],"time_pct":x["time_pct"],"st_pct":x["st_pct"],**p})
    with (OUT/"current_summary.csv").open("w",encoding="utf-8",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(flat[0])); w.writeheader(); w.writerows(flat)
    print(json.dumps({"dates":dates,"race_records":len(records),"current":current,"top10":combos[:10]},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
