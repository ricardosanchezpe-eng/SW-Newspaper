import json, re, html, hashlib, time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
import feedparser
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
FLAGS={'France':'🇫🇷','Spain':'🇪🇸','Italy':'🇮🇹','Portugal':'🇵🇹','Luxembourg':'🇱🇺'}
COUNTRIES=list(FLAGS)

def clean(s):
    return re.sub(r'\s+',' ',BeautifulSoup(html.unescape(s or ''),'html.parser').get_text(' ',strip=True)).strip()

def classify(text):
    t=text.lower()
    rules=[
      ('Water',['eau','agua','acqua','water','sécheresse','secheresse','sequía','sequia','siccità','siccita','drought','inondation','flood']),
      ('Construction',['construction','construccion','construcción','costruzion','infraestruct','infrastruttur','infrastructure','travaux publics','obra publica','opere pubbliche','road','route','rail','ferrovi','port']),
      ('Energy',['energy','energie','énergie','energia','renewable','renouvelable','renovable','rinnovabile']),
      ('Industry',['industrie','industria','industrial','mining','mine','miniera','waste','déchet','dechet','residuo','rifiut']),
      ('Politics',['politic','gouvernement','gobierno','governo','government','élection','election','eleccion','elezione','parlement','parlamento','minister','président','president']),
      ('Economy',['econom','inflation','pib','gdp','employment','emploi','empleo','occupazione','growth','croissance','crecimiento','crescita','budget'])]
    for cat,words in rules:
        if any(w in t for w in words): return cat
    return 'General'

def score(a):
    points={'Water':9,'Construction':9,'Energy':8,'Industry':8,'Economy':7,'Politics':7,'General':4}.get(a['category'],4)
    txt=(a['title']+' '+a['summary']).lower()
    for k in ['infrastructure','construction','water','eau','agua','acqua','mining','waste','road','rail','port','energy','industrie','industria']:
        if k in txt: points+=1
    return min(points,15)

def source_from(entry):
    src=entry.get('source')
    if isinstance(src,dict): return clean(src.get('title',''))
    title=clean(entry.get('title',''))
    return title.rsplit(' - ',1)[-1] if ' - ' in title else 'Google News'

def title_without_source(title,src):
    title=clean(title)
    suffix=' - '+src
    return title[:-len(suffix)] if src and title.endswith(suffix) else title

def collect(cfg):
    now=datetime.now(timezone.utc); cutoff=now-timedelta(days=2); out=[]; seen=set()
    for country in cfg['sources']:
        for query in country['queries']:
            url=f"https://news.google.com/rss/search?q={quote_plus(query+' when:2d')}&hl={country['lang']}&gl={country['gl']}&ceid={quote_plus(country['ceid'])}"
            feed=feedparser.parse(url)
            for e in feed.entries[:12]:
                src=source_from(e); title=title_without_source(e.get('title',''),src); link=e.get('link','')
                if not title or not link: continue
                key=hashlib.sha1((country['country']+'|'+title.lower()).encode()).hexdigest()
                if key in seen: continue
                seen.add(key)
                published=e.get('published','Latest')
                summary=clean(e.get('summary',''))
                # Google News descriptions are often link markup rather than an article abstract.
                if not summary or summary.lower()==title.lower() or len(summary)<35:
                    summary='Open the original article for the full context.'
                elif len(summary)>360: summary=summary[:357].rsplit(' ',1)[0]+'...'
                cat=classify(title+' '+summary)
                a={'country':country['country'],'flag':country['flag'],'category':cat,'source':src or 'Google News','published':published,'title':title,'summary':summary,'why':f"Relevant to {country['country']}'s {cat.lower()} environment and SW Europe market awareness.",'url':link,'image':'assets/news-fallback.svg'}
                a['relevance']=score(a); out.append(a)
            time.sleep(.1)
    out.sort(key=lambda x:(-x['relevance'],x['country'],x['title']))
    # limit concentration: keep strongest 6 per country
    balanced=[]
    for c in COUNTRIES: balanced.extend([a for a in out if a['country']==c][:6])
    balanced.sort(key=lambda x:-x['relevance'])
    return balanced[:30]

def make_brief(articles):
    parts=[]
    for c in COUNTRIES:
        a=next((x for x in articles if x['country']==c),None)
        if a: parts.append(f"{FLAGS[c]} {c}: {a['title']}.")
    return ' '.join(parts) if parts else 'No fresh stories were collected in this run.'

def radar(articles):
    themes=[('Politics & policy',{'Politics'}),('Macro economy',{'Economy'}),('Construction',{'Construction'}),('Water & climate',{'Water'}),('Industry & energy',{'Industry','Energy'})]
    n=max(len(articles),1); result=[]
    for label,cats in themes:
        count=sum(a['category'] in cats for a in articles)
        result.append({'label':label,'value':min(100,35+round(65*count/n*4))})
    return result

def main():
    cfg=json.loads((DATA/'sources.json').read_text(encoding='utf-8'))
    daily=json.loads((DATA/'daily.json').read_text(encoding='utf-8'))
    articles=collect(cfg)
    daily['updated']=datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC')
    daily['executiveBrief']=make_brief(articles)
    daily['radar']=radar(articles)
    daily['articles']=articles
    (DATA/'daily.json').write_text(json.dumps(daily,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Collected and published {len(articles)} stories')
    by={c:sum(a['country']==c for a in articles) for c in COUNTRIES}; print(by)
if __name__=='__main__': main()
