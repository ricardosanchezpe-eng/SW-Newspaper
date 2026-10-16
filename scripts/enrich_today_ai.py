import json, os
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
DAILY=ROOT/'data'/'daily.json'
API='https://api.openai.com/v1/responses'
MODEL=os.getenv('OPENAI_MODEL','gpt-6.1-sol')
COUNTRIES=['France','Spain','Italy','Portugal','Luxembourg']

def packet(d):
    return [{'country':c,'articles':[{'title':x.get('title',''),'summary':x.get('summary',''),'category':x.get('category',''),'source':x.get('source',''),'url':x.get('url','')} for x in d.get('articles',[]) if x.get('country')==c][:18]} for c in COUNTRIES]

SCHEMA={'type':'object','additionalProperties':False,'properties':{
 'executiveSummary':{'type':'string'},
 'countryBriefs':{'type':'array','minItems':5,'maxItems':5,'items':{'type':'object','additionalProperties':False,'properties':{'country':{'type':'string','enum':COUNTRIES},'summary':{'type':'string'}},'required':['country','summary']}}
},'required':['executiveSummary','countryBriefs']}

def main():
    key=os.getenv('OPENAI_API_KEY','').strip()
    if not key:
        print('AI_ENRICHMENT skipped: OPENAI_API_KEY not configured');return
    d=json.loads(DAILY.read_text(encoding='utf-8'))
    instructions='''You are the morning editor for SOLMAX Southwest Europe. Answer one practical question: What should a commercial director know about France, Spain, Italy, Portugal and Luxembourg today? Use ONLY the supplied public-source headlines and snippets; never invent or add external facts. Write clear executive English, not an analyst report. executiveSummary: one readable overview of 90-140 words covering the most important cross-market developments. countryBriefs: exactly one brief per country, each 65-105 words, selecting only the most important political, economic, construction, infrastructure or major business developments. Do not create fixed subsections. Do not include a commercial takeaway, recommended action, SOLMAX implication, or forced geosynthetics angle. Merge duplicate coverage. If evidence for a country is limited, state that today's supplied coverage is limited rather than filling gaps.'''
    body={'model':MODEL,'instructions':instructions,'input':json.dumps(packet(d),ensure_ascii=False),'text':{'format':{'type':'json_schema','name':'today_brief','strict':True,'schema':SCHEMA}}}
    try:
        req=Request(API,data=json.dumps(body).encode(),headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'})
        raw=json.loads(urlopen(req,timeout=120).read().decode());txt=raw.get('output_text')
        if not txt:
            for item in raw.get('output',[]):
                for content in item.get('content',[]):
                    if content.get('type')=='output_text':txt=content.get('text');break
                if txt:break
        ai=json.loads(txt);usage=raw.get('usage',{})
        d['aiToday']={'status':'ok','version':'clean-brief-v2','model':MODEL,'generatedAt':datetime.now(timezone.utc).isoformat(),'executiveSummary':ai['executiveSummary'],'countryBriefs':ai['countryBriefs'],'usage':{'inputTokens':usage.get('input_tokens'),'outputTokens':usage.get('output_tokens'),'totalTokens':usage.get('total_tokens')}}
        DAILY.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print('AI_ENRICHMENT OK',MODEL,d['aiToday']['usage'])
    except Exception as e:
        print('AI_ENRICHMENT WARNING:',type(e).__name__,str(e)[:300])
if __name__=='__main__':main()
