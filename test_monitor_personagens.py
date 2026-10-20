import copy
import json
import os
import tempfile
import threading
import unittest

from app_paths import PRIVATE_FILES
from monitor_personagens import Monitor


def dados(level=100, mortes=None):
    return {'character': {'character': {'name': 'Test Knight', 'level': level, 'vocation': 'Elite Knight'}, 'deaths': mortes or []}}


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
        self.monitor = Monitor(self.temp.name, fetch=fetch, clock=lambda: self.now)
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
        self.monitor = Monitor(self.temp.name, fetch=self.fetch, clock=lambda: self.now)
        self.assertEqual(len(self.scan()['death']), 1)
        self.assertEqual(self.monitor.estado()['death'][0]['at'], '2026-10-20T11:00:00+00:00')

    def test_falha_ou_mortes_malformadas_preserva_referencia(self):
        self.scan()
        for malformed in (None, {}, [{'level': 100}], [{'time': DEATH['time'], 'level': 100, 'killers': 'x'}]):
            self.payload = dados(104)
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

    def test_limite_validacao_singleflight_e_privacidade(self):
        self.assertIn('monitor-personagens.json', PRIVATE_FILES)
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


if __name__ == '__main__':
    unittest.main()
