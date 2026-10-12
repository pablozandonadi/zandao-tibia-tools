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


if __name__ == '__main__':
    unittest.main()
