import json,re,html,hashlib,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote_plus
import feedparser
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'
FLAGS={'France':'🇫🇷','Spain':'🇪🇸','Italy':'🇮🇹','Portugal':'🇵🇹','Luxembourg':'🇱🇺'}; COUNTRIES=list(FLAGS)
LANG={'France':'fr','Spain':'es','Italy':'it','Portugal':'pt','Luxembourg':'fr'}
def clean(s):return re.sub(r'\s+',' ',BeautifulSoup(html.unescape(s or ''),'html.parser').get_text(' ',strip=True)).strip()
def tr(s,lang):
    if not s:return s
    try:return GoogleTranslator(source=lang,target='en').translate(s)
    except Exception:return s
def classify(text):
 t=text.lower(); rules=[('Water',['water','drought','flood','eau','agua','acqua']),('Construction',['construction','infrastructure','road','rail','port','constru','costru','travaux','obra','opere']),('Energy',['energy','energie','énergie','energia','renewable','renovable','rinnovabile']),('Industry',['industry','industrie','industria','mining','mine','waste','dechet','déchet','residuo','rifiut']),('Politics',['politic','government','gouvernement','gobierno','governo','election','élection','minister','president']),('Economy',['econom','inflation','gdp','pib','employment','growth','budget'])]
 for c,ws in rules:
  if any(w in t for w in ws):return c
 return 'General'
def src(e):
 s=e.get('source');
 if isinstance(s,dict):return clean(s.get('title',''))
 t=clean(e.get('title',''));return t.rsplit(' - ',1)[-1] if ' - ' in t else 'Google News'
def collect(cfg):
 out=[];seen=set()
 for c in cfg['sources']:
  for q in c['queries']:
   url=f"https://news.google.com/rss/search?q={quote_plus(q+' when:2d')}&hl={c['lang']}&gl={c['gl']}&ceid={quote_plus(c['ceid'])}"
   for e in feedparser.parse(url).entries[:10]:
    source=src(e); raw=clean(e.get('title','')); suffix=' - '+source; raw=raw[:-len(suffix)] if source and raw.endswith(suffix) else raw; link=e.get('link',''); key=hashlib.sha1((c['country']+'|'+raw.lower()).encode()).hexdigest()
    if not raw or not link or key in seen:continue
    seen.add(key); rawsum=clean(e.get('summary','')); title=tr(raw,LANG[c['country']]); summary=tr(rawsum,LANG[c['country']]) if rawsum else 'Open the original article for the full context.'
    if len(summary)>360:summary=summary[:357].rsplit(' ',1)[0]+'...'
    cat=classify(raw+' '+rawsum); rel={'Water':9,'Construction':9,'Energy':8,'Industry':8,'Economy':7,'Politics':7,'General':4}[cat]
    out.append({'country':c['country'],'flag':FLAGS[c['country']],'category':cat,'source':source,'published':e.get('published','Latest'),'title':title,'summary':summary,'why':f"Relevant to {c['country']}'s {cat.lower()} environment and SW Europe market awareness.",'url':link,'image':'assets/news-fallback.svg','relevance':rel})
   time.sleep(.1)
 balanced=[]
 for c in COUNTRIES:balanced.extend(sorted([a for a in out if a['country']==c],key=lambda x:-x['relevance'])[:6])
 return sorted(balanced,key=lambda x:-x['relevance'])[:30]
def main():
 cfg=json.loads((DATA/'sources.json').read_text(encoding='utf-8')); d=json.loads((DATA/'daily.json').read_text(encoding='utf-8')); a=collect(cfg); parts=[]
 for c in COUNTRIES:
  x=next((z for z in a if z['country']==c),None)
  if x:parts.append(f"{FLAGS[c]} {c}: {x['title']}.")
 d['updated']=datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC');d['executiveBrief']=' '.join(parts);d['articles']=a
 (DATA/'daily.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print('Published',len(a),'English-language stories')
if __name__=='__main__':main()
