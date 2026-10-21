"""Gestão local; bearer só em Python e estado DPAPI fora dos dados sincronizados."""
import json
import os
import re
import secrets
import threading
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler, ProxyHandler
from urllib.error import HTTPError, URLError
from voz_credenciais import _proteger, _desproteger

class AccessError(ValueError): pass
class AccessRejected(AccessError): pass
SECRET=re.compile(r'^[a-f0-9]{64}$')
ID=r'[a-f0-9]{32}'
ALLOWED={
 'GET':re.compile(r'^/(public-config|v1/(connections(?:/'+ID+r'(?:/groups)?)?|subscriptions|runs))$'),
 'POST':re.compile(r'^/v1/(preview|connections(?:/'+ID+r'/pair)?|destinations|subscriptions)$'),
 'PUT':re.compile(r'^/v1/subscriptions/'+ID+r'$'),
 'DELETE':re.compile(r'^/v1/(connections|subscriptions)/'+ID+r'$')}
# Servidor da VM Oracle; AUTOMATION_PORTAL_URL continua valendo como override administrativo.
DEFAULT_ORIGIN='https://140.238.185.24'
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs): raise AccessError('Redirecionamento recusado.')

def origin_url(value):
 try:
  p=urlsplit(value)
  if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('','/','/portal'): raise ValueError()
  if p.port and not 1<=p.port<=65535:raise ValueError()
  return 'https://'+p.netloc.lower()
 except (ValueError,TypeError):raise AccessError('A conexão segura ainda não foi configurada pelo administrador.') from None

class CredentialFile:
 def __init__(self,origin,channel,root=None,protect=_proteger,unprotect=_desproteger):
  self.origin=origin;self.channel='beta' if channel=='beta' else 'stable';self.protect=protect;self.unprotect=unprotect
  local=root or os.environ.get('LOCALAPPDATA')
  if not local:raise AccessError('Não foi possível acessar o armazenamento protegido do Windows.')
  self.path=Path(local)/'TibiaTudo'/'automation'/self.channel/'installation.dpapi'
  self.mutex=threading.RLock()
 @contextmanager
 def locked(self):
  with self.mutex:
   self.path.parent.mkdir(parents=True,exist_ok=True)
   with (self.path.parent/'installation.lock').open('a+b') as lock:
    lock.seek(0,2)
    if lock.tell()==0:lock.write(b'0');lock.flush()
    lock.seek(0)
    try:
     if os.name=='nt':
      import msvcrt
      msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
     else:
      import fcntl
      fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:raise AccessError('A gestão já está sendo atualizada em outra janela.') from None
    try:yield
    finally:
     lock.seek(0)
     if os.name=='nt':msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
     else:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)
 def load(self):
  if not self.path.exists():return None
  try:
   if self.path.is_symlink() or self.path.stat().st_size>16384:raise ValueError()
   value=json.loads(self.unprotect(self.path.read_bytes()))
   if value.get('origin')!=self.origin or value.get('channel')!=self.channel or value.get('state') not in ('active','register','recover'):raise ValueError()
   if not all(SECRET.fullmatch(value.get(k,'')) for k in ('credential','recovery')):raise ValueError()
   if value['state']=='recover' and not all(SECRET.fullmatch(value.get(k,'')) for k in ('oldRecovery','operation')):raise ValueError()
   return value
  except Exception:raise AccessError('A identidade protegida está indisponível. Use seu código de recuperação; nenhuma nova conta foi criada.') from None
 def save(self,value):
  temp=self.path.with_name('installation.'+secrets.token_hex(8)+'.tmp')
  try:
   raw=self.protect(json.dumps(value,separators=(',',':')))
   with os.fdopen(os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:
    stream.write(raw);stream.flush();os.fsync(stream.fileno())
   os.replace(temp,self.path)
  except Exception:raise AccessError('Não foi possível salvar a identidade protegida. Tente novamente antes de fechar.') from None
  finally:temp.unlink(missing_ok=True)

class InstallationClient:
 def __init__(self,origin,credentials,send=None):
  self.origin=origin_url(origin);self.credentials=credentials;self.send=send or self._send
 def _send(self,path,method='GET',body=None,credential=None):
  raw=json.dumps(body).encode() if body is not None else None
  if raw and len(raw)>32768:raise AccessError('Configuração muito grande.')
  request=Request(self.origin+path,data=raw,method=method,headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+credential} if credential else {})})
  try:
   with build_opener(ProxyHandler({}),NoRedirect,HTTPSHandler()).open(request,timeout=15) as response:
    result=response.read(131073)
    if len(result)>131072:raise AccessError('Resposta muito grande.')
    return json.loads(result)
  except HTTPError as error:
   if error.code==401:raise AccessError('Acesso inválido. Use seu código de recuperação.') from None
   if error.code==400:raise AccessRejected('Pedido recusado. Confira seu código de recuperação.') from None
   if error.code==429:raise AccessError('Muitas tentativas. Aguarde antes de tentar novamente.') from None
   raise AccessError('Não foi possível concluir a operação no serviço.') from None
  except (URLError,ValueError):raise AccessError('Serviço indisponível. Sua identidade foi preservada para tentar novamente.') from None
 def _finish(self,value):
  if value['state']=='register':
   try:ack=self.send('/auth/register','POST',{'credential':value['credential'],'recovery':value['recovery']})
   except AccessRejected:
    value['rejected']=True;self.credentials.save(value);raise
  elif value['state']=='recover':
   try:ack=self.send('/auth/recover','POST',{'recovery':value['oldRecovery'],'credential':value['credential'],'newRecovery':value['recovery'],'operation':value['operation']})
   except AccessRejected:
    if value.get('previous'):self.credentials.save(value['previous'])
    else:value['rejected']=True;self.credentials.save(value)
    raise
  else:return value
  if not isinstance(ack,dict) or ack.get('ok') is not True:raise AccessError('Resposta de acesso inválida. Tente novamente.')
  active={k:value[k] for k in ('origin','channel','credential','recovery')};active['state']='active';self.credentials.save(active);return active
 def _ensure(self):
  value=self.credentials.load()
  if value is None:
   value={'origin':self.origin,'channel':self.credentials.channel,'state':'register','credential':secrets.token_hex(32),'recovery':secrets.token_hex(32)}
   self.credentials.save(value)
  if value.get('rejected'):raise AccessError('Código recusado. Informe um código de recuperação válido.')
  return self._finish(value)
 def request(self,path,method='GET',body=None):
  if not isinstance(method,str) or method not in ALLOWED or not isinstance(path,str) or not ALLOWED[method].fullmatch(path):raise AccessError('Operação não permitida.')
  with self.credentials.locked():
   value=self._ensure();return self.send(path,method,body,None if path=='/public-config' else value['credential'])
 def reveal(self):
  with self.credentials.locked():return self._ensure()['recovery']
 def recover(self,code):
  if not isinstance(code,str) or not SECRET.fullmatch(code):raise AccessError('Código de recuperação inválido.')
  with self.credentials.locked():
   # Never replace a pending operation whose successful response may have been lost.
   try:current=self.credentials.load()
   except AccessError:current=None
   if current and current['state']!='active' and not current.get('rejected'):
    current=self._finish(current)
   value={'origin':self.origin,'channel':self.credentials.channel,'state':'recover','credential':secrets.token_hex(32),'recovery':secrets.token_hex(32),'oldRecovery':code,'operation':secrets.token_hex(32)}
   if current and current['state']=='active':value['previous']=current
   self.credentials.save(value);self._finish(value)
  return {'ok':True}

class ManagementAPI:
 def __init__(self,client,config):self._client=client;self._config=json.loads(json.dumps(config))
 def boot(self):
  try:return {'config':self._config,**self._client.request('/public-config')}
  except AccessError as error:return {'error':str(error)}
 def request(self,path,method='GET',body=None):
  try:return {'data':self._client.request(path,method,body)}
  except AccessError as error:return {'error':str(error)}
 def reveal_recovery(self):
  try:return {'code':self._client.reveal()}
  except AccessError as error:return {'error':str(error)}
 def recover(self,code):
  try:return self._client.recover(code)
  except AccessError as error:return {'error':str(error)}

def open_management(config):
 import webview
 import app_paths
 from versao import CANAL_APP
 origin=origin_url(os.environ.get('AUTOMATION_PORTAL_URL','').strip() or DEFAULT_ORIGIN)
 credentials=CredentialFile(origin,CANAL_APP)
 from mensagem_automatica_core import validate
 config=validate(config)
 api=ManagementAPI(InstallationClient(origin,credentials),config)
 path=app_paths.resource_dir()/'web'/'mensagem_automatica_portal'/'index.html'
 webview.create_window('Mensagem automática',str(path),js_api=api,width=900,height=800,min_size=(320,500))
 return {'ok':True}
