"""Painel das mensagens automáticas na janela principal: junta comandos, alerta e bom dia por grupo e respeita a liberação do menu."""
import os
import tempfile
import unittest
from unittest import mock

import mensagem_automatica_access as acesso
import mensagem_automatica_painel as painel
import web_api

D1, D2 = 'd' * 32, 'e' * 32
BOTGROUPS = [{'id': 'b1', 'state': 'active', 'destination': D1, 'destinationLabel': 'Rocks D\'s', 'world': 'Rasteibra', 'cooldown': 120, 'disabled': ['duelo', 'pt'], 'paused': False,
              'groupConfig': True, 'changedByGroup': 1760000000, 'lastUse': 1760000500},
             {'id': 'b2', 'state': 'active', 'destination': D2, 'destinationLabel': 'Zandao group', 'world': 'Antica', 'cooldown': 30, 'paused': True, 'groupConfig': False},
             {'id': 'b3', 'state': 'revoked', 'destination': 'z' * 32, 'destinationLabel': 'Apagado', 'world': 'Antica', 'cooldown': 30}]
WATCHES = [{'id': 'w1', 'state': 'active', 'destination': D1, 'destinationLabel': 'Rocks D\'s', 'guild': 'Piratas do Rocks', 'milestone': 1, 'deaths': True, 'ups': True, 'hourlyCap': 0, 'perMinute': 3,
            'source': 'group', 'lastSent': 1760000900}]
SUBSCRIPTIONS = [{'id': 's1', 'state': 'active', 'destination': D1, 'destinationLabel': 'Rocks D\'s', 'config': {'sendAt': '06:00', 'timezone': 'America/Sao_Paulo', 'mundo': 'Rasteibra'}, 'source': 'group'},
                 {'id': 's2', 'state': 'inactive', 'destination': 'c' * 32, 'destinationLabel': '', 'config': {'sendAt': '07:30', 'timezone': 'America/Cuiaba', 'mundo': 'Antica'}}]
RUNS = [{'subscription': 's1', 'reference': '2026-10-22', 'state': 'accepted'}, {'subscription': 's1', 'reference': '2026-10-23', 'state': 'accepted'},
        {'subscription': 's1', 'reference': '2026-10-24', 'state': 'expired'}, {'subscription': 's2', 'reference': '2026-10-23', 'state': 'failed'}]


class MontarTests(unittest.TestCase):
    def test_uma_linha_por_grupo_com_comandos_alerta_e_bom_dia(self):
        d = painel.montar({'state': 'connected', 'simulated': False}, SUBSCRIPTIONS, WATCHES, BOTGROUPS, RUNS)
        self.assertEqual([g['grupo'] for g in d['grupos']], ['Rocks D\'s', 'Zandao group', 'Grupo sem nome'], 'em ordem alfabética, sem nome por último')
        por = {g['destino']: g for g in d['grupos']}
        rocks = por[D1]
        self.assertEqual((rocks['comandos']['mundo'], rocks['comandos']['intervalo'], rocks['comandos']['desligados'], rocks['comandos']['ultimoUso'], rocks['comandos']['ajustadoPeloGrupo']), ('Rasteibra', 120, ['duelo', 'pt'], 1760000500, True))
        self.assertEqual((rocks['alerta']['guild'], rocks['alerta']['origem'], rocks['alerta']['ultimoEnvio'], rocks['alerta']['limiteHora']), ('Piratas do Rocks', 'grupo', 1760000900, 0))
        self.assertEqual((rocks['bomdia']['envio'], rocks['bomdia']['origem'], rocks['bomdia']['ultimoEnvio']), ('06:00', 'grupo', '2026-10-23'), 'o último envio é o último aceito, não a execução vencida')
        zandao = por[D2]
        self.assertEqual((zandao['comandos']['pausado'], zandao['comandos']['configPeloGrupo'], zandao['alerta'], zandao['bomdia']), (True, False, None, None))
        sem_nome = por['c' * 32]
        self.assertEqual((sem_nome['grupo'], sem_nome['bomdia']['estado'], sem_nome['bomdia']['ultimoEnvio'], sem_nome['bomdia']['origem']), ('Grupo sem nome', 'inactive', None, 'app'))
        self.assertNotIn('z' * 32, por, 'itens revogados não aparecem')

    def test_resumo_conta_bots_ativos_e_limites(self):
        d = painel.montar({'state': 'connected', 'simulated': False}, SUBSCRIPTIONS, WATCHES, BOTGROUPS, RUNS)
        # ativos: comandos de Rocks, alerta de Rocks, bom dia de Rocks (o grupo pausado e o bom dia inativo não contam)
        self.assertEqual(d['resumo'], {'grupos': 3, 'botsAtivos': 3, 'comandos': [2, 3], 'alertas': [1, 3], 'rotinas': [2, 5]})
        self.assertEqual(d['conexao'], {'estado': 'connected', 'simulado': False})

    def test_sem_conexao_ou_dados_estranhos_nao_quebram(self):
        d = painel.montar(None, None, 'lixo', [None, 5, {'state': 'active'}], [{'state': 'accepted'}])
        self.assertEqual((d['conexao'], d['resumo']['grupos']), ({'estado': 'desconectado', 'simulado': False}, 1))
        self.assertEqual(d['grupos'][0]['grupo'], 'Grupo sem nome')
        sujo = painel.montar({'state': 'connected'}, [], [], [{'id': 'x', 'state': 'active', 'destination': 'q', 'destinationLabel': 'x' * 500, 'world': {'a': 1}, 'cooldown': True, 'disabled': 'sim'}], [])
        self.assertEqual(len(sujo['grupos'][0]['grupo']), 80)
        self.assertEqual((sujo['grupos'][0]['comandos']['mundo'], sujo['grupos'][0]['comandos']['intervalo'], sujo['grupos'][0]['comandos']['desligados']), ('', None, []))


class MetodoTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(web_api, 'BASE_DIR', tmp.name); patcher.start(); self.addCleanup(patcher.stop)
        self.dir = tmp.name; self.api = web_api.API()
        self.rotas = {'/v1/connections': [{'id': 'a' * 32, 'state': 'revoked'}, {'id': 'b' * 32, 'state': 'active'}], '/v1/connections/' + 'b' * 32: {'state': 'connected', 'simulated': False},
                      '/v1/subscriptions': SUBSCRIPTIONS, '/v1/watches': WATCHES, '/v1/botgroups': BOTGROUPS, '/v1/runs': RUNS}

    def liberar(self, texto='{"mensagens_automaticas": true}'):
        with open(os.path.join(self.dir, 'recursos-dono.json'), 'w', encoding='utf-8') as f: f.write(texto)

    def test_exige_a_liberacao_e_nao_chama_o_servidor_sem_ela(self):
        with mock.patch('mensagem_automatica_access.owner_get') as get:
            self.assertEqual(self.api.mensagens_painel(), {'erro': 'Este recurso ainda não está disponível.'}); get.assert_not_called()

    def test_monta_o_painel_so_com_leituras_das_rotas_permitidas(self):
        self.liberar()
        with mock.patch('mensagem_automatica_access.owner_get', side_effect=lambda p: self.rotas[p]) as get:
            d = self.api.mensagens_painel()
        self.assertEqual(d['resumo']['grupos'], 3); self.assertEqual(d['conexao']['estado'], 'connected')
        self.assertEqual([c.args[0] for c in get.call_args_list], ['/v1/connections', '/v1/connections/' + 'b' * 32, '/v1/subscriptions', '/v1/watches', '/v1/botgroups', '/v1/runs'])
        for c in get.call_args_list: self.assertTrue(acesso.ALLOWED['GET'].fullmatch(c.args[0]), c.args[0])

    def test_sem_conexao_ativa_mostra_o_painel_desconectado(self):
        self.liberar(); self.rotas['/v1/connections'] = [{'id': 'a' * 32, 'state': 'revoked'}]
        with mock.patch('mensagem_automatica_access.owner_get', side_effect=lambda p: self.rotas[p]) as get:
            d = self.api.mensagens_painel()
        self.assertEqual(d['conexao']['estado'], 'desconectado'); self.assertNotIn('/v1/connections/' + 'a' * 32, [c.args[0] for c in get.call_args_list])

    def test_id_de_conexao_estranho_nunca_vira_caminho(self):
        self.liberar(); self.rotas['/v1/connections'] = [{'id': '../admin/claims', 'state': 'active'}]
        with mock.patch('mensagem_automatica_access.owner_get', side_effect=lambda p: self.rotas[p]) as get:
            d = self.api.mensagens_painel()
        self.assertEqual(d['conexao']['estado'], 'desconectado'); self.assertTrue(all('claims' not in c.args[0] for c in get.call_args_list))

    def test_erros_do_servidor_viram_mensagem(self):
        self.liberar()
        with mock.patch('mensagem_automatica_access.owner_get', side_effect=acesso.AccessError('Serviço indisponível.')):
            self.assertEqual(self.api.mensagens_painel(), {'erro': 'Serviço indisponível.'})
        with mock.patch('mensagem_automatica_access.owner_get', side_effect=RuntimeError('rede')):
            self.assertIn('erro', self.api.mensagens_painel())


if __name__ == '__main__':
    unittest.main()
