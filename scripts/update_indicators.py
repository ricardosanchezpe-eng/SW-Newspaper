import json,re,html
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlencode
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data'/'indicators.json'
COUNTRIES={'France':'FR','Spain':'ES','Italy':'IT','Portugal':'PT','Luxembourg':'LU'}
MARKETS={'France':('CAC 40','^FCHI'),'Spain':('IBEX 35','^IBEX'),'Italy':('FTSE MIB','FTSEMIB.MI'),'Portugal':('PSI','PSI20.LS'),'Luxembourg':('LuxX','LUXX.LU')}
def get_json(url):return json.loads(urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0 SOLMAX-Executive-Newspaper/1.0','Accept':'application/json'}),timeout=30).read().decode())
def eurostat(ds,p):return get_json('https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/'+ds+'?'+urlencode(p,doseq=True))
def series(o):
 vals=o.get('value',{});idx=o.get('dimension',{}).get('time',{}).get('category',{}).get('index',{});order=idx if isinstance(idx,list) else [k for k,v in sorted(idx.items(),key=lambda x:x[1])];a=[]
 for i,t in enumerate(order):
  v=vals.get(str(i),vals.get(i))
  if isinstance(v,(int,float)):a.append((t,float(v)))
 return a
def es(ds,geo,extra,since='2023-01'):
 p={'lang':'en','geo':geo,'sinceTimePeriod':since};p.update(extra)
 try:return series(eurostat(ds,p))
 except Exception as e:print('EUROSTAT_WARNING',ds,geo,type(e).__name__,str(e)[:100]);return []
def pct(a,b):return None if a is None or b in (None,0) else (a/b-1)*100
def safe(v,lo,hi):return v if v is not None and lo<=v<=hi else None
def market(name,ticker):
 try:
  daily=get_json(f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=6mo&interval=1d')['chart']['result'][0]
  dq=daily['indicators']['quote'][0]['close'];dts=daily.get('timestamp',[]);history=[]
  for stamp,value in zip(dts,dq):
   if value is not None:history.append({'date':datetime.fromtimestamp(stamp,timezone.utc).strftime('%Y-%m-%d'),'value':round(float(value),2)})
  history=history[-66:]
  monthly=get_json(f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=2y&interval=1mo')['chart']['result'][0]
  pts=[float(x) for x in monthly['indicators']['quote'][0]['close'] if x is not None]
  cur=history[-1]['value'] if history else pts[-1]
  return {'name':name,'value':round(cur,2),'mom':safe(pct(cur,pts[-2]),-50,50) if len(pts)>1 else None,'yoy':safe(pct(cur,pts[-13]),-80,150) if len(pts)>12 else None,'history3m':history,'source':'Market data'}
 except Exception as e:
  print('MARKET_WARNING',name,type(e).__name__)
  return {'name':name,'value':None,'mom':None,'yoy':None,'history3m':[],'source':'Market data unavailable'}
def index_metric(ds,geo,extra,name,unit):
 s=es(ds,geo,extra)
 if not s:return {'name':name,'value':None,'mom':None,'yoy':None,'period':'N/A','unit':unit,'source':'Eurostat'}
 period,cur=s[-1];mom=pct(cur,s[-2][1]) if len(s)>1 else None;yoy=pct(cur,s[-13][1]) if len(s)>12 else None
 return {'name':name,'value':cur,'mom':safe(mom,-50,50),'yoy':safe(yoy,-80,100),'period':period,'unit':unit,'source':'Eurostat'}
def rate_metric(ds,geo,extra,name,lo,hi):
 s=es(ds,geo,extra)
 if not s:return {'name':name,'value':None,'mom':None,'yoy':None,'period':'N/A','unit':'%','changeUnit':'pp','source':'Eurostat'}
 period,cur=s[-1];cur=safe(cur,lo,hi);prev=s[-2][1] if len(s)>1 else None;ago=s[-13][1] if len(s)>12 else None
 return {'name':name,'value':cur,'mom':safe(cur-prev,-10,10) if cur is not None and prev is not None else None,'yoy':safe(cur-ago,-30,30) if cur is not None and ago is not None else None,'period':period,'unit':'%','changeUnit':'pp','source':'Eurostat'}
def gdp_metric(geo):
 # GDP dataset provides percentage-change units directly. Never calculate a percentage change of those rates.
 qoq=es('namq_10_gdp',geo,{'freq':'Q','s_adj':'SCA','unit':'CLV_PCH_PRE','na_item':'B1GQ'},'2024-Q1')
 yoy=es('namq_10_gdp',geo,{'freq':'Q','s_adj':'SCA','unit':'CLV_PCH_SM','na_item':'B1GQ'},'2024-Q1')
 if not qoq:return {'name':'GDP growth','value':None,'qoq':None,'yoyRate':None,'period':'N/A','unit':'%','frequency':'Quarterly','source':'Eurostat'}
 period,q=qoq[-1];q=safe(q,-20,20);ym={t:v for t,v in yoy};y=safe(ym.get(period),-30,30)
 return {'name':'GDP growth','value':q,'qoq':q,'yoyRate':y,'period':period,'unit':'%','frequency':'Quarterly','source':'Eurostat','method':'Official published GDP growth rates'}
def fntp():
 try:
  raw=urlopen(Request('https://www.fntp.fr/conjoncture-mensuelle/',headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read().decode('utf-8','ignore');text=re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',html.unescape(raw)));m=re.search(r'Travaux réalisés.{0,180}?(-?\d+[,.]\d+)\s*%',text,re.I);return None if not m else safe(float(m.group(1).replace(',','.')),-50,50)
 except Exception as e:print('FNTP_WARNING',type(e).__name__);return None
def main():
 rows=[]
 for country,geo in COUNTRIES.items():
  cons=index_metric('sts_copr_m',geo,{'freq':'M','s_adj':'SCA','unit':'I21','indic_bt':'PROD'},'Construction production','Index 2021=100')
  if country=='France':
   x=fntp()
   if x is not None:cons.update({'nationalYoY':x,'nationalLabel':'FNTP public works activity','nationalSource':'FNTP'})
  # prc_hicp_manr is discontinued; prc_hicp_minr provides current monthly rates. RCH_A is annual inflation.
  inflation=rate_metric('prc_hicp_minr',geo,{'freq':'M','unit':'RCH_A','coicop':'CP00'},'Inflation (HICP YoY)',-10,30)
  unemployment=rate_metric('une_rt_m',geo,{'freq':'M','s_adj':'SA','age':'TOTAL','sex':'T','unit':'PC_ACT'},'Unemployment rate',0,40)
  rows.append({'country':country,'market':market(*MARKETS[country]),'construction':cons,'macro':[inflation,unemployment,gdp_metric(geo)]})
 OUT.write_text(json.dumps({'updated':datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC'),'methodology':'Rates are displayed directly; levels use calculated MoM/YoY changes. Sanity bounds suppress implausible values.','countries':rows},ensure_ascii=False,indent=2),encoding='utf-8');print('INDICATORS_UPDATED',len(rows))
if __name__=='__main__':main()
