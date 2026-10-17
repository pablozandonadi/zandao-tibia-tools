import unittest
from unittest.mock import patch
from datetime import datetime, timezone
import zandaobot
import tibia_info


class TestZandaoBot(unittest.TestCase):
    def setUp(self):
        zandaobot._cache.clear()
        unavailable = {'estado': 'indisponivel', 'motivo': 'Falha na fonte'}
        for name, value in [('mini_changes', unavailable), ('dream_court', unavailable), ('calendar', {'estado': 'indisponivel', 'eventos': []})]:
            patcher = patch.object(zandaobot.sources, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_cache_separa_mundos_e_preserva_data_na_falha(self):
        with patch.object(tibia_info, '_get_json', side_effect=[{'world': {'name': 'Antica'}}, {'world': {'name': 'Rasteibra'}}, OSError()]):
            a = zandaobot._consultar('Antica', '/world/Antica')
            b = zandaobot._consultar('Rasteibra', '/world/Rasteibra')
            velho = zandaobot._consultar('Antica', '/world/Antica', True)
        self.assertEqual(b['dados']['world']['name'], 'Rasteibra')
        self.assertEqual(velho['dados']['world']['name'], 'Antica')
        self.assertEqual(velho['consulta'], a['consulta'])
        self.assertTrue(velho['velho'])

    def test_falha_sem_cache_nao_afirma_ausencia(self):
        with patch.object(tibia_info, '_get_json', side_effect=OSError()), patch.object(tibia_info, 'boostados', return_value={'velho': True}):
            r = zandaobot.buscar('Antica')
        self.assertEqual(r['yasir']['estado'], 'indisponivel')
        self.assertEqual(r['dream_court']['estado'], 'indisponivel')
        self.assertTrue(r['servidor_velho'])
        self.assertFalse(r['anuncios'])

    def test_nao_confunde_conquistas_com_eventos_ativos(self):
        def get(url):
            if '/world/' in url:
                return {'world': {'name': 'Antica', 'world_quest_titles': ['Bewitched']}}
            return {'news': [{'id': 12, 'news': 'Orcsoberfest', 'date': '2026-10-07', 'category': 'community'}, {'news': 'Patch', 'category': 'development'}]}
        with patch.object(tibia_info, '_get_json', side_effect=get), patch.object(tibia_info, 'boostados', return_value={}):
            r = zandaobot.buscar('Antica')
        self.assertNotIn('world_quest_titles', r['servidor'])
        self.assertEqual(len(r['anuncios']), 1)
        self.assertEqual(r['anuncios'][0]['titulo'], 'Orcsoberfest')

    def test_valida_mundo_antes_da_rede(self):
        with patch.object(tibia_info, '_get_json') as get:
            self.assertIn('erro', zandaobot.buscar('../Antica'))
            get.assert_not_called()

    def test_mundos_ordenados(self):
        with patch.object(tibia_info, '_get_json', return_value={'worlds': {'regular_worlds': [{'name': 'Rasteibra'}, {'name': 'Antica'}]}}):
            self.assertEqual(zandaobot.mundos()['mundos'], ['Antica', 'Rasteibra'])

    def test_compensacao_exclusiva_datas_completas_e_limites(self):
        text='As compensation for the recent reset of Ferobra, a double XP/skill weekend will take place on the game world between the server saves of October 16 and October 19, 2026.'
        notice={'texto':text, 'id':9017,'completo':True,'velho':False}
        from datetime import date
        result=zandaobot.eventos_compensacao([notice],'Ferobra',date(2026,10,12))
        self.assertEqual(result[0]['inicio'],'2026-10-16')
        self.assertEqual(result[0]['fim'],'2026-10-19')
        self.assertEqual(result[0]['escopo'],'Ferobra')
        self.assertFalse(zandaobot.eventos_compensacao([notice],'Antica',date(2026,10,12)))
        self.assertFalse(zandaobot.eventos_compensacao([notice],'Ferobra',date(2026,10,19)))
        self.assertFalse(zandaobot.eventos_compensacao([{**notice,'velho':True}],'Ferobra',date(2026,10,12)))
        self.assertFalse(zandaobot.eventos_compensacao([{**notice,'completo':False}],'Ferobra',date(2026,10,12)))

    def test_rashid_vira_no_server_save(self):
        antes = datetime(2026, 10, 12, 7, 59, tzinfo=timezone.utc)
        depois = datetime(2026, 10, 12, 8, 0, tzinfo=timezone.utc)
        self.assertEqual(tibia_info.rashid(antes), 'Carlin')
        self.assertEqual(tibia_info.rashid(depois), 'Svargrond')


class TestKillStatistics(unittest.TestCase):
    def setUp(self):
        zandaobot._cache.clear()

    def fixture(self, world='Xybra'):
        return {'killstatistics': {'world': world, 'entries': [
            {'race': name, 'last_day_killed': i, 'last_week_killed': i + 10,
             'last_day_players_killed': 99} for i, name in enumerate(zandaobot.sources.BOSSES)]},
            'information': {'timestamp': '2026-10-15T14:03:02Z', 'status': {'http_code': 200}}}

    def test_counts_and_cached_source_time(self):
        with patch.object(tibia_info, '_get_json', return_value=self.fixture()) as get:
            first = zandaobot.killstatistics('Xybra')
            second = zandaobot.killstatistics('xybra')
        get.assert_called_once()
        self.assertEqual(first['bosses'][0]['last_day_killed'], 0)
        self.assertEqual(first['bosses'][1]['last_day_killed'], 1)
        self.assertEqual(first['bosses'][1]['last_week_killed'], 11)
        self.assertEqual(first['processamento'], '2026-10-15T14:03:02+00:00')
        self.assertEqual(second['consulta'], first['consulta'])
        self.assertEqual(second['processamento'], first['processamento'])

    def test_missing_and_invalid_counts_are_not_zero(self):
        data = self.fixture()
        del data['killstatistics']['entries'][0]['last_day_killed']
        data['killstatistics']['entries'][1]['last_day_killed'] = True
        data['killstatistics']['entries'][2]['last_day_killed'] = -1
        data['killstatistics']['entries'][3]['last_week_killed'] = '9'
        data['killstatistics']['entries'].pop()
        with patch.object(tibia_info, '_get_json', return_value=data):
            result = zandaobot.killstatistics('Xybra')
        self.assertEqual(len(result['bosses']), 5)
        self.assertIsNone(result['bosses'][0]['last_day_killed'])
        self.assertIsNone(result['bosses'][1]['last_day_killed'])
        self.assertIsNone(result['bosses'][2]['last_day_killed'])
        self.assertIsNone(result['bosses'][3]['last_week_killed'])
        self.assertIsNone(result['bosses'][4]['last_day_killed'])

    def test_invalid_responses_and_missing_world(self):
        invalid = [None, {}, {'killstatistics': {}}, self.fixture('Antica')]
        status = self.fixture(); status['information']['status']['http_code'] = 404
        empty = self.fixture(); empty['killstatistics']['entries'] = []
        malformed = self.fixture(); malformed['killstatistics']['entries'] = {}
        for data in invalid + [status, empty, malformed]:
            with self.subTest(data=data), patch.object(tibia_info, '_get_json', return_value=data):
                self.assertEqual(zandaobot.killstatistics('Xybra', True)['estado'], 'indisponivel')
        with patch.object(tibia_info, '_get_json') as get:
            self.assertEqual(zandaobot.killstatistics('')['estado'], 'selecionar_mundo')
            self.assertEqual(zandaobot.killstatistics('../Xybra')['estado'], 'indisponivel')
            get.assert_not_called()

    def test_failure_preserves_valid_world_cache_and_does_not_poison_it(self):
        with patch.object(tibia_info, '_get_json', side_effect=[self.fixture(), self.fixture('Antica'), {}, OSError()]):
            first = zandaobot.killstatistics('Xybra')
            other = zandaobot.killstatistics('Antica')
            stale = zandaobot.killstatistics('Xybra', True)
            again = zandaobot.killstatistics('Xybra', True)
        self.assertEqual(other['mundo'], 'Antica')
        self.assertEqual(stale['estado'], 'desatualizado')
        self.assertTrue(stale['velho'])
        self.assertEqual(stale['consulta'], first['consulta'])
        self.assertEqual(again['bosses'], first['bosses'])

    def test_multiple_boss_deaths_do_not_change_dream_prediction(self):
        dream = {'nome': 'Maxxenius', 'estado': 'previsto'}
        def get(url):
            if '/killstatistics/' in url:
                return self.fixture()
            if '/world/' in url:
                return {'world': {'name': 'Xybra'}}
            return {'news': []}
        with patch.object(tibia_info, '_get_json', side_effect=get), patch.object(tibia_info, 'boostados', return_value={}), patch.object(zandaobot.sources, 'dream_court', return_value=dream), patch.object(zandaobot.sources, 'mini_changes', return_value={}), patch.object(zandaobot.sources, 'calendar', return_value={'eventos': []}):
            result = zandaobot.buscar('Xybra')
        self.assertEqual(result['dream_court'], dream)
        self.assertEqual(result['killstatistics']['estado'], 'disponivel')
        import zandaobot_report
        message = zandaobot_report.gerar(result)
        self.assertIn('Maxxenius · rotação prevista', message)
        self.assertNotIn('Consulta do aplicativo', message)
        self.assertNotIn('Processamento TibiaData', message)
        result['killstatistics']['estado'] = 'desatualizado'
        self.assertNotIn('mortes (Last Day)', zandaobot_report.gerar(result))


if __name__ == '__main__':
    unittest.main()
