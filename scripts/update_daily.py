import json,re,html,hashlib,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote_plus
import feedparser
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';COUNTRIES=['France','Spain','Italy','Portugal','Luxembourg']
DIRECT={
'France':[('Le Monde','https://www.lemonde.fr/rss/une.xml',None),('Le Monde','https://www.lemonde.fr/politique/rss_full.xml','Politics'),('Le Monde','https://www.lemonde.fr/economie/rss_full.xml','Economy')],
'Spain':[('La Vanguardia','https://www.lavanguardia.com/feed/rss/home',None),('La Vanguardia','https://www.lavanguardia.com/rss/politica.xml','Politics'),('Expansion Construccion','https://www.expansion.com/rss/googlenews/empresas/construccion-servicios.xml','Construction')],
'Italy':[('ANSA','https://www.ansa.it/sito/notizie/topnews/topnews_rss.xml',None),('la Repubblica','https://www.repubblica.it/rss/homepage/rss2.0.xml',None),('La Stampa','https://www.lastampa.it/rss/copertina.xml',None),('Edilportale','https://www.edilportale.com/rss.xml','Construction'),('Il Sole 24 Ore','https://www.ilsole24ore.com/rss/italia.xml','Economy')],
'Portugal':[('RTP Noticias','https://www.rtp.pt/noticias/rss',None)],
'Luxembourg':[('RTL Today','https://today.rtl.lu/rss/feed/headlines.rss',None),('RTL','https://www.rtl.lu/rss/feed/headlines.rss',None),('Le Quotidien','https://lequotidien.lu/feed',None)]}
MAINSTREAM={
'France':['Le Figaro','Les Echos','Liberation','Franceinfo','Le Parisien'],
'Spain':['El Pais','El Mundo','ABC','20minutos','elDiario.es'],
'Italy':['Corriere della Sera','Il Sole 24 Ore','Il Fatto Quotidiano','AGI','Adnkronos'],
'Portugal':['Publico','Expresso','Observador','Jornal de Noticias','SIC Noticias','Diario de Noticias'],
'Luxembourg':['Luxemburger Wort','Luxembourg Times','L essentiel','Virgule','Contacto']}
# Dedicated sector/economy publications. Queried individually even when no stable direct RSS URL is configured.
SECTOR={
'France':{'Construction':['Le Moniteur','Batiactu','ConstructionBTP'],'Economy':['Les Echos','La Tribune']},
'Spain':{'Construction':['Alimarket Construccion','Interempresas Construccion','Expansion Construccion y Servicios'],'Economy':['Expansion','Cinco Dias','El Economista']},
'Italy':{'Construction':['Edilportale','NT Edilizia e Territorio','Ingenio'],'Economy':['Il Sole 24 Ore','Milano Finanza']},
'Portugal':{'Construction':['Construir','Jornal Economico Construcao','Jornal de Negocios Construcao'],'Economy':['Jornal Economico','Jornal de Negocios','ECO']},
'Luxembourg':{'Construction':['Paperjam Architecture Real Estate','Delano Architecture Real Estate'],'Economy':['Paperjam Economie','Delano Economy']}}
POL={'France':'France politique gouvernement elections','Spain':'Espana politica gobierno elecciones','Italy':'Italia politica governo elezioni','Portugal':'Portugal politica governo eleicoes','Luxembourg':'Luxembourg politique gouvernement elections'}
POL_WORDS=['politic','politique','politica','government','gouvernement','gobierno','governo','elecci','elect','elezi','parlement','parlamento','minister','president','coalition','parti','partido','partito']
def clean(s):
 s=html.unescape(s or '')
 if '<' in s and '>' in s:s=BeautifulSoup(s,'html.parser').get_text(' ',strip=True)
 return re.sub(r'\s+',' ',s).strip()
def classify(t):
 t=t.lower()
 if any(w in t for w in POL_WORDS):return 'Politics'
 for cat,ws in [('Water',['water','drought','flood','eau','agua','acqua','secher','sequia']),('Construction',['construction','infrastructure','road','rail','port','constru','costru','travaux','obra','opere','autostr','ferrovi','ediliz','btp']),('Energy',['energy','energie','energia','renewable','renovable','rinnovabile']),('Industry',['industry','industrie','industria','mining','mine','waste','dechet','residuo','rifiut']),('Economy',['econom','inflation','gdp','pib','employment','growth','croissance','crecimiento','crescita','budget','finance','market','mercado','mercati'])]:
  if any(w in t for w in ws):return cat
 return 'General'
def source_name(e):
 s=e.get('source')
 if isinstance(s,dict) and s.get('title'):return clean(s.get('title'))
 t=clean(e.get('title',''));return t.rsplit(' - ',1)[-1] if ' - ' in t else 'Google News'
def gnews(c,q):return f"https://news.google.com/rss/search?q={quote_plus(q+' when:2d')}&hl={c['lang']}&gl={c['gl']}&ceid={quote_plus(c['ceid'])}"
def ingest(out,seen,country,url,forced=None,override=None,kind='general',limit=12):
 feed=feedparser.parse(url);count=0
 if getattr(feed,'bozo',0):print('FEED_WARNING',country,override or url,str(getattr(feed,'bozo_exception',''))[:100])
 for e in feed.entries[:limit]:
  src=override or source_name(e);title=clean(e.get('title',''));suffix=' - '+src
  if override is None and src and title.endswith(suffix):title=title[:-len(suffix)]
  link=e.get('link','');key=hashlib.sha1((country+'|'+re.sub(r'\W+','',title.lower())[:180]).encode()).hexdigest()
  if not title or not link or key in seen:continue
  seen.add(key);summary=clean(e.get('summary','')) or 'Open the original article for the full context.'
  if len(summary)>360:summary=summary[:357].rsplit(' ',1)[0]+'...'
  cat=forced or classify(title+' '+summary);bonus={'direct':6,'mainstream':3,'sector':5,'general':0}.get(kind,0);rel={'Politics':11,'Water':9,'Construction':10,'Energy':8,'Industry':8,'Economy':10,'General':6}[cat]+bonus
  out.append({'country':country,'category':cat,'source':src,'published':e.get('published','Latest'),'title':title,'summary':summary,'why':f"Relevant to {country}'s {cat.lower()} environment and SW Europe market awareness.",'url':link,'image':'assets/news-fallback.svg','relevance':rel,'sourceKind':kind});count+=1
 print('FEED',country,kind,override or 'Google News',count)
def collect(cfg):
 out=[];seen=set();configs={x['country']:x for x in cfg['sources']}
 for country in COUNTRIES:
  c=configs[country]
  for publisher,url,forced in DIRECT.get(country,[]):ingest(out,seen,country,url,forced,publisher,'direct',15)
  for publisher in MAINSTREAM[country]:ingest(out,seen,country,gnews(c,f'"{publisher}" {country}'),None,publisher,'mainstream',6)
  for forced,publishers in SECTOR[country].items():
   for publisher in publishers:ingest(out,seen,country,gnews(c,f'"{publisher}" {country}'),forced,publisher,'sector',6)
  ingest(out,seen,country,f"https://news.google.com/rss?hl={c['lang']}&gl={c['gl']}&ceid={quote_plus(c['ceid'])}",None,None,'general',18)
  ingest(out,seen,country,gnews(c,POL[country]),'Politics',None,'general',15)
  for q in c['queries']:ingest(out,seen,country,gnews(c,q),None,None,'general',10)
  time.sleep(.1)
 selected=[]
 for country in COUNTRIES:
  pool=[a for a in out if a['country']==country];chosen=[]
  def take(items,target):
   for x in sorted(items,key=lambda z:-z['relevance']):
    if x not in chosen and len(chosen)<target:chosen.append(x)
  take([a for a in pool if a['sourceKind']=='direct'],5)
  take([a for a in pool if a['sourceKind']=='mainstream'],8)
  take([a for a in pool if a['category']=='Politics'],11)
  take([a for a in pool if a['sourceKind']=='sector'],14)
  take([a for a in pool if a['category'] in ('Economy','Construction','Water','Energy','Industry')],17)
  take(pool,18);selected.extend(chosen[:18])
 return selected
def main():
 cfg=json.loads((DATA/'sources.json').read_text(encoding='utf-8'));d=json.loads((DATA/'daily.json').read_text(encoding='utf-8'));a=collect(cfg);d['updated']=datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC');d['articles']=a;d['executiveBrief']='Country-by-country executive brief';d['countryBriefs']=[]
 for c in COUNTRIES:
  top=[x for x in a if x['country']==c][:3];summary='. '.join(x['title'].rstrip('.') for x in top)+'.' if top else 'No significant fresh developments were collected in this edition.';d['countryBriefs'].append({'country':c,'summary':summary})
 (DATA/'daily.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print('SUMMARY total=',len(a),'politics=',sum(x['category']=='Politics' for x in a),'economy=',sum(x['category']=='Economy' for x in a),'construction=',sum(x['category']=='Construction' for x in a),'sector=',sum(x['sourceKind']=='sector' for x in a))
if __name__=='__main__':main()
