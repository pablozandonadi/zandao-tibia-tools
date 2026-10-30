"""Segurança do acesso: toda rota do servidor tem um nível exigido (público, conta registrada, cliente liberado, administrador) e é testada com os quatro visitantes."""
import tempfile
import unittest
from pathlib import Path
from cryptography.fernet import Fernet
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from automation.api import create_app
from automation.auth import Verifier
from automation.domain import Invalid
from automation.store import Store
from automation.transport import FakeTransport

PUBLICO, CONTA, CLIENTE, ADMIN = 0, 1, 2, 3
# Nível mínimo de cada rota. Rota nova sem entrada aqui faz o primeiro teste falhar: classifique-a antes de publicar.
EXIGE = {
    ('GET', '/health'): PUBLICO, ('GET', '/public-config'): PUBLICO, ('GET', '/portal'): PUBLICO, ('GET', '/public/botcmds'): PUBLICO,
    ('POST', '/auth/register'): PUBLICO, ('POST', '/auth/recover'): PUBLICO,
    ('POST', '/v1/claim'): CONTA, ('POST', '/v1/assistant/command'): CONTA,
    ('GET', '/v1/admin/claims'): ADMIN, ('POST', '/v1/admin/claims'): ADMIN, ('DELETE', '/v1/admin/claims/{key}'): ADMIN,
    ('GET', '/v1/admin/accounts'): ADMIN, ('DELETE', '/v1/admin/accounts/{key}'): ADMIN,
    ('GET', '/v1/admin/botcmds'): ADMIN, ('POST', '/v1/admin/botcmds/preview'): ADMIN,
    ('PUT', '/v1/admin/botcmds/{scope}/{cmd}'): ADMIN, ('DELETE', '/v1/admin/botcmds/{scope}/{cmd}'): ADMIN,
    ('POST', '/v1/preview'): CLIENTE,
    ('POST', '/v1/connections'): CLIENTE, ('GET', '/v1/connections'): CLIENTE, ('POST', '/v1/connections/{key}/pair'): CLIENTE,
    ('GET', '/v1/connections/{key}'): CLIENTE, ('GET', '/v1/connections/{key}/groups'): CLIENTE, ('DELETE', '/v1/connections/{key}'): CLIENTE,
    ('POST', '/v1/destinations'): CLIENTE,
    ('POST', '/v1/subscriptions'): CLIENTE, ('PUT', '/v1/subscriptions/{key}'): CLIENTE, ('DELETE', '/v1/subscriptions/{key}'): CLIENTE, ('GET', '/v1/subscriptions'): CLIENTE,
    ('POST', '/v1/watches'): CLIENTE, ('PUT', '/v1/watches/{key}'): CLIENTE, ('DELETE', '/v1/watches/{key}'): CLIENTE, ('GET', '/v1/watches'): CLIENTE,
    ('POST', '/v1/botgroups'): CLIENTE, ('PUT', '/v1/botgroups/{key}'): CLIENTE, ('DELETE', '/v1/botgroups/{key}'): CLIENTE, ('GET', '/v1/botgroups'): CLIENTE,
    ('GET', '/v1/runs'): CLIENTE,
}
PREENCHE = {'{key}': 'a' * 32, '{scope}': 'whatsapp', '{cmd}': 'help'}
CONTAS = {'conta': ('a', '1'), 'cliente': ('b', '2'), 'admin': ('c', '3'), 'cliente2': ('d', '4')}  # credencial e código de recuperação são hexadecimais


class SegurancaTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.store = Store(Path(tmp.name) / 's.sqlite', Fernet.generate_key())  # modo real: fechado
        self.verifier = Verifier(self.store)
        self.app = create_app(self.store, FakeTransport(), self.verifier)
        self.client = TestClient(self.app)
        self.cab = {}
        for nome, (credencial, recuperacao) in CONTAS.items():
            self.verifier.register(credencial * 64, recuperacao * 64)
            self.cab[nome] = {'Authorization': 'Bearer ' + credencial * 64}
        self.client.post('/v1/claim', json={'code': self.store.create_claim('dono')}, headers=self.cab['admin'])
        for nome in ('cliente', 'cliente2'):
            self.client.post('/v1/claim', json={'code': self.store.admin_new_claim('Cliente ' + nome)}, headers=self.cab[nome])

    def rotas(self):
        return {(m, r.path) for r in self.app.routes if isinstance(r, APIRoute) for m in r.methods if m not in ('HEAD', 'OPTIONS')}

    def chamar(self, metodo, caminho, cabecalho):
        for chave, valor in PREENCHE.items(): caminho = caminho.replace(chave, valor)
        corpo = {'json': {}} if metodo in ('POST', 'PUT') else {}
        return self.client.request(metodo, caminho, headers=cabecalho or None, **corpo)

    def test_toda_rota_do_servidor_esta_classificada(self):
        self.assertEqual(self.rotas(), set(EXIGE), 'rota nova ou removida: atualize EXIGE com o nível de acesso certo')

    def test_cada_visitante_so_entra_onde_o_nivel_permite(self):
        visitantes = ((PUBLICO, 'anonimo', None), (CONTA, 'conta', self.cab['conta']), (CLIENTE, 'cliente', self.cab['cliente']), (ADMIN, 'admin', self.cab['admin']))
        for (metodo, caminho), exige in sorted(EXIGE.items()):
            for nivel, nome, cabecalho in visitantes:
                r = self.chamar(metodo, caminho, cabecalho); onde = f'{nome} em {metodo} {caminho}'
                if nivel < exige:
                    self.assertEqual(r.status_code, 401 if nome == 'anonimo' else 403, onde)
                else:
                    self.assertNotIn(r.status_code, (401, 403), onde)

    def test_credencial_invalida_nunca_vale(self):
        for cabecalho in ({'Authorization': 'Bearer ' + 'z' * 64}, {'Authorization': 'Bearer '}, {'Authorization': 'Basic ' + 'a' * 64}, {'Authorization': 'Bearer ' + 'a' * 20000}, {'Authorization': 'a' * 64}):
            for metodo, caminho in (('GET', '/v1/connections'), ('POST', '/v1/claim'), ('GET', '/v1/admin/claims')):
                self.assertEqual(self.chamar(metodo, caminho, cabecalho).status_code, 401, f'{cabecalho} em {caminho}')

    def test_codigo_de_cliente_nao_vira_administrador_nem_com_nome_parecido(self):
        for nota in ('dono', 'Dono', ' DONO '):
            with self.assertRaises(Invalid, msg=nota): self.store.admin_new_claim(nota)  # o nome "dono" é reservado ao código do dono
        self.verifier.register('e' * 64, '5' * 64); cab = {'Authorization': 'Bearer ' + 'e' * 64}
        self.assertEqual(self.client.post('/v1/claim', json={'code': self.store.admin_new_claim('dоno')}, headers=cab).status_code, 200)  # "о" cirílico: parece, mas não é
        self.assertEqual(self.client.get('/v1/connections', headers=cab).status_code, 200)
        for caminho in ('/v1/admin/claims', '/v1/admin/accounts', '/v1/admin/botcmds'):
            self.assertEqual(self.client.get(caminho, headers=cab).status_code, 403, caminho)

    def test_clientes_nao_enxergam_nem_alteram_o_que_e_do_outro(self):
        dono, outro = self.cab['cliente'], self.cab['cliente2']
        a = self.client.post('/v1/connections', json={'riskAccepted': True}, headers=dono).json()['id']
        self.client.post(f'/v1/connections/{a}/pair', headers=dono)
        dest = self.client.post('/v1/destinations', json={'connection': a, 'group': 'fake-group'}, headers=dono).json()['id']
        grupo = self.client.post('/v1/botgroups', json={'world': 'Antica', 'cooldown': 30, 'connection': a, 'destination': dest, 'active': True}, headers=dono).json()['id']
        alerta = self.client.post('/v1/watches', json={'guild': 'Piratas do Rocks', 'connection': a, 'destination': dest, 'active': True}, headers=dono).json()['id']
        for lista in ('connections', 'subscriptions', 'watches', 'botgroups'):
            self.assertEqual(self.client.get('/v1/' + lista, headers=outro).json(), [], lista)
        ataques = [('GET', f'/v1/connections/{a}', None), ('GET', f'/v1/connections/{a}/groups', None), ('POST', f'/v1/connections/{a}/pair', {}), ('DELETE', f'/v1/connections/{a}', None),
                   ('PUT', f'/v1/botgroups/{grupo}', {'world': 'Hack', 'cooldown': 5, 'connection': a, 'destination': dest, 'active': False}), ('DELETE', f'/v1/botgroups/{grupo}', None),
                   ('PUT', f'/v1/watches/{alerta}', {'guild': 'Hack', 'connection': a, 'destination': dest, 'active': False}), ('DELETE', f'/v1/watches/{alerta}', None),
                   ('POST', '/v1/destinations', {'connection': a, 'group': 'fake-group'}), ('POST', '/v1/botgroups', {'world': 'Antica', 'cooldown': 30, 'connection': a, 'destination': dest, 'active': True})]
        for metodo, caminho, corpo in ataques:
            r = self.client.request(metodo, caminho, headers=outro, **({'json': corpo} if corpo is not None else {}))
            self.assertEqual(r.status_code, 400, f'{metodo} {caminho}')
        self.assertEqual(self.client.get(f'/v1/connections/{a}', headers=dono).json()['state'], 'connected')
        g = self.client.get('/v1/botgroups', headers=dono).json()[0]; self.assertEqual((g['world'], g['state']), ('Antica', 'active'))
        w = self.client.get('/v1/watches', headers=dono).json()[0]; self.assertEqual((w['guild'], w['state']), ('Piratas do Rocks', 'active'))

    def test_trocar_o_codigo_do_dono_invalida_o_antigo_sem_derrubar_quem_ja_usou(self):
        vazado = self.store.create_claim('dono')
        self.assertEqual(self.store.revoke_claims('dono'), 2, 'o código do setUp e o "vazado"')
        self.verifier.register('e' * 64, '5' * 64); intruso = {'Authorization': 'Bearer ' + 'e' * 64}
        self.assertEqual(self.client.post('/v1/claim', json={'code': vazado}, headers=intruso).status_code, 400, 'código antigo morreu')
        self.assertEqual(self.client.get('/v1/admin/claims', headers=intruso).status_code, 403)
        self.assertEqual(self.client.get('/v1/admin/claims', headers=self.cab['admin']).status_code, 200, 'o administrador que já usou continua administrador')
        self.assertEqual(self.client.get('/v1/connections', headers=self.cab['cliente']).status_code, 200, 'clientes continuam liberados')
        novo = self.store.create_claim('dono', 1)
        self.assertEqual(self.client.post('/v1/claim', json={'code': novo}, headers=self.cab['conta']).status_code, 200)
        self.assertEqual(self.client.get('/v1/admin/accounts', headers=self.cab['conta']).status_code, 200, 'o código novo funciona')
        self.assertEqual(self.store.revoke_claims('nao-existe'), 0)

    def test_administrador_nao_perde_o_acesso_por_engano(self):
        contas = self.client.get('/v1/admin/accounts', headers=self.cab['admin']).json()
        admin = next(c for c in contas if c['admin'])
        self.assertEqual(self.client.delete('/v1/admin/accounts/' + admin['owner'], headers=self.cab['admin']).status_code, 400)
        self.assertEqual(self.client.get('/v1/admin/claims', headers=self.cab['admin']).status_code, 200)

    def test_rotas_publicas_nao_vazam_dados_de_clientes(self):
        self.client.put('/v1/admin/botcmds/whatsapp/duelo', json={'enabled': False, 'text': ''}, headers=self.cab['admin'])
        self.client.put('/v1/admin/botcmds/assistente/exp', json={'enabled': False, 'text': 'Desligado.'}, headers=self.cab['admin'])
        self.assertEqual(self.client.get('/public/botcmds').json(), {'exp': {'enabled': False, 'text': 'Desligado.'}}, 'só o assistente, nunca o bot do WhatsApp')
        self.assertEqual(set(self.client.get('/public-config').json()), {'mode', 'installationCapacity'})


if __name__ == '__main__': unittest.main()
