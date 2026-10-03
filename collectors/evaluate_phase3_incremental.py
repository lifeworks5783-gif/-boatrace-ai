from __future__ import annotations
import csv,json,math
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
DATES=["20260930","20261001","20261002"]
OUT=Path("evaluations/phase3_incremental")
GRADE={"A1":1.0,"A2":0.75,"B1":0.45,"B2":0.25}
def f(v):
    try:return float(v)
    except:return None
def i(v):
    try:return int(float(v))
    except:return None
def dt(v): return datetime.strptime(v,"%Y%m%d").date()
def normid(v): return "".join(c for c in (v or "") if c.isdigit())
def load_archive():
    z=[]
    for p in sorted(Path("archive").glob("*/*/*/boat_results_*_all.csv")):
        with p.open(encoding="utf-8-sig",newline="") as h:
            z += [r for r in csv.DictReader(h) if r.get("date") and r.get("race_id") and r.get("boat")]
    return z
def load_program(d):
    ps=[Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/program_entries_{d}.csv"),Path(f"data/program_entries_{d}.csv")]
    out={}
    for p in ps:
        if p.exists():
            with p.open(encoding="utf-8-sig",newline="") as h:
                for r in csv.DictReader(h): out[(normid(r.get("race_id")),i(r.get("boat")))]=r
            break
    return out
def hs(rows):
    fs=[i(r.get("finish")) for r in rows if i(r.get("finish")) in range(1,7)]
    if not fs:return {}
    return {"win":sum(x==1 for x in fs)/len(fs),"top3":sum(x<=3 for x in fs)/len(fs),"n":len(fs)}
def rankpct(vals,key,reverse=False):
    good=[(b,b.get(key)) for b in vals if b.get(key) is not None]
    if len(good)!=6:return None
    ordered=sorted(good,key=(lambda x:(x[1],x[0]["boat"])) if reverse else (lambda x:(-x[1],x[0]["boat"])))
    # 1.00 best ... 0.00 worst
    return {b["boat"]:1-j/5 for j,(b,v) in enumerate(ordered)}
def eval_model(races,name,fn):
    n=t1=t3=ex=0
    for rid,boats in races.items():
        if len(boats)!=6:continue
        scores=fn(boats)
        if scores is None:continue
        pred=sorted(boats,key=lambda b:(-scores[b["boat"]],b["boat"]))
        act=sorted(boats,key=lambda b:(b["finish"],b["boat"]))
        n+=1;t1+=pred[0]["boat"]==act[0]["boat"]
        t3+=set(b["boat"] for b in pred[:3])==set(b["boat"] for b in act[:3])
        ex+=[b["boat"] for b in pred[:3]]==[b["boat"] for b in act[:3]]
    return {"name":name,"races":n,"top1_matches":t1,"top1_accuracy_pct":round(t1/n*100,2) if n else None,
      "top3_matches":t3,"top3_alignment_pct":round(t3/n*100,2) if n else None,
      "exact_matches":ex,"exact_alignment_pct":round(ex/n*100,2) if n else None}
def main():
    rows=load_archive(); bydate=defaultdict(list)
    for r in rows:bydate[r["date"]].append(r)
    allr=defaultdict(list); byday={}
    for d in DATES:
        td=dt(d); prior=[r for r in rows if td-timedelta(days=90)<=dt(r["date"])<td]; prog=load_program(d)
        rg=defaultdict(list);rc=defaultdict(list);rv=defaultdict(list)
        for r in prior:
            reg=r.get("registration_no","");c=i(r.get("course"));v=str(r.get("venue_code","")).zfill(2)
            if reg:rg[reg].append(r);rv[(reg,v)].append(r)
            if reg and c:rc[(reg,c)].append(r)
        races=defaultdict(list)
        for r in bydate[d]:
            b=i(r.get("boat"));fin=i(r.get("finish"))
            if b not in range(1,7) or fin not in range(1,7):continue
            rid=r["race_id"];v=str(r.get("venue_code","")).zfill(2);reg=r.get("registration_no","");p=prog.get((normid(rid),b),{})
            a=hs(rg[reg]);c=hs(rc[(reg,b)]);vv=hs(rv[(reg,v)])
            x={"boat":b,"finish":fin,"rc_win":c.get("win"),"rc_top3":c.get("top3"),"national_win":a.get("win"),"national_top3":a.get("top3"),
               "venue_win":vv.get("win"),"venue_top3":vv.get("top3"),"grade":GRADE.get(p.get("grade","")),
               "motor":(f(p.get("motor_top2_rate"))/100 if f(p.get("motor_top2_rate")) is not None else None),
               "boatstat":(f(p.get("boat_top2_rate"))/100 if f(p.get("boat_top2_rate")) is not None else None)}
            races[rid].append(x);allr[rid].append(x)
        byday[d]=races
    # Base is course-specific win rate. Corrections are rank-normalized so unlike units are comparable.
    specs=[("BASE rc_win",[]),("BASE + grade",[("grade",.10)]),("BASE + national_win",[("national_win",.10)]),
      ("BASE + national_top3",[("national_top3",.10)]),("BASE + venue_win",[("venue_win",.10)]),("BASE + venue_top3",[("venue_top3",.10)]),
      ("BASE + motor",[("motor",.10)]),("BASE + boat",[("boatstat",.10)])]
    # Also scan mild correction strengths to avoid declaring 10% arbitrarily.
    scan=[]
    for key,label in [("grade","grade"),("national_win","national_win"),("national_top3","national_top3"),("venue_win","venue_win"),("venue_top3","venue_top3"),("motor","motor"),("boatstat","boat")]:
        for w in [.02,.05,.10,.15,.20]:scan.append((f"BASE + {label} {int(w*100)}%",[(key,w)]))
    specs += scan
    def make_fn(corr):
        def fn(bs):
            base=rankpct(bs,"rc_win")
            if base is None:return None
            ranks={}
            for k,w in corr:
                q=rankpct(bs,k)
                if q is None:return None
                ranks[k]=(q,w)
            return {b["boat"]:base[b["boat"]]+sum(w*q[b["boat"]] for q,w in ranks.values()) for b in bs}
        return fn
    summary=[eval_model(allr,n,make_fn(c)) for n,c in specs]
    # unique names only, and per-day for main 10% variants + base
    seen=set();summary=[x for x in summary if not (x["name"] in seen or seen.add(x["name"]))]
    detail=[]
    for d,races in byday.items():
        for n,c in specs[:8]:
            x=eval_model(races,n,make_fn(c));x["date"]=d;detail.append(x)
    summary.sort(key=lambda x:((x["top1_accuracy_pct"] or -1),(x["top3_alignment_pct"] or -1),(x["exact_alignment_pct"] or -1)),reverse=True)
    OUT.mkdir(parents=True,exist_ok=True)
    fields=["name","races","top1_matches","top1_accuracy_pct","top3_matches","top3_alignment_pct","exact_matches","exact_alignment_pct"]
    with (OUT/"phase3_incremental_summary.csv").open("w",encoding="utf-8",newline="") as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(summary)
    with (OUT/"phase3_incremental_by_date.csv").open("w",encoding="utf-8",newline="") as h:
        fs=["date"]+fields;w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(detail)
    (OUT/"phase3_incremental_summary.json").write_text(json.dumps({"dates":DATES,"method":"BASE=選手×枠コース90日1着率。追加要素はレース内順位を0..1化し、2/5/10/15/20%の穏やかな補正として比較。対象日より前90日のみ。結果はラベルのみ。","priority":"1着一致 > TOP3整合 > 完全一致","summary":summary},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary[:15],ensure_ascii=False,indent=2))
if __name__=="__main__":main()
