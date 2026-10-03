from __future__ import annotations
import csv,json,itertools
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
DATES=["20260930","20261001","20261002"]; OUT=Path("evaluations/phase4_combinations")
GRADE={"A1":1.0,"A2":0.75,"B1":0.45,"B2":0.25}
def f(v):
    try:return float(v)
    except:return None
def i(v):
    try:return int(float(v))
    except:return None
def dt(v):return datetime.strptime(v,"%Y%m%d").date()
def nid(v):return "".join(c for c in (v or "") if c.isdigit())
def archive():
    z=[]
    for p in Path("archive").glob("*/*/*/boat_results_*_all.csv"):
        with p.open(encoding="utf-8-sig",newline="") as h:z += list(csv.DictReader(h))
    return z
def program(d):
    for p in [Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/program_entries_{d}.csv"),Path(f"data/program_entries_{d}.csv")]:
        if p.exists():
            with p.open(encoding="utf-8-sig",newline="") as h:return {(nid(r["race_id"]),i(r["boat"])):r for r in csv.DictReader(h)}
    return {}
def hs(rs):
    x=[i(r.get("finish")) for r in rs if i(r.get("finish")) in range(1,7)]
    return {} if not x else {"win":sum(a==1 for a in x)/len(x),"top3":sum(a<=3 for a in x)/len(x)}
def rank(bs,k):
    if any(b.get(k) is None for b in bs):return None
    o=sorted(bs,key=lambda b:(-b[k],b["boat"]))
    return {b["boat"]:1-j/5 for j,b in enumerate(o)}
def evaluate(races,mods):
    n=a=b=c=0
    for rid,bs in races.items():
        if len(bs)!=6:continue
        base=rank(bs,"rc_win")
        qs=[(rank(bs,k),w) for k,w in mods]
        if base is None or any(q is None for q,w in qs):continue
        sc={x["boat"]:base[x["boat"]]+sum(w*q[x["boat"]] for q,w in qs) for x in bs}
        p=sorted(bs,key=lambda x:(-sc[x["boat"]],x["boat"])); y=sorted(bs,key=lambda x:(x["finish"],x["boat"]))
        n+=1;a+=p[0]["boat"]==y[0]["boat"];b+=set(x["boat"] for x in p[:3])==set(x["boat"] for x in y[:3]);c+=[x["boat"] for x in p[:3]]==[x["boat"] for x in y[:3]]
    return n,a,b,c
def pct(x,n):return round(100*x/n,2) if n else None
def main():
    rows=archive(); bd=defaultdict(list)
    for r in rows:
        if r.get("date") in DATES:bd[r["date"]].append(r)
    races=defaultdict(list)
    for d in DATES:
        td=dt(d); prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=dt(r["date"])<td]; pg=program(d)
        rg=defaultdict(list);rc=defaultdict(list);rv=defaultdict(list)
        for r in prior:
            reg=r.get("registration_no",""); v=str(r.get("venue_code","")).zfill(2); co=i(r.get("course"))
            if reg:rg[reg].append(r);rv[(reg,v)].append(r)
            if reg and co:rc[(reg,co)].append(r)
        for r in bd[d]:
            bo=i(r.get("boat"));fi=i(r.get("finish"))
            if bo not in range(1,7) or fi not in range(1,7):continue
            reg=r.get("registration_no","");v=str(r.get("venue_code","")).zfill(2);p=pg.get((nid(r.get("race_id")),bo),{})
            A=hs(rg[reg]);C=hs(rc[(reg,bo)]);V=hs(rv[(reg,v)])
            races[r["race_id"]].append({"boat":bo,"finish":fi,"rc_win":C.get("win"),"grade":GRADE.get(p.get("grade","")),
              "national_win":A.get("win"),"national_top3":A.get("top3"),"venue_win":V.get("win"),"venue_top3":V.get("top3"),
              "motor":f(p.get("motor_top2_rate"))/100 if f(p.get("motor_top2_rate")) is not None else None,
              "boatstat":f(p.get("boat_top2_rate"))/100 if f(p.get("boat_top2_rate")) is not None else None})
    # Main factors from phase3; scan 2- and 3-factor combinations at 10/20/30% each.
    fac={"grade":"級別","motor":"モーター","national_top3":"全国3連対","national_win":"全国1着","boatstat":"ボート"}
    rowsout=[]
    specs=[("BASE",[])]
    for k,l in fac.items():
        for w in [.1,.2,.3]: specs.append((f"{l}{int(w*100)}",[(k,w)]))
    for ks in itertools.combinations(["grade","motor","national_top3","national_win","boatstat"],2):
        for ws in itertools.product([.1,.2,.3],repeat=2):
            specs.append((" + ".join(f"{fac[k]}{int(w*100)}" for k,w in zip(ks,ws)),list(zip(ks,ws))))
    for ks in itertools.combinations(["grade","motor","national_top3","national_win"],3):
        for ws in itertools.product([.1,.2],repeat=3):
            specs.append((" + ".join(f"{fac[k]}{int(w*100)}" for k,w in zip(ks,ws)),list(zip(ks,ws))))
    for name,mods in specs:
        n,a,b,c=evaluate(races,mods)
        rowsout.append({"model":name,"races":n,"top1_matches":a,"top1_accuracy_pct":pct(a,n),"top3_matches":b,"top3_alignment_pct":pct(b,n),"exact_matches":c,"exact_alignment_pct":pct(c,n)})
    # fair ranking: only models with same race count as base
    base_n=next(x["races"] for x in rowsout if x["model"]=="BASE")
    fair=[x for x in rowsout if x["races"]==base_n]
    fair.sort(key=lambda x:(x["top1_accuracy_pct"],x["top3_alignment_pct"],x["exact_alignment_pct"]),reverse=True)
    OUT.mkdir(parents=True,exist_ok=True)
    fs=list(rowsout[0])
    with (OUT/"phase4_all_combinations.csv").open("w",encoding="utf-8",newline="") as h:w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(rowsout)
    with (OUT/"phase4_fair_ranked.csv").open("w",encoding="utf-8",newline="") as h:w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(fair)
    (OUT/"phase4_summary.json").write_text(json.dumps({"dates":DATES,"base_races":base_n,"rule":"同一母数のみ順位比較。1着一致 > TOP3整合 > 完全一致。対象日前90日のみ。","top20":fair[:20]},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"base_n":base_n,"top20":fair[:20]},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
