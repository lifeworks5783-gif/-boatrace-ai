from __future__ import annotations
import csv,json,itertools
from pathlib import Path
DATES=["20260930","20261001","20261002","20261003","20261004","20261005"];OUT=Path("evaluations/plus10_formation_multiday_v1")
def I(x):
 try:return int(float(x))
 except:return None
def F(x):
 try:return float(x)
 except:return None
def rid(x):return "".join(c for c in str(x) if c.isdigit())
def read(p):
 with Path(p).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def parse(s):
 z=[]
 for x in str(s or "").split("/"):
  try:z.append(tuple(map(int,x.strip().split("-"))))
  except:pass
 return z
def met():return {"races":0,"trigger_races":0,"hits":0,"points":0,"invest":0,"return":0,"manshu":0}
def add(m,cs,a,p,tr):
 m["races"]+=1;m["trigger_races"]+=int(tr);m["points"]+=len(cs);m["invest"]+=100*len(cs)
 if a in cs:m["hits"]+=1;m["return"]+=p or 0;m["manshu"]+=int((p or 0)>=10000)
def fin(m):
 return {**m,"avg_points":round(m["points"]/m["races"],2) if m["races"] else 0,"hit_rate_pct":round(100*m["hits"]/m["races"],2) if m["races"] else 0,"roi_pct":round(100*m["return"]/m["invest"],2) if m["invest"] else 0}
def paths(d):
 y,m,dd=d[:4],d[4:6],d[6:8]
 return f"predictions/{y}/{m}/{dd}/live/live_predictions_final_{d}.csv",f"predictions/{y}/{m}/{dd}/live/formation_predictions_final_{d}.csv",f"archive/{y}/{m}/{dd}/results_{d}_all.csv"
def day(d,th,mode):
 lp,fp,rp=paths(d);live=read(lp);forms=read(fp);res=read(rp);L=defaultdict(list)
 for r in live:L[rid(r["race_id"])].append(r)
 FF={rid(r["race_id"]):r for r in forms};RR={}
 for r in res:
  k=rid(f'{d}{int(r["venue_code"]):02d}{int(r["race"]):02d}')
  try:RR[k]=(tuple(map(int,r["trifecta"].split("-"))),I(r["trifecta_pay"]))
  except:pass
 b,s=met(),met()
 for k,rows in L.items():
  if k not in FF or k not in RR:continue
  rows=sorted(rows,key=lambda x:I(x["rank"]) or 99);order=[I(x["boat"]) for x in rows];a,p=RR[k];bc=parse(FF[k]["combinations"])
  holes=[I(x["boat"]) for x in rows if F(x.get("morning_score_reference")) is not None and F(x.get("score")) is not None and F(x["score"])-F(x["morning_score_reference"])>=th and I(x["boat"]) not in order[:3]]
  sc=list(bc)
  if holes:
   h=max(holes,key=lambda q:next(F(x["score"])-F(x["morning_score_reference"]) for x in rows if I(x["boat"])==q));top=order[:3];extra=[]
   anchors=top if mode=="top3" else top[:2]
   for aa in anchors:
    for x in top:
     if x!=aa:
      for bb,cc in [(h,x),(x,h)]:
       if len({aa,bb,cc})==3:extra.append((aa,bb,cc))
   sc=list(dict.fromkeys(sc+extra))
  add(b,bc,a,p,holes);add(s,sc,a,p,holes)
 return fin(b),fin(s)
from collections import defaultdict
def merge(ms):
 z=met()
 for m in ms:
  for k in ["races","trigger_races","hits","points","invest","return","manshu"]:z[k]+=m[k]
 return fin(z)
def main():
 out=[]
 for th in [7.5,10,10.5,11,11.5,12,12.5,13,15]:
  for mode in ["top2","top3"]:
   ds={};bb=[];ss=[]
   for d in DATES:
    b,s=day(d,th,mode);ds[d]={"base":b,"signal":s};bb.append(b);ss.append(s)
   out.append({"threshold":th,"mode":mode,"combined":{"base":merge(bb),"signal":merge(ss)},"by_date":ds})
 best=max(out,key=lambda x:(x["combined"]["signal"]["roi_pct"],x["combined"]["signal"]["hit_rate_pct"]))
 OUT.mkdir(parents=True,exist_ok=True);(OUT/"summary.json").write_text(json.dumps({"production_changed":False,"dates":DATES,"definition":"live score - saved morning_score_reference; score logic unchanged; only extra combinations","variants":out,"best":best},ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"best":best},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
