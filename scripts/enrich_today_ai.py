import json, os, sys
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT=Path(__file__).resolve().parents[1]
DAILY=ROOT/'data'/'daily.json'
API='https://api.openai.com/v1/responses'
MODEL=os.getenv('OPENAI_MODEL','gpt-6.1-sol')
COUNTRIES=['France','Spain','Italy','Portugal','Luxembourg']

def source_packet(d):
    packet=[]
    for c in COUNTRIES:
        rows=[x for x in d.get('articles',[]) if x.get('country')==c][:18]
        packet.append({'country':c,'articles':[{
            'title':x.get('title',''),'summary':x.get('summary',''),'category':x.get('category',''),
            'source':x.get('source',''),'why':x.get('why',''),'url':x.get('url','')
        } for x in rows]})
    return packet

SCHEMA={
 'type':'object','additionalProperties':False,
 'properties':{
  'executiveSummary':{'type':'string'},
  'commercialTakeaway':{'type':'string'},
  'countryBriefs':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{
   'country':{'type':'string','enum':COUNTRIES},'summary':{'type':'string'},'infrastructure':{'type':'string'},
   'solmaxImplication':{'type':'string'},'headlines':{'type':'array','items':{'type':'string'},'maxItems':3}},
   'required':['country','summary','infrastructure','solmaxImplication','headlines']}},
  'topSignals':{'type':'array','maxItems':5,'items':{'type':'object','additionalProperties':False,'properties':{
   'country':{'type':'string','enum':COUNTRIES},'title':{'type':'string'},'whyItMatters':{'type':'string'},
   'sourceUrls':{'type':'array','items':{'type':'string'}}},'required':['country','title','whyItMatters','sourceUrls']}}
 },'required':['executiveSummary','commercialTakeaway','countryBriefs','topSignals']}

def main():
    key=os.getenv('OPENAI_API_KEY','').strip()
    if not key:
        print('AI_ENRICHMENT skipped: OPENAI_API_KEY not configured');return 0
    d=json.loads(DAILY.read_text(encoding='utf-8'));packet=source_packet(d)
    instructions='''You are the intelligence editor for SOLMAX Southwest Europe. Analyze ONLY the supplied public-source headlines and snippets. Never invent facts. Write concise executive English. Prioritize politics, economy, construction, infrastructure, water, waste, mining, transport and developments relevant to geosynthetics. Merge duplicate coverage into one development. SOLMAX implications must be cautious and commercially useful, using wording such as may/could when the source does not explicitly establish product demand. sourceUrls must only contain URLs present in the supplied packet. Return all five countries, even if a country has limited material. If evidence is weak, say so.'''
    body={'model':MODEL,'instructions':instructions,'input':json.dumps(packet,ensure_ascii=False),
          'text':{'format':{'type':'json_schema','name':'today_intelligence','strict':True,'schema':SCHEMA}}}
    req=Request(API,data=json.dumps(body).encode(),headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'})
    try:
        raw=json.loads(urlopen(req,timeout=120).read().decode())
        txt=raw.get('output_text')
        if not txt:
            for item in raw.get('output',[]):
                for content in item.get('content',[]):
                    if content.get('type')=='output_text':txt=content.get('text');break
                if txt:break
        ai=json.loads(txt);usage=raw.get('usage',{})
        d['aiToday']={'status':'ok','model':MODEL,'generatedAt':datetime.now(timezone.utc).isoformat(),'executiveSummary':ai['executiveSummary'],'commercialTakeaway':ai['commercialTakeaway'],'countryBriefs':ai['countryBriefs'],'topSignals':ai['topSignals'],'usage':{'inputTokens':usage.get('input_tokens'),'outputTokens':usage.get('output_tokens'),'totalTokens':usage.get('total_tokens')}}
        DAILY.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
        print('AI_ENRICHMENT OK',MODEL,d['aiToday']['usage']);return 0
    except Exception as e:
        print('AI_ENRICHMENT WARNING:',type(e).__name__,str(e)[:300]);return 0
if __name__=='__main__':raise SystemExit(main())
