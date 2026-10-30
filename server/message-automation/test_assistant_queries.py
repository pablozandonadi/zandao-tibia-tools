"""Consultas do app não usam ponte, inbox, envio nem serviços externos nos testes."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from automation.api import create_app
from automation.auth import Verifier
from automation.store import Store
from automation.transport import FakeTransport
from automation.assistant_queries import execute,CATALOG
from automation.botcmds import Bot
from assistente_consultas import NEW_COMMANDS

class QueryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.store=Store(Path(self.tmp.name)/'s.sqlite',Fernet.generate_key());self.verifier=Verifier(self.store)
  self.verifier.register('a'*64,'b'*64);self.headers={'Authorization':'Bearer '+'a'*64}
  self.transport=FakeTransport();self.client=TestClient(create_app(self.store,self.transport,self.verifier))
 def post(self,body,headers=None):return self.client.post('/v1/assistant/command',json=body,headers=self.headers if headers is None else headers)
 def test_known_installation_does_not_need_whatsapp_entitlement(self):
  self.assertEqual(self.post({'text':'!help'},{}).status_code,401)
  result=self.post({'text':'!help'});self.assertEqual(result.status_code,200);self.assertIn('Assistente Tibiano',result.json()['text'])
  self.assertEqual(self.client.get('/v1/connections',headers=self.headers).status_code,403)
  self.assertEqual(self.transport.sent,[])
 def test_read_only_allowlist_and_context_validation(self):
  for body in ({'text':'!set world Antica'},{'text':'!alerta on'},{'text':'!bomdia teste'},{'text':'!duelo a x b','owner':'private'},{'text':3},{'text':'!help','mundo':'../bad'},{'text':'!help','personagem':'bad<script>'},{'text':'x'*181}):
   with self.subTest(body=body):self.assertEqual(self.post(body).status_code,400)
  self.assertEqual(self.transport.sent,[])
 def test_shared_bot_and_xp_cache_no_transport(self):
  sample={0:10,7:70,30:300,'_meta':{w:{'source':'GuildStats','fresh':True} for w in (0,7,30)},'_projection':True,'_rates':{30:10},'_daily':[]}
  with patch('automation.assistant_queries.XPProvider') as provider,patch('automation.botcmds.default_sheet',side_effect=lambda n:{'name':n,'world':'Antica','level':500,'vocation':'Elite Knight'}):
   provider.return_value.report.return_value=sample
   result=self.post({'text':'!duelo Alpha Knight x Beta Druid','mundo':'Antica'})
  self.assertEqual(result.status_code,200);text=result.json()['text'];self.assertIn('🛡️',text);self.assertEqual(text.count('30 dias:'),2);self.assertNotIn('GuildStats',text)
  self.assertEqual(self.transport.sent,[])
 def test_aliases_and_assistant_settings_do_not_change_whatsapp(self):
  self.store.bot_set('assistente','evolucao',False,'')
  self.assertIn('desativado',self.post({'text':'!evo Alpha Knight'}).json()['text']);self.assertEqual(self.store.bot_settings('whatsapp'),{})
  self.store.bot_set('assistente','help',True,'Somente consultas')
  self.assertEqual(self.post({'text':'!ajuda'}).json()['text'],'Somente consultas')
 def test_existing_char_template_keeps_legacy_variables(self):
  self.store.bot_set('assistente','char',True,'[{titulo}] {argumento}')
  with patch('comandos_tibia.HANDLERS',{'char':lambda *a:'Ficha pública\nCorpo'}):
   result=self.post({'text':'!personagem Alpha Knight'})
  self.assertEqual(result.json()['text'],'[Ficha pública] Alpha Knight')
 def test_new_catalog_preview_and_old_models_remain(self):
  self.store.grant(self.verifier.verify('a'*64),'dono')
  identity=self.verifier.verify('a'*64)
  with self.store.tx() as db:db.execute('INSERT INTO admins(owner) VALUES(?)',(identity,))
  listed=self.client.get('/v1/admin/botcmds',headers=self.headers).json()['assistente']
  self.assertTrue(set(NEW_COMMANDS)<=set(c['cmd'] for c in listed));self.assertEqual(next(c for c in listed if c['cmd']=='char')['default'],'{titulo}\n{corpo}')
  result=self.client.post('/v1/admin/botcmds/preview',headers=self.headers,json={'bot':'assistente','cmd':'help','text':'Novo {resposta}','arg':''})
  self.assertEqual(result.status_code,200);self.assertTrue(result.json()['text'].startswith('Novo 📖'))
  self.assertEqual(self.store.bot_settings('assistente'),{})
 def test_concurrency_is_bounded_and_does_not_queue_unlimited_work(self):
  from concurrent.futures import ThreadPoolExecutor
  from threading import Event,Lock
  ready=Event();release=Event();lock=Lock();entered=0
  def slow(*args):
   nonlocal entered
   with lock:
    entered+=1
    if entered==4:ready.set()
   release.wait(5)
   return {'command':'help','text':'Resposta'}
  with patch('automation.api.assistant_execute',side_effect=slow),ThreadPoolExecutor(max_workers=4) as pool:
   pending=[pool.submit(self.post,{'text':'!help'}) for _ in range(4)]
   try:
    self.assertTrue(ready.wait(5),'Four requests must enter the bounded executor')
    self.assertEqual(self.post({'text':'!help'}).status_code,429)
   finally:release.set()
   self.assertTrue(all(f.result().status_code==200 for f in pending))

if __name__=='__main__':unittest.main()
