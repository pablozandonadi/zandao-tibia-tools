import tempfile
import unittest
from pathlib import Path
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from automation.store import Store
from automation.auth import Verifier
from automation.api import create_app
from automation.transport import FakeTransport
from automation.domain import Invalid

class InstallationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=Store(Path(self.tmp.name)/'db',Fernet.generate_key());self.auth=Verifier(self.store)
 def test_register_idempotent_hash_only_and_capacity(self):
  self.auth.capacity=1;self.auth.register('a'*64,'b'*64);owner=self.auth.verify('a'*64)
  self.auth.register('a'*64,'b'*64);self.assertEqual(self.auth.verify('a'*64),owner)
  with self.assertRaises(Invalid):self.auth.register('c'*64,'d'*64)
  with self.store.tx() as db: raw=str([tuple(x) for x in db.execute('SELECT * FROM installations')])
  self.assertNotIn('a'*64,raw);self.assertNotIn('b'*64,raw)
 def test_recovery_retry_preserves_owner_data_old_keys_invalid(self):
  self.auth.register('a'*64,'b'*64);owner=self.auth.verify('a'*64);item=self.store.create(owner,'subscription',{'synthetic':True})
  self.auth.recover('b'*64,'c'*64,'d'*64,'e'*64)
  # Lost response: identical retry confirms new pair without old code authorizing again.
  Verifier(self.store).recover('b'*64,'c'*64,'d'*64,'e'*64)
  self.assertEqual(self.auth.verify('c'*64),owner);self.assertEqual(self.store.get(owner,item,'subscription')['data'],{'synthetic':True})
  for action in [lambda:self.auth.verify('a'*64),lambda:self.auth.register('a'*64,'b'*64),lambda:self.auth.recover('b'*64,'f'*64,'1'*64,'2'*64)]:
   with self.assertRaises(Invalid):action()
 def test_concurrent_recovery_only_one_old_code_rotation_wins(self):
  from concurrent.futures import ThreadPoolExecutor
  from threading import Barrier
  self.auth.register('a'*64,'b'*64);barrier=Barrier(2)
  def rotate(values):
   barrier.wait()
   try:self.auth.recover('b'*64,*values);return True
   except Invalid:return False
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(rotate,[('c'*64,'d'*64,'e'*64),('f'*64,'1'*64,'2'*64)]))
  self.assertEqual(sorted(results),[False,True])
 def test_restore_revokes_credentials_and_recovery(self):
  self.auth.register('a'*64,'b'*64);backup=Path(self.tmp.name)/'backup';self.store.backup(backup);self.store.restore_offline(backup)
  with self.assertRaises(Invalid):self.auth.verify('a'*64)
  with self.assertRaises(Invalid):self.auth.recover('b'*64,'c'*64,'d'*64,'e'*64)
  with self.assertRaises(Invalid):self.auth.register('a'*64,'b'*64)
 def test_public_rate_is_persistent_ip_hashed_ttl_and_proxy_ignored(self):
  now=[120];self.auth.clock=lambda:now[0]
  for i in range(10):self.assertTrue(self.auth.limit('synthetic-ip'))
  self.assertFalse(Verifier(self.store,clock=lambda:now[0]).limit('synthetic-ip'))
  with self.store.tx() as db:self.assertNotIn('synthetic-ip',str([tuple(r) for r in db.execute('SELECT * FROM enrollment_rates')]))
  with self.store.tx() as db:self.assertEqual(db.execute("SELECT count FROM enrollment_rates WHERE scope='global'").fetchone()[0],10)
  now[0]=360;self.assertTrue(self.auth.limit('another-ip'))
  with self.store.tx() as db:self.assertEqual(db.execute('SELECT count(*) FROM enrollment_rates').fetchone()[0],2)
  app=TestClient(create_app(self.store,FakeTransport(),self.auth))
  for i in range(10):self.assertEqual(app.post('/auth/register',json={},headers={'X-Forwarded-For':str(i)}).status_code,400)
  self.assertEqual(app.post('/auth/register',json={},headers={'X-Forwarded-For':'new'}).status_code,429)
 def test_register_endpoint_never_accepts_owner(self):
  app=TestClient(create_app(self.store,FakeTransport(),self.auth));data={'credential':'a'*64,'recovery':'b'*64}
  self.assertEqual(app.post('/auth/register',json={**data,'owner':'forged'}).status_code,400)
  self.assertEqual(app.post('/auth/register',json=data).json(),{'ok':True})
  self.assertEqual(app.get('/v1/connections',headers={'Authorization':'Bearer '+'a'*64}).json(),[])

if __name__=='__main__':unittest.main()
