#!/usr/bin/env python3
import csv,json,os,statistics
DATES=["20260930","20261001","20261002","20261003","20261004","20261005"]
CANDS=[
 ("現行_順位14",14,0,.04,.5),
 ("候補1_本人差14",0,14,.06,.4),
 ("候補2_順位7_本人差7",7,7,.04,.3),
 ("候補3_順位6_本人差8",6,8,.06,.3),
]
def F(x):
 try:return float(x)
 except:return None
def I(x):
 try:return int(float(x))
 except:return None
def rank(vals,low=False):
 a=sorted(vals.items(),key=lambda z:((z[1] if low else -z[1]),z[0]));n=len(a)
 return {k:(1-i/(n-1) if n>1 else .5) for i,(k,v) in enumerate(a)}
def ds(est,av,scale):
 if est is None or av is None:return .5
 return max(0,min(1,.5-(est-av)/(2*scale)))
def struct(rs,live):
 specs=[("lw" if live else "cw",.16,False),("l2" if live else "c2",.08,False),("l3" if live else "c3",.12,False),("lst" if live else "cst",.04,True),("grade",.20,False),("nat2",.15,False),("motor_win",.08,False),("motor_top3",.12,False),("boat2",.025,False),("boat3",.025,False)]
 maps={k:rank({I(r["boat"]):F(r[k]) for r in rs if F(r[k]) is not None},low) for k,w,low in specs}
 return {I(r["boat"]):sum(w*maps[k].get(I(r["boat"]),.5) for k,w,low in specs) for r in rs}
allout={}
for d in DATES:
 p=f"evaluations/pdca_datasets/{d}/comparison_dataset_{d}.csv"
 rows=list(csv.DictReader(open(p,encoding="utf-8-sig")))
 races={}
 for r in rows:races.setdefault(r["race_id"],[]).append(r)
 prepared=[]
 for rid,rs in races.items():
  if len(rs)!=6:continue
  actual=[r for r in rs if I(r["finish"]) in (1,2,3)]
  if len(actual)!=3:continue
  actual=sorted(actual,key=lambda r:I(r["finish"])); aset={I(r["boat"]) for r in actual}
  ms=struct(rs,False);ls=struct(rs,True); morning=sorted(ms,key=lambda b:(-ms[b],b)); mh=set(morning[:3])==aset
  tr=rank({I(r["boat"]):F(r["etime"]) for r in rs if F(r["etime"]) is not None},True)
  sr=rank({I(r["boat"]):F(r["est"]) for r in rs if F(r["est"]) is not None and not (r["exhibition_st_flag"] or "").strip() and F(r["est"])>=0},True)
  prepared.append((rs,aset,I(actual[0]["boat"]),[I(x["boat"]) for x in actual],ls,mh,tr,sr))
 day={}
 for name,rw,dw,scale,fv in CANDS:
  n=oo=ox=xo=xx=t3=t1=exact=0
  for rs,aset,winner,aorder,ls,mh,tr,sr in prepared:
   sc={}
   for r in rs:
    b=I(r["boat"]);flag=bool((r["exhibition_st_flag"] or "").strip()) or (F(r["est"]) is not None and F(r["est"])<0)
    rv=fv if flag else sr.get(b,.5); dv=fv if flag else ds(F(r["est"]),F(r["lst"]),scale)
    sc[b]=.80*ls[b]+.06*tr.get(b,.5)+(rw/100)*rv+(dw/100)*dv
   pred=sorted(sc,key=lambda b:(-sc[b],b)); ph=set(pred[:3])==aset
   n+=1;t3+=ph;t1+=pred[0]==winner;exact+=pred[:3]==aorder
   if mh and ph:oo+=1
   elif mh:ox+=1
   elif ph:xo+=1
   else:xx+=1
  day[name]={"n":n,"oo":oo,"ox":ox,"xo":xo,"xx":xx,"top3":t3,"top3_pct":round(100*t3/n,2),"top1_pct":round(100*t1/n,2),"exact_pct":round(100*exact/n,2)}
 allout[d]=day
summary={}
for name,*_ in CANDS:
 vals=[allout[d][name] for d in DATES]
 summary[name]={"races":sum(x["n"] for x in vals),"top3_total_pct":round(100*sum(x["top3"] for x in vals)/sum(x["n"] for x in vals),2),"top1_weighted_pct":round(sum(x["top1_pct"]*x["n"] for x in vals)/sum(x["n"] for x in vals),2),"oo":sum(x["oo"] for x in vals),"ox":sum(x["ox"] for x in vals),"xo":sum(x["xo"] for x in vals),"top3_daily_avg":round(statistics.mean(x["top3_pct"] for x in vals),2),"top3_daily_min":min(x["top3_pct"] for x in vals),"top3_daily_max":max(x["top3_pct"] for x in vals)}
os.makedirs("evaluations/st_candidate_crossvalidation",exist_ok=True)
json.dump({"definition":"Cross-date validation from reusable PDCA daily datasets; 80 structural + 6 exTime fixed, only ST14 internal allocation varies","dates":allout,"summary":summary},open("evaluations/st_candidate_crossvalidation/summary.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps(summary,ensure_ascii=False,indent=2))
