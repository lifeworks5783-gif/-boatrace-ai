from __future__ import annotations
import csv,json
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path

DATES=["20260930","20261001","20261002"]
OUT=Path("evaluations/phase2_single_factor")
GRADE={"A1":1.0,"A2":0.75,"B1":0.45,"B2":0.25}

def f(v):
    try:return float(v)
    except:return None
def i(v):
    try:return int(float(v))
    except:return None
def date(v): return datetime.strptime(v,"%Y%m%d").date()

def load_archive():
    rows=[]
    for p in sorted(Path("archive").glob("*/*/*/boat_results_*_all.csv")):
        with p.open(encoding="utf-8-sig",newline="") as h:
            for r in csv.DictReader(h):
                if r.get("date") and r.get("race_id") and r.get("boat"):
                    rows.append(r)
    return rows

def load_program(d):
    p=Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/program_entries_{d}.csv")
    if not p.exists(): p=Path(f"data/program_entries_{d}.csv")
    out={}
    if p.exists():
        with p.open(encoding="utf-8-sig",newline="") as h:
            for r in csv.DictReader(h): out[(r.get("race_id"),i(r.get("boat")))]=r
    return out

def hist_summary(rows):
    n=len(rows)
    fins=[i(x.get("finish")) for x in rows if i(x.get("finish")) in range(1,7)]
    sts=[f(x.get("st")) for x in rows if f(x.get("st")) is not None]
    ex=[f(x.get("exhibition_time")) for x in rows if f(x.get("exhibition_time")) is not None]
    if not n:return {}
    return {
      "win_rate":sum(x==1 for x in fins)/n,
      "top2_rate":sum(x<=2 for x in fins)/n,
      "top3_rate":sum(x<=3 for x in fins)/n,
      "avg_finish":sum(fins)/len(fins) if fins else None,
      "avg_st":sum(sts)/len(sts) if sts else None,
      "avg_exhibition":sum(ex)/len(ex) if ex else None,
      "starts":n,
    }

def evaluate_factor(races, factor, reverse=False):
    n=top1=top3=exact=0
    for rid,boats in races.items():
        if len(boats)!=6: continue
        actual=sorted(boats,key=lambda x:(x["finish"],x["boat"]))
        vals=[b for b in boats if b.get(factor) is not None]
        if len(vals)!=6: continue
        pred=sorted(boats,key=lambda x:((x[factor] if reverse else -x[factor]),x["boat"]))
        n+=1
        top1 += pred[0]["boat"]==actual[0]["boat"]
        top3 += set(x["boat"] for x in pred[:3])==set(x["boat"] for x in actual[:3])
        exact += [x["boat"] for x in pred[:3]]==[x["boat"] for x in actual[:3]]
    return {"races":n,"top1_matches":top1,"top1_accuracy_pct":round(top1/n*100,2) if n else None,
            "top3_matches":top3,"top3_alignment_pct":round(top3/n*100,2) if n else None,
            "exact_matches":exact,"exact_alignment_pct":round(exact/n*100,2) if n else None}

def main():
    allrows=load_archive()
    bydate=defaultdict(list)
    for r in allrows: bydate[r["date"]].append(r)
    combined=defaultdict(list)
    details=[]
    factors=[
      ("racer_d90_win","選手90日1着率",False),("racer_d90_top2","選手90日2連対率",False),
      ("racer_d90_top3","選手90日3連対率",False),("racer_d90_avg_finish","選手90日平均着順",True),
      ("racer_d90_avg_st","選手90日平均ST",True),("grade","級別係数",False),
      ("racer_course_d90_win","選手×コース90日1着率",False),("racer_course_d90_top3","選手×コース90日3連対率",False),
      ("racer_venue_d90_win","選手×場90日1着率",False),("racer_venue_d90_top3","選手×場90日3連対率",False),
      ("motor_d90_win","モーター90日1着率",False),("motor_d90_top2","モーター90日2連対率",False),("motor_d90_top3","モーター90日3連対率",False),
      ("boat_d90_win","ボート90日1着率",False),("boat_d90_top2","ボート90日2連対率",False),("boat_d90_top3","ボート90日3連対率",False),
    ]
    for d in DATES:
        td=date(d); start=td-timedelta(days=90); prog=load_program(d)
        prior=[r for r in allrows if start <= date(r["date"]) < td]
        rg=defaultdict(list); rc=defaultdict(list); rv=defaultdict(list); mg=defaultdict(list); bg=defaultdict(list)
        for r in prior:
            reg=r.get("registration_no",""); course=i(r.get("course")); venue=r.get("venue_code","").zfill(2)
            if reg: rg[reg].append(r)
            if reg and course: rc[(reg,course)].append(r)
            if reg and venue: rv[(reg,venue)].append(r)
            mn=i(r.get("motor_no")); bn=i(r.get("boat_no"))
            if mn is not None: mg[(venue,mn)].append(r)
            if bn is not None: bg[(venue,bn)].append(r)
        races=defaultdict(list)
        for r in bydate[d]:
            fin=i(r.get("finish")); boat=i(r.get("boat"))
            if fin not in range(1,7) or boat not in range(1,7): continue
            rid=r["race_id"]; venue=r.get("venue_code","").zfill(2); reg=r.get("registration_no","")
            pr=prog.get((rid,boat),{})
            course=boat # morning-safe: frame as assumed course
            rs=hist_summary(rg[reg]); rcs=hist_summary(rc[(reg,course)]); rvs=hist_summary(rv[(reg,venue)])
            ms=hist_summary(mg[(venue,i(r.get("motor_no")))]) if i(r.get("motor_no")) is not None else {}
            bs=hist_summary(bg[(venue,i(r.get("boat_no")))]) if i(r.get("boat_no")) is not None else {}
            b={"boat":boat,"finish":fin,
               "racer_d90_win":rs.get("win_rate"),"racer_d90_top2":rs.get("top2_rate"),"racer_d90_top3":rs.get("top3_rate"),"racer_d90_avg_finish":rs.get("avg_finish"),"racer_d90_avg_st":rs.get("avg_st"),
               "grade":GRADE.get(pr.get("grade","")),
               "racer_course_d90_win":rcs.get("win_rate"),"racer_course_d90_top3":rcs.get("top3_rate"),
               "racer_venue_d90_win":rvs.get("win_rate"),"racer_venue_d90_top3":rvs.get("top3_rate"),
               "motor_d90_win":ms.get("win_rate"),"motor_d90_top2":ms.get("top2_rate"),"motor_d90_top3":ms.get("top3_rate"),
               "boat_d90_win":bs.get("win_rate"),"boat_d90_top2":bs.get("top2_rate"),"boat_d90_top3":bs.get("top3_rate")}
            races[rid].append(b); combined[rid].append(b)
        for key,label,rev in factors:
            x=evaluate_factor(races,key,rev); x.update({"date":d,"factor":key,"label":label}); details.append(x)
    summary=[]
    for key,label,rev in factors:
        x=evaluate_factor(combined,key,rev); x.update({"factor":key,"label":label}); summary.append(x)
    summary.sort(key=lambda x:((x["top1_accuracy_pct"] or -1),(x["top3_alignment_pct"] or -1),(x["exact_alignment_pct"] or -1)),reverse=True)
    OUT.mkdir(parents=True,exist_ok=True)
    fields=["factor","label","races","top1_matches","top1_accuracy_pct","top3_matches","top3_alignment_pct","exact_matches","exact_alignment_pct"]
    with (OUT/"single_factor_summary_20260930_20261002.csv").open("w",encoding="utf-8",newline="") as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows([{k:x.get(k) for k in fields} for x in summary])
    with (OUT/"single_factor_by_date_20260930_20261002.csv").open("w",encoding="utf-8",newline="") as h:
        fs=["date"]+fields;w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows([{k:x.get(k) for k in fs} for x in details])
    payload={"dates":DATES,"definition":{"top1":"予測1位=実1着","top3":"予測上位3艇と実上位3艇が順不同で3艇すべて一致","exact":"予測1-3位と実1-3着が順番まで一致"},"leakage_guard":"各対象日より前90日だけで特徴量を再計算。対象日結果は評価ラベルのみに使用。朝コースは枠番を使用。","summary":summary}
    (OUT/"single_factor_summary_20260930_20261002.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
