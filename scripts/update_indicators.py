import json, math, re
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'/'indicators.json'
COUNTRIES={'France':'FR','Spain':'ES','Italy':'IT','Portugal':'PT','Luxembourg':'LU'}
MARKETS={'France':('CAC 40','^FCHI'),'Spain':('IBEX 35','^IBEX'),'Italy':('FTSE MIB','FTSEMIB.MI'),'Portugal':('PSI','PSI20.LS'),'Luxembourg':('LuxX','LUXX.LU')}
def get_json(url):
 req=Request(url,headers={'User-Agent':'Mozilla/5.0 SOLMAX-Executive-Newspaper/1.0','Accept':'application/json'});return json.loads(urlopen(req,timeout=30).read().decode())
def eurostat(dataset,params):
 base=f'https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}?';return get_json(base+urlencode(params,doseq=True))
def series(obj):
 vals=obj.get('value',{});times=obj.get('dimension',{}).get('time',{}).get('category',{}).get('index',{})
 if isinstance(times,list): order=times
 else: order=[x[0] for x in sorted(times.items(),key=lambda kv:kv[1])]
 arr=[]
 for i,t in enumerate(order):
  v=vals.get(str(i),vals.get(i))
  if isinstance(v,(int,float)):arr.append((t,float(v)))
 return arr
def latest_es(dataset,geo,extra):
 p={'lang':'en','geo':geo,'sinceTimePeriod':'2023-01'};p.update(extra)
 try:return series(eurostat(dataset,p))
 except Exception as e:print('EUROSTAT_WARNING',dataset,geo,type(e).__name__,str(e)[:100]);return []
def delta(cur,prev):
 if cur is None or prev in (None,0):return None
 return (cur/prev-1)*100
def fmt(v,suffix=''):
 return 'N/A' if v is None else f'{v:.1f}{suffix}'
def market(name,ticker):
 try:
  j=get_json(f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=2y&interval=1mo');r=j['chart']['result'][0];q=r['indicators']['quote'][0]['close'];ts=r['timestamp'];pts=[(a,b) for a,b in zip(ts,q) if b is not None];cur=pts[-1][1];m=delta(cur,pts[-2][1]) if len(pts)>1 else None;y=delta(cur,pts[-13][1]) if len(pts)>12 else None
  return {'name':name,'value':round(cur,2),'mom':m,'yoy':y,'status':'ok','source':'Market data: Yahoo Finance chart endpoint'}
 except Exception as e:print('MARKET_WARNING',name,type(e).__name__,str(e)[:100]);return {'name':name,'value':None,'mom':None,'yoy':None,'status':'unavailable','source':'Market data unavailable'}
def metric(dataset,geo,extra,name,unit,frequency='Monthly'):
 s=latest_es(dataset,geo,extra)
 if not s:return {'name':name,'value':None,'mom':None,'yoy':None,'period':'N/A','unit':unit,'frequency':frequency,'source':'Eurostat'}
 period,cur=s[-1];prev=s[-2][1] if len(s)>1 else None;ago=s[-13][1] if len(s)>12 else None
 return {'name':name,'value':cur,'mom':delta(cur,prev),'yoy':delta(cur,ago),'period':period,'unit':unit,'frequency':frequency,'source':'Eurostat'}
def rate_metric(dataset,geo,extra,name,unit='%',frequency='Monthly'):
 s=latest_es(dataset,geo,extra)
 if not s:return {'name':name,'value':None,'mom':None,'yoy':None,'period':'N/A','unit':unit,'frequency':frequency,'source':'Eurostat'}
 period,cur=s[-1];prev=s[-2][1] if len(s)>1 else None;ago=s[-13][1] if len(s)>12 else None
 # Percentage-point changes are more meaningful for rates.
 return {'name':name,'value':cur,'mom':None if prev is None else cur-prev,'yoy':None if ago is None else cur-ago,'period':period,'unit':unit,'frequency':frequency,'changeUnit':'pp','source':'Eurostat'}
def fntp():
 try:
  raw=urlopen(Request('https://www.fntp.fr/conjoncture-mensuelle/',headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read().decode('utf-8','ignore');text=re.sub(r'<[^>]+>',' ',raw);text=re.sub(r'\s+',' ',text)
  m=re.search(r'Travaux réalisés.{0,180}?(-?\d+[,.]\d+)\s*%',text,re.I)
  return None if not m else float(m.group(1).replace(',','.'))
 except Exception as e:print('FNTP_WARNING',type(e).__name__);return None
def main():
 rows=[]
 for country,geo in COUNTRIES.items():
  mk=market(*MARKETS[country])
  cons=metric('sts_copr_m',geo,{'freq':'M','s_adj':'SCA','unit':'I21','indic_bt':'PROD'},'Construction production','Index 2021=100')
  if country=='France':
   fy=fntp()
   if fy is not None:cons['nationalYoY']=fy;cons['nationalLabel']='FNTP public works activity';cons['nationalSource']='FNTP monthly business survey'
  inflation=rate_metric('prc_hicp_manr',geo,{'freq':'M','unit':'RCH_A','coicop':'CP00'},'Inflation (HICP annual rate)')
  unemployment=rate_metric('une_rt_m',geo,{'freq':'M','s_adj':'SA','age':'TOTAL','sex':'T','unit':'PC_ACT'},'Unemployment rate')
  gdp=metric('namq_10_gdp',geo,{'freq':'Q','s_adj':'SCA','unit':'CLV_PCH_PRE','na_item':'B1GQ'},'GDP growth','%',frequency='Quarterly')
  rows.append({'country':country,'market':mk,'construction':cons,'macro':[inflation,unemployment,gdp]})
 OUT.write_text(json.dumps({'updated':datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC'),'countries':rows},ensure_ascii=False,indent=2),encoding='utf-8');print('INDICATORS_UPDATED',len(rows))
if __name__=='__main__':main()
