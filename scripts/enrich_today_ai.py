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
    return [{'country':c,'articles':[{
        'title':x.get('title',''),'summary':x.get('summary',''),'category':x.get('category',''),
        'source':x.get('source',''),'url':x.get('url','')
    } for x in d.get('articles',[]) if x.get('country')==c][:20]} for c in COUNTRIES]

HEADLINE={'type':'object','additionalProperties':False,'properties':{
    'title':{'type':'string'},'context':{'type':'string'},'source':{'type':'string'},'url':{'type':'string'}
},'required':['title','context','source','url']}
COUNTRY={'type':'object','additionalProperties':False,'properties':{
    'country':{'type':'string','enum':COUNTRIES},
    'politicalSummary':{'type':'string'},
    'topHeadlines':{'type':'array','minItems':3,'maxItems':3,'items':HEADLINE},
    'industryNote':{'type':'string'}
},'required':['country','politicalSummary','topHeadlines','industryNote']}
SCHEMA={'type':'object','additionalProperties':False,'properties':{
    'executiveSummary':{'type':'string'},
    'countryBriefs':{'type':'array','minItems':5,'maxItems':5,'items':COUNTRY}
},'required':['executiveSummary','countryBriefs']}

def main():
    key=os.getenv('OPENAI_API_KEY','').strip()
    if not key:
        print('AI_ENRICHMENT skipped: OPENAI_API_KEY not configured');return
    d=json.loads(DAILY.read_text(encoding='utf-8'))
    instructions='''Eres el editor de un briefing ejecutivo matinal sobre Francia, España, Italia, Portugal y Luxemburgo. Escribe TODO en español claro, natural y conciso. Usa ÚNICAMENTE los titulares y fragmentos públicos suministrados; no añadas hechos externos ni inventes información.

Objetivo: responder “¿Qué debo saber hoy de estos países?” desde una perspectiva general, con mayor atención a la situación política, institucional y económica. No escribas para SOLMAX ni fuerces un ángulo comercial.

executiveSummary: 110-160 palabras, lectura fluida, destacando los 3-5 asuntos transversales más importantes del día.

Para cada país:
- politicalSummary: 75-115 palabras sobre qué está pasando, dando prioridad a política, gobierno, elecciones, presupuesto, regulación, economía y asuntos sociales relevantes.
- topHeadlines: selecciona exactamente los 3 acontecimientos más relevantes de ese país. Cada uno debe tener un título corto, una frase de contexto, el nombre de la fuente y una URL que exista literalmente en el material suministrado. No repitas el mismo acontecimiento.
- industryNote: déjalo como cadena vacía salvo que las fuentes incluyan un desarrollo MATERIAL en construcción, infraestructuras, agua, residuos, minería, transporte, energía o vivienda. Si existe, escribe una sola nota factual de 25-45 palabras bajo el concepto “Industria e infraestructuras”. No hagas recomendaciones ni menciones SOLMAX.

Si la cobertura de un país es limitada, indícalo de forma breve y no rellenes los huecos con suposiciones.'''
    body={'model':MODEL,'instructions':instructions,'input':json.dumps(packet(d),ensure_ascii=False),
          'text':{'format':{'type':'json_schema','name':'today_brief_es','strict':True,'schema':SCHEMA}}}
    try:
        req=Request(API,data=json.dumps(body).encode(),headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'})
        raw=json.loads(urlopen(req,timeout=120).read().decode());txt=raw.get('output_text')
        if not txt:
            for item in raw.get('output',[]):
                for content in item.get('content',[]):
                    if content.get('type')=='output_text':txt=content.get('text');break
                if txt:break
        ai=json.loads(txt);usage=raw.get('usage',{})
        d['aiToday']={'status':'ok','version':'spanish-political-cards-v3','language':'es','model':MODEL,
          'generatedAt':datetime.now(timezone.utc).isoformat(),'executiveSummary':ai['executiveSummary'],
          'countryBriefs':ai['countryBriefs'],'usage':{'inputTokens':usage.get('input_tokens'),
          'outputTokens':usage.get('output_tokens'),'totalTokens':usage.get('total_tokens')}}
        DAILY.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
        print('AI_ENRICHMENT OK',MODEL,d['aiToday']['usage'])
    except Exception as e:
        print('AI_ENRICHMENT WARNING:',type(e).__name__,str(e)[:300])
if __name__=='__main__':main()
