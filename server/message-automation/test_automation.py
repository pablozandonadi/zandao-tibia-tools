"""Fixtures sintéticas: nenhuma consulta externa ou conexão WhatsApp."""
import copy
import json
import logging
import tempfile
import unittest
from unittest.mock import patch
import httpx
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from pathlib import Path
from types import SimpleNamespace
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from automation.domain import UTC,Invalid,SourceUnavailable,validate,local_instant,reference_day,fresh
from automation.store import Store
from automation.worker import Worker
from automation.transport import FakeTransport,Ambiguous,BridgeTransport,NotDispatched
from automation.auth import Verifier
from automation.api import create_app
from mensagem_automatica_report import generate

NOW=datetime(2026,10,21,12,tzinfo=UTC)
def config(): return {'personagem':'Pirata Teste','mundo':'Antica','blocks':{'mundo':True},'fields':{},'values':{},'extras':{},'args':{},'generateAt':'12:00','sendAt':'12:00','timezone':'UTC'}
def snapshot(c,now): return {'text':'Conteúdo sintético secreto','reference_date':reference_day(now),'generated_at':now.timestamp(),'sources':[{'source':'fixture','reference_date':reference_day(now),'fetched_at':now.timestamp()}]}

class CoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.key=Fernet.generate_key();self.store=Store(self.root/'state.sqlite',self.key);self.transport=FakeTransport()
 def subscription(self,user='owner',c=None):
  conn=self.store.create(user,'connection',{'riskAccepted':True},'active');self.transport.pair(conn)
  dest=self.store.create(user,'destination',{'connection':conn,'group':'fake-group'},'active')
  sub=self.store.create(user,'subscription',{'config':validate(c or config(),True),'connection':conn,'destination':dest},'active')
  return conn,dest,sub
 def runs(self):
  with self.store.tx() as db:return [dict(x) for x in db.execute("SELECT * FROM runs WHERE error IS NULL OR error!='generation_late'")]
 def test_simulated_end_to_end_concurrency_and_ciphertext(self):
  self.subscription();worker=Worker(self.store,self.transport,snapshot)
  with ThreadPoolExecutor(2) as pool:list(pool.map(lambda _:worker.tick(NOW),range(2)))
  self.assertEqual(len(self.transport.sent),1);self.assertEqual(self.runs()[0]['state'],'simulated')
  self.assertNotIn(b'Conte',self.store.path.read_bytes());self.assertNotIn(b'Antica',self.store.path.read_bytes())
  worker.tick(NOW+timedelta(minutes=2));self.assertEqual(len(self.transport.sent),1)
 def test_revoke_and_config_change_cancel_prepared(self):
  conn,dest,sub=self.subscription(c={**config(),'sendAt':'12:20'});worker=Worker(self.store,self.transport,snapshot);worker.tick(NOW)
  self.assertEqual(self.runs()[0]['state'],'ready');self.store.revoke('owner',conn);worker.tick(NOW+timedelta(minutes=20))
  self.assertEqual(self.runs()[0]['state'],'cancelled');self.assertFalse(self.transport.sent)
 def test_slow_dispatch_does_not_lock_api_writes_and_revoke_is_uncertain(self):
  conn,_,_=self.subscription();started=threading.Event();release=threading.Event()
  original=self.transport.send
  def slow(*args):
   started.set();release.wait(3);return original(*args)
  self.transport.send=slow
  with ThreadPoolExecutor(1) as pool:
   future=pool.submit(Worker(self.store,self.transport,snapshot).tick,NOW)
   self.assertTrue(started.wait(2));begin=time.monotonic();self.store.revoke('owner',conn)
   self.assertLess(time.monotonic()-begin,1);release.set();future.result(timeout=3)
  self.assertEqual(self.runs()[0]['state'],'uncertain')
 def test_configuration_revision_never_dispatches_old_snapshot(self):
  conn,dest,sub=self.subscription(c={**config(),'sendAt':'12:20'});worker=Worker(self.store,self.transport,snapshot);worker.tick(NOW)
  data=self.store.get('owner',sub,'subscription')['data'];data['config']['values']={'comunidade':'Mudou'}
  self.store.update('owner',sub,'subscription',data,'active');worker.tick(NOW+timedelta(minutes=20))
  self.assertFalse(self.transport.sent);self.assertEqual(self.runs()[0]['state'],'cancelled')
 def test_generation_late_crossing_server_save_expires(self):
  self.subscription(c={**config(),'generateAt':'07:55','sendAt':'08:10'})
  Worker(self.store,self.transport,snapshot).tick(NOW.replace(hour=8,minute=5))
  self.assertFalse(self.transport.sent);self.assertTrue(any(r['state']=='expired' and r['reference']=='2026-10-20' for r in self.runs()))
 def test_collection_refreshes_clock_and_send_crossing_server_save_expires(self):
  self.subscription(c={**config(),'generateAt':'07:59','sendAt':'08:01'});current=[NOW.replace(hour=7,minute=59)]
  def slow(c,now):
   current[0]=NOW.replace(hour=8,minute=1);return snapshot(c,now)
  Worker(self.store,self.transport,slow,clock=lambda:current[0]).tick()
  self.assertFalse(self.transport.sent);self.assertEqual(self.runs()[0]['state'],'expired')
 def test_dst_nonexistent_does_not_reserve_next_valid_day(self):
  self.subscription(c={**config(),'generateAt':'02:30','sendAt':'02:30','timezone':'Europe/Berlin'})
  worker=Worker(self.store,self.transport,snapshot);worker.tick(datetime(2026,3,29,2,tzinfo=UTC));worker.tick(datetime(2026,3,30,0,30,tzinfo=UTC))
  self.assertEqual(len(self.transport.sent),1)
  self.assertTrue(any(r['reference']=='2026-03-29' and r['state']=='simulated' for r in self.runs()))
 def test_uncertain_not_retried_and_restart(self):
  self.subscription();self.transport.send=lambda *a:(_ for _ in ()).throw(Ambiguous())
  worker=Worker(self.store,self.transport,snapshot);worker.tick(NOW);self.assertEqual(self.runs()[0]['state'],'uncertain');worker.tick(NOW+timedelta(minutes=1));self.assertEqual(self.runs()[0]['state'],'uncertain')
  with self.store.tx() as db:db.execute("UPDATE runs SET state='sending',lease=? WHERE error='transport_uncertain'",(NOW.timestamp(),))
  worker.tick(NOW+timedelta(seconds=1));self.assertEqual(self.runs()[0]['state'],'uncertain')
 def test_sources_expire_and_old_run_never_dispatches(self):
  self.subscription(c={**config(),'sendAt':'13:00'});worker=Worker(self.store,self.transport,snapshot);worker.tick(NOW);worker.tick(NOW+timedelta(hours=1));self.assertEqual(self.runs()[0]['state'],'expired');self.assertFalse(self.transport.sent)
 def test_dst_and_server_save(self):
  self.assertIsNone(local_instant('2026-03-29','02:30','Europe/Berlin'))
  self.assertEqual(local_instant('2026-10-25','02:30','Europe/Berlin').hour,0)
  self.assertEqual(reference_day(datetime(2026,3,29,7,59,tzinfo=UTC)),'2026-03-28')
  self.assertEqual(reference_day(datetime(2026,3,29,8,tzinfo=UTC)),'2026-03-29')
  self.assertEqual(reference_day(datetime(2026,10,25,9,tzinfo=UTC)),'2026-10-25')
 def test_validation_and_selective_generation(self):
  for patch in [{'blocks':{'mini':True}},{'sendAt':'11:59'},{'timezone':'Invalid/Zone'},{'owner':'victim'}]:
   with self.assertRaises(Invalid):validate({**config(),**patch},True)
  self.assertEqual(generate(config(),NOW)['text'],'🌍 Mundo: Antica')
  for k in ['dia','saudacao','frase','mundo','rashid','server_save']:
   c={**config(),'blocks':{k:True}};self.assertTrue(generate(c,NOW)['text'])
  c={**config(),'fields':{'coin_compra':True},'values':{'coin_compra':'100'}}
  with self.assertRaises(Invalid):generate(c,NOW)
  c['manualDate']='2026-10-21';self.assertIn('100',generate(c,NOW)['text'])
 def test_failclosed_sources_and_extras(self):
  class Provider:
   def summary(self,c,now):return {'yasir':{'estado':'indisponivel','consulta':now.timestamp()}}
  with self.assertRaises(Invalid):generate({**config(),'blocks':{'yasir':True}},NOW,Provider())
  class Good:
   def summary(self,c,now):return {'yasir':{'estado':'ausente','consulta':now.timestamp(),'mudancas':[]}}
   def extra(self,*a):return 'extra test',[{'source':'fixture','fetched_at':NOW.timestamp(),'reference_date':'2026-10-21'}]
  out=generate({**config(),'blocks':{'yasir':True,'mudancas_online':True},'extras':{'guild':True}},NOW,Good())
  self.assertIn('Inativo',out['text']);self.assertNotIn('World Board',out['text']);self.assertIn('extra test',out['text'])
  out['sources'][0]['fetched_at']-=4000
  with self.assertRaises(Invalid):fresh(out,NOW,'2026-10-21')
 def test_restore_invalidates_connections_and_jobs(self):
  conn,_,_=self.subscription();backup=self.root/'backup.fernet';self.store.backup(backup);self.store.revoke('owner',conn);self.store.restore_offline(backup)
  self.assertEqual(self.store.get('owner',conn,'connection')['state'],'revoked');self.assertEqual(self.store.list('owner','subscription')[0]['state'],'inactive')
  self.assertFalse(list(self.root.glob('*.tmp')))
 def test_backup_rejects_active_database_and_alias(self):
  self.subscription();before=self.store.path.read_bytes()
  with self.assertRaises(Invalid):self.store.backup(self.store.path)
  alias=self.root/'alias';alias.hardlink_to(self.store.path)
  with self.assertRaises(Invalid):self.store.backup(alias)
  self.assertEqual(before,self.store.path.read_bytes());self.assertEqual(len(self.store.list('owner','subscription')),1)
 def test_generation_transient_retry_persists_across_restart(self):
  self.subscription(c={**config(),'sendAt':'12:05'});calls=[]
  def flaky(c,now):
   calls.append(now)
   if len(calls)==1:raise SourceUnavailable('fixture')
   return snapshot(c,now)
  Worker(self.store,self.transport,flaky).tick(NOW);self.assertEqual(self.runs()[0]['state'],'pending')
  restarted=Worker(Store(self.store.path,self.key),self.transport,flaky);restarted.tick(NOW+timedelta(seconds=30));self.assertEqual(len(calls),1)
  restarted.tick(NOW+timedelta(seconds=60));self.assertEqual(self.runs()[0]['state'],'ready');restarted.tick(NOW+timedelta(minutes=5));self.assertEqual(len(self.transport.sent),1)
 def test_generation_retry_bound_and_expiry(self):
  self.subscription();calls=[]
  def unavailable(c,now):calls.append(now);raise SourceUnavailable('fixture')
  worker=Worker(self.store,self.transport,unavailable)
  for delta in [0,60,120,180,240,1801]:worker.tick(NOW+timedelta(seconds=delta))
  self.assertEqual(len(calls),3);self.assertEqual(self.runs()[0]['state'],'failed');self.assertEqual(self.runs()[0]['generation_attempts'],3)
 def test_invalid_data_does_not_retry(self):
  self.subscription();calls=[]
  def invalid(c,now):calls.append(now);raise Invalid('fixture')
  worker=Worker(self.store,self.transport,invalid);worker.tick(NOW);worker.tick(NOW+timedelta(minutes=2));self.assertEqual(len(calls),1)
 def test_private_bridge_predispatch_vs_ambiguous_without_network(self):
  original=httpx.Client;calls=[]
  for stage,exception in [('resume',NotDispatched),('send',Ambiguous),('not_started',NotDispatched)]:
   def response(request):
    calls.append(request.url.path)
    if request.url.path.endswith('/resume'):
     if stage=='resume':raise httpx.ReadTimeout('fixture')
     return httpx.Response(200,json={'state':'connected','simulated':False})
    if stage=='not_started':return httpx.Response(409,json={'dispatch':'not_started'})
    raise httpx.ReadTimeout('fixture')
   with patch('automation.transport.httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(response),**kw)):
    with self.assertRaises(exception):BridgeTransport('http://127.0.0.1:8788','x'*48).send('internal-id','opaque-group','private fixture','attempt')
  self.assertEqual(len(calls),5)
 def test_logs_exclude_library_payloads(self):
  from automation.safe_logging import SafeFilter
  f=SafeFilter()
  self.assertFalse(f.filter(logging.LogRecord('whatsmeow',logging.ERROR,'',0,'QR secret phone jid message',(),None)))
  self.assertFalse(f.filter(logging.LogRecord('automation',logging.ERROR,'',0,'unexpected secret',(),None)))
  self.assertTrue(f.filter(logging.LogRecord('automation',logging.INFO,'',0,'run=%s state=%s',('internal','simulated'),None)))
 def test_real_backend_refuses_fake_bridge_and_unclear_receipts(self):
  original=httpx.Client;transport=BridgeTransport('http://127.0.0.1:8788','x'*48);calls=[]
  def fake(request):calls.append(request.url.path);return httpx.Response(200,json={'state':'connected','simulated':True})
  with patch('automation.transport.httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(fake),**kw)):
   for method in [transport.status,transport.pair]:
    with self.assertRaises(NotDispatched):method('internal-id')
   self.subscription();Worker(self.store,transport,snapshot).tick(NOW)
   self.assertEqual(self.runs()[0]['state'],'failed');self.assertEqual(self.runs()[0]['error'],'transport_not_started')
   self.assertFalse(any(path.endswith('/send') for path in calls))
  for receipt,exception in [({'simulated':True},NotDispatched),({'id':'unknown'},Ambiguous),({'simulated':False,'id':''},Ambiguous)]:
   def response(request):return httpx.Response(200,json={'state':'connected','simulated':False} if request.url.path.endswith('/resume') else receipt)
   with patch('automation.transport.httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(response),**kw)):
    with self.assertRaises(exception):transport.send('id','group','private fixture','attempt')
 def test_auth_api_ownership_forgery_and_limits(self):
  private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  keys=SimpleNamespace(get_signing_key_from_jwt=lambda token:SimpleNamespace(key=private.public_key()))
  verifier=Verifier('https://accounts.google.com','test-client','https://www.googleapis.com/oauth2/v3/certs',key_client=keys)
  app=create_app(self.store,self.transport,verifier,origins=('https://portal.test',),generator=snapshot);client=TestClient(app)
  def headers(sub):
   now=datetime.now(UTC);token=jwt.encode({'sub':sub,'iss':'https://accounts.google.com','aud':'test-client','iat':now,'exp':now+timedelta(minutes=5)},private,algorithm='RS256')
   return {'Authorization':'Bearer '+token}
  a=headers('A');b=headers('B')
  self.assertEqual(client.get('/v1/connections').status_code,401)
  self.assertEqual(client.get('/v1/connections',headers={'Authorization':'Bearer invalid'}).status_code,401)
  self.assertEqual(client.get('/v1/connections',headers={**a,'Origin':'https://evil.test'}).status_code,403)
  self.assertEqual(client.post('/v1/preview',json=config(),headers=a).status_code,200)
  nonce='n'*40
  for claim,expected in [(None,401),('wrong-nonce',401),(nonce,200)]:
   now=datetime.now(UTC);claims={'sub':'A','iss':'https://accounts.google.com','aud':'test-client','iat':now,'exp':now+timedelta(minutes=5)}
   if claim is not None:claims['nonce']=claim
   token=jwt.encode(claims,private,algorithm='RS256')
   response=client.post('/auth/check',json={'nonce':nonce},headers={'Authorization':'Bearer '+token})
   self.assertEqual(response.status_code,expected)
  conn=client.post('/v1/connections',json={'riskAccepted':True},headers=a).json()['id']
  for path in [f'/v1/connections/{conn}',f'/v1/connections/{conn}/groups']:
   self.assertEqual(client.get(path,headers=b).status_code,400)
  self.assertEqual(client.post(f'/v1/connections/{conn}/pair',headers=b).status_code,400)
  self.assertEqual(client.post(f'/v1/connections/{conn}/pair',headers=a).status_code,200)
  self.assertEqual(client.post('/v1/destinations',json={'connection':conn,'group':'arbitrary-jid'},headers=a).status_code,400)
  dest=client.post('/v1/destinations',json={'connection':conn,'group':'fake-group'},headers=a).json()['id']
  sub=client.post('/v1/subscriptions',json={'config':config(),'connection':conn,'destination':dest,'active':True},headers=a)
  self.assertEqual(sub.status_code,200);self.assertEqual(sub.json()['mode'],'simulation')
  self.assertEqual(client.get('/v1/subscriptions',headers=b).json(),[])
  self.assertEqual(client.delete(f'/v1/connections/{conn}',headers=b).status_code,400)
  self.assertEqual(client.delete(f'/v1/connections/{conn}',headers=a).status_code,200)
  self.assertEqual(client.post(f'/v1/connections/{conn}/pair',headers=a).status_code,400)
  self.assertEqual(client.post('/v1/preview',content='x'*33000,headers=a).status_code,413)
  self.assertEqual(TestClient(create_app(self.store,self.transport)).get('/v1/connections',headers=a).status_code,401)
  wrong=jwt.encode({'sub':'A','iss':'https://accounts.google.com','aud':'test-client','exp':datetime.now(UTC)+timedelta(minutes=2),'iat':datetime.now(UTC)},'secret'*10,algorithm='HS256')
  self.assertEqual(client.get('/v1/connections',headers={'Authorization':'Bearer '+wrong}).status_code,401)

if __name__=='__main__':unittest.main()
