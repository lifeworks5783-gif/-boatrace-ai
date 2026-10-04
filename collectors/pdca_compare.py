from __future__ import annotations
import argparse,csv,json
from pathlib import Path

def F(v):
 try:return float(v)
 except:return None
def I(v):
 try:return int(float(v))
 except:return None
def rank6(rows,key,lower=False):
 vals=[(I(r["boat"]),F(r.get(key))) for r in rows]
 if len(vals)!=6 or any(b is None or v is None for b,v in vals):return None
 vals.sort(key=lambda x:((x[1] if lower else -x[1]),x[0]))
 return {b:1-i/5 for i,(b,_) in enumerate(vals)}
DEFAULT={"course_win":16,"course_top2":8,"course_top3":12,"course_avg_st":4,"grade":20,"national_top2":15,"motor_win":8,"motor_top3":12,"boat_top2":2.5,"boat_top3":2.5}
ALIASES={"cw":"course_win","c2":"course_top2","c3":"course_top3","cst":"course_avg_st","nat2":"national_top2","boat2":"boat_top2","boat3":"boat_top3"}
LOWER={"course_avg_st","exhibition_time","exhibition_st"}

def load_rows(path):
 with open(path,encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def score(rows,weights):
 maps={}
 for key in weights:
  src={"course_win":"cw","course_top2":"c2","course_top3":"c3","course_avg_st":"cst","national_top2":"nat2","boat_top2":"boat2","boat_top3":"boat3"}.get(key,key)
  maps[key]=rank6(rows,src,key in LOWER)
  if maps[key] is None:return None
 return {I(r["boat"]):sum((weights[k]/100)*maps[k][I(r["boat"])] for k in weights) for r in rows}
def evaluate(races,base,cand):
 z={"races":0,"base_top3":0,"candidate_top3":0,"base_top1":0,"candidate_top1":0,"changed_order":0,"top3_improved":0,"top3_worsened":0,"top1_improved":0,"top1_worsened":0}
 details=[]
 for rid,rows in races.items():
  if len(rows)!=6:continue
  bs=score(rows,base);cs=score(rows,cand)
  if bs is None or cs is None:continue
  actual=sorted(rows,key=lambda r:(I(r["finish"]),I(r["boat"])))
  bo=sorted(bs,key=lambda b:(-bs[b],b));co=sorted(cs,key=lambda b:(-cs[b],b))
  actual3={I(r["boat"]) for r in actual[:3]};bh=set(bo[:3])==actual3;ch=set(co[:3])==actual3
  b1=bo[0]==I(actual[0]["boat"]);c1=co[0]==I(actual[0]["boat"])
  z["races"]+=1;z["base_top3"]+=bh;z["candidate_top3"]+=ch;z["base_top1"]+=b1;z["candidate_top1"]+=c1
  z["changed_order"]+=bo!=co;z["top3_improved"]+=(not bh and ch);z["top3_worsened"]+=(bh and not ch);z["top1_improved"]+=(not b1 and c1);z["top1_worsened"]+=(b1 and not c1)
  if bo!=co:details.append({"race_id":rid,"base_order":bo,"candidate_order":co,"actual_order":[I(r["boat"]) for r in actual],"base_top3_hit":bh,"candidate_top3_hit":ch,"base_top1_hit":b1,"candidate_top1_hit":c1})
 n=z["races"]
 for p,num in [("base_top3_pct","base_top3"),("candidate_top3_pct","candidate_top3"),("base_top1_pct","base_top1"),("candidate_top1_pct","candidate_top1")]:z[p]=round(100*z[num]/n,2) if n else None
 z["top3_delta_pt"]=round(z["candidate_top3_pct"]-z["base_top3_pct"],2) if n else None;z["top1_delta_pt"]=round(z["candidate_top1_pct"]-z["base_top1_pct"],2) if n else None
 return z,details

def main():
 p=argparse.ArgumentParser(description="Saved PDCA dataset parameter what-if comparator")
 p.add_argument("--dataset",required=True);p.add_argument("--set",action="append",default=[]);p.add_argument("--label",default="candidate");p.add_argument("--output")
 a=p.parse_args();weights=dict(DEFAULT)
 for item in a.set:
  k,v=item.split("=",1);k=ALIASES.get(k,k)
  if k not in weights:raise SystemExit(f"unknown factor: {k}")
  weights[k]=float(v)
 rows=load_rows(a.dataset);races={}
 for r in rows:races.setdefault(r["race_id"],[]).append(r)
 summary,details=evaluate(races,DEFAULT,weights)
 out={"label":a.label,"dataset":a.dataset,"baseline_weights":DEFAULT,"candidate_weights":weights,"summary":summary,"changed_races":details}
 txt=json.dumps(out,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(txt,encoding="utf-8")
 print(txt)
if __name__=="__main__":main()
