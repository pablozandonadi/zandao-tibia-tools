import json
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from mensagem_automatica_access import CredentialFile,InstallationClient,ManagementAPI,AccessError,AccessRejected,origin_url

class AccessTests(unittest.TestCase):
 def test_validation_error_is_not_a_recovery_failure(self):
  from unittest.mock import MagicMock
  opener=MagicMock()
  opener.open.side_effect=HTTPError('https://service.test/v1/preview',400,'Bad Request',{},io.BytesIO(json.dumps({'error':'Fonte GuildStats indisponível. Tente novamente.'}).encode()))
  with patch('mensagem_automatica_access.build_opener',return_value=opener):
   with self.assertRaisesRegex(AccessRejected,'Fonte GuildStats indisponível'):
    InstallationClient('https://service.test',None)._send('/v1/preview','POST',{})
  for path,body,expected in [('/v1/preview',b'not json','Confira os dados'),('/v1/preview',b'x'*8193,'Confira os dados'),('/auth/recover',b'{"error":"sensitive detail"}','código de recuperação')]:
   opener.open.side_effect=HTTPError('https://service.test'+path,400,'Bad Request',{},io.BytesIO(body))
   with patch('mensagem_automatica_access.build_opener',return_value=opener):
    with self.assertRaisesRegex(AccessRejected,expected):InstallationClient('https://service.test',None)._send(path,'POST',{})
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  # Deterministic stand-in only for filesystem/failure tests; real DPAPI tested separately.
  self.files=CredentialFile('https://service.test','beta',self.tmp.name,lambda s:bytes(x^91 for x in s.encode()),lambda b:bytes(x^91 for x in b).decode())
  self.server={};self.fail_after=False
  def send(path,method='GET',body=None,credential=None):
   pending=self.files.load();self.assertIsNotNone(pending,'Durable pending must precede every request')
   if path=='/auth/register':
    self.server.setdefault('credential',body['credential']);self.server.setdefault('recovery',body['recovery'])
   elif path=='/auth/recover':
    if self.server.get('credential')!=body['credential']:
     if body['recovery']!=self.server['recovery']:raise AccessRejected('wrong code')
     self.server.update(credential=body['credential'],recovery=body['newRecovery'])
   else:
    if path!='/public-config':self.assertEqual(credential,self.server['credential'])
    return {'mode':'simulation'} if path=='/public-config' else []
   if self.fail_after:self.fail_after=False;raise AccessError('lost response')
   return {'ok':True}
  self.client=InstallationClient('https://service.test',self.files,send)
 def test_register_lost_response_and_finalize_write_failure_retry_same_identity(self):
  self.fail_after=True
  with self.assertRaises(AccessError):self.client.request('/public-config')
  key=self.server['credential'];self.assertEqual(self.files.load()['state'],'register')
  self.client.request('/public-config');self.assertEqual(self.files.load()['credential'],key)
  self.assertNotIn(key.encode(),self.files.path.read_bytes())
  old=self.files.save
  def fail_active(v):
   if v['state']=='active':raise AccessError('disk failure')
   return old(v)
  with patch.object(self.files,'save',side_effect=fail_active):
   with self.assertRaises(AccessError):self.client.recover(self.server['recovery'])
  pending=self.files.load();self.assertEqual(pending['state'],'recover');self.assertEqual(pending['credential'],self.server['credential'])
  self.client.request('/v1/connections');self.assertEqual(self.files.load()['state'],'active')
 def test_recovery_lost_response_pending_survives_restart_and_wrong_code_preserves_access(self):
  self.client.request('/public-config');old=self.server['credential'];code=self.client.reveal();self.fail_after=True
  with self.assertRaises(AccessError):self.client.recover(code)
  self.assertNotEqual(old,self.server['credential']);self.assertEqual(self.files.load()['state'],'recover')
  InstallationClient('https://service.test',self.files,self.client.send).request('/v1/connections')
  current=self.files.load()['credential']
  with self.assertRaises(AccessRejected):self.client.recover('f'*64)
  self.assertEqual(self.files.load()['credential'],current);self.client.request('/v1/connections')
  # Hub: excluir rotina passa pela lista fechada; caminho fora do formato continua bloqueado.
  self.assertEqual(self.client.request('/v1/subscriptions/'+'a'*32,'DELETE'),[])
  with self.assertRaises(AccessError):self.client.request('/v1/subscriptions/x','DELETE')
  # Alertas da guild: mesmas regras (lista fechada, id hexadecimal de 32 caracteres, sem query).
  self.client.request('/v1/watches');self.client.request('/v1/watches','POST',{});self.client.request('/v1/watches/'+'a'*32,'PUT',{});self.client.request('/v1/watches/'+'a'*32,'DELETE')
  self.client.request('/v1/botgroups');self.client.request('/v1/botgroups','POST',{});self.client.request('/v1/botgroups/'+'a'*32,'PUT',{});self.client.request('/v1/botgroups/'+'a'*32,'DELETE')
  for path,method in [('/v1/botgroups/x','DELETE'),('/v1/botgroups?x=1','GET'),('/v1/botgroups/'+'a'*32,'POST'),('/v1/watches/x','DELETE'),('/v1/watches?x=1','GET'),('/v1/watches/'+'a'*32,'POST'),('/v1/watches/../connections','GET')]:
   with self.assertRaises(AccessError):self.client.request(path,method)
 def test_corruption_origin_channel_and_proxy_fail_closed(self):
  self.client.request('/public-config')
  bound=CredentialFile('https://other.test','beta',self.tmp.name,self.files.protect,self.files.unprotect)
  with self.assertRaises(AccessError):bound.load()
  self.files.path.write_bytes(b'corrupt')
  with self.assertRaises(AccessError):self.client.request('/public-config')
  other=CredentialFile('https://other.test','beta',self.tmp.name,self.files.protect,self.files.unprotect)
  with self.assertRaises(AccessError):other.load()
  stable=CredentialFile('https://service.test','stable',self.tmp.name,self.files.protect,self.files.unprotect);self.assertNotEqual(stable.path,self.files.path)
  for path in ['https://evil.test','//evil.test','/auth/register','/v1/connections/../../auth/recover','/v1/connections/abc','/v1/runs?secret=x']:
   with self.assertRaises(AccessError):self.client.request(path)
  with self.assertRaises(AccessError):origin_url('http://unsafe.test')
 def test_management_boot_never_exposes_bearer_and_recovery_is_explicit(self):
  api=ManagementAPI(self.client,{'personagem':'Sintético','mundo':'Antica'});boot=api.boot()
  self.assertEqual(sorted(n for n in dir(api) if not n.startswith('_')),['boot','recover','request','reveal_recovery'])
  self.assertEqual(boot['config']['mundo'],'Antica');self.assertNotIn(self.server['credential'],json.dumps(boot))
  self.assertEqual((self.files.path.parent/'installation.lock').stat().st_size,1)
  self.assertEqual(api.reveal_recovery()['code'],self.server['recovery']);self.assertIn('error',api.request('/auth/register'))
 def test_trusted_local_window_and_proxy_environment_redirect_boundaries(self):
  from types import SimpleNamespace
  from mensagem_automatica_access import open_management,NoRedirect
  from unittest.mock import MagicMock as Mock
  window=Mock()
  with patch.dict('sys.modules',{'webview':SimpleNamespace(create_window=window)}),patch.dict(os.environ,{'AUTOMATION_PORTAL_URL':'https://service.test','LOCALAPPDATA':self.tmp.name}):
   self.assertTrue(open_management({'personagem':'Sintetico','mundo':'Antica','blocks':{'mundo':True}})['ok'])
  args,kwargs=window.call_args;self.assertTrue(args[1].endswith('index.html'));self.assertNotIn('https:',args[1]);self.assertEqual(sorted(n for n in dir(kwargs['js_api']) if not n.startswith('_')),['boot','recover','request','reveal_recovery'])
  # Sem variável de ambiente, usa o servidor embutido.
  env={k:v for k,v in os.environ.items() if k!='AUTOMATION_PORTAL_URL'};env['LOCALAPPDATA']=self.tmp.name
  with patch.dict('sys.modules',{'webview':SimpleNamespace(create_window=window)}),patch.dict(os.environ,env,clear=True):
   self.assertTrue(open_management({'personagem':'Sintetico','mundo':'Antica','blocks':{'mundo':True}})['ok'])
  self.assertEqual(window.call_args.kwargs['js_api']._client.origin,'https://140.238.185.24')
  # Sem preferências salvas a tela abre mesmo assim, só com personagem e mundo.
  with patch.dict('sys.modules',{'webview':SimpleNamespace(create_window=window)}),patch.dict(os.environ,env,clear=True):
   self.assertTrue(open_management({'personagem':' Sintetico ','mundo':'Antica','blocks':{}})['ok'])
  self.assertEqual(window.call_args.kwargs['js_api']._config,{'personagem':'Sintetico','mundo':'Antica'})
  with self.assertRaises(AccessError):NoRedirect().redirect_request(None,None,None,None,None,None)
  from urllib.request import ProxyHandler
  fake=Mock();fake.open.return_value.__enter__.return_value.read.return_value=b'{}'
  with patch('mensagem_automatica_access.build_opener',return_value=fake) as build:
   InstallationClient('https://service.test',self.files)._send('/public-config')
  handler=build.call_args.args[0];self.assertIsInstance(handler,ProxyHandler);self.assertEqual(handler.proxies,{})
 @unittest.skipUnless(os.name=='nt','DPAPI CurrentUser requires Windows')
 def test_real_dpapi_roundtrip_no_plaintext(self):
  from voz_credenciais import _proteger,_desproteger
  value='synthetic-secret-'+('a'*64);encrypted=_proteger(value);self.assertNotIn(value.encode(),encrypted);self.assertEqual(_desproteger(encrypted),value)

if __name__=='__main__':unittest.main()
