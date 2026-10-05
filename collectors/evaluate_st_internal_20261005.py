import csv,json,itertools
from pathlib import Path
D=Path("evaluations/pdca_datasets/20261005/comparison_dataset_20261005.csv")
O=Path("evaluations/st_internal_20261005");O.mkdir(parents=True,exist_ok=True)
rows=list(csv.DictReader(D.open()))
def F(x):
 try:return float(x)
 except:return None
def I(x):
 try:return int(float(x))
 except:return None
def rank(vals,reverse=False):
 a=sorted(vals.items(),key=lambda z:(z[1],z[0]),reverse=reverse); n=len(a)
 return {k:(1-i/(n-1) if n>1 else .5) for i,(k,v) in enumerate(a)}
races={}
for r in rows:races.setdefault(r["race_id"],[]).append(r)
def structural(rs,live):
 vals={}
 for r in rs:
  b=I(r["boat"])
  course=.16*F(r["lw" if live else "cw"])+.08*F(r["l2" if live else "c2"])+.12*F(r["l3" if live else "c3"])+.04*(1-F(r["lst" if live else "cst"])/.3 if F(r["lst" if live else "cst"]) is not None else .5)
  vals[b]=course+.20*F(r["grade"])+.15*F(r["nat2"])+.08*F(r["motor_win"])+.12*F(r["motor_top3"])+.025*F(r["boat2"])+.025*F(r["boat3"])
 return vals
def delta_score(est,avg,scale):
 if est is None or avg is None:return .5
 d=est-avg
 # positive = slower than own average. scale is seconds for full +/- effect.
 return max(0,min(1,.5-d/(2*scale)))
base={}
for rid,rs in races.items():
 if len(rs)!=6:continue
 actual=sorted(rs,key=lambda r:(I(r["finish"]) if I(r["finish"]) else 99,I(r["boat"])))
 aset={I(x["boat"]) for x in actual[:3]}
 ms=structural(rs,False); ls=structural(rs,True)
 morning=sorted(ms,key=lambda b:(-ms[b],b))
 tr=rank({I(r["boat"]):F(r["etime"]) for r in rs if F(r["etime"]) is not None})
 sr=rank({I(r["boat"]):F(r["est"]) for r in rs if F(r["est"]) is not None and not (r["exhibition_st_flag"] or "").strip() and F(r["est"])>=0})
 base[rid]=(rs,aset,I(actual[0]["boat"]),ms,ls,morning,tr,sr)
splits=[(14,0),(10,4),(8,6),(7,7),(6,8),(4,10),(0,14)]
scales=[.02,.03,.04,.05,.06]
fvals=[.5,.4,.3,.2,.1,0]
out=[]
for rw,dw in splits:
 for scale in scales:
  for fv in fvals:
   n=oo=ox=xo=xx=t3=t1=exact=0
   for rid,(rs,aset,winner,ms,ls,morning,tr,sr) in base.items():
    if len(aset)!=3:continue
    mh=set(morning[:3])==aset
    scores={}
    for r in rs:
     b=I(r["boat"]); flag=bool((r["exhibition_st_flag"] or "").strip()) or (F(r["est"]) is not None and F(r["est"])<0)
     rankv=fv if flag else sr.get(b,.5)
     deltav=fv if flag else delta_score(F(r["est"]),F(r["lst"]),scale)
     scores[b]=.80*ls[b]+.06*tr.get(b,.5)+(rw/100)*rankv+(dw/100)*deltav
    pred=sorted(scores,key=lambda b:(-scores[b],b)); ph=set(pred[:3])==aset
    n+=1;t3+=ph;t1+=pred[0]==winner\n    actual_order=[I(x["boat"]) for x in sorted(rs,key=lambda r:(I(r["finish"]) if I(r["finish"]) else 99,I(r["boat"])))[:3]]\n    exact+=pred[:3]==actual_order
    if mh and ph:oo+=1
    elif mh:ox+=1
    elif ph:xo+=1
    else:xx+=1
   out.append(dict(rank_weight=rw,delta_weight=dw,delta_full_scale=scale,f_score=fv,n=n,oo=oo,ox=ox,xo=xo,xx=xx,top3=t3,top3_pct=round(100*t3/n,2),top1_pct=round(100*t1/n,2),exact_pct=round(100*exact/n,2)))
out.sort(key=lambda x:(x["ox"],-x["oo"],-x["top3"],-x["top1_pct"],-x["exact_pct"]))
json.dump({"definition":"80 structural + 6 exhibition time fixed; only 14-point exhibition-ST internal allocation varies","candidates":out[:100]},(O/"summary.json").open("w"),ensure_ascii=False,indent=2)
with (O/"candidates.csv").open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=out[0].keys());w.writeheader();w.writerows(out)
print(json.dumps(out[:20],ensure_ascii=False,indent=2))

# workflow trigger
