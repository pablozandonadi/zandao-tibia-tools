"""Preferências da janela: fixar por cima, transparência e o tamanho da interface (escala).  Rodar: python -m unittest"""

import json
import os
import tempfile
import unittest
from unittest import mock

import web_api


class TestPrefsJanela(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.antigo = web_api.PREFS_PATH
        web_api.PREFS_PATH = os.path.join(self.tmp.name, "prefs.json")

    def tearDown(self):
        web_api.PREFS_PATH = self.antigo
        self.tmp.cleanup()

    def _gravar(self, d):
        with open(web_api.PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f)

    def test_padrao_sem_arquivo(self):
        self.assertEqual(web_api.ler_prefs(), {"por_cima": False, "opacidade": 100, "escala": 100})

    def test_arquivo_antigo_sem_escala_vale_100(self):
        self._gravar({"por_cima": True, "opacidade": 80})
        self.assertEqual(web_api.ler_prefs(), {"por_cima": True, "opacidade": 80, "escala": 100})

    def test_escala_fica_entre_50_e_130(self):
        for gravado, esperado in ((10, 50), (49, 50), (75, 75), (130, 130), (500, 130), ("lixo", 100), (None, 100)):
            self._gravar({"escala": gravado})
            self.assertEqual(web_api.ler_prefs()["escala"], esperado, gravado)

    def test_aplicar_guarda_a_escala_e_mantem_quando_nao_vem(self):
        api = object.__new__(web_api.API)
        api._window = None
        api.janela_aplicar(True, 90, 70)
        self.assertEqual(web_api.ler_prefs(), {"por_cima": True, "opacidade": 90, "escala": 70})
        api.janela_aplicar(False, 100)                       # versão antiga da tela não manda a escala: não perde a que existe
        self.assertEqual(web_api.ler_prefs(), {"por_cima": False, "opacidade": 100, "escala": 70})
        api.janela_aplicar(False, 100, 9999)
        self.assertEqual(web_api.ler_prefs()["escala"], 130)

    def test_tamanho_da_janela(self):
        api = object.__new__(web_api.API)
        chamadas = []

        class Janela:
            def resize(self, w, h):
                chamadas.append((w, h))

        api._window = Janela()
        with mock.patch.object(api, "janela_moldura", return_value=True):
            self.assertTrue(api.janela_tamanho("gadget"))
            self.assertTrue(api.janela_tamanho("normal"))
            self.assertFalse(api.janela_tamanho("outro"))
        self.assertEqual(chamadas, [web_api.TAMANHO_GADGET, web_api.TAMANHO_NORMAL])
        api._window = None
        self.assertFalse(api.janela_tamanho("gadget"))

    def test_tamanhos_personalizados_sobrevivem_a_troca_e_reabertura(self):
        api = object.__new__(web_api.API)

        class Janela:
            title = "teste"
            width, height = 1000, 720

            def resize(self, w, h):
                self.width, self.height = w, h

        api._window = Janela()
        with mock.patch.object(api, "janela_moldura", return_value=True):
            self.assertTrue(api.janela_tamanho("gadget"))
            self.assertEqual((api._window.width, api._window.height), web_api.TAMANHO_GADGET)
            api._window.width, api._window.height = 450, 580
            api.janela_redimensionada(450, 580)
            api.janela_tamanho("normal")
            self.assertEqual((api._window.width, api._window.height), (1000, 720))
            api.janela_tamanho("gadget")
            self.assertEqual((api._window.width, api._window.height), (450, 580))
        # Novas chamadas de escala/opacidade não podem apagar os tamanhos.
        api._window = None
        api.janela_aplicar(True, 90, 85)
        prefs = web_api.ler_prefs()
        self.assertEqual(prefs["modo"], "gadget")
        self.assertEqual(prefs["tamanhos"], {"normal": [1000, 720], "gadget": [450, 580]})
        outra_api = object.__new__(web_api.API)
        outra_api._window = Janela()
        with mock.patch.object(outra_api, "janela_moldura", return_value=True):
            outra_api.janela_tamanho(prefs["modo"])
        self.assertEqual((outra_api._window.width, outra_api._window.height), (450, 580))

    def test_evento_atrasado_salva_tamanho_atual_e_ignora_transicao(self):
        api = object.__new__(web_api.API)
        api._window = mock.Mock(width=900, height=650)
        api._modo_janela = "normal"
        api.janela_redimensionada(800, 600)
        self.assertEqual(web_api.ler_prefs()["tamanhos"]["normal"], [900, 650])
        api._trocando_modo = True
        api._window.width, api._window.height = 340, 640
        self.assertFalse(api.janela_redimensionada(340, 640))
        self.assertEqual(web_api.ler_prefs()["tamanhos"]["normal"], [900, 650])

    def test_tamanhos_invalidos_nao_substituem_preferencia(self):
        self._gravar({"modo": "gadget", "tamanhos": {"normal": [1000, 720], "gadget": [0, 0]}})
        self.assertEqual(web_api.ler_prefs()["tamanhos"], {"normal": [1000, 720]})
        api = object.__new__(web_api.API)
        api._window = mock.Mock(width=0, height=0)
        self.assertFalse(api.janela_redimensionada(0, 0))
        self.assertEqual(web_api.ler_prefs()["tamanhos"]["normal"], [1000, 720])


class TestMolduraDaJanela(unittest.TestCase):
    """No modo gadget a barra de título do Windows some (só fica uma faixa fina com o X no hover)."""

    def test_estilo_sem_e_com_moldura(self):
        base = 0x00CF0000 | 0x00040000                       # janela normal: título, bordas, botões
        sem = web_api.estilo_moldura(base, False)
        self.assertEqual(sem & web_api.WS_CAPTION, 0)
        self.assertNotEqual(sem & web_api.WS_THICKFRAME, 0)   # continua dando para redimensionar pelas bordas
        self.assertEqual(web_api.estilo_moldura(sem, True) & web_api.WS_CAPTION, web_api.WS_CAPTION)
        self.assertEqual(web_api.estilo_moldura(base, True), base)

    def test_posicao_do_arrasto_acompanha_o_mouse(self):
        self.assertEqual(web_api.posicao_arrasto((100, 50), (500, 300), (530, 290)), (130, 40))
        self.assertEqual(web_api.posicao_arrasto((100, 50), (500, 300), (500, 300)), (100, 50))

    def test_api_moldura_chama_o_windows(self):
        api = object.__new__(web_api.API)
        chamadas = []

        class Janela:
            title = "Zandao Tibia Tools"

        api._window = Janela()
        with mock.patch.object(web_api, "hwnd_do_app", return_value=123),                 mock.patch.object(web_api, "definir_moldura", side_effect=lambda h, m: chamadas.append((h, m))):
            self.assertTrue(api.janela_moldura(False))
            self.assertTrue(api.janela_moldura(True))
        self.assertEqual(chamadas, [(123, False), (123, True)])
        with mock.patch.object(web_api, "hwnd_do_app", return_value=None):
            self.assertFalse(api.janela_moldura(False))        # janela não achada: não quebra
        api._window = None
        self.assertFalse(api.janela_moldura(False))

    def test_api_arrastar_move_a_janela_junto_com_o_mouse(self):
        api = object.__new__(web_api.API)

        class Janela:
            title = "Zandao Tibia Tools"

        api._window = Janela()
        movidas = []
        cursor = [(500, 300)]
        with mock.patch.object(web_api, "hwnd_do_app", return_value=7),                 mock.patch.object(web_api, "_cursor", side_effect=lambda: cursor[0]),                 mock.patch.object(web_api, "_canto_da_janela", return_value=(100, 50)),                 mock.patch.object(web_api, "_mover_janela", side_effect=lambda h, x, y: movidas.append((h, x, y))):
            self.assertTrue(api.janela_arrastar("inicio"))
            cursor[0] = (540, 320)
            self.assertTrue(api.janela_arrastar("mover"))
            cursor[0] = (480, 300)
            self.assertTrue(api.janela_arrastar("mover"))
            self.assertTrue(api.janela_arrastar("fim"))
            self.assertFalse(api.janela_arrastar("mover"))      # sem arrasto em andamento: ignora
        self.assertEqual(movidas, [(7, 140, 70), (7, 80, 50)])

    def test_fechar(self):
        api = object.__new__(web_api.API)
        fechou = []

        class Janela:
            def destroy(self):
                fechou.append(True)

        api._window = Janela()
        self.assertTrue(api.janela_fechar())
        self.assertEqual(fechou, [True])
        api._window = None
        self.assertFalse(api.janela_fechar())


if __name__ == "__main__":
    unittest.main()
