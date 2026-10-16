import json,re,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'/'opportunities.json'; API='https://api.ted.europa.eu/v3/notices/search'
COUNTRIES={'France':'FRA','Spain':'ESP','Italy':'ITA','Portugal':'PRT','Luxembourg':'LUX'}
PRODUCT=['geotextile','géotextile','geotextil','geotessil','geogrid','géogrille','geomalla','geogriglia','geomembrane','géomembrane','geomembrana','geosynthetic','géosynthétique','geosintét','geosintet','geocomposite','géocomposite','geocompuesto','geocell','geocelda','geotube','bentonite liner','gcl']
POTENTIAL=['landfill','décharge','vertedero','discarica','retaining wall','soutènement','contención','soil reinforcement','erosion','drainage','drenaje','waterproof','étanché','impermeabil','reservoir','réservoir','embalse','wastewater','eaux usées','aguas residuales','coastal','dredg','dragage','embankment','remblai','rail','ferrovi','road','route','carretera','tunnel','dam','barrage','presa','earthworks','terrassement','movimiento de tierras','slope','talus','canal','mining','tailings']
FIELDS=['publication-number','publication-date','notice-title','buyer-name','classification-cpv','deadline','total-value','total-value-cur','procedure-type','description-proc']
def api(body):
 r=Request(API,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Accept':'application/json','User-Agent':'SOLMAX-Executive-Newspaper/1.0'});return json.loads(urlopen(r,timeout=60).read())
def txt(v):
 if isinstance(v,str):return v
 if isinstance(v,list):return ' / '.join(filter(None,(txt(x) for x in v[:8])))
 if isinstance(v,dict):return next((txt(v[k]) for k in ('eng','en','fra','fre','spa','ita','por') if k in v),txt(next(iter(v.values()))) if v else '')
 return '' if v is None else str(v)
def get(n,*ks):return next((n[k] for k in ks if n.get(k) not in (None,'',[])),None)
def date(v):
 m=re.search(r'\d{4}-\d{2}-\d{2}',txt(v));return m.group(0) if m else txt(v)[:10]
def cpvs(n):return re.findall(r'\d{4,8}',txt(get(n,'classification-cpv','cpv')))
def val(n):
 try:return float(str(get(n,'total-value','estimated-value','procedure-value')).replace(',','.'))
 except:return None
def classify(n):
 b=(txt(get(n,'notice-title','title'))+' '+txt(get(n,'description-proc','description'))).lower(); ph=sorted({x for x in PRODUCT if x in b}); ah=sorted({x for x in POTENTIAL if x in b}); cp=any(x.startswith(('451','452','905')) for x in cpvs(n))
 if ph:return 'Explicit SOLMAX product',min(99,35+8*len(ph)+3*len(ah)),ph,ah
 if ah or cp:return 'Potential application',min(99,10+4*len(ah)+(5 if cp else 0)),ph,ah
 return None
def segment(n):
 b=(txt(get(n,'notice-title','title'))+' '+txt(get(n,'description-proc','description'))).lower()
 for name,words in {'Water':['water','eau','agua','reservoir','wastewater'],'Environmental / Waste':['landfill','waste','décharge','vertedero'],'Coastal / Hydraulic':['coastal','dredg','dam','barrage','canal'],'Earthworks / Geotechnics':['earthwork','terrassement','soil','slope','talus','retaining'],'Road & Rail':['road','route','carretera','rail','ferrovi','bridge'],'Energy / Industrial':['energy','industrial','mining','tailings']}.items():
  if any(x in b for x in words):return name
 return 'Other construction'
def months(now):
 out=[]
 for i in range(11,-1,-1):
  y=now.year;m=now.month-i
  while m<1:y-=1;m+=12
  out.append(f'{y:04d}-{m:02d}')
 return out
def main():
 now=datetime.now(timezone.utc); ms=months(now); since=(now-timedelta(days=370)).strftime('%Y%m%d'); rows=[];diag=[];seen=set(); activity={c:{m:{'explicit':0,'potential':0} for m in ms} for c in COUNTRIES}
 for country,code in COUNTRIES.items():
  raw=kept=0
  try:
   q=f'buyer-country={code} AND classification-cpv=45* AND PD>={since} SORT BY publication-date DESC';page=1;notices=[]
   while page<=20:
    j=api({'query':q,'page':page,'limit':100,'scope':'ALL','fields':FIELDS});x=j.get('notices') or j.get('results') or [];notices+=x
    if len(x)<100:break
    page+=1
   raw=len(notices)
   for n in notices:
    pub=txt(get(n,'publication-number','publicationNumber'));key=pub or txt(get(n,'notice-title','title'))+date(get(n,'publication-date'))
    if key in seen:continue
    cl=classify(n)
    if not cl:continue
    seen.add(key);kind,score,ph,ah=cl;published=date(get(n,'publication-date'));mk=published[:7]
    if mk in activity[country]:activity[country][mk]['explicit' if kind.startswith('Explicit') else 'potential']+=1
    rows.append({'country':country,'matchType':kind,'segment':segment(n),'title':txt(get(n,'notice-title','title')) or 'Untitled procurement notice','buyer':txt(get(n,'buyer-name','buyer')),'published':published,'deadline':date(get(n,'deadline')),'value':val(n),'currency':txt(get(n,'total-value-cur')) or 'EUR','cpv':' / '.join(cpvs(n)[:8]),'score':score,'productMatches':ph[:6],'potentialSignals':ah[:6],'url':f'https://ted.europa.eu/en/notice/-/detail/{pub}' if pub else 'https://ted.europa.eu/en/search/result'});kept+=1
   diag.append({'country':country,'status':'OK','retrieved':raw,'relevant':kept})
  except Exception as e:diag.append({'country':country,'status':'ERROR','error':f'{type(e).__name__}: {e}'})
 rows.sort(key=lambda x:(-x['score'],x['country']));today=now.strftime('%Y-%m-%d');recent=(now-timedelta(days=30)).strftime('%Y-%m-%d')
 active=[r for r in rows if (r['deadline'] and r['deadline']>=today) or (r['published'] and r['published']>=recent)]
 OUT.write_text(json.dumps({'updated':now.strftime('%d %B %Y, %H:%M UTC'),'source':'Official TED Search API','months':ms,'activity':activity,'diagnostics':diag,'opportunities':active[:300],'history':rows[:2000]},ensure_ascii=False,indent=2))
 print('ACTIVE',len(active),'HISTORY',len(rows),diag)
if __name__=='__main__':main()
