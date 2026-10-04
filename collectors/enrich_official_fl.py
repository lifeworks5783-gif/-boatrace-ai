from __future__ import annotations
import argparse,csv,html,re,time,urllib.request
from pathlib import Path

UA="Mozilla/5.0 (compatible; boatrace-ai-data-collector/1.0)"
ROW=re.compile(r'<tbody[^>]*>(.*?)</tbody>',re.I|re.S)
TAG=re.compile(r'<[^>]+>')
REG=re.compile(r'(?<!\d)(\d{4})(?!\d)')
F=re.compile(r'\bF\s*([0-9]+)\b',re.I)
L=re.compile(r'\bL\s*([0-9]+)\b',re.I)
ST=re.compile(r'\b(0\.\d{2})\b')
def clean(x): return re.sub(r'\s+',' ',html.unescape(TAG.sub(' ',x))).strip()
def fetch(url):
 req=urllib.request.Request(url,headers={"User-Agent":UA})
 with urllib.request.urlopen(req,timeout=30) as r:return r.read().decode("utf-8","replace")
def parse_page(txt):
 out={}
 for block in ROW.findall(txt):
  t=clean(block); m=REG.search(t)
  if not m: continue
  fm, lm, sm=F.search(t),L.search(t),ST.search(t)
  if fm and lm and sm:
   out[m.group(1)]={"f_count":int(fm.group(1)),"l_count":int(lm.group(1)),"official_avg_st":float(sm.group(1))}
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--date",required=True);ap.add_argument("--input");ap.add_argument("--output");a=ap.parse_args()
 inp=Path(a.input or f"data/program_entries_{a.date}.csv");outp=Path(a.output or f"data/program_entries_fl_{a.date}.csv")
 with inp.open(encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f)); fields=list(rows[0].keys())
 by_race={}
 for r in rows:by_race.setdefault((r["venue_code"],int(r["race"])),[]).append(r)
 matched=0;missing=[]
 for (jcd,rno),rs in sorted(by_race.items()):
  url=f"https://www.boatrace.jp/owpc/pc/race/racelist?hd={a.date}&jcd={jcd}&rno={rno}"
  got=parse_page(fetch(url));time.sleep(.05)
  for r in rs:
   x=got.get(str(r["registration_no"]))
   if x:r.update(x);matched+=1
   else:r.update({"f_count":"","l_count":"","official_avg_st":""});missing.append((r["race_id"],r["boat"],r["registration_no"]))
 for k in ["f_count","l_count","official_avg_st"]:
  if k not in fields:fields.append(k)
 outp.parent.mkdir(parents=True,exist_ok=True)
 with outp.open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 print({"date":a.date,"rows":len(rows),"matched":matched,"missing":len(missing),"output":str(outp)})
 if missing: print("missing_sample",missing[:20])
 if matched != len(rows): raise SystemExit(2)
if __name__=="__main__":main()
