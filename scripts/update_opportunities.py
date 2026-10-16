import json,re,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'/'opportunities.json'; API='https://api.ted.europa.eu/v3/notices/search'
COUNTRIES={'France':'FRA','Spain':'ESP','Italy':'ITA','Portugal':'PRT','Luxembourg':'LUX'}
PRODUCTS={'geotextile':['geotextile','géotextile','geotextil','geotessil'],'geogrid':['geogrid','géogrille','geomalla','geogriglia'],'geomembrane':['geomembrane','géomembrane','geomembrana'],'geosynthetic':['geosynthetic','géosynthétique','geosintét','geosintet'],'geocomposite':['geocomposite','géocomposite','geocompuesto'],'geocell':['geocell','géocellule','geocelda'],'GCL':['bentonite liner','bentonitic liner','gcl'],'Geotube / dewatering tube':['geotube','dewatering tube']}
POTENTIAL=['landfill','décharge','vertedero','discarica','aterro','retaining wall','soutènement','contención','soil reinforcement','erosion','drainage','drenaje','drenaggio','waterproof','étanché','impermeabil','reservoir','réservoir','embalse','wastewater','eaux usées','aguas residuales','coastal','dredg','dragage','embankment','remblai','rail','ferrovi','road','route','carretera','tunnel','dam','barrage','presa','earthworks','terrassement','movimiento de tierras','slope','talus','canal','mining','tailings']
FIELDS=['publication-number','publication-date','notice-title','buyer-name','buyer-country','classification-cpv','deadline','total-value','total-value-cur','procedure-type','description-proc']
def api(body):
 raw=json.dumps(body).encode()
 for i in range(3):
  try:
   r=Request(API,data=raw,headers={'Content-Type':'application/json','Accept':'application/json','User-Agent':'SOLMAX-Executive-Newspaper/1.0'});return json.loads(urlopen(r,timeout=60).read())
  except (HTTPError,URLError,TimeoutError):
   if i==2:raise
   time.sleep(2**i)
def text(v):
 if isinstance(v,str):return v
 if isinstance(v,list):return ' / '.join(filter(None,(text(x) for x in v[:12])))
 if isinstance(v,dict):
  for k in ('eng','en','fra','fre','spa','ita','por'):
   if k in v and text(v[k]):return text(v[k])
  return ' / '.join(filter(None,(text(x) for x in list(v.values())[:4])))
 return '' if v is None else str(v)
def get(n,*keys):return next((n[k] for k in keys if n.get(k) not in (None,'',[])),None)
def clean_date(v):
 m=re.search(r'\d{4}-\d{2}-\d{2}',text(v));return m.group(0) if m else text(v)[:10]
def cpvs(n):return re.findall(r'\d{4,8}',text(get(n,'classification-cpv','cpv','cpv-main')))
def number(n):
 try:return float(str(get(n,'total-value','estimated-value','procedure-value')).replace(' ','').replace(',','.'))
 except:return None
def blob(n):return (text(get(n,'notice-title','title'))+' '+text(get(n,'description-proc','description','short-description'))).lower()
def quantities(n):
 b=blob(n);found=[]
 units=r'(?:m²|m2|sqm|square metres?|square meters?|hectares?|ha|linear metres?|linear meters?|ml|lm|tonnes?|tons?|kg|units?|unités?|unidades?)'
 num=r'\d[\d\s.,]*'
 for product,terms in PRODUCTS.items():
  for term in terms:
   for pat in (rf'{re.escape(term)}.{{0,100}}?({num}\s*{units})',rf'({num}\s*{units}).{{0,100}}?{re.escape(term)}'):
    m=re.search(pat,b,re.I)
    if m:
     q=re.sub(r'\s+',' ',m.group(1)).strip(' ,.;:')
     item=f'{product}: {q}'
     if item not in found:found.append(item)
     break
   if any(x.startswith(product+':') for x in found):break
 return found[:6]
def classify(n):
 b=blob(n);ph=sorted({p for p,ts in PRODUCTS.items() if any(t in b for t in ts)});ah=sorted({x for x in POTENTIAL if x in b});cp=any(x.startswith(('451','452','905')) for x in cpvs(n))
 if ph:return 'Explicit SOLMAX product',min(99,35+8*len(ph)+3*len(ah)),ph,ah
 if ah or cp:return 'Potential application',min(99,10+4*len(ah)+(5 if cp else 0)),ph,ah
 return None
def segment(n):
 b=blob(n)
 for name,words in {'Water':['water','eau','agua','reservoir','wastewater'],'Environmental / Waste':['landfill','waste','décharge','vertedero'],'Coastal / Hydraulic':['coastal','dredg','dam','barrage','canal'],'Earthworks / Geotechnics':['earthwork','terrassement','soil','slope','talus','retaining'],'Road & Rail':['road','route','carretera','rail','ferrovi','bridge'],'Energy / Industrial':['energy','industrial','mining','tailings']}.items():
  if any(x in b for x in words):return name
 return 'Other construction'
def month_keys(now):
 out=[]
 for i in range(11,-1,-1):
  y=now.year;m=now.month-i
  while m<1:y-=1;m+=12
  out.append(f'{y:04d}-{m:02d}')
 return out
def main():
 now=datetime.now(timezone.utc);ms=month_keys(now);since=(now-timedelta(days=370)).strftime('%Y%m%d');rows=[];diag=[];seen=set();activity={c:{m:{'explicit':0,'potential':0} for m in ms} for c in COUNTRIES}
 for country,code in COUNTRIES.items():
  try:
   q=f'buyer-country={code} AND classification-cpv=45* AND PD>={since} SORT BY publication-date DESC';page=1;notices=[]
   while page<=20:
    j=api({'query':q,'page':page,'limit':100,'scope':'ALL','fields':FIELDS});batch=j.get('notices') or j.get('results') or [];notices+=batch
    print('TED_PAGE',country,page,len(batch))
    if len(batch)<100:break
    page+=1
   kept=0
   for n in notices:
    pub=text(get(n,'publication-number','publicationNumber'));key=pub or text(get(n,'notice-title','title'))+clean_date(get(n,'publication-date'))
    if key in seen:continue
    cl=classify(n)
    if not cl:continue
    seen.add(key);kind,score,ph,ah=cl;published=clean_date(get(n,'publication-date'));mk=published[:7]
    if mk in activity[country]:activity[country][mk]['explicit' if kind.startswith('Explicit') else 'potential']+=1
    rows.append({'country':country,'matchType':kind,'segment':segment(n),'title':text(get(n,'notice-title','title')) or 'Untitled procurement notice','buyer':text(get(n,'buyer-name','buyer')),'published':published,'deadline':clean_date(get(n,'deadline')),'value':number(n),'currency':text(get(n,'total-value-cur')) or 'EUR','cpv':' / '.join(cpvs(n)[:8]),'score':score,'productMatches':ph[:6],'potentialSignals':ah[:6],'productQuantities':quantities(n),'url':f'https://ted.europa.eu/en/notice/-/detail/{pub}' if pub else 'https://ted.europa.eu/en/search/result'});kept+=1
   diag.append({'country':country,'status':'OK','retrieved':len(notices),'relevant':kept})
  except Exception as e:diag.append({'country':country,'status':'ERROR','error':f'{type(e).__name__}: {str(e)[:240]}'})
 rows.sort(key=lambda x:(-x['score'],x['country']));today=now.strftime('%Y-%m-%d');recent=(now-timedelta(days=30)).strftime('%Y-%m-%d');active=[r for r in rows if (r['deadline'] and r['deadline']>=today) or (r['published'] and r['published']>=recent)]
 payload={'updated':now.strftime('%d %B %Y, %H:%M UTC'),'source':'Official TED Search API','months':ms,'activity':activity,'diagnostics':diag,'opportunities':active[:300],'history':rows[:2000]}
 OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');print('ACTIVE',len(active),'HISTORY',len(rows),diag)
 if all(x['status']=='ERROR' for x in diag):raise SystemExit('TED failed for all countries')
if __name__=='__main__':main()
