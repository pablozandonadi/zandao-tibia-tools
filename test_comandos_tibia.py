import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import chat
import comandos_tibia as c
import tibia_info
import zandaobot


def ks(*pares):
    return {'killstatistics': {'world': 'Antica', 'entries': [
        {'race': n, 'last_day_killed': k, 'last_week_killed': k * 7, 'last_day_players_killed': 0, 'last_week_players_killed': 0} for n, k in pares]}}


def fonte(mapa):
    def get(url, timeout=12):
        for sufixo, dados in mapa.items():
            if url.endswith(sufixo):
                if isinstance(dados, Exception):
                    raise dados
                return dados
        raise OSError('sem rota ' + url)
    return get


class ComandosTibia(unittest.TestCase):
    def setUp(self):
        zandaobot._cache.clear()

    def run_(self, texto, mundo='Antica', mapa=None, hoje=date(2026, 10, 17)):
        with patch.object(tibia_info, '_get_json', side_effect=fonte(mapa or {})):
            return c.responder(texto, mundo, hoje)

    def test_texto_que_nao_e_comando_devolve_none(self):
        self.assertIsNone(c.responder('quanto falta no timer do drume', 'Antica'))
        self.assertIsNone(c.responder('', 'Antica'))
        self.assertIsNone(c.responder('killer instinct', 'Antica'))

    def test_kill_top10_ordenado_e_ignora_zero(self):
        pares = [(f'Mob{i}', i) for i in range(1, 13)] + [('Parado', 0), ('(elemental forces)', 99999)]
        r = self.run_('kill', mapa={'/killstatistics/Antica': ks(*pares)})
        linhas = [l for l in r.splitlines() if l[:1].isdigit()]
        self.assertEqual(len(linhas), 10)
        self.assertIn('Mob12', linhas[0])
        self.assertNotIn('Parado', r)
        self.assertNotIn('elemental', r)
        self.assertIn('Antica', r)

    def test_kill_aceita_mundo_no_comando_e_pede_quando_falta(self):
        r = self.run_('!kill Rasteibra', mundo='', mapa={'/killstatistics/Rasteibra': ks(('Hydra', 5))})
        self.assertIn('Hydra', r)
        self.assertIn('Informe o mundo', self.run_('kill', mundo=''))

    def test_kill_sem_rede_avisa_sem_inventar(self):
        r = self.run_('kill')
        self.assertIn('Não consegui', r)

    def test_online_mundo(self):
        r = self.run_('online Antica', mapa={'/world/Antica': {'world': {'name': 'Antica', 'status': 'online', 'players_online': 315}}})
        self.assertIn('315', r)
        self.assertIn('Antica', r)

    def test_online_guild_quando_nao_e_mundo(self):
        membros = [{'name': 'Zaz', 'level': 512, 'vocation': 'Elite Knight', 'status': 'online'},
                   {'name': 'Off', 'level': 300, 'vocation': 'Druid', 'status': 'offline'}]
        r = self.run_('online Quixada', mapa={'/guild/Quixada': {'guild': {'name': 'Quixada', 'members': membros}}})
        self.assertIn('Zaz', r)
        self.assertNotIn('Off', r)
        self.assertIn('1 de 2', r)

    def test_char_mostra_ficha_e_mortes(self):
        dados = {'character': {'character': {'name': 'Zazamyon', 'level': 512, 'vocation': 'Elite Knight', 'world': 'Jadebra',
                                             'guild': {'name': 'Quixada'}, 'last_login': '2026-09-15T22:41:00Z'},
                               'deaths': [{'time': '2026-09-12T10:00:00Z', 'level': 509, 'reason': 'Died at Level 509 by a grim reaper.'}]}}
        r = self.run_('char Zazamyon', mapa={'/character/Zazamyon': dados})
        for esperado in ('Zazamyon', '512', 'Elite Knight', 'Jadebra', 'Quixada', 'grim reaper'):
            self.assertIn(esperado, r)

    def test_char_inexistente(self):
        self.assertIn('Não consegui', self.run_('char Fulano'))

    def test_death_exige_personagem(self):
        self.assertIn('death <personagem>', self.run_('death'))

    def test_guild_conta_quem_entrou_em_7_dias(self):
        membros = [{'name': 'Novo', 'level': 355, 'vocation': 'Royal Paladin', 'status': 'online', 'joined': '2026-10-14'},
                   {'name': 'Velho', 'level': 400, 'vocation': 'Elite Knight', 'status': 'offline', 'joined': '2020-01-01'}]
        dados = {'guild': {'name': 'Quixada', 'world': 'Jadebra', 'founded': '2019-03-14', 'members': membros}}
        r = self.run_('guild Quixada', mapa={'/guild/Quixada': dados})
        self.assertIn('Novo', r)
        self.assertNotIn('Velho', r.split('Entraram')[-1])
        self.assertIn('Jadebra', r)

    def test_boss_junta_boosted_e_mortos_ontem(self):
        boost = {'boss': {'nome': 'Eradicator'}, 'criatura': {'nome': 'Hydra'}, 'velho': False}
        kills = {'bosses': [{'nome': 'Tyrn', 'last_day_killed': 2}, {'nome': 'Zomba', 'last_day_killed': 0}], 'velho': False, 'consulta': 1}
        with patch.object(tibia_info, 'boostados', return_value=boost), patch.object(zandaobot, 'killstatistics', return_value=kills):
            r = c.responder('boss', 'Antica')
        self.assertIn('Eradicator', r)
        self.assertIn('Tyrn', r)
        self.assertNotIn('Zomba', r)

    def test_bomdia_usa_painel_e_relata_erro(self):
        with patch.object(zandaobot, 'buscar', return_value={'erro': 'Mundo não encontrado.'}):
            self.assertEqual(c.responder('bomdia Xyz', 'Antica'), 'Mundo não encontrado.')
        with patch.object(zandaobot, 'buscar', return_value={'mundo': 'Antica'}) as b, \
                patch.object(c.zandaobot_report, 'gerar', return_value='☀️ Bom dia') as g:
            self.assertEqual(c.responder('bom dia', 'Antica'), '☀️ Bom dia')
        b.assert_called_once_with('Antica')
        g.assert_called_once()

    def test_chat_responde_localmente_sem_ia(self):
        store = SimpleNamespace(context=lambda: {'character_id': 'T', 'world_id': 'Antica', 'level': 1}, clock=lambda: None)
        with patch.object(tibia_info, '_get_json', side_effect=fonte({'/killstatistics/Antica': ks(('Hydra', 5))})):
            r = chat.Chat(store, '.').responder('kill', permitir_ia=False)
        self.assertEqual(r['origem'], 'local')
        self.assertIn('Hydra', r['resposta'])


if __name__ == '__main__':
    unittest.main()
