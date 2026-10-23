"""API autenticada: todas as entidades são resolvidas pelo proprietário no servidor."""
from datetime import datetime
import time
import logging
from collections import defaultdict,deque
from threading import Lock
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from .auth import Verifier
from .domain import UTC, Invalid, validate
from .watch import validate_watch
from .commands import validate_botgroup
from .botcmds import HELP
from .store import BOT_COMMANDS
from mensagem_automatica_report import generate

def create_app(store,transport,verifier=None,origins=(),generator=generate):
    verifier=verifier or Verifier(store);app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
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
    claim_attempts=defaultdict(deque)
    def known(request:Request):
        """Conta autenticada, liberada ou não (usada só para apresentar um código de liberação)."""
        return authenticate(request,False)
    def owner(request:Request):
        return authenticate(request,True)
    def administrator(request:Request):
        identity=authenticate(request,True)
        if not store.is_admin(identity): raise HTTPException(403,'Somente o administrador pode fazer isso.')
        return identity
    def authenticate(request,need_access):
        value=request.headers.get('authorization','')
        if not value.startswith('Bearer ') or len(value)>10000: raise HTTPException(401,'Login necessário.')
        try: identity=verifier.verify(value[7:])
        except Invalid: raise HTTPException(401,'Login indisponível ou credencial inválida.') from None
        # Recurso fechado (futuro plano pago): quem não foi liberado não usa conexões, rotinas, alertas nem comandos.
        if need_access and not store.entitled(identity): raise HTTPException(403,'Este recurso ainda não está disponível para a sua conta.')
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
    def public_config(): return {'mode':'live' if transport.real else 'simulation','installationCapacity':verifier.capacity}
    def enrollment_limit(request):
        if not verifier.limit(request.client.host if request.client else 'unknown'): raise HTTPException(429,'Limite de tentativas atingido.')
    @app.post('/auth/register')
    async def register(request:Request):
        enrollment_limit(request);data=await payload(request);fields(data,{'credential','recovery'})
        return verifier.register(data.get('credential'),data.get('recovery'))
    @app.post('/auth/recover')
    async def recover(request:Request):
        enrollment_limit(request);data=await payload(request);fields(data,{'recovery','credential','newRecovery','operation'})
        return verifier.recover(data.get('recovery'),data.get('credential'),data.get('newRecovery'),data.get('operation'))
    @app.post('/v1/claim')
    async def claim(request:Request,user=Depends(known)):
        data=await payload(request);fields(data,{'code'})
        with rate_lock:  # poucas tentativas por conta: o código tem 256 bits, mas não há por que deixar insistir
            stamp=time.monotonic();queue=claim_attempts[user]
            while queue and queue[0]<stamp-600: queue.popleft()
            if len(queue)>=5: raise HTTPException(429,'Muitas tentativas. Aguarde alguns minutos.')
            queue.append(stamp)
        store.claim(user,data.get('code'));return {'ok':True,'admin':store.is_admin(user)}
    # ---- Administração dos códigos de acesso (clientes que pagam pelo menu Mensagens) ----
    @app.get('/v1/admin/claims')
    def admin_claims(user=Depends(administrator)): return store.admin_claims()
    @app.post('/v1/admin/claims')
    async def admin_new_claim(request:Request,user=Depends(administrator)):
        data=await payload(request);fields(data,{'note','uses'})
        return {'code':store.admin_new_claim(data.get('note',''),data.get('uses',1))}  # o código só aparece nesta resposta
    @app.delete('/v1/admin/claims/{key}')
    def admin_revoke_claim(key,user=Depends(administrator)):
        store.admin_revoke_claim(key);return {'id':key,'revoked':True}
    @app.get('/v1/admin/accounts')
    def admin_accounts(user=Depends(administrator)): return store.admin_accounts()
    @app.delete('/v1/admin/accounts/{key}')
    def admin_remove_account(key,user=Depends(administrator)):
        store.admin_remove_account(key);return {'owner':key,'removed':True}
    # ---- Comandos dos bots: o administrador liga/desliga e reescreve a resposta; o bot do WhatsApp lê daqui, o app lê a parte pública ----
    @app.get('/v1/admin/botcmds')
    def admin_botcmds(user=Depends(administrator)):
        return {scope:[{'cmd':cmd,'label':label,'enabled':saved.get(cmd,{}).get('enabled',True),'text':saved.get(cmd,{}).get('text',''),'default':HELP if (scope,cmd)==('whatsapp','help') else '{resposta}'} for cmd,label in cmds.items()]
                for scope,cmds in BOT_COMMANDS.items() for saved in [store.bot_settings(scope)]}
    @app.put('/v1/admin/botcmds/{scope}/{cmd}')
    async def admin_botcmd_set(scope,cmd,request:Request,user=Depends(administrator)):
        data=await payload(request);fields(data,{'enabled','text'})
        store.bot_set(scope,cmd,data.get('enabled'),data.get('text',''));return {'scope':scope,'cmd':cmd}
    @app.delete('/v1/admin/botcmds/{scope}/{cmd}')
    def admin_botcmd_reset(scope,cmd,user=Depends(administrator)):
        store.bot_reset(scope,cmd);return {'scope':scope,'cmd':cmd,'reset':True}
    @app.get('/public/botcmds')
    def public_botcmds(): return store.bot_settings('assistente')  # sem login: o app de qualquer usuário lê só o que o administrador mudou no assistente
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
        if store.get(user,key,'subscription')['state']=='revoked': raise Invalid('Rotina excluída.')
        data,state=subscription_data(user,await payload(request));store.update(user,key,'subscription',data,state);return {'id':key,'state':state}
    @app.delete('/v1/subscriptions/{key}')
    def delete_subscription(key,user=Depends(owner)):
        # 'revoked' libera a vaga do limite e cancela execuções pendentes; o histórico de runs fica.
        item=store.get(user,key,'subscription');store.update(user,key,'subscription',item['data'],'revoked');return {'id':key,'state':'revoked'}
    @app.get('/v1/subscriptions')
    def subscriptions(user=Depends(owner)):
        labels={d['id']:d['data'].get('label','') for d in store.list(user,'destination')}
        return [{'id':x['id'],'state':x['state'],**x['data'],'destinationLabel':labels.get(x['data']['destination'],'')} for x in store.list(user,'subscription') if x['state']!='revoked']
    def watch_data(user,data):
        fields(data,{'guild','milestone','deaths','ups','hourlyCap','perMinute','connection','destination','active'})
        if type(data.get('active',False)) is not bool: raise Invalid('Estado inválido.')
        config=validate_watch(data)
        conn=connection(user,data.get('connection',''));dest=store.get(user,data.get('destination',''),'destination')
        if dest['data']['connection']!=conn['id'] or dest['state']!='active': raise Invalid('Destino não autorizado.')
        if data.get('active'):
            if conn['state']!='active' or transport.status(conn['id']).get('state')!='connected': raise Invalid('Conexão indisponível.')
            if not any(g['id']==dest['data']['group'] for g in transport.groups(conn['id'])): raise Invalid('Grupo indisponível.')
        return {**config,'connection':conn['id'],'destination':dest['id']},'active' if data.get('active') else 'inactive'
    @app.post('/v1/watches')
    async def add_watch(request:Request,user=Depends(owner)):
        data,state=watch_data(user,await payload(request));return {'id':store.create(user,'watch',data,state,limit=3),'state':state,'mode':'live' if transport.real else 'simulation'}
    @app.put('/v1/watches/{key}')
    async def update_watch(key,request:Request,user=Depends(owner)):
        if store.get(user,key,'watch')['state']=='revoked': raise Invalid('Alerta excluído.')
        data,state=watch_data(user,await payload(request));store.update(user,key,'watch',data,state);return {'id':key,'state':state}
    @app.delete('/v1/watches/{key}')
    def delete_watch(key,user=Depends(owner)):
        item=store.get(user,key,'watch');store.update(user,key,'watch',item['data'],'revoked');return {'id':key,'state':'revoked'}
    @app.get('/v1/watches')
    def watches(user=Depends(owner)):
        labels={d['id']:d['data'].get('label','') for d in store.list(user,'destination')}
        return [{'id':x['id'],'state':x['state'],**x['data'],'destinationLabel':labels.get(x['data']['destination'],'')} for x in store.list(user,'watch') if x['state']!='revoked']
    def botgroup_data(user,data,own=None):
        fields(data,{'world','cooldown','connection','destination','active'})
        if type(data.get('active',False)) is not bool: raise Invalid('Estado inválido.')
        config=validate_botgroup(data)
        conn=connection(user,data.get('connection',''));dest=store.get(user,data.get('destination',''),'destination')
        if dest['data']['connection']!=conn['id'] or dest['state']!='active': raise Invalid('Destino não autorizado.')
        if data.get('active'):
            if conn['state']!='active' or transport.status(conn['id']).get('state')!='connected': raise Invalid('Conexão indisponível.')
            if not any(g['id']==dest['data']['group'] for g in transport.groups(conn['id'])): raise Invalid('Grupo indisponível.')
            if any(o['state']=='active' and o['data']['destination']==dest['id'] and o['id']!=own for o in store.list(user,'botgroup')): raise Invalid('Este grupo já tem comandos ativos.')
        return {**config,'connection':conn['id'],'destination':dest['id']},'active' if data.get('active') else 'inactive'
    @app.post('/v1/botgroups')
    async def add_botgroup(request:Request,user=Depends(owner)):
        data,state=botgroup_data(user,await payload(request));return {'id':store.create(user,'botgroup',data,state,limit=3),'state':state,'mode':'live' if transport.real else 'simulation'}
    @app.put('/v1/botgroups/{key}')
    async def update_botgroup(key,request:Request,user=Depends(owner)):
        if store.get(user,key,'botgroup')['state']=='revoked': raise Invalid('Comandos excluídos.')
        data,state=botgroup_data(user,await payload(request),own=key);store.update(user,key,'botgroup',data,state);return {'id':key,'state':state}
    @app.delete('/v1/botgroups/{key}')
    def delete_botgroup(key,user=Depends(owner)):
        item=store.get(user,key,'botgroup');store.update(user,key,'botgroup',item['data'],'revoked');return {'id':key,'state':'revoked'}
    @app.get('/v1/botgroups')
    def botgroups(user=Depends(owner)):
        labels={d['id']:d['data'].get('label','') for d in store.list(user,'destination')}
        return [{'id':x['id'],'state':x['state'],**x['data'],'destinationLabel':labels.get(x['data']['destination'],'')} for x in store.list(user,'botgroup') if x['state']!='revoked']
    @app.get('/v1/runs')
    def runs(user=Depends(owner)):
        with store.tx() as db: return [dict(x) for x in db.execute('SELECT id,subscription,reference,state,error FROM runs WHERE owner=? ORDER BY generation DESC LIMIT 100',(user,))]
    @app.get('/portal')
    def portal(): return JSONResponse({'message':'Abra a gestao de mensagens pelo aplicativo instalado.'})
    return app
