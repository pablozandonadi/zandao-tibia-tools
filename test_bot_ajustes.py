"""Ajustes do administrador nos comandos do assistente: cache em segundo plano, validação do que vem do servidor e efeito no `responder`."""
import threading
import time
import unittest
from unittest import mock

import bot_ajustes
import comandos_tibia
import mensagem_automatica_access as acesso


def esperar(condicao, limite=3):
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return False


class BotAjustesTests(unittest.TestCase):
    def tearDown(self):
        bot_ajustes.iniciar(None)

    def test_sem_buscador_tudo_segue_o_padrao(self):
        bot_ajustes.iniciar(None)
        self.assertEqual(bot_ajustes.ajuste('exp'), {})

    def test_busca_em_segundo_plano_e_nunca_trava_o_comando(self):
        soltar = threading.Event()
        def buscar():
            soltar.wait(3)
            return {'exp': {'enabled': False, 'text': ''}}
        bot_ajustes.iniciar(buscar)
        self.assertEqual(bot_ajustes.ajuste('exp'), {}, 'a primeira consulta devolve o padrão sem esperar o servidor')
        soltar.set()
        self.assertTrue(esperar(lambda: bot_ajustes.ajuste('exp') == {'enabled': False, 'text': ''}))

    def test_so_aceita_o_formato_esperado(self):
        sujo = {'exp': {'enabled': 'sim', 'text': ''}, 'naoexiste': {'enabled': False, 'text': ''}, 'boss': {'enabled': True, 'text': 5},
                'kill': {'enabled': True, 'text': 'x' * 3000}, 'guild': 'lixo', 'char': {'enabled': False}}
        self.assertEqual(bot_ajustes._limpar(sujo), {'kill': {'enabled': True, 'text': 'x' * 1500}, 'char': {'enabled': False, 'text': ''}})
        self.assertEqual(bot_ajustes._limpar([1]), {})

    def test_servidor_fora_do_ar_mantem_o_ultimo_conhecido(self):
        respostas = [{'exp': {'enabled': False, 'text': ''}}, OSError('sem rede')]
        def buscar():
            r = respostas.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        bot_ajustes.iniciar(buscar)
        bot_ajustes.ajuste('exp')
        self.assertTrue(esperar(lambda: bot_ajustes.ajuste('exp').get('enabled') is False))
        with mock.patch.object(bot_ajustes, 'TTL', -1):  # força nova busca, que falha
            bot_ajustes.ajuste('exp')
            self.assertTrue(esperar(lambda: not respostas))
            self.assertTrue(esperar(lambda: bot_ajustes._ocupado is False))
        self.assertEqual(bot_ajustes.ajuste('exp'), {'enabled': False, 'text': ''})

    def test_responder_desligado_texto_fixo_e_resposta_embutida(self):
        automatica = mock.Mock(return_value='AUTO')
        with mock.patch.dict(comandos_tibia.HANDLERS, {'exp': automatica}):
            with mock.patch.object(bot_ajustes, 'ajuste', return_value={'enabled': False, 'text': ''}):
                self.assertIsNone(comandos_tibia.responder('exp', 'Antica')); automatica.assert_not_called()
            with mock.patch.object(bot_ajustes, 'ajuste', return_value={'enabled': True, 'text': 'Só no site.'}):
                self.assertEqual(comandos_tibia.responder('exp', 'Antica'), 'Só no site.'); automatica.assert_not_called()
            with mock.patch.object(bot_ajustes, 'ajuste', return_value={'enabled': True, 'text': 'Oi\n{resposta}\nFim'}):
                self.assertEqual(comandos_tibia.responder('exp', 'Antica'), 'Oi\nAUTO\nFim')
            with mock.patch.object(bot_ajustes, 'ajuste', return_value={}):
                self.assertEqual(comandos_tibia.responder('exp', 'Antica'), 'AUTO')
            with mock.patch.object(bot_ajustes, 'ajuste', return_value={'enabled': True, 'text': ''}):
                self.assertEqual(comandos_tibia.responder('exp', 'Antica'), 'AUTO')

    def test_proxy_local_aceita_so_as_rotas_exatas_dos_comandos(self):
        A = acesso.ALLOWED
        for metodo, caminho in (('GET', '/v1/admin/botcmds'), ('PUT', '/v1/admin/botcmds/whatsapp/duelo'), ('DELETE', '/v1/admin/botcmds/assistente/exp')):
            self.assertTrue(A[metodo].fullmatch(caminho), caminho)
        for metodo, caminho in (('POST', '/v1/admin/botcmds'), ('PUT', '/v1/admin/botcmds/outro/exp'), ('PUT', '/v1/admin/botcmds/whatsapp/'), ('PUT', '/v1/admin/botcmds/whatsapp/Exp'),
                                ('DELETE', '/v1/admin/botcmds/whatsapp'), ('GET', '/v1/admin/botcmds/whatsapp/exp'), ('PUT', '/v1/admin/botcmds/whatsapp/a/b')):
            self.assertFalse(A.get(metodo) and A[metodo].fullmatch(caminho), caminho)

    def test_leitura_publica_nao_usa_credencial(self):
        usados = []
        def falso(self, path, method='GET', body=None, credential=None):
            usados.append((path, method, credential)); return {}
        with mock.patch.object(acesso.InstallationClient, '_send', falso):
            self.assertEqual(acesso.public_botcmds(), {})
        self.assertEqual(usados, [('/public/botcmds', 'GET', None)])


if __name__ == '__main__':
    unittest.main()
