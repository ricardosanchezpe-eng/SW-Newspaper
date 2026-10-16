import json, re, time
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'opportunities.json'
API = 'https://api.ted.europa.eu/v3/notices/search'
COUNTRIES = {'France':'FRA','Spain':'ESP','Italy':'ITA','Portugal':'PRT','Luxembourg':'LUX'}

# Broad project families where SOLMAX materials can be specified even when the notice title does not name them.
CPV_PREFIXES = ('4511','45112','4521','4522','4523','4524','4525','4526','905')
SEGMENTS = {
    'Road & Rail': ('4522','4523','3494'),
    'Water': ('4524','4525','45252','651'),
    'Environmental / Waste': ('45222','45232','905'),
    'Earthworks / Geotechnics': ('4511','45112','45233','45262'),
    'Coastal / Hydraulic': ('4524','45246','45247'),
    'Energy / Industrial': ('4525','45251','45259'),
}

# Explicit product language. Multilingual stems intentionally catch common variants.
PRODUCT_TERMS = {
    'geotextile': 14, 'géotextile': 14, 'geotextil': 14, 'geotessil': 14,
    'geogrid': 14, 'géogrille': 14, 'geomalla': 14, 'geogriglia': 14,
    'geomembrane': 14, 'géomembrane': 14, 'geomembrana': 14,
    'geosynthetic': 14, 'géosynthétique': 14, 'geosintét': 14, 'geosintet': 14,
    'bentonite liner': 14, 'bentonitic liner': 14, 'gcl': 10,
    'drainage geocomposite': 14, 'geocomposite': 12, 'géocomposite': 12, 'geocompuesto': 12,
    'erosion control mat': 12, 'geocell': 12, 'géocellule': 12, 'geocelda': 12,
    'geotube': 14, 'dewatering tube': 12,
}
PROJECT_TERMS = {
    'landfill':8,'décharge':8,'vertedero':8,'discarica':8,'aterro':8,
    'retaining wall':7,'mur de soutènement':7,'muro de contención':7,'muro di sostegno':7,
    'soil reinforcement':7,'renforcement des sols':7,'refuerzo de suelos':7,'rinforzo del terreno':7,
    'erosion':6,'érosion':6,'erosione':6,'drainage':5,'drenaje':5,'drenaggio':5,
    'waterproof':6,'étanché':6,'impermeabil':6,'reservoir':7,'réservoir':7,'embalse':7,'bacino':7,
    'wastewater':7,'eaux usées':7,'aguas residuales':7,'acque reflue':7,
    'coastal':7,'côtier':7,'costero':7,'costiero':7,'dredg':7,'dragage':7,'dragado':7,'dragaggio':7,
    'embankment':6,'remblai':6,'terraplén':6,'rilevato':6,'rail':4,'ferrovi':4,
    'road':3,'route':3,'carretera':3,'strada':3,'tunnel':5,'dam':7,'barrage':7,'presa':7,'diga':7,
    'earthworks':6,'terrassement':6,'movimiento de tierras':6,'movimento terra':6,
    'slope':5,'talus':5,'talud':5,'scarpata':5,'canal':5,'basin':5,'bassin':5,'balsa':5,
    'mining':6,'mine':6,'miniera':6,'tailings':8,'quarry':4,'carrière':4,'cantera':4,'cava':4,
}
FIELDS = ['publication-number','publication-date','notice-title','buyer-name','buyer-country',
          'classification-cpv','deadline','total-value','total-value-cur','procedure-type',
          'notice-type','contract-nature','place-of-performance','description-proc']

def api(body, attempts=3):
    raw = json.dumps(body).encode('utf-8')
    for attempt in range(attempts):
        try:
            req = Request(API, data=raw, headers={
                'User-Agent':'SOLMAX-Executive-Newspaper/1.0',
                'Content-Type':'application/json','Accept':'application/json'})
            return json.loads(urlopen(req, timeout=60).read().decode('utf-8'))
        except (HTTPError, URLError, TimeoutError) as e:
            if attempt == attempts - 1: raise
            time.sleep(2 ** attempt)

def val(o, *keys):
    for k in keys:
        x = o.get(k)
        if x not in (None, '', []): return x
    return None

def textval(v):
    if isinstance(v, str): return v
    if isinstance(v, (int,float)): return str(v)
    if isinstance(v, list): return ' / '.join(x for x in (textval(i) for i in v[:8]) if x)
    if isinstance(v, dict):
        for k in ('eng','en','fra','fre','spa','ita','por'):
            if k in v:
                x=textval(v[k])
                if x:return x
        return ' / '.join(x for x in (textval(i) for i in list(v.values())[:3]) if x)
    return ''

def clean_date(v):
    s=textval(v).strip()
    m=re.search(r'\d{4}-\d{2}-\d{2}',s)
    return m.group(0) if m else s[:10]

def cpvs(n):
    raw=textval(val(n,'classification-cpv','cpv','cpv-main'))
    return re.findall(r'\d{4,8}',raw)

def amount(n):
    v=val(n,'total-value','estimated-value','procedure-value','estimated-value-lot','value')
    candidates=[]
    if isinstance(v,(int,float,str)):candidates=[v]
    elif isinstance(v,list):candidates=v
    elif isinstance(v,dict):candidates=list(v.values())
    for x in candidates:
        try:return float(str(x).replace(' ','').replace(',','.'))
        except (ValueError,TypeError):pass
    return None

def blob(n):
    return ' '.join([textval(val(n,'notice-title','title')), textval(val(n,'description-proc','description','short-description'))]).lower()

def classify(n):
    b=blob(n); codes=cpvs(n)
    explicit_hits=sorted({term for term in PRODUCT_TERMS if term in b})
    product_score=sum(weight for term,weight in PRODUCT_TERMS.items() if term in b)
    potential_hits=sorted({term for term in PROJECT_TERMS if term in b})
    project_score=sum(weight for term,weight in PROJECT_TERMS.items() if term in b)
    cpv_relevant=any(code.startswith(CPV_PREFIXES) for code in codes)
    if explicit_hits:
        kind='Explicit SOLMAX product'
        score=20+product_score+min(project_score,12)
    elif potential_hits or cpv_relevant:
        kind='Potential application'
        score=5+project_score+(5 if cpv_relevant else 0)
    else:
        return None
    v=amount(n)
    if v and v>=1_000_000:score+=2
    return kind, min(score,99), explicit_hits[:6], potential_hits[:6]

def segment(n):
    codes=cpvs(n); b=blob(n); best='Other construction'; hits=0
    words={
      'Road & Rail':['road','route','carretera','strada','rail','ferrovi','bridge','pont','puente'],
      'Water':['water','eau','agua','acqua','wastewater','reservoir','réservoir','embalse'],
      'Environmental / Waste':['waste','landfill','décharge','vertedero','discarica','erosion'],
      'Earthworks / Geotechnics':['earthwork','terrassement','soil','sol','slope','talus','retaining','geotechn'],
      'Coastal / Hydraulic':['coastal','côtier','dredg','dragage','hydraulic','dam','barrage','canal'],
      'Energy / Industrial':['energy','énergie','energia','industrial','mine','mining','tailings']}
    for name,prefixes in SEGMENTS.items():
        h=sum(any(c.startswith(p) for p in prefixes) for c in codes)+sum(w in b for w in words[name])
        if h>hits:best,hits=name,h
    return best

def notice_url(n):
    pub=textval(val(n,'publication-number','notice-publication-number','publicationNumber')).strip()
    return f'https://ted.europa.eu/en/notice/-/detail/{pub}' if pub else 'https://ted.europa.eu/en/search/result'

def query_pages(country_code, since):
    # TED expert syntax: ISO-3 buyer country, publication date alias PD and CPV wildcard.
    query=f'buyer-country={country_code} AND classification-cpv=45* AND PD>={since} SORT BY publication-date DESC'
    page=1; total=[]
    while page<=20:
        body={'query':query,'page':page,'limit':100,'scope':'ALL','fields':FIELDS}
        data=api(body)
        notices=data.get('notices') or data.get('results') or []
        total.extend(notices)
        print('TED_PAGE',country_code,page,'records',len(notices),'reported_total',data.get('totalNoticeCount','?'))
        if len(notices)<100:break
        page+=1
    return total, query

def month_keys(now):
    y,m=now.year,now.month; out=[]
    for back in range(11,-1,-1):
        mm=m-back; yy=y
        while mm<=0:yy-=1;mm+=12
        out.append(f'{yy:04d}-{mm:02d}')
    return out

def main():
    now=datetime.now(timezone.utc)
    since=(now-timedelta(days=370)).strftime('%Y%m%d')
    months=month_keys(now)
    rows=[]; diagnostics=[]; activity={c:{m:{'explicit':0,'potential':0} for m in months} for c in COUNTRIES}
    seen=set()
    for country,code in COUNTRIES.items():
        raw_count=0; kept=0
        try:
            notices,query=query_pages(code,since);raw_count=len(notices)
            for n in notices:
                pub=textval(val(n,'publication-number','notice-publication-number','publicationNumber')).strip()
                key=pub or (country+'|'+textval(val(n,'notice-title','title'))+'|'+clean_date(val(n,'publication-date','publicationDate')))
                if key in seen:continue
                result=classify(n)
                if not result:continue
                seen.add(key);kind,score,product_hits,potential_hits=result
                published=clean_date(val(n,'publication-date','publicationDate'))
                mk=published[:7]
                if mk in activity[country]:activity[country][mk]['explicit' if kind.startswith('Explicit') else 'potential']+=1
                row={'country':country,'matchType':kind,'segment':segment(n),
                     'title':textval(val(n,'notice-title','title')) or 'Untitled procurement notice',
                     'buyer':textval(val(n,'buyer-name','buyer')),'published':published,
                     'deadline':clean_date(val(n,'deadline','deadline-receipt-tender')),
                     'value':amount(n),'currency':textval(val(n,'total-value-cur','currency')) or 'EUR',
                     'procedure':textval(val(n,'procedure-type','procedure')),
                     'cpv':' / '.join(cpvs(n)[:8]),'score':score,
                     'productMatches':product_hits,'potentialSignals':potential_hits,
                     'source':'TED - Supplement to the Official Journal of the EU','url':notice_url(n)}
                rows.append(row);kept+=1
            diagnostics.append({'country':country,'status':'OK','retrieved':raw_count,'relevant':kept,'query':query})
            print('TED_COUNTRY',country,'retrieved',raw_count,'relevant',kept)
        except Exception as e:
            diagnostics.append({'country':country,'status':'ERROR','retrieved':raw_count,'relevant':kept,'error':f'{type(e).__name__}: {str(e)[:220]}'})
            print('TED_ERROR',country,type(e).__name__,str(e)[:220])
    rows.sort(key=lambda x:(-x['score'],x['deadline'] or '9999-99-99',x['country']))
    # Dashboard cards focus on recent/open radar items; monthly activity retains the full 12-month sample.
    current=[]
    recent_cutoff=(now-timedelta(days=120)).strftime('%Y-%m-%d')
    today=now.strftime('%Y-%m-%d')
    for r in rows:
        if (r['deadline'] and r['deadline']>=today) or (r['published'] and r['published']>=recent_cutoff):current.append(r)
    payload={'updated':now.strftime('%d %B %Y, %H:%M UTC'),'source':'Official TED Search API',
      'methodology':'TED construction notices are split into Explicit SOLMAX product when product language is present and Potential application when project wording or CPV scope indicates a plausible application. The score is a transparent relevance heuristic, not win probability.',
      'months':months,'activity':activity,'diagnostics':diagnostics,'opportunities':current[:300]}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    errors=sum(d['status']=='ERROR' for d in diagnostics)
    print('OPPORTUNITIES_WRITTEN',len(current[:300]),'HISTORICAL_RELEVANT',len(rows),'ERRORS',errors)
    if errors==len(COUNTRIES):raise SystemExit('TED failed for every country; opportunities.json contains diagnostics but no live data.')

if __name__=='__main__':main()
