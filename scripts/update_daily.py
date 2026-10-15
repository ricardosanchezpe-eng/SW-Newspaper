import json,re,html,hashlib,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote_plus
import feedparser
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';COUNTRIES=['France','Spain','Italy','Portugal','Luxembourg']
def clean(s):return re.sub(r'\s+',' ',BeautifulSoup(html.unescape(s or ''),'html.parser').get_text(' ',strip=True)).strip()
def translate_en(text):
 text=clean(text)
 if not text:return text
 for delay in (0,1,2):
  try:
   result=GoogleTranslator(source='auto',target='en').translate(text=text)
   if result and result.strip():return clean(result)
  except Exception as exc:
   if delay==2: print('TRANSLATION_WARNING:',type(exc).__name__,str(exc)[:160])
   time.sleep(delay+1)
 return text
def classify(t):
 t=t.lower();rules=[('Water',['water','drought','flood','eau','agua','acqua']),('Construction',['construction','infrastructure','road','rail','port','constru','costru','travaux','obra','opere']),('Energy',['energy','energie','énergie','energia','renewable','renovable','rinnovabile']),('Industry',['industry','industrie','industria','mining','mine','waste','dechet','déchet','residuo','rifiut']),('Politics',['politic','government','gouvernement','gobierno','governo','election','élection','minister','president']),('Economy',['econom','inflation','gdp','pib','employment','growth','budget'])]
 for c,ws in rules:
  if any(w in t for w in ws):return c
 return 'General'
def src(e):
 s=e.get('source')
 if isinstance(s,dict):return clean(s.get('title',''))
 t=clean(e.get('title',''));return t.rsplit(' - ',1)[-1] if ' - ' in t else 'Google News'
def collect(cfg):
 out=[];seen=set()
 for c in cfg['sources']:
  for q in c['queries']:
   url=f"https://news.google.com/rss/search?q={quote_plus(q+' when:2d')}&hl={c['lang']}&gl={c['gl']}&ceid={quote_plus(c['ceid'])}"
   feed=feedparser.parse(url)
   for e in feed.entries[:10]:
    source=src(e);raw_title=clean(e.get('title',''));suffix=' - '+source;raw_title=raw_title[:-len(suffix)] if source and raw_title.endswith(suffix) else raw_title;link=e.get('link','');key=hashlib.sha1((c['country']+'|'+raw_title.lower()).encode()).hexdigest()
    if not raw_title or not link or key in seen:continue
    seen.add(key);raw_summary=clean(e.get('summary',''));title=translate_en(raw_title);summary=translate_en(raw_summary) if raw_summary else 'Open the original article for the full context.'
    if len(summary)>360:summary=summary[:357].rsplit(' ',1)[0]+'...'
    cat=classify(raw_title+' '+raw_summary);rel={'Water':9,'Construction':9,'Energy':8,'Industry':8,'Economy':7,'Politics':7,'General':4}[cat]
    out.append({'country':c['country'],'category':cat,'source':source,'published':e.get('published','Latest'),'title':title,'summary':summary,'why':f"Relevant to {c['country']}'s {cat.lower()} environment and SW Europe market awareness.",'url':link,'image':'assets/news-fallback.svg','relevance':rel,'translation':'English' if title!=raw_title or not raw_summary or summary!=raw_summary else 'Source may already be English'})
   time.sleep(.2)
 balanced=[]
 for c in COUNTRIES:balanced.extend(sorted([a for a in out if a['country']==c],key=lambda x:-x['relevance'])[:6])
 return sorted(balanced,key=lambda x:-x['relevance'])[:30]
def main():
 cfg=json.loads((DATA/'sources.json').read_text(encoding='utf-8'));d=json.loads((DATA/'daily.json').read_text(encoding='utf-8'));a=collect(cfg);d['updated']=datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC');d['articles']=a;d['executiveBrief']='Country-by-country executive brief';d['countryBriefs']=[]
 for c in COUNTRIES:
  top=[x for x in a if x['country']==c][:3];summary='. '.join(x['title'].rstrip('.') for x in top)+'.' if top else 'No significant fresh developments were collected in this edition.';d['countryBriefs'].append({'country':c,'summary':summary})
 (DATA/'daily.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print('Published',len(a),'stories. Level-1 translation attempted for every collected title/description.')
if __name__=='__main__':main()
