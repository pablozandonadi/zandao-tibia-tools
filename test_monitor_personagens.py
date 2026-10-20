import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.error import HTTPError

from app_paths import PRIVATE_FILES
from monitor_personagens import Monitor, MAX_TRACKED, guild_preview
from unittest.mock import patch


def dados(level=100, mortes=None):
    return {'character': {'character': {'name': 'Test Knight', 'level': level, 'vocation': 'Elite Knight', 'world': 'Antica'}, 'deaths': mortes or []}}


DEATH = {'time': '2026-10-20T10:00:00Z', 'level': 100, 'reason': 'Died by a dragon.', 'killers': [{'name': 'dragon', 'player': False}]}


class MonitorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 100000
        self.payload = dados(mortes=[DEATH])
        self.calls = 0
        def fetch(nome):
            self.calls += 1
            return copy.deepcopy(self.payload)
        self.fetch = fetch
        self.world_payload = None
        self.world_calls = []
        def fetch_world(world):
            self.world_calls.append(world)
            return copy.deepcopy(self.world_payload) if self.world_payload is not None else {
                'world': {'name': world, 'online_players': [self.payload['character']['character']]},
                'information': {'timestamp': datetime.fromtimestamp(self.now, timezone.utc).isoformat()}}
        self.fetch_world = fetch_world
        self.monitor = Monitor(self.temp.name, fetch=fetch, clock=lambda: self.now, fetch_world=fetch_world, wait=lambda _: False)
        self.monitor.configurar('Test Knight')

    def scan(self):
        self.now += 60
        self.monitor.scan()
        return self.monitor.estado()

    def test_baseline_sem_eventos_e_level_salvo_sem_alterar_cadastro(self):
        first = self.scan()
        self.assertFalse(first['up'])
        self.assertFalse(first['death'])
        self.payload = dados(103, [DEATH])
        state = self.scan()
        self.assertIn('🛡️ Test Knight subiu do level 100 para 103', state['up'][0]['texto'])
        self.assertIn('horário da detecção', state['up'][0]['texto'])
        self.assertEqual(os.listdir(self.temp.name), ['monitor-personagens.json'])

    def test_deaths_fingerprint_estavel_restart_e_mesma_entrada(self):
        self.scan()
        novo = {**DEATH, 'time': '2026-10-20T11:00:00Z', 'level': 101}
        self.payload = dados(101, [novo, DEATH, novo])
        self.assertEqual(len(self.scan()['death']), 1)
        self.monitor = Monitor(self.temp.name, fetch=self.fetch, clock=lambda: self.now, fetch_world=self.fetch_world, wait=lambda _: False)
        self.assertEqual(len(self.scan()['death']), 1)
        self.assertEqual(self.monitor.estado()['death'][0]['at'], '2026-10-20T11:00:00+00:00')

    def test_falha_ou_mortes_malformadas_preserva_referencia(self):
        self.scan()
        for malformed in (None, {}, [{'level': 100}], [{'time': DEATH['time'], 'level': 100, 'killers': 'x'}]):
            self.payload = dados()
            self.payload['character']['deaths'] = malformed
            self.assertEqual(self.scan()['up'], [])
        self.payload = dados(105, [DEATH])
        self.assertIn('100 para 105', self.scan()['up'][0]['texto'])

    def test_toggle_rebaseline_e_minimo60s(self):
        self.scan()
        self.monitor.configurar('Test Knight', False, False)
        self.payload = dados(110, [{**DEATH, 'time': '2026-10-20T12:00:00Z'}])
        self.monitor.configurar('Test Knight', True, True)
        self.monitor.scan()
        self.assertEqual(self.calls, 1)
        state = self.scan()
        self.assertEqual(state['up'], [])
        self.assertEqual(state['death'], [])

    def test_uplevel_independe_de_deaths_quando_death_desligado(self):
        self.monitor.configurar('Test Knight', up=True, death=False)
        self.payload = dados()
        del self.payload['character']['deaths']
        self.scan()
        self.payload['character']['character']['level'] = 102
        self.payload['character']['deaths'] = 'malformado'
        self.assertIn('100 para 102', self.scan()['up'][0]['texto'])

    def test_arquivo_invalido_preservado_sem_crash(self):
        for content in ('[]', 'null', '"texto"', '{}', '{'):
            with self.subTest(content=content):
                with open(self.monitor.path, 'w', encoding='utf-8') as file:
                    file.write(content)
                monitor = Monitor(self.temp.name, fetch=self.fetch)
                self.assertTrue(monitor.estado()['aviso'])
                with open(monitor.path, encoding='utf-8') as file:
                    self.assertEqual(file.read(), content)

    def test_remove_durante_consulta_nao_ressuscita(self):
        self.scan()
        entered, release = threading.Event(), threading.Event()
        def fetch(nome):
            entered.set()
            release.wait(2)
            return dados(110, [{**DEATH, 'time': '2026-10-20T12:00:00Z'}])
        self.monitor.fetch = fetch
        self.now += 60
        thread = threading.Thread(target=self.monitor.scan)
        thread.start()
        self.assertTrue(entered.wait(1))
        self.monitor.configurar('Test Knight', remover=True)
        release.set()
        thread.join(2)
        self.assertEqual(self.monitor.estado()['personagens'], [])
        self.assertEqual(self.monitor.estado()['up'], [])

    def test_toggle_durante_consulta_rejeita_resultado_e_rebaseline(self):
        self.scan()
        entered, release = threading.Event(), threading.Event()
        def fetch(nome):
            entered.set()
            release.wait(2)
            return dados(110, [{**DEATH, 'time': '2026-10-20T12:00:00Z'}])
        self.monitor.fetch = fetch
        self.now += 60
        thread = threading.Thread(target=self.monitor.scan)
        thread.start()
        self.assertTrue(entered.wait(1))
        self.monitor.configurar('Test Knight', False, False)
        self.monitor.configurar('Test Knight', True, True)
        release.set()
        thread.join(2)
        self.assertEqual(self.monitor.estado()['up'], [])
        self.assertEqual(self.monitor.estado()['death'], [])
        self.assertEqual(self.scan()['death'], [])

    def test_thread_singleton_e_close(self):
        self.monitor.start()
        thread = self.monitor.thread
        self.monitor.start()
        self.assertIs(self.monitor.thread, thread)
        self.monitor.close()
        self.assertFalse(thread.is_alive())

    def test_bulk_preserves_existing_flags_baselines_and_deduplicates(self):
        self.scan();before=copy.deepcopy(self.monitor.data['personagens'][0])
        members=[{'nome':'test knight','world':'Secura'},{'nome':'New Paladin','world':'Antica','vocation':'Royal Paladin'},{'nome':'NEW PALADIN','world':'Antica'}]
        with patch.object(self.monitor,'_save',wraps=self.monitor._save) as save:
            result=self.monitor.importar(members,up=False,death=True)
        save.assert_called_once();self.assertEqual(before,self.monitor.data['personagens'][0])
        self.assertEqual({'adicionados':1,'existentes':1,'total':2},result['importacao'])
        new=self.monitor.data['personagens'][1];self.assertFalse(new['up']);self.assertTrue(new['death']);self.assertIsNone(new['mortes'])
        restarted=Monitor(self.temp.name,fetch=self.fetch,clock=lambda:self.now,fetch_world=self.fetch_world,wait=lambda _:False)
        self.assertEqual(self.monitor.data,restarted.data)

    def test_bulk_rejects_any_invalid_member_or_limit_without_partial_save(self):
        before=Path(self.monitor.path).read_text(encoding='utf8')
        for members in ([{'nome':'Valid Knight','world':'Antica'},{'nome':'../invalid','world':'Antica'}],[{'nome':'Valid Knight','world':'Antica'},{'nome':'Other Knight','world':'../bad'}]):
            with self.assertRaises(ValueError):self.monitor.importar(members)
            self.assertEqual(before,Path(self.monitor.path).read_text(encoding='utf8'))
        with patch('monitor_personagens.MAX_TRACKED',2):
            with self.assertRaises(ValueError):self.monitor.importar([{'nome':'New Knight','world':'Antica'},{'nome':'New Druid','world':'Antica'}])
        self.assertEqual(before,Path(self.monitor.path).read_text(encoding='utf8'))
        self.assertEqual(1000,MAX_TRACKED)

    def test_bulk_concurrent_merges_use_latest_configuration_and_limit(self):
        barrier=threading.Barrier(2)
        def add(name):
            barrier.wait()
            try:return self.monitor.importar([{'nome':name,'world':'Antica'}])
            except ValueError:return None
        with patch('monitor_personagens.MAX_TRACKED',2),ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(add,['Concurrent Knight','Concurrent Druid']))
        self.assertEqual(1,sum(result is not None for result in results))
        self.assertEqual(2,len(self.monitor.data['personagens']))

    def test_guild_over_twenty_uses_world_hint_and_initial_world_read_is_silent(self):
        members=[{'nome':'Guild Member '+chr(65+i),'world':'Antica'} for i in range(25)]
        self.monitor.importar(members,up=True,death=False)
        self.assertEqual(26,len(self.monitor.data['personagens']))
        restarted=Monitor(self.temp.name,fetch=self.fetch,clock=lambda:self.now,fetch_world=lambda world:{'world':{'name':world,'online_players':[{'name':m['nome'],'level':100,'vocation':'Knight'} for m in members]},'information':{'timestamp':datetime.fromtimestamp(self.now,timezone.utc).isoformat()}},wait=lambda _:False)
        restarted._scan_world();self.assertEqual([],restarted.estado()['up']);self.assertEqual(0,self.calls)
        self.assertTrue(all(r.get('world_baseline') for r in restarted.data['personagens'][1:]))

    def test_guild_preview_shares_request_gate_cache_and_backoff(self):
        payload={'guild':{'name':'Example Guild','world':'Antica','members':[{'name':'Test Knight'}]}}
        with patch('monitor_personagens.tibia_info._get_json',return_value=payload) as fetch,patch.object(self.monitor,'_request',wraps=self.monitor._request) as gate:
            first=self.monitor.guild('Example Guild');second=self.monitor.guild('Example Guild')
            self.assertEqual(first,second);self.assertEqual(1,fetch.call_count);self.assertEqual(1,gate.call_count)
        self.now+=301
        with patch('monitor_personagens.tibia_info._get_json',side_effect=HTTPError('https://api.tibiadata.com/v4/guild/Example',429,'limit',{'Retry-After':'600'},None)):
            stale=self.monitor.guild('Example Guild')
        self.assertTrue(stale['velho']);self.assertEqual(self.now+600,self.monitor.network_until)
        with patch('monitor_personagens.tibia_info._get_json') as fetch:
            self.assertTrue(self.monitor.guild('Example Guild')['velho']);fetch.assert_not_called()

    def test_guild_preview_one_query_no_configuration_and_cache_metadata(self):
        before=copy.deepcopy(self.monitor.data);consult=patch('monitor_personagens._fetch').start();self.addCleanup(patch.stopall)
        result={'dados':{'guild':{'name':'Example Guild','world':'Antica','members':[{'name':'Test Knight','vocation':'Elite Knight'},{'name':'test knight'},{'name':'Other Paladin'}]}},'consulta':123,'velho':True}
        with patch('zandaobot._consultar',return_value=result) as query:
            preview=guild_preview('Example Guild',query)
        query.assert_called_once_with('guild:example guild','/guild/Example%20Guild',ttl=300)
        self.assertEqual(2,preview['total']);self.assertTrue(preview['velho']);self.assertEqual('Antica',preview['world'])
        self.assertEqual(before,self.monitor.data);consult.assert_not_called()

    def test_limite_validacao_singleflight_e_privacidade(self):
        self.assertIn('monitor-personagens.json', PRIVATE_FILES)
        with patch('monitor_personagens.MAX_TRACKED',20):
            for i in range(19):
                self.monitor.configurar('Player ' + chr(65 + i))
            with self.assertRaises(ValueError):
                self.monitor.configurar('Player Twentyone')
        with self.assertRaises(ValueError):
            self.monitor.configurar('../Test')
        with self.assertRaises(ValueError):
            self.monitor.configurar('Test Knight', up='true')
        self.monitor.configurar('test knight', up=False, death=False)
        self.assertEqual(len(self.monitor.estado()['personagens']), 20)
        with self.monitor.scan_lock:
            self.monitor.scan()
        self.assertEqual(self.calls, 0)
        self.assertNotIn('mortes', self.monitor.estado()['personagens'][0])

    def test_historia_limitada200e_arquivo_atomico(self):
        self.scan()
        for i in range(205):
            self.payload = dados(101 + i, [DEATH])
            self.scan()
        self.assertEqual(len(self.monitor.estado()['up']), 200)
        with open(self.monitor.path, encoding='utf-8') as file:
            self.assertEqual(len(json.load(file)['up']), 200)
        self.assertFalse(os.path.exists(self.monitor.path + '.tmp'))

    def world(self, level=100, players=None, at=None, name='Antica'):
        return {'world': {'name': name, 'online_players': players if players is not None else [
            {'name': 'Test Knight', 'level': level, 'vocation': 'Elite Knight'}]},
            'information': {'timestamp': datetime.fromtimestamp(at or self.now, timezone.utc).isoformat()}}

    def test_world_compartilhado_60s_e_baseline_migracao_legada(self):
        self.monitor.configurar('Other Paladin', up=True, death=False)
        with self.monitor.lock:
            for row in self.monitor.data['personagens']:
                row.update(world='Antica', level=999)
        self.world_payload = self.world(players=[{'name': 'Test Knight', 'level': 100, 'vocation': 'Knight'},
                                                {'name': 'Other Paladin', 'level': 200, 'vocation': 'Royal Paladin'}])
        self.monitor._scan_world()
        self.assertEqual(self.world_calls, ['Antica'])
        self.assertEqual(self.monitor.estado()['up'], [])
        self.now += 59
        self.monitor._scan_world()
        self.assertEqual(len(self.world_calls), 1)
        self.now += 1
        self.world_payload = self.world(players=[{'name': 'Test Knight', 'level': 101, 'vocation': 'Knight'},
                                                {'name': 'Other Paladin', 'level': 201, 'vocation': 'Royal Paladin'}])
        self.monitor._scan_world()
        self.assertEqual(len(self.world_calls), 2)
        self.assertEqual(len(self.monitor.estado()['up']), 2)
        self.assertIn('🏹 Other Paladin', self.monitor.estado()['up'][1]['texto'])

    def test_ficha_antiga_nao_regride_level_online_nem_duplica_up(self):
        self.payload = dados(212)
        self.world_payload = self.world(212)
        self.scan()
        self.world_payload = self.world(214, at=self.now + 60)
        self.scan()
        self.assertEqual(self.monitor.estado()['personagens'][0]['level'], 214)
        self.scan()
        self.assertEqual(self.monitor.estado()['personagens'][0]['level'], 214)
        self.assertEqual(len(self.monitor.estado()['up']), 1)

    def test_offline_e_timestamp_antigo_preservam_baseline(self):
        self.world_payload = self.world(100)
        self.scan()
        self.world_payload = self.world(players=[], at=self.now + 60)
        self.scan()
        self.assertEqual(self.monitor.estado()['personagens'][0]['level'], 100)
        self.assertIn('Não aparece online', self.monitor.estado()['personagens'][0]['estado_up'])
        self.world_payload = self.world(101, at=self.now - 1)
        self.scan()
        self.assertEqual(self.monitor.estado()['up'], [])
        self.assertIn('Resposta antiga', self.monitor.estado()['personagens'][0]['estado_up'])
        self.world_payload = self.world(101, at=self.now + 60)
        self.assertEqual(len(self.scan()['up']), 1)

    def test_mudanca_mundo_recria_baseline_sem_up_artificial(self):
        self.scan()
        self.payload['character']['character'].update(world='Secura', level=200)
        self.world_payload = self.world(200, name='Secura', at=self.now + 60)
        self.scan()
        self.assertEqual(self.monitor.estado()['up'], [])
        self.assertEqual(self.monitor.estado()['personagens'][0]['world'], 'Secura')

    def test_world_lento_removido_nao_ressuscita(self):
        self.scan()
        entered, release = threading.Event(), threading.Event()
        def fetch_world(world):
            entered.set(); release.wait(2)
            return self.world(110)
        self.monitor.fetch_world = fetch_world
        self.now += 60
        thread = threading.Thread(target=self.monitor._scan_world)
        thread.start(); self.assertTrue(entered.wait(1))
        self.monitor.configurar('Test Knight', remover=True)
        release.set(); thread.join(2)
        self.assertEqual(self.monitor.estado()['personagens'], [])
        self.assertEqual(self.monitor.estado()['up'], [])

    def test_ficha_bloqueada_nao_impede_up_pelo_mundo(self):
        self.scan()
        entered, release = threading.Event(), threading.Event()
        def fetch(nome):
            entered.set(); release.wait(2)
            return dados(100)
        self.monitor.fetch = fetch
        self.now += 60
        thread = threading.Thread(target=self.monitor._scan_char)
        thread.start(); self.assertTrue(entered.wait(1))
        self.world_payload = self.world(101)
        try:
            self.monitor._scan_world()
            self.assertEqual(len(self.monitor.estado()['up']), 1)
        finally:
            release.set(); thread.join(2)

    def test_backoff_global_respeita_retry_after(self):
        self.scan()
        calls = []
        def limited(world):
            calls.append(world)
            raise HTTPError('https://api.tibiadata.com/v4/world/Antica', 429, 'limit', {'Retry-After': '600'}, None)
        self.monitor.fetch_world = limited
        self.now += 60
        self.monitor._scan_world()
        self.assertIn('HTTP 429', self.monitor.estado()['aviso_rede'])
        chars = self.calls
        self.now += 599
        self.monitor.scan()
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.calls, chars)
        self.now += 1
        self.monitor._scan_world()
        self.assertEqual(len(calls), 2)

    def test_inicio_de_requests_espacado_sem_lock_durante_fetch(self):
        starts = []
        self.monitor.wait = lambda seconds: setattr(self, 'now', self.now + seconds) or False
        def fetch(arg):
            starts.append(self.now)
            return {}
        self.monitor._request(fetch, 'one')
        self.monitor._request(fetch, 'two')
        self.assertGreaterEqual(starts[1] - starts[0], 1)

    def test_backoffs_concorrentes_nunca_encurtam_pausa_global(self):
        def fail(seconds):
            error = HTTPError('https://api.tibiadata.com/v4/world/Antica', 503, 'unavailable', {'Retry-After': str(seconds)}, None)
            return self.monitor._failure(error)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(fail, [300, 600, 900, 300, 600, 300] * 10))
        self.assertEqual(self.monitor.network_until, self.now + 900)
        fail(300)
        self.assertEqual(self.monitor.network_until, self.now + 900)

    def test_world_invalido_preserva_referencia(self):
        self.scan()
        for payload in ({'world': {'name': 'Antica'}}, self.world(players=[{'name': 'Test Knight', 'level': True}]),
                        {**self.world(100), 'information': {'timestamp': 'invalid'}}):
            self.world_payload = payload
            self.scan()
            self.assertEqual(self.monitor.estado()['personagens'][0]['level'], 100)
            self.assertEqual(self.monitor.estado()['up'], [])


if __name__ == '__main__':
    unittest.main()
