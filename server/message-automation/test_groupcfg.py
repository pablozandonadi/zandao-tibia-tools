"""Configuração pelo grupo: !set e !alerta, só para administradores do grupo, com os mesmos registros e limites do app."""
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from cryptography.fernet import Fernet
from automation.botcmds import Bot, HELP
from automation.commands import Commander
from automation.domain import UTC, Invalid
from automation.groupcfg import GroupConfig, parse_duration, duration_text
from automation.store import Store
from automation.transport import FakeTransport

NOW = datetime(2026, 10, 23, 15, tzinfo=UTC)

def item(text, id_='m1', sender='s1', admin=False):
    return {'id': id_, 'group': 'fake-group', 'sender': sender, 'text': text, 'admin': admin}


class DurationTests(unittest.TestCase):
    def test_unidades_e_limites(self):
        self.assertEqual([parse_duration(x) for x in ('30', '30s', '2m', '1h', ' 3 S ', '24h', '86400')], [30, 30, 120, 3600, 3, 86400, 86400])
        for bad in ('2', '86401', '25h', '0', '', 'abc', '1,5m', '-3', '1d', '9999999'):
            with self.assertRaises(Invalid, msg=bad): parse_duration(bad)
        self.assertEqual([duration_text(x) for x in (30, 120, 3600, 90, 7200)], ['30 s', '2 min', '1 h', '90 s', '2 h'])


class GroupConfigTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.store = Store(Path(tmp.name) / 's.sqlite', Fernet.generate_key(), open_access=True); self.transport = FakeTransport()
        self.conn = self.store.create('o', 'connection', {'riskAccepted': True}, 'active'); self.transport.pair(self.conn)
        self.dest = self.store.create('o', 'destination', {'connection': self.conn, 'group': 'fake-group'}, 'active')
        self.guilds = {'piratas do rocks': True, 'outra guild': True}
        self.commander = Commander(self.store, self.transport, Bot(trade=lambda w: {'estado': 'ok', 'gold_por_tc': 48000, 'data_base': '2026-10-22T10:00:00+00:00', 'motivo': ''}))
        self.commander.config = GroupConfig(self.store, guild_exists=lambda name: self.guilds.get(name.casefold(), False))
        self.key = self.store.create('o', 'botgroup', {'world': 'Tornabra', 'cooldown': 30, 'connection': self.conn, 'destination': self.dest, 'groupConfig': True}, 'active')
        self.step = 0

    def say(self, text, admin=True, sender='adm', at=None):
        self.step += 1; before = len(self.transport.sent)
        self.transport.inbound[self.conn] = [item(text, f'm{self.step}', sender, admin)]
        self.commander.tick(NOW + timedelta(seconds=self.step * 100 if at is None else at))
        return self.transport.sent[-1]['text'] if len(self.transport.sent) > before else None

    def group(self): return self.store.get('o', self.key, 'botgroup')['data']
    def watches(self): return [w for w in self.store.list('o', 'watch') if w['state'] != 'revoked']

    def test_so_admin_do_grupo_configura(self):
        self.assertIn('Só administradores', self.say('!set world Jadebra', admin=False))
        self.assertEqual(self.group()['world'], 'Tornabra')
        self.assertIn('Só administradores', self.say('!alerta guild Piratas do Rocks', admin=False, sender='outro'))
        self.assertEqual(self.watches(), [])
        self.assertIn('Jadebra', self.say('!set world jadebra'))
        self.assertEqual((self.group()['world'], self.group()['changedByGroup']), ('Jadebra', int((NOW + timedelta(seconds=300)).timestamp())))

    def test_nao_admin_que_insiste_cai_no_cooldown_em_silencio(self):
        self.assertIn('Só administradores', self.say('!set', admin=False, at=0))
        self.assertIsNone(self.say('!set', admin=False, at=10), 'dentro da espera: silêncio')
        self.assertIn('Só administradores', self.say('!set', admin=False, at=40))

    def test_admin_nao_espera_entre_comandos(self):
        for n in range(4): self.assertIsNotNone(self.say('!set cooldown 3m' if n % 2 else '!set', at=0), n)

    def test_cooldown_com_unidades_e_limites(self):
        self.assertIn('2 min', self.say('!set cooldown 2m')); self.assertEqual(self.group()['cooldown'], 120)
        self.assertIn('30 s', self.say('!set cooldown 30')); self.assertEqual(self.group()['cooldown'], 30)
        self.assertIn('1 h', self.say('!set cooldown 1h')); self.assertEqual(self.group()['cooldown'], 3600)
        for bad in ('!set cooldown 2', '!set cooldown 25h', '!set cooldown abc'):
            self.assertIn('⚠️', self.say(bad)); self.assertEqual(self.group()['cooldown'], 3600)
        self.assertIn('1 h', self.say('!set cooldown'))

    def test_world_invalido_e_mostrar(self):
        self.assertIn('⚠️', self.say('!set world 123')); self.assertEqual(self.group()['world'], 'Tornabra')
        self.assertIn('Tornabra', self.say('!set world')); self.assertIn('Tornabra', self.say('!set'))

    def test_pausar_e_desligar_um_comando_so_naquele_grupo(self):
        self.assertEqual(self.say('!help', admin=False, sender='a'), HELP)
        self.assertIn('desligado', self.say('!set cmd duelo off')); self.assertEqual(self.group()['disabled'], ['duelo'])
        self.assertIsNone(self.say('!duelo a x b', admin=False, sender='b'), 'desligado neste grupo: silêncio')
        self.assertEqual(self.say('!help', admin=False, sender='c'), HELP, 'os outros comandos seguem')
        self.assertIn('ligado', self.say('!set cmd duelo on')); self.assertEqual(self.group()['disabled'], [])
        self.assertIn('Use:', self.say('!set cmd naoexiste off')); self.assertIn('Use:', self.say('!set cmd duelo'))
        self.assertIn('pausados', self.say('!set comandos off')); self.assertTrue(self.group()['paused'])
        self.assertIsNone(self.say('!help', admin=False, sender='d'), 'pausado: sem resposta')
        self.assertIn('pausados', self.say('!set'), 'a configuração continua funcionando para os admins')
        self.assertIn('ligados', self.say('!set comandos on')); self.assertEqual(self.say('!help', admin=False, sender='e'), HELP)

    def test_alerta_criar_ajustar_pausar_e_remover(self):
        self.assertIn('nenhum', self.say('!alerta'))
        self.assertIn('⚠️', self.say('!alerta level 5'), 'sem alerta ainda')
        self.assertIn('Não encontrei a guild', self.say('!alerta guild Guild Fantasma'))
        self.assertIn('criado', self.say('!alerta guild Piratas do Rocks'))
        [w] = self.watches()
        self.assertEqual((w['data']['guild'], w['data']['milestone'], w['data']['deaths'], w['data']['ups'], w['data']['hourlyCap'], w['data']['perMinute'], w['state'], w['data']['source']),
                         ('Piratas do Rocks', 1, True, True, 0, 3, 'active', 'group'))
        self.assertEqual((w['data']['connection'], w['data']['destination']), (self.conn, self.dest))
        self.assertIn('50', self.say('!alerta level 50')); self.assertIn('Sem limite', self.say('!alerta limite hora 0')); self.assertIn('20', self.say('!alerta limite hora 20'))
        self.assertIn('5', self.say('!alerta limite minuto 5')); self.assertIn('desligados', self.say('!alerta mortes off'))
        [w] = self.watches(); d = w['data']
        self.assertEqual((d['milestone'], d['hourlyCap'], d['perMinute'], d['deaths'], d['ups']), (50, 20, 5, False, True))
        self.assertIn('⚠️', self.say('!alerta ups off'), 'precisa de mortes ou ups')
        self.assertIn('Outra Guild', self.say('!alerta guild Outra Guild')); self.assertEqual(len(self.watches()), 1)
        self.assertIn('pausado', self.say('!alerta off')); self.assertEqual(self.watches()[0]['state'], 'inactive')
        self.assertIn('ligado', self.say('!alerta on')); self.assertEqual(self.watches()[0]['state'], 'active')
        for bad in ('!alerta level 0', '!alerta level 1001', '!alerta limite minuto 0', '!alerta limite minuto 121', '!alerta limite dia 3', '!alerta mortes talvez', '!alerta guild <b>x</b>'):
            self.assertIn('⚠️', self.say(bad), bad)
        self.assertIn('removido', self.say('!alerta remover')); self.assertEqual(self.watches(), [])
        self.assertIn('nenhum', self.say('!alerta'))

    def subs(self): return [s for s in self.store.list('o', 'subscription') if s['state'] != 'revoked']

    def test_bomdia_liga_sempre_completo_com_a_assinatura(self):
        from automation.domain import BLOCKS
        from automation.groupcfg import SIGNATURE
        self.assertIn('desligado', self.say('!bomdia')); self.assertEqual(self.subs(), [])
        reply = self.say('!bomdia on'); self.assertIn('ligado', reply); self.assertIn('06:00', reply); self.assertIn('Yasir', reply); self.assertIn('boss boostado', reply); self.assertIn('amanhã', reply)
        [s] = self.subs(); c = s['data']['config']
        self.assertEqual((s['state'], s['data']['source'], s['data']['connection'], s['data']['destination']), ('active', 'group', self.conn, self.dest))
        self.assertEqual((c['sendAt'], c['generateAt'], c['timezone'], c['mundo']), ('06:00', '05:50', 'America/Sao_Paulo', 'Tornabra'))
        self.assertTrue(all(c['blocks'][k] for k in BLOCKS) and len(BLOCKS) == 13, 'os 13 itens da tela, sempre')
        self.assertEqual((c['fields']['assinatura'], c['values']['assinatura']), (True, SIGNATURE))
        self.assertIn('https://tibia-tudo.web.app', SIGNATURE); self.assertTrue(SIGNATURE.endswith('\nby Zandão'))
        self.assertIn('ligado', self.say('!bomdia')); self.assertEqual(len(self.subs()), 1, 'ligar de novo não duplica')

    def test_mensagem_gerada_tem_todos_os_itens_e_a_assinatura(self):
        from mensagem_automatica_report import generate
        from automation.domain import reference_day
        self.say('!bomdia on')
        config = self.subs()[0]['data']['config']
        class Provider:
            def summary(self, c, now):
                base = {'consulta': now.timestamp(), 'dia': reference_day(now)}
                return {'calendario': {**base, 'estado': 'disponivel', 'eventos': []}, 'yasir': {**base, 'estado': 'presente', 'mudancas': ['Mudança fixture']},
                        'boostados': {**base, 'boss': {'nome': 'Boss fixture'}, 'criatura': {'nome': 'Criatura fixture'}},
                        'dream_court': {**base, 'estado': 'previsto', 'nome': 'Dream fixture'},
                        'killstatistics': {**base, 'estado': 'disponivel', 'bosses': [{'nome': 'Boss', 'last_day_killed': 1}]}}
            def extra(self, key, arg, c, now):
                return f'EXTRA {key} [{arg}]', [{'source': key, 'fetched_at': now.timestamp(), 'reference_date': reference_day(now)}]
        text = generate(config, NOW, Provider())['text']
        for part in ('Bom dia', 'Mundo:* Tornabra', 'Yasir', 'Rashid', 'Criatura do dia', 'Boss do dia', 'Dream Court', 'Dream Court — mortes', 'Outras world changes', 'Próximo SS', 'Evento',
                     'EXTRA noticias', 'EXTRA kill', 'EXTRA exp_mundo', 'EXTRA transfer', '✍️ TibiaTudo IA, acesso o site https://tibia-tudo.web.app\nby Zandão'):
            self.assertIn(part, text, part)
        for part in ('EXTRA exp_guild', 'EXTRA guild', 'EXTRA online_guild', 'EXTRA char'):
            self.assertNotIn(part, text, 'sem guild definida, só as consultas que não dependem dela (e nunca online/personagem)')
        self.assertTrue(text.index('EXTRA transfer') < text.index('TibiaTudo IA, acesso'), 'a assinatura fecha a mensagem')
        self.say('!bomdia guild Piratas do Rocks')
        text = generate(self.subs()[0]['data']['config'], NOW, Provider())['text']
        self.assertIn('EXTRA exp_guild [Piratas do Rocks]', text); self.assertIn('EXTRA guild [Piratas do Rocks]', text)

    def test_bomdia_guild_vem_do_alerta_ou_do_comando_e_acompanha_mudancas(self):
        self.say('!bomdia on')
        self.assertIn('Para incluir top XP', self.say('!bomdia')); self.assertEqual(self.subs()[0]['data']['config']['args'], {})
        self.say('!alerta guild Piratas do Rocks')
        c = self.subs()[0]['data']['config']; self.assertEqual((c['args']['exp_guild'], c['args']['guild'], c['extras']['exp_guild'], c['extras']['guild']), ('Piratas do Rocks',) * 2 + (True, True))
        self.assertIn('Piratas do Rocks', self.say('!bomdia'))
        self.assertIn('Outra Guild', self.say('!bomdia guild Outra Guild')); self.assertEqual(self.subs()[0]['data']['config']['args']['exp_guild'], 'Outra Guild')
        self.say('!alerta guild Piratas do Rocks'); self.assertEqual(self.subs()[0]['data']['config']['args']['exp_guild'], 'Outra Guild', 'a escolha do !bomdia guild manda')
        self.assertIn('segue', self.say('!bomdia guild auto')); self.assertEqual(self.subs()[0]['data']['config']['args']['exp_guild'], 'Piratas do Rocks')
        self.say('!alerta remover'); self.assertEqual(self.subs()[0]['data']['config']['args'], {}, 'sem guild, as consultas da guild saem')
        self.assertIn('Não encontrei', self.say('!bomdia guild Guild Fantasma')); self.assertIn('⚠️', self.say('!bomdia guild <b>x</b>'))
        self.say('!bomdia horario 07:00'); self.say('!set world Jadebra'); c = self.subs()[0]['data']['config']
        self.assertEqual((c['sendAt'], c['mundo']), ('07:00', 'Jadebra'))

    def test_bomdia_teste_envia_na_hora_sem_gastar_o_envio_do_dia(self):
        calls = []
        long_text = 'A' * 5000 + '\n✍️ TibiaTudo IA, acesso o site https://tibia-tudo.web.app\nby Zandão'
        self.commander.config.generator = lambda config, now: (calls.append(config), {'text': long_text})[1]
        reply = self.say('!bomdia teste')
        self.assertTrue(reply.startswith('🧪 *Teste do bom dia*') and reply.endswith('by Zandão'), 'a mensagem inteira vai, com a assinatura no fim (sem o corte de 3500)')
        self.assertEqual((len(calls), self.subs()), (1, []), 'sem rotina ligada: usa a configuração padrão e não cria nada')
        self.assertTrue(all(calls[0]['blocks'][k] for k in calls[0]['blocks']) and calls[0]['sendAt'] == '06:00')
        self.assertEqual([x for x in self.transport.typing_log if x[2] == 'composing'][-1][1], 'fake-group', 'mostra "digitando…" enquanto monta')
        self.say('!bomdia on'); self.say('!bomdia guild Piratas do Rocks')
        self.assertIn('TibiaTudo IA', self.say('!bomdia agora')); self.assertEqual(calls[-1]['args']['exp_guild'], 'Piratas do Rocks', 'usa a rotina do grupo (com a guild)')
        with self.store.tx() as db: self.assertEqual(db.execute('SELECT count(*) FROM runs').fetchone()[0], 0, 'o teste não consome o envio do dia')
        self.commander.config.generator = lambda config, now: (_ for _ in ()).throw(RuntimeError('fonte fora do ar'))
        self.assertIn('Não consegui montar', self.say('!bomdia teste'))
        self.assertIn('!bomdia', self.say('!bomdia teste', admin=False, sender='intruso'))

    def test_bomdia_horario_diz_a_hora_de_agora_e_quando_envia(self):
        self.say('!bomdia on')
        late = self.say('!bomdia horario 22:00')   # NOW é 12:00 em Brasília
        self.assertIn('Agora são 12:0', late); self.assertIn('em Brasília', late); self.assertIn('*hoje*', late); self.assertIn('!bomdia teste', late)
        self.assertIn('*amanhã*', self.say('!bomdia horario 06:00'))
        self.assertIn('agora são 12:', self.say('!bomdia'))

    def test_bomdia_horario_pausa_e_remocao(self):
        self.assertIn('Ligue primeiro', self.say('!bomdia horario 07:00'))
        self.say('!bomdia on')
        for typed, send, generate in (('07:30', '07:30', '07:20'), ('7:05', '07:05', '06:55'), ('8h', '08:00', '07:50'), ('00:05', '00:05', '00:00'), ('18h30', '18:30', '18:20')):
            self.assertIn(send, self.say('!bomdia horario ' + typed)); c = self.subs()[0]['data']['config']; self.assertEqual((c['sendAt'], c['generateAt']), (send, generate), typed)
        for bad in ('25:00', '12:60', 'abc', '99'): self.assertIn('⚠️', self.say('!bomdia horario ' + bad), bad)
        self.assertEqual(self.subs()[0]['data']['config']['sendAt'], '18:30')
        self.assertIn('pausado', self.say('!bomdia off')); self.assertEqual(self.subs()[0]['state'], 'inactive')
        self.assertIn('pausado', self.say('!bomdia')); self.assertIn('ligado', self.say('!bomdia on')); self.assertEqual(self.subs()[0]['state'], 'active')
        self.assertIn('removido', self.say('!bomdia remover')); self.assertEqual(self.subs(), []); self.assertIn('desligado', self.say('!bomdia off'))

    def test_bomdia_so_admin_e_respeita_rotina_do_app(self):
        self.assertIn('!bomdia', self.say('!bomdia on', admin=False)); self.assertEqual(self.subs(), [])
        app = self.store.create('o', 'subscription', {'config': {}, 'connection': self.conn, 'destination': self.dest}, 'active', limit=5)
        self.assertIn('criada no app', self.say('!bomdia on')); self.assertEqual(len(self.subs()), 1)
        self.store.update('o', app, 'subscription', {'config': {}, 'connection': self.conn, 'destination': self.dest}, 'inactive')
        self.assertIn('ligado', self.say('!bomdia on'))

    def test_bomdia_respeita_o_limite_de_rotinas_do_dono(self):
        for n in range(5): self.store.create('o', 'subscription', {'config': {}, 'connection': self.conn, 'destination': f'x{n}'}, 'inactive', limit=5)
        self.assertIn('todas as rotinas permitidas', self.say('!bomdia on')); self.assertEqual(len([s for s in self.subs() if s['data']['destination'] == self.dest]), 0)

    def test_bomdia_acompanha_o_mundo_do_grupo_e_aparece_no_resumo(self):
        self.say('!bomdia on'); self.say('!set world Jadebra')
        self.assertEqual(self.subs()[0]['data']['config']['mundo'], 'Jadebra')
        summary = self.say('!set'); self.assertIn('Bom dia automático', summary); self.assertIn('bomdia ajuda', summary)

    def test_pausar_ou_editar_no_app_nao_apaga_a_origem_pelo_grupo(self):
        from fastapi.testclient import TestClient
        from automation.api import create_app
        from automation.auth import Verifier
        verifier = Verifier(self.store); client = TestClient(create_app(self.store, self.transport, verifier))
        verifier.register('a' * 64, 'c' * 64); head = {'Authorization': 'Bearer ' + 'a' * 64}
        conn = client.post('/v1/connections', json={'riskAccepted': True}, headers=head).json()['id']; client.post(f'/v1/connections/{conn}/pair', headers=head)
        dest = client.post('/v1/destinations', json={'connection': conn, 'group': 'fake-group'}, headers=head).json()['id']
        owner = next(o['owner'] for o in self.store.owners() if o['owner'] != 'o')
        sub = self.store.create(owner, 'subscription', {'config': GroupConfig.bomdia_config('Antica', '06:00'), 'connection': conn, 'destination': dest, 'source': 'group', 'createdAt': 5}, 'active', limit=5)
        watch = self.store.create(owner, 'watch', {'guild': 'Piratas do Rocks', 'milestone': 1, 'deaths': True, 'ups': True, 'hourlyCap': 0, 'perMinute': 3, 'connection': conn, 'destination': dest, 'source': 'group', 'createdAt': 6}, 'active', limit=3)
        body = {'config': GroupConfig.bomdia_config('Antica', '07:00'), 'connection': conn, 'destination': dest, 'active': False}
        self.assertEqual(client.put('/v1/subscriptions/' + sub, json=body, headers=head).status_code, 200)
        after = self.store.get(owner, sub, 'subscription'); self.assertEqual((after['state'], after['data']['source'], after['data']['createdAt'], after['data']['config']['sendAt']), ('inactive', 'group', 5, '07:00'))
        self.assertEqual(client.put('/v1/watches/' + watch, json={'guild': 'Piratas do Rocks', 'milestone': 5, 'connection': conn, 'destination': dest, 'active': False}, headers=head).status_code, 200)
        after = self.store.get(owner, watch, 'watch'); self.assertEqual((after['state'], after['data']['source'], after['data']['milestone']), ('inactive', 'group', 5))
        listed = client.get('/v1/subscriptions', headers=head).json()[0]; self.assertEqual(listed['source'], 'group')

    def test_listas_do_app_trazem_ultimo_uso_e_ultimo_aviso_sem_conteudo(self):
        from fastapi.testclient import TestClient
        from automation.api import create_app
        from automation.auth import Verifier
        verifier = Verifier(self.store); client = TestClient(create_app(self.store, self.transport, verifier))
        verifier.register('a' * 64, 'c' * 64); head = {'Authorization': 'Bearer ' + 'a' * 64}
        conn = client.post('/v1/connections', json={'riskAccepted': True}, headers=head).json()['id']; client.post(f'/v1/connections/{conn}/pair', headers=head)
        dest = client.post('/v1/destinations', json={'connection': conn, 'group': 'fake-group'}, headers=head).json()['id']
        group = client.post('/v1/botgroups', json={'world': 'Antica', 'cooldown': 30, 'connection': conn, 'destination': dest, 'active': True}, headers=head).json()['id']
        watch = client.post('/v1/watches', json={'guild': 'Piratas do Rocks', 'connection': conn, 'destination': dest, 'active': True}, headers=head).json()['id']
        self.assertEqual((client.get('/v1/botgroups', headers=head).json()[0]['lastUse'], client.get('/v1/watches', headers=head).json()[0]['lastSent']), (None, None), 'ninguém usou ainda')
        owner = next(o['owner'] for o in self.store.owners() if o['owner'] != 'o')
        with self.store.tx() as db:
            db.executemany('INSERT INTO command_use(botgroup,sender,last) VALUES(?,?,?)', [(group, 'x', 1760000100.0), (group, 'y', 1760000500.0)])
            db.executemany("INSERT INTO watch_events(id,owner,watch,key,text,state,created,sent_at) VALUES(?,?,?,?,?,?,?,?)",
                           [('e1', owner, watch, 'k1', b'x', 'accepted', 1.0, 1760000300.0), ('e2', owner, watch, 'k2', b'x', 'failed', 2.0, 1760000999.0), ('e3', owner, watch, 'k3', b'x', 'accepted', 3.0, 1760000800.0)])
        self.assertEqual(client.get('/v1/botgroups', headers=head).json()[0]['lastUse'], 1760000500.0, 'o uso mais recente de qualquer pessoa')
        self.assertEqual(client.get('/v1/watches', headers=head).json()[0]['lastSent'], 1760000800.0, 'só avisos realmente enviados contam')
        self.assertNotIn('sender', str(client.get('/v1/botgroups', headers=head).json()), 'nenhum nome de quem usou')

    def test_guild_que_nao_deu_para_conferir_nao_cria(self):
        self.commander.config.guild_exists = lambda name: None
        self.assertIn('Não consegui conferir', self.say('!alerta guild Piratas do Rocks')); self.assertEqual(self.watches(), [])

    def test_respeita_o_limite_de_alertas_do_dono(self):
        for n in range(3):
            self.store.create('o', 'watch', {'guild': f'G{n}', 'milestone': 1, 'deaths': True, 'ups': True, 'hourlyCap': 0, 'perMinute': 3, 'connection': self.conn, 'destination': 'outro-destino'}, 'active', limit=3)
        self.assertIn('todos os alertas permitidos', self.say('!alerta guild Piratas do Rocks'))
        self.assertEqual(len([w for w in self.watches() if w['data']['destination'] == self.dest]), 0)

    def test_dono_pode_desligar_a_configuracao_pelo_grupo(self):
        self.store.update('o', self.key, 'botgroup', {**self.group(), 'groupConfig': False}, 'active')
        self.assertIn('desligada pelo dono', self.say('!set world Jadebra')); self.assertEqual(self.group()['world'], 'Tornabra')
        self.assertEqual(self.say('!help', admin=False, sender='z'), HELP, 'os comandos normais seguem')

    def test_nao_vaza_para_outro_dono_nem_outro_grupo(self):
        other_conn = self.store.create('p', 'connection', {'riskAccepted': True}, 'active'); self.transport.pair(other_conn)
        other_dest = self.store.create('p', 'destination', {'connection': other_conn, 'group': 'fake-group'}, 'active')
        other = self.store.create('p', 'botgroup', {'world': 'Antica', 'cooldown': 30, 'connection': other_conn, 'destination': other_dest, 'groupConfig': True}, 'active')
        self.say('!set world Jadebra')
        self.assertEqual(self.store.get('p', other, 'botgroup')['data']['world'], 'Antica')

    def test_edicao_pelo_app_preserva_o_que_o_grupo_ajustou(self):
        from fastapi.testclient import TestClient
        from automation.api import create_app
        from automation.auth import Verifier
        verifier = Verifier(self.store); client = TestClient(create_app(self.store, self.transport, verifier))
        verifier.register('a' * 64, 'c' * 64); head = {'Authorization': 'Bearer ' + 'a' * 64}
        def ok(response):
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()
        conn = ok(client.post('/v1/connections', json={'riskAccepted': True}, headers=head))['id']; client.post(f'/v1/connections/{conn}/pair', headers=head)
        dest = ok(client.post('/v1/destinations', json={'connection': conn, 'group': 'fake-group'}, headers=head))['id']
        made = ok(client.post('/v1/botgroups', json={'world': 'Antica', 'cooldown': 30, 'connection': conn, 'destination': dest, 'active': True}, headers=head))['id']
        listed = client.get('/v1/botgroups', headers=head).json()[0]
        self.assertEqual((listed['groupConfig'], listed.get('paused'), listed.get('disabled')), (True, None, None))
        owner = next(o['owner'] for o in self.store.owners() if o['owner'] != 'o')
        mine = self.store.get(owner, made, 'botgroup')
        self.store.update(owner, made, 'botgroup', {**mine['data'], 'paused': True, 'disabled': ['duelo'], 'changedByGroup': 123}, 'active')
        r = client.put('/v1/botgroups/' + made, json={'world': 'Jadebra', 'cooldown': 90, 'connection': conn, 'destination': dest, 'active': True}, headers=head)
        self.assertEqual(r.status_code, 200, r.text)
        after = self.store.get(owner, made, 'botgroup')['data']
        self.assertEqual((after['world'], after['cooldown'], after['paused'], after['disabled'], after['changedByGroup'], after['groupConfig']), ('Jadebra', 90, True, ['duelo'], 123, True))
        client.put('/v1/botgroups/' + made, json={'world': 'Jadebra', 'cooldown': 90, 'connection': conn, 'destination': dest, 'active': True, 'groupConfig': False}, headers=head)
        self.assertEqual(self.store.get(owner, made, 'botgroup')['data']['groupConfig'], False)


if __name__ == '__main__': unittest.main()
