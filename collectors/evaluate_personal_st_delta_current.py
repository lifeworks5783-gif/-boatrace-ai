#!/usr/bin/env python3
import csv,json,glob,os,statistics
from collections import defaultdict

def readcsv(p):
 with open(p,encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
feat={}
for r in readcsv("features/racer_features.csv"):
 try:
  n=int(r.get("d90_st_samples") or 0); av=float(r["d90_avg_st"]) if r.get("d90_avg_st") else None
 except: n,av=0,None
 feat[str(r.get("registration_no",""))]=(n,av)

out={"definition":"delta = exhibition_st - racer d90_avg_st; negative=faster than personal baseline","dates":{},"groups":{}}
groups=defaultdict(list)
for d in ["20261001","20261002","20261003","20261004"]:
 lp=f"predictions/{d[:4]}/{d[4:6]}/{d[6:8]}/live/live_predictions_final_{d}.json"
 mp=f"predictions/{d[:4]}/{d[4:6]}/{d[6:8]}/morning_predictions_{d}.json"
 rp=f"archive/{d[:4]}/{d[4:6]}/{d[6:8]}/boat_results_{d}_all.csv"
 if not all(os.path.exists(x) for x in [lp,mp,rp]): continue
 L=json.load(open(lp,encoding="utf-8")); M=json.load(open(mp,encoding="utf-8"))
 truth=defaultdict(dict)
 for x in readcsv(rp):
  try: truth[x["race_id"].replace("_","-")][int(x["boat"])]=int(float(x["finish"]))
  except: pass
 mm={r["race_id"]:r for r in M.get("races",[])}
 cnt=defaultdict(int); cases=[]
 for r in L.get("races",[]):
  rid=r["race_id"]; tr=truth.get(rid)
  if not tr: continue
  actual=[b for b,_ in sorted(tr.items(),key=lambda z:z[1])][:3]
  live=[int(x) for x in r.get("live_order",[])]
  mr=mm.get(rid,{})
  morning=[int(x) for x in (mr.get("morning_order") or mr.get("order") or mr.get("predicted_order") or [])]
  if not morning:
   morning=[int(b["boat"]) for b in sorted(r["boats"],key=lambda z:float(z.get("morning_score_reference",0)),reverse=True)]
  me=set(morning[:3])==set(actual); le=set(live[:3])==set(actual)
  typ="x_to_o" if (not me and le) else "o_to_x" if (me and not le) else "other"
  if typ=="other": continue
  cnt[typ]+=1
  vals=[]
  for b in r["boats"]:
   reg=str(b.get("registration_no","")); n,av=feat.get(reg,(0,None)); est=b.get("exhibition_st")
   if av is None or est is None or n<10 or b.get("exhibition_f"): continue
   delta=float(est)-av
   vals.append(delta); groups[typ].append(delta)
  if vals: cases.append({"race_id":rid,"type":typ,"mean_delta":round(statistics.mean(vals),4),"n":len(vals)})
 out["dates"][d]={"counts":dict(cnt),"cases_with_personal_st":len(cases)}
for k,v in groups.items():
 out["groups"][k]={"boat_samples":len(v),"mean_delta":round(statistics.mean(v),4),"median_delta":round(statistics.median(v),4),"faster_than_personal_pct":round(100*sum(x<0 for x in v)/len(v),2)}
os.makedirs("evaluations/personal_st_delta",exist_ok=True)
json.dump(out,open("evaluations/personal_st_delta/summary.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False,indent=2))
