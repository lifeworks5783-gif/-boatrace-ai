from __future__ import annotations
import csv,json,itertools
from pathlib import Path
DATE="20261005";OUT=Path("evaluations/plus10_formation_v1")
def I(x):
 try:return int(float(x))
 except:return None
def F(x):
 try:return float(x)
 except:return None
def rid(x):return "".join(c for c in str(x) if c.isdigit())
def read(path):
 with Path(path).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def parse(s):
 z=[]
 for x in str(s or "").split("/"):
  try:z.append(tuple(map(int,x.strip().split("-"))))
  except:pass
 return z
def met():return {"races":0,"trigger_races":0,"hits":0,"points":0,"invest":0,"return":0,"manshu":0}
def add(m,cs,a,p,tr):
 m["races"]+=1;m["trigger_races"]+=tr;m["points"]+=len(cs);m["invest"]+=len(cs)*100
 if a in cs:m["hits"]+=1;m["return"]+=p or 0;m["manshu"]+=int((p or 0)>=10000)
def fin(m):
 m["avg_points"]=round(m["points"]/m["races"],2);m["hit_rate_pct"]=round(100*m["hits"]/m["races"],2);m["roi_pct"]=round(100*m["return"]/m["invest"],2) if m["invest"] else None;return m
def main():
 morning=read(f"predictions/2026/10/05/morning_predictions_20261005.csv");live=read(f"predictions/2026/10/05/live/live_predictions_final_20261005.csv");forms=read(f"predictions/2026/10/05/live/formation_predictions_final_20261005.csv");res=read("archive/2026/10/05/results_20261005_all.csv")
 M={(rid(r["race_id"]),I(r["boat"])):F(r["score"]) for r in morning};L={}
 for r in live:L.setdefault(rid(r["race_id"]),[]).append(r)
 FF={rid(r["race_id"]):r for r in forms};RR={}
 for r in res:
  k=rid(f'{DATE}{int(r["venue_code"]):02d}{int(r["race"]):02d}')
  try:RR[k]=(tuple(map(int,r["trifecta"].split("-"))),I(r["trifecta_pay"]))
  except:pass
 variants=[]
 for th in [7.5,10,12.5,15]:
  for mode in ["top3_plus_hole_23","top2_plus_hole_23","top3_plus_hole_all23"]:
   base=met();sig=met();detail=[]
   for k,rows in L.items():
    if k not in FF or k not in RR:continue
    rows=sorted(rows,key=lambda x:I(x["rank"]) or 99);order=[I(x["boat"]) for x in rows];actual,pay=RR[k];bc=parse(FF[k]["combinations"]);holes=[q for q in order if M.get((k,q)) is not None and next(F(x["score"]) for x in rows if I(x["boat"])==q)-M[(k,q)]>=th and q not in order[:3]]
    sc=list(bc)
    if holes:
     h=holes[0];top=order[:3]
     extra=[]
     if mode=="top3_plus_hole_23":
      for a in top:
       for b,c in [(h,x) for x in top if x!=a]+[(x,h) for x in top if x!=a]:
        if len({a,b,c})==3:extra.append((a,b,c))
     elif mode=="top2_plus_hole_23":
      for a in top[:2]:
       for x in top:
        if x!=a:
         for b,c in [(h,x),(x,h)]:
          if len({a,b,c})==3:extra.append((a,b,c))
     else:
      pool=top+[h]
      extra=[c for c in itertools.permutations(pool,3) if h in c[1:]]
     sc=list(dict.fromkeys(sc+extra))
    add(base,bc,actual,pay,bool(holes));add(sig,sc,actual,pay,bool(holes))
    if holes:detail.append({"race_id":k,"holes":holes,"base_points":len(bc),"signal_points":len(sc),"actual":"-".join(map(str,actual)),"pay":pay,"base_hit":actual in bc,"signal_hit":actual in sc})
   variants.append({"threshold":th,"mode":mode,"base":fin(base),"signal":fin(sig),"trigger_details":detail})
 best=max(variants,key=lambda x:(x["signal"]["roi_pct"],x["signal"]["hit_rate_pct"]))
 out={"production_changed":False,"date":DATE,"definition":"actual live score - actual saved morning score >= threshold; scores unchanged; only extra trifecta combinations are added","variants":[{k:v for k,v in x.items() if k!="trigger_details"} for x in variants],"best":best}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
