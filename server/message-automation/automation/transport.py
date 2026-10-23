"""Transporte falso por padrão; ponte privada explicitamente configurada."""
import secrets
import re
import httpx
from .domain import Invalid

class Ambiguous(Exception): pass
class NotDispatched(Invalid): pass

class FakeTransport:
    real=False
    def __init__(self): self.sessions={};self.sent=[];self.inbound={}
    def inbox(self,session): return self.inbound.pop(session,[])  # testes colocam aqui as linhas de comando "recebidas"
    def pair(self,session): self.sessions[session]='connected';return {'state':'connected','simulated':True}
    def status(self,session): return {'state':self.sessions.get(session,'connected'),'simulated':True}
    def groups(self,session):
        if self.status(session)['state']!='connected': raise Invalid('Conexão indisponível.')
        return [{'id':'fake-group','label':'Grupo sintético (simulação)'}]
    def revoke(self,session): self.sessions[session]='revoked'
    def send(self,session,group,text,attempt):
        if self.status(session)['state']!='connected' or group!='fake-group': raise Invalid('Destino indisponível.')
        self.sent.append({'session':session,'group':group,'text':text,'attempt':attempt})
        return {'id':secrets.token_hex(16),'simulated':True}

class BridgeTransport:
    real=True
    def __init__(self,url,token):
        if url not in ('http://127.0.0.1:8788','http://localhost:8788') or len(token)<32: raise Invalid('Ponte privada inválida.')
        self.url=url;self.token=token
    def request(self,method,path,body=None):
        try:
            with httpx.Client(timeout=15,follow_redirects=False,trust_env=False) as client:
                r=client.request(method,self.url+path,headers={'Authorization':'Bearer '+self.token},json=body)
            result=r.json()
        except (httpx.HTTPError,ValueError): raise Ambiguous() from None
        if r.status_code>=400:
            if result.get('dispatch')=='not_started': raise NotDispatched('Envio não iniciado.')
            raise Invalid('Ponte indisponível.')
        return result
    def live_status(self,result):
        if not isinstance(result,dict) or result.get('simulated') is not False: raise NotDispatched('Modo real da ponte não confirmado.')
        if result.get('state') not in ('connected','disconnected','pairing','revoked'): raise NotDispatched('Estado da ponte não confirmado.')
        return result
    def pair(self,session): return self.live_status(self.request('POST','/sessions/'+session+'/pair',{'riskAccepted':True}))
    def status(self,session): return self.live_status(self.request('GET','/sessions/'+session))
    def groups(self,session):
        if self.status(session)['state']!='connected': raise NotDispatched('Conexão indisponível.')
        return self.request('GET','/sessions/'+session+'/groups')['groups']
    def revoke(self,session): return self.request('DELETE','/sessions/'+session)
    def inbox(self,session):
        """Linhas de comando ("!...") recebidas nos grupos desde a última leitura. Falha de rede devolve vazio: ler comandos nunca atrapalha o envio."""
        try:
            if self.live_status(self.request('POST','/sessions/'+session+'/resume')).get('state')!='connected': return []
            result=self.request('POST','/sessions/'+session+'/inbox')
        except Exception: return []
        items=result.get('messages') if isinstance(result,dict) and result.get('simulated') is False else None
        keys=('id','group','sender','text')
        return [i for i in items if isinstance(i,dict) and all(isinstance(i.get(k),str) and i[k] for k in keys)][:100] if isinstance(items,list) else []
    def send(self,session,group,text,attempt):
        # Any uncertain bridge response after dispatch remains uncertain; never retry here.
        try:
            status=self.live_status(self.request('POST','/sessions/'+session+'/resume'))
            if status['state']!='connected': raise NotDispatched('Conexão indisponível.')
        except Exception: raise NotDispatched('Conexão indisponível antes do envio.') from None
        try:
            receipt=self.request('POST','/sessions/'+session+'/send',{'group':group,'text':text,'attempt':attempt})
            if isinstance(receipt,dict) and receipt.get('simulated') is True: raise NotDispatched('Ponte em simulação; envio real não realizado.')
            if not isinstance(receipt,dict) or receipt.get('simulated') is not False or not isinstance(receipt.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,128}',receipt['id']): raise Ambiguous()
            return receipt
        except NotDispatched: raise
        except Exception: raise Ambiguous() from None
