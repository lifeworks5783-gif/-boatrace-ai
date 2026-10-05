#!/usr/bin/env python3
import csv,json,os
from collections import defaultdict
D="20261005"
LP="predictions/2026/10/05/live/live_predictions_final_20261005.json"
MP="predictions/2026/10/05/morning_predictions_20261005.json"
RP="archive/2026/10/05/boat_results_20261005_all.csv"
def readcsv(p):
 with open(p,encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
feat={}
for r in readcsv("features/racer_features.csv"):
 try: feat[str(r.get("registration_no",""))]=(int(r.get("d90_st_samples") or 0),float(r["d90_avg_st"]) if r.get("d90_avg_st") else None)
 except: feat[str(r.get("registration_no",""))]=(0,None)
L=json.load(open(LP,encoding="utf-8"));M=json.load(open(MP,encoding="utf-8"))
truth=defaultdict(dict)
for x in readcsv(RP):
 try: truth[x["race_id"].replace("_","-")][int(x["boat"])]=int(float(x["finish"]))
 except: pass
mm={r["race_id"]:r for r in M.get("races",[])}
def delta_score(est,av,scale):
 if est is None or av is None:return .5
 return max(0,min(1,.5-(float(est)-av)/(2*scale)))
splits=[(14,0),(10,4),(8,6),(7,7),(6,8),(4,10),(0,14)]
scales=[.02,.03,.04,.05,.06]
fvals=[.5,.4,.3,.2,.1,0]
out=[]
for rw,dw in splits:
 for scale in scales:
  for fv in fvals:
   n=oo=ox=xo=xx=t3=t1=exact=0
   for r in L.get("races",[]):
    rid=r["race_id"];tr=truth.get(rid)
    if not tr:continue
    actual=[b for b,_ in sorted(tr.items(),key=lambda z:z[1]) if _ in (1,2,3)]
    if len(actual)!=3:continue
    mr=mm.get(rid,{})
    morning=[int(x) for x in (mr.get("morning_order") or mr.get("order") or mr.get("predicted_order") or [])]
    if not morning: morning=[int(b["boat"]) for b in sorted(r["boats"],key=lambda z:float(z.get("morning_score_reference",0)),reverse=True)]
    me=set(morning[:3])==set(actual)
    scores={}
    for b in r["boats"]:
     lane=int(b["boat"]); comp=b.get("components") or {}; curst=((comp.get("exST") or {}).get("raw_score_0_1"))
     if curst is None:curst=.5
     base=float(b["score"])/100-.14*float(curst)
     isf=bool(b.get("exhibition_f")); est=b.get("exhibition_st"); n90,av=feat.get(str(b.get("registration_no","")),(0,None))
     rankv=fv if isf else float(curst)
     deltav=fv if isf else delta_score(est,av if n90>=10 else None,scale)
     scores[lane]=base+(rw/100)*rankv+(dw/100)*deltav
    pred=sorted(scores,key=lambda b:(-scores[b],b)); le=set(pred[:3])==set(actual)
    n+=1;t3+=le;t1+=pred[0]==actual[0];exact+=pred[:3]==actual
    if me and le:oo+=1
    elif me:ox+=1
    elif le:xo+=1
    else:xx+=1
   out.append(dict(rank_weight=rw,delta_weight=dw,delta_full_scale=scale,f_score=fv,n=n,oo=oo,ox=ox,xo=xo,xx=xx,top3=t3,top3_pct=round(100*t3/n,2),top1_pct=round(100*t1/n,2),exact_pct=round(100*exact/n,2)))
out.sort(key=lambda x:(x["ox"],-x["oo"],-x["top3"],-x["xo"],-x["top1_pct"],-x["exact_pct"]))
os.makedirs("evaluations/st_internal_exact_20261005",exist_ok=True)
json.dump({"definition":"10/5 saved production live score; remove only current 14% exST and replace with rank/personal-delta/F internal mix; structural80 and exTime6 unchanged","candidates":out},open("evaluations/st_internal_exact_20261005/summary.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
with open("evaluations/st_internal_exact_20261005/candidates.csv","w",encoding="utf-8",newline="") as f:
 w=csv.DictWriter(f,fieldnames=out[0].keys());w.writeheader();w.writerows(out)
print(json.dumps(out[:25],ensure_ascii=False,indent=2))
