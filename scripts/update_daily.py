import json,re,html,hashlib,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote_plus
import feedparser
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';COUNTRIES=['France','Spain','Italy','Portugal','Luxembourg']
# Direct feeds: used when a concrete publisher RSS endpoint is configured.
DIRECT={
 'France':[('Le Monde','https://www.lemonde.fr/rss/une.xml',None),('Le Monde','https://www.lemonde.fr/politique/rss_full.xml','Politics'),('Le Monde','https://www.lemonde.fr/economie/rss_full.xml','Economy')],
 'Spain':[('La Vanguardia','https://www.lavanguardia.com/feed/rss/home',None),('La Vanguardia','https://www.lavanguardia.com/rss/politica.xml','Politics')],
 'Italy':[('ANSA','https://www.ansa.it/sito/notizie/topnews/topnews_rss.xml',None),('la Repubblica','https://www.repubblica.it/rss/homepage/rss2.0.xml',None),('La Stampa','https://www.lastampa.it/rss/copertina.xml',None)],
 'Portugal':[('RTP Noticias','https://www.rtp.pt/noticias/rss',None)],
 'Luxembourg':[('RTL Today','https://today.rtl.lu/rss/feed/headlines.rss',None),('RTL','https://www.rtl.lu/rss/feed/headlines.rss',None),('Le Quotidien','https://lequotidien.lu/feed',None)]}
# Major publishers without a hard-coded direct feed are queried individually through Google News.
DISCOVERY={
 'France':['Le Figaro','Les Echos','Liberation','Franceinfo','Le Parisien'],
 'Spain':['El Pais','El Mundo','ABC','20minutos','elDiario.es'],
 'Italy':['Corriere della Sera','Il Sole 24 Ore','Il Fatto Quotidiano','AGI','Adnkronos'],
 'Portugal':['Publico','Expresso','Observador','Jornal de Noticias','SIC Noticias','Diario de Noticias'],
 'Luxembourg':['Luxemburger Wort','Luxembourg Times','L essentiel','Virgule','Contacto']}
POL={'France':'France politique gouvernement elections','Spain':'Espana politica gobierno elecciones','Italy':'Italia politica governo elezioni','Portugal':'Portugal politica governo eleicoes','Luxembourg':'Luxembourg politique gouvernement elections'}
POL_WORDS=['politic','politique','politica','government','gouvernement','gobierno','governo','elecci','elect','elezi','parlement','parlamento','minister','president','coalition','parti','partido','partito']
def clean(s):
 s=html.unescape(s or '')
 if '<' in s and '>' in s:s=BeautifulSoup(s,'html.parser').get_text(' ',strip=True)
 return re.sub(r'\s+',' ',s).strip()
def classify(t):
 t=t.lower()
 if any(w in t for w in POL_WORDS):return 'Politics'
 for cat,ws in [('Water',['water','drought','flood','eau','agua','acqua','secher','sequia']),('Construction',['construction','infrastructure','road','rail','port','constru','costru','travaux','obra','opere','autostr','ferrovi']),('Energy',['energy','energie','energia','renewable','renovable','rinnovabile']),('Industry',['industry','industrie','industria','mining','mine','waste','dechet','residuo','rifiut']),('Economy',['econom','inflation','gdp','pib','employment','growth','croissance','crecimiento','crescita','budget'])]:
  if any(w in t for w in ws):return cat
 return 'General'
def source_name(e):
 s=e.get('source')
 if isinstance(s,dict) and s.get('title'):return clean(s.get('title'))
 t=clean(e.get('title',''));return t.rsplit(' - ',1)[-1] if ' - ' in t else 'Google News'
def gnews(cfg,q):return f"https://news.google.com/rss/search?q={quote_plus(q+' when:2d')}&hl={cfg['lang']}&gl={cfg['gl']}&ceid={quote_plus(cfg['ceid'])}"
def ingest(out,seen,country,url,forced=None,override=None,direct=False,limit=12):
 feed=feedparser.parse(url);count=0
 if getattr(feed,'bozo',0):print('FEED_WARNING',country,override or url,str(getattr(feed,'bozo_exception',''))[:120])
 for e in feed.entries[:limit]:
  source=override or source_name(e);title=clean(e.get('title',''));suffix=' - '+source
  if override is None and source and title.endswith(suffix):title=title[:-len(suffix)]
  link=e.get('link','');key=hashlib.sha1((country+'|'+re.sub(r'\W+','',title.lower())[:180]).encode()).hexdigest()
  if not title or not link or key in seen:continue
  seen.add(key);summary=clean(e.get('summary','')) or 'Open the original article for the full context.'
  if len(summary)>360:summary=summary[:357].rsplit(' ',1)[0]+'...'
  cat=forced or classify(title+' '+summary);rel={'Politics':11,'Water':9,'Construction':9,'Energy':8,'Industry':8,'Economy':9,'General':6}[cat]+(6 if direct else 2 if override else 0)
  out.append({'country':country,'category':cat,'source':source,'published':e.get('published','Latest'),'title':title,'summary':summary,'why':f"Relevant to {country}'s {cat.lower()} environment and SW Europe market awareness.",'url':link,'image':'assets/news-fallback.svg','relevance':rel,'directPublisher':direct,'priorityPublisher':bool(override)});count+=1
 print('FEED',country,override or 'Google News',count)
def collect(cfg):
 out=[];seen=set();configs={x['country']:x for x in cfg['sources']}
 for country in COUNTRIES:
  c=configs[country]
  # 1. Direct major-media feeds where configured.
  for publisher,url,forced in DIRECT.get(country,[]):ingest(out,seen,country,url,forced,publisher,True,15)
  # 2. Other major titles searched individually.
  for publisher in DISCOVERY[country]:ingest(out,seen,country,gnews(c,f'"{publisher}" {country}'),None,publisher,False,6)
  # 3. Broad national top headlines.
  ingest(out,seen,country,f"https://news.google.com/rss?hl={c['lang']}&gl={c['gl']}&ceid={quote_plus(c['ceid'])}",None,None,False,18)
  # 4. Dedicated politics stream, guaranteeing politics inventory.
  ingest(out,seen,country,gnews(c,POL[country]),'Politics',None,False,15)
  # 5. SOLMAX-relevant specialist/intelligence queries from sources.json.
  for q in c['queries']:ingest(out,seen,country,gnews(c,q),None,None,False,10)
  time.sleep(.1)
 selected=[]
 for country in COUNTRIES:
  pool=[a for a in out if a['country']==country];chosen=[]
  def take(items,target):
   for x in sorted(items,key=lambda z:-z['relevance']):
    if x not in chosen and len(chosen)<target:chosen.append(x)
  take([a for a in pool if a['directPublisher']],5)
  take([a for a in pool if a['priorityPublisher']],8)
  take([a for a in pool if a['category']=='Politics'],11)
  take([a for a in pool if a['category'] in ('Economy','Construction','Water','Energy','Industry')],14)
  take(pool,15)
  selected.extend(chosen[:15])
 return selected
def main():
 cfg=json.loads((DATA/'sources.json').read_text(encoding='utf-8'));d=json.loads((DATA/'daily.json').read_text(encoding='utf-8'));a=collect(cfg);d['updated']=datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC');d['articles']=a;d['executiveBrief']='Country-by-country executive brief';d['countryBriefs']=[]
 for c in COUNTRIES:
  top=[x for x in a if x['country']==c][:3];summary='. '.join(x['title'].rstrip('.') for x in top)+'.' if top else 'No significant fresh developments were collected in this edition.';d['countryBriefs'].append({'country':c,'summary':summary})
 (DATA/'daily.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print('SUMMARY total=',len(a),'politics=',sum(x['category']=='Politics' for x in a),'direct=',sum(x['directPublisher'] for x in a),'priority=',sum(x['priorityPublisher'] for x in a))
if __name__=='__main__':main()
