import json,re,html,hashlib,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote_plus
import feedparser
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';COUNTRIES=['France','Spain','Italy','Portugal','Luxembourg']
PRIORITY={'France':['Le Monde','Le Figaro','Franceinfo','Les Echos','Libération'],'Spain':['La Vanguardia','El País','El Mundo','ABC','20minutos'],'Italy':['la Repubblica','Corriere della Sera','La Stampa','Il Sole 24 Ore','ANSA'],'Portugal':['PÚBLICO','Expresso','Observador','Jornal de Notícias','RTP'],'Luxembourg':['Luxemburger Wort','Luxembourg Times','RTL Today','L’essentiel','Virgule']}
POL_WORDS=['politic','politique','política','politica','government','gouvernement','gobierno','governo','elecci','élect','election','parlement','parlamento','minister','président','president','premier ministr','prime minister','assemblée','congreso','senat','senado','coalition','parti','partido','partito']
def clean(s):
 s=html.unescape(s or '')
 if '<' in s and '>' in s:s=BeautifulSoup(s,'html.parser').get_text(' ',strip=True)
 return re.sub(r'\s+',' ',s).strip()
def classify(t):
 t=t.lower()
 if any(w in t for w in POL_WORDS):return 'Politics'
 for cat,ws in [('Water',['water','drought','flood','eau','agua','acqua','sécher','sequia']),('Construction',['construction','infrastructure','road','rail','port','constru','costru','travaux','obra','opere','autostr','ferrovi']),('Energy',['energy','energie','énergie','energia','renewable','renovable','rinnovabile']),('Industry',['industry','industrie','industria','mining','mine','waste','dechet','déchet','residuo','rifiut']),('Economy',['econom','inflation','gdp','pib','employment','growth','croissance','crecimiento','crescita','budget'])]:
  if any(w in t for w in ws):return cat
 return 'General'
def source_name(e):
 s=e.get('source')
 if isinstance(s,dict) and s.get('title'):return clean(s.get('title'))
 t=clean(e.get('title',''));return t.rsplit(' - ',1)[-1] if ' - ' in t else 'Google News'
def add_feed(out,seen,country,url,forced_category=None,limit=12):
 for e in feedparser.parse(url).entries[:limit]:
  source=source_name(e);title=clean(e.get('title',''));suffix=' - '+source;title=title[:-len(suffix)] if source and title.endswith(suffix) else title;link=e.get('link','')
  if not title or not link:continue
  key=hashlib.sha1((country+'|'+re.sub(r'\W+','',title.lower())[:160]).encode()).hexdigest()
  if key in seen:continue
  seen.add(key);summary=clean(e.get('summary','')) or 'Open the original article for the full context.'
  if len(summary)>360:summary=summary[:357].rsplit(' ',1)[0]+'...'
  cat=forced_category or classify(title+' '+summary);priority=source in PRIORITY.get(country,[])
  rel={'Politics':10,'Water':9,'Construction':9,'Energy':8,'Industry':8,'Economy':8,'General':5}[cat]+(4 if priority else 0)
  out.append({'country':country,'category':cat,'source':source,'published':e.get('published','Latest'),'title':title,'summary':summary,'why':f"Relevant to {country}'s {cat.lower()} environment and SW Europe market awareness.",'url':link,'image':'assets/news-fallback.svg','relevance':rel,'mainstream':priority})
def gnews(country,cfg,query):return f"https://news.google.com/rss/search?q={quote_plus(query+' when:2d')}&hl={cfg['lang']}&gl={cfg['gl']}&ceid={quote_plus(cfg['ceid'])}"
def collect(cfg):
 out=[];seen=set();configs={x['country']:x for x in cfg['sources']}
 for country in COUNTRIES:
  c=configs[country]
  # Layer 1: main national headlines, deliberately broad.
  add_feed(out,seen,country,f"https://news.google.com/rss?hl={c['lang']}&gl={c['gl']}&ceid={quote_plus(c['ceid'])}",None,15)
  # Layer 2: guaranteed politics stream.
  politics={'France':'France politique gouvernement élections','Spain':'España política gobierno elecciones','Italy':'Italia politica governo elezioni','Portugal':'Portugal política governo eleições','Luxembourg':'Luxembourg politique gouvernement élections'}[country]
  add_feed(out,seen,country,gnews(country,c,politics),'Politics',12)
  # Layer 3: explicit mainstream publishers.
  for publisher in PRIORITY[country]:add_feed(out,seen,country,gnews(country,c,f'site:{publisher.replace(" ","")} {country}'),None,5)
  # Layer 4: SOLMAX-relevant specialist/intelligence queries.
  for q in c['queries']:add_feed(out,seen,country,gnews(country,c,q),None,8)
  time.sleep(.1)
 selected=[]
 for country in COUNTRIES:
  pool=[a for a in out if a['country']==country];chosen=[]
  def take(items,n):
   for x in sorted(items,key=lambda z:-z['relevance']):
    if x not in chosen and len(chosen)<n:chosen.append(x)
  take([a for a in pool if a['mainstream']],2)
  take([a for a in pool if a['category']=='Politics'],4)
  take([a for a in pool if a['category'] in ('Construction','Water','Energy','Industry','Economy')],7)
  take(pool,10)
  selected.extend(chosen[:10])
 return sorted(selected,key=lambda x:(COUNTRIES.index(x['country']),-x['relevance']))
def main():
 cfg=json.loads((DATA/'sources.json').read_text(encoding='utf-8'));d=json.loads((DATA/'daily.json').read_text(encoding='utf-8'));a=collect(cfg);d['updated']=datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC');d['articles']=a;d['executiveBrief']='Country-by-country executive brief';d['countryBriefs']=[]
 for c in COUNTRIES:
  top=[x for x in a if x['country']==c][:3];summary='. '.join(x['title'].rstrip('.') for x in top)+'.' if top else 'No significant fresh developments were collected in this edition.';d['countryBriefs'].append({'country':c,'summary':summary})
 (DATA/'daily.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
 print('Published',len(a),'stories. Politics:',sum(x['category']=='Politics' for x in a),'Mainstream-priority matches:',sum(x.get('mainstream',False) for x in a))
if __name__=='__main__':main()
