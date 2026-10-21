"""API autenticada: todas as entidades são resolvidas pelo proprietário no servidor."""
from datetime import datetime
from pathlib import Path
import time
import logging
from collections import defaultdict,deque
from threading import Lock
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from .auth import Verifier
from .domain import UTC, Invalid, validate
from mensagem_automatica_report import generate

def create_app(store,transport,verifier=None,origins=(),generator=generate):
    verifier=verifier or Verifier();app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    app.state.store=store;app.state.transport=transport
    rates=defaultdict(deque);rate_lock=Lock()
    @app.middleware('http')
    async def boundaries(request,call_next):
        started=time.monotonic()
        origin=request.headers.get('origin')
        if origin and origin not in origins: return JSONResponse({'error':'Origem não autorizada.'},403)
        size=request.headers.get('content-length','0')
        if not size.isdigit() or int(size)>32768: return JSONResponse({'error':'Corpo muito grande.'},413)
        body=await request.body()
        if len(body)>32768: return JSONResponse({'error':'Corpo muito grande.'},413)
        if request.method=='OPTIONS':
            response=JSONResponse({},200)
            if origin in origins:
                response.headers.update({'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Headers':'Authorization,Content-Type','Access-Control-Allow-Methods':'GET,POST,PUT,DELETE,OPTIONS'})
        else: response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        if origin in origins: response.headers['Access-Control-Allow-Origin']=origin
        logging.getLogger('automation').info('api status=%s duration_ms=%s',response.status_code,round((time.monotonic()-started)*1000))
        return response
    @app.exception_handler(Invalid)
    async def invalid(request,error): return JSONResponse({'error':str(error)},400)
    @app.exception_handler(Exception)
    async def failed(request,error): return JSONResponse({'error':'Serviço temporariamente indisponível.'},503)
    def owner(request:Request):
        value=request.headers.get('authorization','')
        if not value.startswith('Bearer ') or len(value)>10000: raise HTTPException(401,'Login necessário.')
        try: identity=verifier.verify(value[7:])
        except Invalid: raise HTTPException(401,'Login indisponível ou credencial inválida.') from None
        with rate_lock:
            stamp=time.monotonic();queue=rates[identity]
            while queue and queue[0]<stamp-60: queue.popleft()
            if len(queue)>=60: raise HTTPException(429,'Limite de solicitações atingido.')
            queue.append(stamp)
            if len(rates)>1000:
                for key in list(rates):
                    if rates[key] and rates[key][-1]<stamp-60: del rates[key]
        return identity
    async def payload(request):
        try:
            result=await request.json()
            if not isinstance(result,dict): raise ValueError()
            return result
        except Exception: raise Invalid('JSON inválido.') from None
    def fields(data,allowed):
        if set(data)-set(allowed): raise Invalid('Campos desconhecidos.')
    def connection(user,key):
        item=store.get(user,key,'connection')
        if item['state']=='revoked': raise Invalid('Conexão revogada.')
        return item
    @app.get('/health')
    def health(): return {'ok':True,'mode':'live' if transport.real else 'simulation'}
    @app.get('/public-config')
    def public_config(): return {'clientId':verifier.audience if verifier.issuer=='https://accounts.google.com' else '', 'mode':'live' if transport.real else 'simulation'}
    @app.post('/auth/check')
    async def check_login(request:Request):
        data=await payload(request);fields(data,{'nonce'})
        value=request.headers.get('authorization','')
        if not value.startswith('Bearer ') or len(value)>10000 or not isinstance(data.get('nonce'),str): raise HTTPException(401,'Login inválido.')
        try: verifier.verify(value[7:],data['nonce'])
        except Invalid: raise HTTPException(401,'Fluxo de login inválido.') from None
        return {'ok':True}
    @app.post('/v1/preview')
    async def preview(request:Request,user=Depends(owner)):
        c=validate(await payload(request));return generator(c,datetime.now(UTC))
    @app.post('/v1/connections')
    async def add_connection(request:Request,user=Depends(owner)):
        data=await payload(request);fields(data,{'riskAccepted'})
        if data.get('riskAccepted') is not True: raise Invalid('Aceite os riscos antes de conectar.')
        key=store.create(user,'connection',{'riskAccepted':True,'acceptedAt':datetime.now(UTC).isoformat()},limit=1)
        return {'id':key,'mode':'live' if transport.real else 'simulation'}
    @app.get('/v1/connections')
    def connections(user=Depends(owner)): return [{'id':x['id'],'state':x['state']} for x in store.list(user,'connection')]
    @app.post('/v1/connections/{key}/pair')
    def pair(key,user=Depends(owner)):
        item=connection(user,key);result=transport.pair(item['id'])
        store.update(user,key,'connection',item['data'],'active' if result['state']=='connected' else 'pairing');return result
    @app.get('/v1/connections/{key}')
    def status(key,user=Depends(owner)):
        item=connection(user,key);result=transport.status(key)
        if result.get('state')!='connected':
            store.update(user,key,'connection',item['data'],'pairing')
        elif item['state']!='active': store.update(user,key,'connection',item['data'],'active')
        return result
    @app.get('/v1/connections/{key}/groups')
    def groups(key,user=Depends(owner)):
        connection(user,key);return transport.groups(key)
    @app.delete('/v1/connections/{key}')
    def revoke(key,user=Depends(owner)):
        store.revoke(user,key)
        try: transport.revoke(key)
        except Exception: return {'state':'revoked','remoteLogoutPending':True}
        return {'state':'revoked'}
    @app.post('/v1/destinations')
    async def destination(request:Request,user=Depends(owner)):
        data=await payload(request);fields(data,{'connection','group'});connection(user,data.get('connection',''))
        match=next((g for g in transport.groups(data['connection']) if g['id']==data.get('group')),None)
        if not match: raise Invalid('Grupo não autorizado.')
        for existing in store.list(user,'destination'):
            if existing['state']=='active' and existing['data']['connection']==data['connection'] and existing['data']['group']==match['id']:
                return {'id':existing['id'],'label':existing['data']['label']}
        key=store.create(user,'destination',{'connection':data['connection'],'group':match['id'],'label':match['label']},state='active')
        return {'id':key,'label':match['label']}
    def subscription_data(user,data):
        fields(data,{'config','connection','destination','active'})
        if type(data.get('active',False)) is not bool: raise Invalid('Estado inválido.')
        c=validate(data.get('config'),schedule=data.get('active',False))
        conn=connection(user,data.get('connection',''));dest=store.get(user,data.get('destination',''),'destination')
        if dest['data']['connection']!=conn['id'] or dest['state']!='active': raise Invalid('Destino não autorizado.')
        if data.get('active'):
            if conn['state']!='active' or transport.status(conn['id']).get('state')!='connected': raise Invalid('Conexão indisponível.')
            if not any(g['id']==dest['data']['group'] for g in transport.groups(conn['id'])): raise Invalid('Grupo indisponível.')
        return {'config':c,'connection':conn['id'],'destination':dest['id']},'active' if data.get('active') else 'inactive'
    @app.post('/v1/subscriptions')
    async def subscribe(request:Request,user=Depends(owner)):
        data,state=subscription_data(user,await payload(request));return {'id':store.create(user,'subscription',data,state,limit=5),'state':state,'mode':'live' if transport.real else 'simulation'}
    @app.put('/v1/subscriptions/{key}')
    async def update_subscription(key,request:Request,user=Depends(owner)):
        data,state=subscription_data(user,await payload(request));store.update(user,key,'subscription',data,state);return {'id':key,'state':state}
    @app.get('/v1/subscriptions')
    def subscriptions(user=Depends(owner)): return [{'id':x['id'],'state':x['state'],**x['data']} for x in store.list(user,'subscription')]
    @app.get('/v1/runs')
    def runs(user=Depends(owner)):
        with store.tx() as db: return [dict(x) for x in db.execute('SELECT id,subscription,reference,state,error FROM runs WHERE owner=? ORDER BY generation DESC LIMIT 100',(user,))]
    @app.get('/portal')
    def portal(): return FileResponse(Path(__file__).parent.parent/'portal/index.html')
    @app.get('/portal.js')
    def portal_js(): return FileResponse(Path(__file__).parent.parent/'portal/portal.js',media_type='application/javascript')
    return app
