import json,re
from pathlib import Path
from datetime import datetime,timezone,timedelta
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data'/'opportunities.json'
API='https://api.ted.europa.eu/v3/notices/search'
COUNTRIES={'France':'FRA','Spain':'ESP','Italy':'ITA','Portugal':'PRT','Luxembourg':'LUX'}
# CPV families mapped to SOLMAX-relevant applications. CPV 45 = construction works; additional families narrow the signal.
SEGMENTS={
 'Road & Rail':['4523','4522'],
 'Water':['4524','4525','45252'],
 'Environmental / Waste':['45222','45232','905'],
 'Earthworks / Geotechnics':['4511','45112','45233'],
 'Coastal / Hydraulic':['4524','45246'],
 'Energy / Industrial':['4525','45251']}
KEYWORDS={'geosynthetic':8,'geotextile':10,'geomembrane':10,'landfill':8,'retaining':6,'reinforcement':5,'erosion':6,'drainage':5,'waterproof':5,'reservoir':6,'wastewater':6,'coastal':7,'dredg':6,'embankment':6,'rail':4,'road':3,'tunnel':5,'dam':6,'earthworks':5,'slope':5}
def api(body):
 raw=json.dumps(body).encode();req=Request(API,data=raw,headers={'User-Agent':'SOLMAX-Executive-Newspaper/1.0','Content-Type':'application/json','Accept':'application/json'});return json.loads(urlopen(req,timeout=45).read().decode())
def val(o,*keys):
 for k in keys:
  x=o.get(k)
  if x not in (None,'',[]):return x
 return None
def textval(v):
 if isinstance(v,str):return v
 if isinstance(v,list):return ' / '.join(textval(x) for x in v[:3])
 if isinstance(v,dict):
  for k in ('eng','en','fra','fre','spa','ita','por'):
   if k in v:return textval(v[k])
  return textval(next(iter(v.values()))) if v else ''
 return '' if v is None else str(v)
def amount(n):
 for k in ('procedure-value','estimated-value','estimated-value-lot','value'):
  v=n.get(k)
  if isinstance(v,(int,float)):return float(v)
  if isinstance(v,dict):
   for x in v.values():
    try:return float(x)
    except:pass
 return None
def segment(n):
 blob=' '.join([textval(val(n,'title','notice-title')),textval(val(n,'classification-cpv','cpv','cpv-main'))]).lower();best='Other construction';hits=0
 for seg,prefixes in SEGMENTS.items():
  n_hit=sum(blob.count(p.lower()) for p in prefixes)
  if n_hit>hits:best,hits=seg,n_hit
 return best
def relevance(n):
 blob=' '.join([textval(val(n,'title','notice-title')),textval(val(n,'description','short-description'))]).lower();score=sum(w for k,w in KEYWORDS.items() if k in blob);cpv=textval(val(n,'classification-cpv','cpv','cpv-main'))
 if cpv.startswith('45'):score+=5
 v=amount(n)
 if v and v>=1000000:score+=2
 return score
def notice_url(n):
 pub=textval(val(n,'publication-number','notice-publication-number','publicationNumber'))
 return f'https://ted.europa.eu/en/notice/{pub}/html' if pub else 'https://ted.europa.eu/en/'
def main():
 since=(datetime.now(timezone.utc)-timedelta(days=35)).strftime('%Y%m%d');rows=[]
 # Official TED query, one country at a time and construction CPV family. Field names follow TED expert-search conventions.
 for country,code in COUNTRIES.items():
  query=f'country-procurement:{code} AND classification-cpv:45* AND publication-date>={since}'
  body={'query':query,'page':1,'limit':100,'fields':['publication-number','publication-date','title','buyer-name','classification-cpv','place-of-performance','deadline','estimated-value','procedure-type','notice-type']}
  try:j=api(body)
  except Exception as e:print('TED_WARNING',country,type(e).__name__,str(e)[:160]);continue
  notices=j.get('notices') or j.get('results') or []
  for n in notices:
   sc=relevance(n)
   if sc<5:continue
   rows.append({'country':country,'segment':segment(n),'title':textval(val(n,'title','notice-title')) or 'Untitled procurement notice','buyer':textval(val(n,'buyer-name','buyer')),'published':textval(val(n,'publication-date','publicationDate')),'deadline':textval(val(n,'deadline','deadline-receipt-tender')),'value':amount(n),'procedure':textval(val(n,'procedure-type','procedure')),'cpv':textval(val(n,'classification-cpv','cpv','cpv-main')),'score':sc,'source':'TED - Supplement to the Official Journal of the EU','url':notice_url(n)})
 rows.sort(key=lambda x:(-x['score'],x['country'],x['deadline'] or '9999'))
 OUT.write_text(json.dumps({'updated':datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC'),'source':'Official TED Search API','methodology':'Construction notices from TED (CPV 45 family), filtered and ranked for SOLMAX-relevant application language. Score is a transparent relevance heuristic, not an estimate of win probability.','opportunities':rows[:150]},ensure_ascii=False,indent=2),encoding='utf-8');print('OPPORTUNITIES',len(rows[:150]))
if __name__=='__main__':main()
