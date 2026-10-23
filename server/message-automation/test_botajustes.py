"""Ajustes dos comandos dos bots feitos pelo administrador: ligar/desligar e texto da resposta (WhatsApp no servidor, assistente via rota pública)."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from automation.api import create_app
from automation.auth import Verifier
from automation.botcmds import Bot, HELP
from automation.domain import Invalid
from automation.store import Store
from automation.transport import FakeTransport

TODAY = date(2026, 10, 23)
TRADE = lambda world: {'estado': 'ok', 'gold_por_tc': 48000, 'data_base': '2026-10-22T10:00:00+00:00', 'motivo': ''}

class AjustesTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.store = Store(Path(tmp.name) / 's.sqlite', Fernet.generate_key())

    def test_store_valida_e_guarda_so_o_que_mudou(self):
        s = self.store
        self.assertEqual(s.bot_settings('whatsapp'), {})
        s.bot_set('whatsapp', 'help', True, ' Olá\r\nmundo \x07 ')
        self.assertEqual(s.bot_settings('whatsapp'), {'help': {'enabled': True, 'text': 'Olá\nmundo'}})
        s.bot_set('whatsapp', 'duelo', False, '')
        self.assertEqual(s.bot_settings('whatsapp')['duelo'], {'enabled': False, 'text': ''})
        s.bot_set('whatsapp', 'duelo', True, '')  # ligado e sem texto = padrão: some da tabela
        self.assertNotIn('duelo', s.bot_settings('whatsapp'))
        s.bot_reset('whatsapp', 'help'); self.assertEqual(s.bot_settings('whatsapp'), {})
        self.assertEqual(s.bot_settings('assistente'), {})
        for args in (('x', 'help', True, ''), ('whatsapp', 'naoexiste', True, ''), ('whatsapp', 'help', 1, ''), ('whatsapp', 'help', True, 5), ('whatsapp', 'help', True, 'a' * 1501), ('assistente', 'duelo', True, '')):
            with self.assertRaises(Invalid, msg=args): s.bot_set(*args)
        with self.assertRaises(Invalid): s.bot_settings('x')
        with self.assertRaises(Invalid): s.bot_reset('whatsapp', 'naoexiste')

    def test_todo_comando_dos_bots_esta_na_lista_do_admin(self):
        """Comando novo que não entrar em BOT_COMMANDS (e no mapa do bot) não aparece no Admin: este teste falha para lembrar."""
        import comandos_tibia, bot_ajustes
        from automation.botcmds import KEYS
        from automation.store import BOT_COMMANDS
        self.assertEqual(set(KEYS.values()), set(BOT_COMMANDS['whatsapp']))
        self.assertEqual(set(comandos_tibia.HANDLERS), set(BOT_COMMANDS['assistente']))
        self.assertEqual(set(comandos_tibia.HANDLERS), set(bot_ajustes.CHAVES))
        pick = Bot().pick
        for cmd in BOT_COMMANDS['whatsapp']: self.assertTrue(pick('!' + cmd), cmd)

    def test_modelo_padrao_de_cada_comando_do_whatsapp_reproduz_a_resposta_de_hoje(self):
        """O texto que o Admin entrega como base tem de gerar exatamente a resposta padrão (e as variáveis do catálogo têm de existir)."""
        from automation.botcmds import MODELS
        import modelos
        b = Bot(trade=TRADE, settings=lambda: {})
        reply = b.coin('Rasteibra', '', TODAY)
        self.assertEqual(reply.text(), modelos.renderizar(MODELS['precocoin']['template'], reply.variables))
        self.assertEqual(reply.text('{resposta}'), reply.text(), '{resposta} = padrão')
        self.assertEqual(reply.text('💰 {preco} gold em {mundo}'), '💰 48.000 gold em Rasteibra')
        self.assertEqual(reply.text('{aviso_inexistente}'), '{aviso_inexistente}')
        for cmd, info in MODELS.items():
            self.assertEqual(set(modelos.VARIAVEL.findall(info['template'])) - set(info['vars']), set(), cmd)

    def test_preview_roda_o_comando_com_o_modelo_ainda_nao_salvo(self):
        from unittest.mock import patch
        import comandos_tibia
        verifier = Verifier(self.store); client = TestClient(create_app(self.store, FakeTransport(), verifier))
        h = {}
        for letter, recovery in (('a', 'c'), ('b', 'd')):
            verifier.register(letter * 64, recovery * 64); h[letter] = {'Authorization': 'Bearer ' + letter * 64}
        client.post('/v1/claim', json={'code': self.store.create_claim('dono')}, headers=h['a'])
        client.post('/v1/claim', json={'code': self.store.admin_new_claim('Cliente')}, headers=h['b'])
        corpo = {'bot': 'whatsapp', 'cmd': 'precocoin', 'text': 'Moeda em {mundo}: {preco}', 'arg': 'Antica'}
        self.assertEqual(client.post('/v1/admin/botcmds/preview', json=corpo, headers=h['b']).status_code, 403)
        with patch('automation.botcmds.default_trade', TRADE):
            r = client.post('/v1/admin/botcmds/preview', json=corpo, headers=h['a'])
            self.assertEqual((r.status_code, r.json()), (200, {'text': 'Moeda em Antica: 48.000'}))
            self.assertIn('🪙 *Tibia Coin — Antica*', client.post('/v1/admin/botcmds/preview', json={**corpo, 'text': ''}, headers=h['a']).json()['text'])
        with patch.dict(comandos_tibia.HANDLERS, {'exp': lambda rest, mundo, personagem, hoje: '🏆 Top XP\nlinha 1\nlinha 2'}):
            r = client.post('/v1/admin/botcmds/preview', json={'bot': 'assistente', 'cmd': 'exp', 'text': '[{titulo}]\n{corpo}', 'arg': ''}, headers=h['a'])
            self.assertEqual(r.json(), {'text': '[🏆 Top XP]\nlinha 1\nlinha 2'})
        self.assertEqual(self.store.bot_settings('whatsapp'), {}, 'a prévia nunca grava')
        for ruim in ({**corpo, 'cmd': 'naoexiste'}, {**corpo, 'bot': 'x'}, {**corpo, 'text': 'a' * 1501}, {**corpo, 'arg': 'a' * 81}, {**corpo, 'extra': 1}, {'bot': 'whatsapp'}):
            self.assertEqual(client.post('/v1/admin/botcmds/preview', json=ruim, headers=h['a']).status_code, 400, ruim)

    def test_bot_desligado_fica_em_silencio_e_ligado_segue_padrao(self):
        ajustes = {'duelo': {'enabled': False, 'text': ''}}
        b = Bot(trade=TRADE, settings=lambda: ajustes)
        self.assertFalse(b.known('!duelo a x b')); self.assertIsNone(b.handle('!duelo a x b', 'Tornabra', TODAY))
        self.assertTrue(b.known('!help')); self.assertEqual(b.handle('!help', '', TODAY), HELP)

    def test_texto_fixo_nao_consulta_a_fonte_e_resposta_embute_o_automatico(self):
        chamadas = []
        def trade(world): chamadas.append(world); return TRADE(world)
        ajustes = {'precocoin': {'enabled': True, 'text': 'Cotação só no site.'}, 'help': {'enabled': True, 'text': 'Oi!\n{resposta}\nBoa caçada'}}
        b = Bot(trade=trade, settings=lambda: ajustes)
        self.assertEqual(b.handle('!tc Antica', '', TODAY), 'Cotação só no site.'); self.assertEqual(chamadas, [], 'texto fixo: sem consulta')
        r = b.handle('!ajuda', '', TODAY); self.assertTrue(r.startswith('Oi!\n📖') and r.endswith('\nBoa caçada'))
        ajustes['precocoin']['text'] = 'Moeda: {resposta}'
        self.assertIn('*48.000* gold', b.handle('!precocoin Antica', '', TODAY)); self.assertEqual(chamadas, ['Antica'])

    def test_rotas_so_administrador_e_leitura_publica_do_assistente(self):
        verifier = Verifier(self.store); client = TestClient(create_app(self.store, FakeTransport(), verifier))
        h = {}
        for letter, recovery in (('a', 'c'), ('b', 'd')):
            verifier.register(letter * 64, recovery * 64); h[letter] = {'Authorization': 'Bearer ' + letter * 64}
        client.post('/v1/claim', json={'code': self.store.create_claim('dono')}, headers=h['a'])
        client.post('/v1/claim', json={'code': self.store.admin_new_claim('Cliente')}, headers=h['b'])
        self.assertEqual(client.get('/v1/admin/botcmds').status_code, 401)
        self.assertEqual(client.get('/v1/admin/botcmds', headers=h['b']).status_code, 403)
        self.assertEqual(client.put('/v1/admin/botcmds/assistente/exp', json={'enabled': False, 'text': ''}, headers=h['b']).status_code, 403)
        self.assertEqual(client.delete('/v1/admin/botcmds/assistente/exp', headers=h['b']).status_code, 403)
        listed = client.get('/v1/admin/botcmds', headers=h['a']).json()
        self.assertEqual([c['cmd'] for c in listed['whatsapp']], ['help', 'duelo', 'evolucao', 'precocoin', 'pt', 'char', 'online', 'xptop'])
        self.assertEqual(next(c for c in listed['whatsapp'] if c['cmd'] == 'help')['default'], HELP)
        self.assertTrue(all(c['enabled'] and c['text'] == '' for c in listed['assistente']))
        porta = next(c for c in listed['whatsapp'] if c['cmd'] == 'precocoin')
        self.assertIn('{mundo}', porta['default']); self.assertIn('{preco}', porta['default']); self.assertEqual(porta['example'], 'Rasteibra')
        self.assertEqual(next(v for v in porta['vars'] if v['name'] == 'preco')['desc'], 'gold por 1 TC'); self.assertIn('resposta', [v['name'] for v in porta['vars']])
        self.assertTrue(all(c['default'] == '{titulo}\n{corpo}' for c in listed['assistente']))
        self.assertTrue(all(c['vars'] and c['example'] is not None for c in listed['assistente'] + listed['whatsapp'] if c['cmd'] != 'help'))
        self.assertEqual(client.get('/public/botcmds').json(), {})
        for bad in ({'enabled': 'sim', 'text': ''}, {'enabled': True, 'text': 'a' * 1501}, {'enabled': True, 'extra': 1}, {'text': 'x'}):
            self.assertEqual(client.put('/v1/admin/botcmds/assistente/exp', json=bad, headers=h['a']).status_code, 400, bad)
        self.assertEqual(client.put('/v1/admin/botcmds/assistente/naoexiste', json={'enabled': True, 'text': ''}, headers=h['a']).status_code, 400)
        self.assertEqual(client.put('/v1/admin/botcmds/outro/exp', json={'enabled': True, 'text': ''}, headers=h['a']).status_code, 400)
        self.assertEqual(client.put('/v1/admin/botcmds/assistente/exp', json={'enabled': False, 'text': 'Desligado.'}, headers=h['a']).status_code, 200)
        self.assertEqual(client.put('/v1/admin/botcmds/whatsapp/duelo', json={'enabled': False, 'text': ''}, headers=h['a']).status_code, 200)
        # a rota pública só mostra o assistente; os ajustes do WhatsApp não vazam
        self.assertEqual(client.get('/public/botcmds').json(), {'exp': {'enabled': False, 'text': 'Desligado.'}})
        self.assertEqual(client.delete('/v1/admin/botcmds/assistente/exp', headers=h['a']).status_code, 200)
        self.assertEqual(client.get('/public/botcmds').json(), {})
        self.assertFalse(next(c for c in client.get('/v1/admin/botcmds', headers=h['a']).json()['whatsapp'] if c['cmd'] == 'duelo')['enabled'])

if __name__ == '__main__': unittest.main()
