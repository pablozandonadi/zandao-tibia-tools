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

    def test_news_separa_eventos_ordena_limita_e_inclui_tickers_gerais(self):
        image = 'https://static.tibia.com/images/news/news_fixes_243x200.png'
        main = {'id': 9024, 'date': '2026-10-20', 'category': 'development', 'type': 'news',
                'news': 'Balancing, Fixes and Changes'}
        entries = [main, dict(main), {**main, 'id': 9023, 'category': 'technical'},
                   {**main, 'id': 9022, 'category': 'unknown-safe'},
                   {**main, 'id': 9021, 'category': 'community'},
                   {**main, 'id': 9020, 'type': 'ticker'}, None,
                   {**main, 'id': True}, {**main, 'id': -1}]
        entries += [{**main, 'id': i, 'date': '2026-10-19'} for i in range(9010, 9020)]
        tickers = [{**main, 'id': i, 'type': 'ticker', 'news': 'Maintenance in Antica ' + 'x' * 500}
                   for i in range(9030, 9042)]
        tickers += [{**main, 'type': 'ticker'}, {**main, 'id': 9050}]
        def get(url):
            if url.endswith('/news/latest'):
                return {'news': entries}
            if url.endswith('/news/newsticker'):
                return {'news': tickers}
            if '/news/id/' in url:
                return {'news': {'content_html': f'<img src="{image}">'}}
            if '/world/' in url:
                return {'world': {'name': 'Xybra'}}
            return {'news': []}
        with patch.object(tibia_info, '_get_json', side_effect=get) as fetch, patch.object(tibia_info, 'boostados', return_value={}):
            result = zandaobot.buscar('Xybra')
            cached = zandaobot.buscar('Xybra')
        self.assertEqual([x['id'] for x in result['noticias']], [9024, 9023, 9022, 9019, 9018, 9017, 9016, 9015])
        self.assertEqual([x['id'] for x in result['anuncios']], [9021])
        self.assertEqual(result['noticias'][0]['imagem'], image)
        self.assertEqual(len(result['news_ticker']), 10)
        self.assertEqual(result['news_ticker'][0]['id'], 9041)
        self.assertEqual(len(result['news_ticker'][0]['texto']), 400)
        self.assertEqual(result['avisos_mundo'], [])
        self.assertEqual(cached['noticias_consulta'], result['noticias_consulta'])
        self.assertEqual(sum(call.args[0].endswith('/news/id/9024') for call in fetch.call_args_list), 1)

    def test_news_preserva_cache_e_indica_falha_por_fonte(self):
        entries = [{'id': 9024, 'date': '2026-10-20', 'category': 'development', 'news': 'Patch'}]
        def get(url):
            return {'news': entries} if url.endswith('/news/latest') else {'news': []}
        with patch.object(tibia_info, '_get_json', side_effect=get), patch.object(tibia_info, 'boostados', return_value={}):
            first = zandaobot.buscar()
        with patch.object(tibia_info, '_get_json', side_effect=OSError()), patch.object(tibia_info, 'boostados', return_value={}):
            stale = zandaobot.buscar(forcar=True)
        self.assertEqual(stale['noticias'], first['noticias'])
        self.assertEqual(stale['noticias_consulta'], first['noticias_consulta'])
        self.assertTrue(stale['noticias_velhas'])
        self.assertTrue(stale['news_ticker_velho'])
        zandaobot._cache.clear()
        with patch.object(tibia_info, '_get_json', side_effect=OSError()), patch.object(tibia_info, 'boostados', return_value={}):
            empty = zandaobot.buscar()
        self.assertEqual(empty['noticias'], [])
        self.assertEqual(empty['news_ticker'], [])
        self.assertIsNone(empty['noticias_consulta'])

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

    def test_anuncios_trazem_imagem_so_do_dominio_oficial_e_so_da_comunidade(self):
        oficial = '<p><img style="x" src="https://static.tibia.com/images/news/orcsoberfest_transparent_350.png" width="350"/></p>'
        externa = '<img src="https://evil.example/news/x.png"><img src="https://static.tibia.com/images/other/y.png">'
        itens = [{'id': 1, 'date': '2026-10-07', 'news': 'Orcsoberfest ', 'category': 'community'},
                 {'id': 2, 'date': '2026-10-06', 'news': 'Sem imagem', 'category': 'community'},
                 {'id': 3, 'date': '2026-10-05', 'news': 'Patch', 'category': 'development'}]
        def get(url):
            if url.endswith('/news/latest'):
                return {'news': itens}
            if url.endswith('/news/id/1'):
                return {'news': {'content_html': oficial}}
            if url.endswith('/news/id/2'):
                return {'news': {'content_html': externa}}
            if '/world/' in url:
                return {'world': {'name': 'Xybra'}}
            return {'news': []}
        with patch.object(tibia_info, '_get_json', side_effect=get), patch.object(tibia_info, 'boostados', return_value={}):
            result = zandaobot.buscar('Xybra')
        titulos = [(a['titulo'], a['categoria'], a['imagem']) for a in result['anuncios']]
        self.assertEqual(titulos, [('Orcsoberfest', 'community', 'https://static.tibia.com/images/news/orcsoberfest_transparent_350.png'),
                                   ('Sem imagem', 'community', None)])


if __name__ == '__main__':
    unittest.main()
