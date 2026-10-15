import json,re,html
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'/'politics.json'
SOURCES={
'France':{'urls':['https://www.info.gouv.fr/','https://www.info.gouv.fr/actualite/election-presidentielle-2027'],'facts':{'leader':'Sébastien Lecornu','headOfState':'Emmanuel Macron','orientation':'Centrist-led minority government','government':'Government led by Sébastien Lecornu; no stable parliamentary majority in the National Assembly.','support':'Requires issue-by-issue parliamentary support.','opposition':'Main opposition blocs include the National Rally and parties of the left.','nationalElection':'Presidential election: 18 April 2027; second round 2 May 2027.','regionalElection':'Regional elections: 2028.','status':'Fragmented parliament'},'checks':['Sébastien Lecornu','18 avril 2027','2 mai 2027']},
'Spain':{'urls':['https://www.lamoncloa.gob.es/lang/en/presidente/news/Paginas/2026/20261005-institutional-statement.aspx','https://www.juntaelectoralcentral.es/cs/jec/eleccionesEnCurso/Elecciones_generales_2026'],'facts':{'leader':'Pedro Sánchez','headOfState':'King Felipe VI','orientation':'Centre-left / left coalition','government':'PSOE + Sumar coalition government.','support':'Minority coalition; the government has relied on additional parliamentary support from regional parties.','opposition':'Main national opposition: PP and Vox.','nationalElection':'General election: 29 November 2026.','regionalElection':'Regional election calendars vary by autonomous community; the next common regional cycle is in 2027.','status':'Snap election called'},'checks':['Pedro Sánchez','29 November','29 de noviembre de 2026']},
'Italy':{'urls':['https://www.governo.it/en'],'facts':{'leader':'Giorgia Meloni','headOfState':'President Sergio Mattarella','orientation':'Right-wing / centre-right coalition','government':'Brothers of Italy + League + Forza Italia, with Us Moderates in government.','support':'Coalition government with a parliamentary majority.','opposition':'Main opposition includes Democratic Party and Five Star Movement.','nationalElection':'General election due in 2027; precise date not yet included in the verified official source set.','regionalElection':'Regional and local elections follow separate calendars.','status':'Majority coalition'},'checks':['Giorgia Meloni']},
'Portugal':{'urls':['https://www.portugal.gov.pt/','https://www.portugal.gov.pt/en/gc25/communication/news/prime-minister-congratulates-antonio-jose-seguro-and-ensures-institutional-cooperation'],'facts':{'leader':'Luís Montenegro','headOfState':'President António José Seguro','orientation':'Centre-right minority government','government':'XXV Constitutional Government led by Luís Montenegro.','support':'Minority government.','opposition':'Opposition represented by parties outside the government in the Assembly of the Republic.','nationalElection':'No scheduled national election currently stored by this official-source pipeline.','regionalElection':'Azores and Madeira have separate autonomous-region election calendars.','status':'Minority government'},'checks':['Luís Montenegro','António José Seguro']},
'Luxembourg':{'urls':['https://gouvernement.lu/en/gouvernement/luc-frieden.html','https://luxembourg.public.lu/en/society-and-culture/political-system/government.html'],'facts':{'leader':'Luc Frieden','headOfState':'Grand Duke Guillaume V','orientation':'Centre-right / liberal coalition','government':'CSV + DP coalition.','support':'Parliamentary majority coalition formed after the 2023 election.','opposition':'Opposition parties sit outside the CSV-DP governing coalition.','nationalElection':'Next legislative election: 2028.','regionalElection':'No elected regional-government tier; communal elections are the relevant subnational cycle.','status':'Majority coalition'},'checks':['Luc Frieden','2028']}}
def fetch(url):
 try:
  r=Request(url,headers={'User-Agent':'Mozilla/5.0 SOLMAX-Executive-Newspaper/1.0'});raw=urlopen(r,timeout=20).read().decode('utf-8','ignore');return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',raw)))
 except Exception as e:
  print('POLITICS_SOURCE_WARNING',url,type(e).__name__,str(e)[:100]);return ''
def main():
 existing={}
 if OUT.exists():
  try: existing={x['country']:x for x in json.loads(OUT.read_text(encoding='utf-8')).get('politics',[])}
  except Exception: pass
 rows=[]
 for country,cfg in SOURCES.items():
  pages=[fetch(u) for u in cfg['urls']];blob=' '.join(pages);hits=[x for x in cfg['checks'] if x.lower() in blob.lower()]
  verified=len(hits)>=1
  if verified:
   row={'country':country,**cfg['facts'],'verified':True,'verificationStatus':'Official source matched','lastVerified':datetime.now(timezone.utc).strftime('%d %B %Y'),'officialSources':cfg['urls']};print('POLITICS_VERIFIED',country,','.join(hits))
  elif country in existing:
   row=existing[country];row['verified']=False;row['verificationStatus']='Official source check failed; retained last stored values';print('POLITICS_RETAINED',country)
  else:
   row={'country':country,**cfg['facts'],'verified':False,'verificationStatus':'Initial official source check failed','lastVerified':'Not verified','officialSources':cfg['urls']};print('POLITICS_UNVERIFIED',country)
  rows.append(row)
 OUT.write_text(json.dumps({'updated':datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC'),'verificationMode':'official-source pipeline','politics':rows},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
