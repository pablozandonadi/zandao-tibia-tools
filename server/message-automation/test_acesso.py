"""Recurso fechado (futuro plano pago): só contas liberadas usam conexões, rotinas, alertas e comandos; quem já tinha dados continua liberado."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from automation.api import create_app
from automation.auth import Verifier
from automation.botcmds import Bot
from automation.commands import Commander
from automation.domain import UTC, Invalid
from automation.store import Store
from automation.transport import FakeTransport
from automation.watch import Watcher, validate_watch
from automation.worker import Worker

NOW = datetime(2026, 10, 23, 15, tzinfo=UTC)

class AcessoTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 's.sqlite'; self.key = Fernet.generate_key()
        self.store = Store(self.path, self.key)  # modo real: fechado

    def test_conta_nova_recebe_403_ate_ser_liberada(self):
        verifier = Verifier(self.store); client = TestClient(create_app(self.store, FakeTransport(), verifier))
        a = {'Authorization': 'Bearer ' + 'a' * 64}; verifier.register('a' * 64, 'c' * 64)
        self.assertEqual(client.get('/public-config').status_code, 200)
        for path in ('/v1/connections', '/v1/watches', '/v1/botgroups', '/v1/subscriptions'):
            r = client.get(path, headers=a); self.assertEqual(r.status_code, 403, path); self.assertIn('ainda não está disponível', r.text)
        self.assertEqual(client.post('/v1/connections', json={'riskAccepted': True}, headers=a).status_code, 403)
        self.assertEqual(client.get('/v1/connections', headers={'Authorization': 'Bearer ' + 'b' * 64}).status_code, 401, 'credencial desconhecida segue 401')
        owner = self.store.owners()[0]; self.assertFalse(owner['liberada'])
        self.store.grant(owner['owner'], 'dono')
        self.assertEqual(client.get('/v1/connections', headers=a).status_code, 200)
        self.assertEqual(client.post('/v1/connections', json={'riskAccepted': True}, headers=a).status_code, 200)
        self.assertTrue(self.store.owners()[0]['liberada'])
        self.store.ungrant(owner['owner']); self.assertEqual(client.get('/v1/connections', headers=a).status_code, 403)

    def test_quem_ja_tinha_dados_continua_liberado_so_na_migracao(self):
        old = Path(self.path.parent) / 'antigo.sqlite'
        with closing(sqlite3.connect(old)) as db:
            db.execute('CREATE TABLE objects(id TEXT PRIMARY KEY,owner TEXT NOT NULL,kind TEXT NOT NULL,state TEXT NOT NULL,body BLOB NOT NULL,version INTEGER NOT NULL DEFAULT 1)')
            db.execute("INSERT INTO objects VALUES('x','dono-antigo','connection','active',x'00',1)"); db.commit()
        store = Store(old, self.key)
        self.assertTrue(store.entitled('dono-antigo')); self.assertFalse(store.entitled('outro'))
        store.create('novo', 'connection', {'riskAccepted': True}, 'active')
        self.assertFalse(Store(old, self.key).entitled('novo'), 'depois da migração, conta nova não entra sozinha')

    def test_codigo_do_dono_libera_a_conta_de_quem_digita(self):
        verifier = Verifier(self.store); client = TestClient(create_app(self.store, FakeTransport(), verifier))
        a = {'Authorization': 'Bearer ' + 'a' * 64}; verifier.register('a' * 64, 'c' * 64)
        code = self.store.create_claim('dono')
        self.assertNotIn(code.encode(), self.path.read_bytes(), 'só o hash é gravado')
        self.assertEqual(client.get('/v1/connections', headers=a).status_code, 403)
        self.assertEqual(client.post('/v1/claim', json={'code': 'x' * 43}, headers=a).status_code, 400)
        self.assertEqual(client.post('/v1/claim', json={'code': code, 'extra': 1}, headers=a).status_code, 400)
        self.assertEqual(client.post('/v1/claim', json={'code': code}).status_code, 401, 'sem login, nada')
        ok = client.post('/v1/claim', json={'code': code}, headers=a); self.assertEqual(ok.status_code, 200)
        self.assertEqual(client.get('/v1/connections', headers=a).status_code, 200)
        # um PC novo (outra instalação) usa o mesmo código do dono e também é liberado
        verifier.register('b' * 64, 'd' * 64); b = {'Authorization': 'Bearer ' + 'b' * 64}
        self.assertEqual(client.get('/v1/connections', headers=b).status_code, 403)
        self.assertEqual(client.post('/v1/claim', json={'code': code}, headers=b).status_code, 200)
        self.assertEqual(client.get('/v1/connections', headers=b).status_code, 200)

    def test_codigo_de_uso_unico_e_limite_de_tentativas(self):
        verifier = Verifier(self.store); client = TestClient(create_app(self.store, FakeTransport(), verifier))
        for letter, recovery in (('a', 'c'), ('b', 'd')): verifier.register(letter * 64, recovery * 64)
        a = {'Authorization': 'Bearer ' + 'a' * 64}; b = {'Authorization': 'Bearer ' + 'b' * 64}
        code = self.store.create_claim('cliente', uses=1)
        self.assertEqual(client.post('/v1/claim', json={'code': code}, headers=a).status_code, 200)
        self.assertEqual(client.post('/v1/claim', json={'code': code}, headers=b).status_code, 400, 'já usado')
        statuses = [client.post('/v1/claim', json={'code': 'z' * 43}, headers=b).status_code for _ in range(6)]
        self.assertEqual(statuses[-1], 429, 'a sexta tentativa errada seguida é barrada')

    def _contas(self):
        verifier = Verifier(self.store); client = TestClient(create_app(self.store, FakeTransport(), verifier))
        heads = {}
        for letter, recovery in (('a', 'c'), ('b', 'd'), ('e', 'f')):
            verifier.register(letter * 64, recovery * 64); heads[letter] = {'Authorization': 'Bearer ' + letter * 64}
        return client, heads

    def test_so_administrador_gera_lista_e_revoga_codigos_de_cliente(self):
        client, h = self._contas()
        dono = self.store.create_claim('dono')
        client.post('/v1/claim', json={'code': dono}, headers=h['a'])  # a conta do dono vira administradora
        for path in ('/v1/admin/claims', '/v1/admin/accounts'):
            self.assertEqual(client.get(path, headers=h['b']).status_code, 403, 'conta comum (nem liberada) não administra')
        self.assertEqual(client.post('/v1/admin/claims', json={'note': 'Fulano'}, headers=h['b']).status_code, 403)
        for bad in ({'note': ''}, {'note': 'dono'}, {'note': 'x' * 61}, {'note': 'Ok', 'uses': 0}, {'note': 'Ok', 'uses': 1001}, {'note': 'Ok', 'extra': 1}, {'uses': 1}):
            self.assertEqual(client.post('/v1/admin/claims', json=bad, headers=h['a']).status_code, 400, bad)
        made = client.post('/v1/admin/claims', json={'note': '  Cliente   Um ', 'uses': 1}, headers=h['a'])
        self.assertEqual(made.status_code, 200); code = made.json()['code']; self.assertRegex(code, r'^[A-Za-z0-9_-]{43}$')
        listed = client.get('/v1/admin/claims', headers=h['a']).json()
        self.assertEqual([(c['note'], c['uses']) for c in listed], [('Cliente Um', 1)]); self.assertNotIn(code, str(listed)); self.assertNotIn('dono', [c['note'] for c in listed])
        # o cliente usa o código: libera, mas não vira administrador
        self.assertEqual(client.post('/v1/claim', json={'code': code}, headers=h['b']).status_code, 200)
        self.assertEqual(client.get('/v1/connections', headers=h['b']).status_code, 200)
        self.assertEqual(client.get('/v1/admin/claims', headers=h['b']).status_code, 403)
        self.assertEqual(client.get('/v1/admin/claims', headers=h['a']).json()[0]['uses'], 0)
        self.assertEqual(client.post('/v1/claim', json={'code': code}, headers=h['e']).status_code, 400, 'uso único')
        # revogar um código ainda não usado
        again = client.post('/v1/admin/claims', json={'note': 'Cliente Dois'}, headers=h['a']).json()['code']
        item = next(c for c in client.get('/v1/admin/claims', headers=h['a']).json() if c['note'] == 'Cliente Dois')
        self.assertEqual(client.delete('/v1/admin/claims/' + item['id'], headers=h['a']).status_code, 200)
        self.assertEqual(client.post('/v1/claim', json={'code': again}, headers=h['e']).status_code, 400)
        self.assertEqual(client.delete('/v1/admin/claims/' + item['id'], headers=h['a']).status_code, 400)
        self.assertEqual(client.delete('/v1/admin/claims/nao-existe', headers=h['a']).status_code, 400)

    def test_remover_conta_corta_o_acesso_mas_nunca_a_do_administrador(self):
        client, h = self._contas()
        client.post('/v1/claim', json={'code': self.store.create_claim('dono')}, headers=h['a'])
        client.post('/v1/claim', json={'code': self.store.admin_new_claim('Cliente')}, headers=h['b'])
        contas = client.get('/v1/admin/accounts', headers=h['a']).json()
        self.assertEqual(sorted((c['note'], c['admin']) for c in contas), [('Cliente', False), ('dono', True)])
        cliente = next(c for c in contas if c['note'] == 'Cliente'); admin = next(c for c in contas if c['admin'])
        self.assertEqual(client.delete('/v1/admin/accounts/' + admin['owner'], headers=h['a']).status_code, 400, 'administrador não se remove')
        self.assertEqual(client.delete('/v1/admin/accounts/' + cliente['owner'], headers=h['b']).status_code, 403)
        self.assertEqual(client.delete('/v1/admin/accounts/' + cliente['owner'], headers=h['a']).status_code, 200)
        self.assertEqual(client.get('/v1/connections', headers=h['b']).status_code, 403, 'sem acesso depois de removido')
        self.assertEqual(client.delete('/v1/admin/accounts/' + cliente['owner'], headers=h['a']).status_code, 400)
        self.assertEqual(client.delete('/v1/admin/accounts/xyz', headers=h['a']).status_code, 400)

    def test_liberar_conta_inexistente_e_recusado(self):
        with self.assertRaises(Invalid): self.store.grant('ninguem')

    def test_vigia_comandos_e_rotinas_param_sem_liberacao(self):
        transport = FakeTransport(); conn = self.store.create('o', 'connection', {'riskAccepted': True}, 'active'); transport.pair(conn)
        dest = self.store.create('o', 'destination', {'connection': conn, 'group': 'fake-group'}, 'active')
        self.store.create('o', 'watch', {**validate_watch({'guild': 'Piratas do Rocks'}), 'connection': conn, 'destination': dest}, 'active')
        self.store.create('o', 'botgroup', {'world': 'Tornabra', 'cooldown': 30, 'connection': conn, 'destination': dest}, 'active')
        chamadas = []
        def feed(path): chamadas.append(path); raise OSError('sem rede')
        self.assertFalse(self.store.entitled('o'))
        Watcher(self.store, transport, feed).tick(NOW)
        transport.inbound[conn] = [{'id': 'm1', 'group': 'fake-group', 'sender': 's', 'text': '!help'}]
        Commander(self.store, transport, Bot()).tick(NOW)
        Worker(self.store, transport).tick(NOW)
        self.assertEqual((chamadas, transport.sent), ([], []), 'conta sem liberação: nada é consultado nem enviado')
        self.store.grant('o')
        Watcher(self.store, transport, feed).tick(NOW + timedelta(minutes=5)); self.assertTrue(chamadas, 'liberada, o vigia volta a consultar')
        transport.inbound[conn] = [{'id': 'm2', 'group': 'fake-group', 'sender': 's', 'text': '!help'}]
        Commander(self.store, transport, Bot()).tick(NOW + timedelta(minutes=5)); self.assertEqual(len(transport.sent), 1)

if __name__ == '__main__': unittest.main()
