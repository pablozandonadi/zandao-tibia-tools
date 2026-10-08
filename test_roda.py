"""Testes das rodas (Wheel of Destiny): códigos, cadastro e cache dos arquivos do planner.  Rodar: python -m unittest"""

import json
import os
import tempfile
import time
import unittest

import roda


class TestCodigo(unittest.TestCase):
    def test_validar(self):
        self.assertEqual(roda.validar_codigo("K0Y2AgDP4jAQA"), "K0Y2AgDP4jAQA")
        self.assertEqual(roda.validar_codigo("  S0Y2AgDP4jAQA \n"), "S0Y2AgDP4jAQA")
        # link do planner: pega o code=
        self.assertEqual(roda.validar_codigo("https://www.tibia.com/community/?subtopic=wheelofdestinyplanner&code=K0Y2AgDP4jAQA"), "K0Y2AgDP4jAQA")
        self.assertEqual(roda.validar_codigo("K0OzEthYGBYVqKN5BM8TZiwAb-IwEA"), "K0OzEthYGBYVqKN5BM8TZiwAb-IwEA")  # tem '-'
        for ruim in ("", "   ", None, "abc", "X0Y2AgDP4jAQA", "K0Y2 AgDP4jAQA", "K0Y2AgDP4jAQA!", "K" * 300, "https://tibia.com/?code=%%%"):
            self.assertIsNone(roda.validar_codigo(ruim), repr(ruim))

    def test_vocacao_pela_primeira_letra(self):
        for letra, voc in (("K", "Knight"), ("P", "Paladin"), ("S", "Sorcerer"), ("D", "Druid"), ("M", "Monk")):
            self.assertEqual(roda.vocacao_do_codigo(letra + "0Y2AgDP4jAQA"), voc)
        self.assertIsNone(roda.vocacao_do_codigo("X0Y2AgDP4jAQA"))


class TestCadastro(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arq = os.path.join(self.tmp.name, "rodas.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_adicionar_listar_remover(self):
        self.assertEqual(roda.listar(self.arq), [])
        r = roda.adicionar("Beam Master", "S0Y2AgDP4jAQA", self.arq)
        self.assertEqual((r["titulo"], r["codigo"], r["vocacao"]), ("Beam Master", "S0Y2AgDP4jAQA", "Sorcerer"))
        self.assertTrue(r["id"])
        roda.adicionar("Fire LOD", "https://www.tibia.com/community/?subtopic=wheelofdestinyplanner&code=K0Y2AgDP4jAQA", self.arq)
        self.assertEqual([x["titulo"] for x in roda.listar(self.arq)], ["Beam Master", "Fire LOD"])
        self.assertEqual(roda.obter(r["id"], self.arq)["codigo"], "S0Y2AgDP4jAQA")
        self.assertTrue(roda.remover(r["id"], self.arq))
        self.assertFalse(roda.remover(r["id"], self.arq))
        self.assertEqual([x["titulo"] for x in roda.listar(self.arq)], ["Fire LOD"])

    def test_recusa_codigo_ruim_e_titulo_vazio_vira_vocacao(self):
        with self.assertRaises(ValueError):
            roda.adicionar("X", "isso não é um código", self.arq)
        self.assertEqual(roda.adicionar("   ", "D0Y2AgDP4jAQA", self.arq)["titulo"], "Roda Druid")
        self.assertEqual(len(roda.listar(self.arq)), 1)

    def test_renomear(self):
        r = roda.adicionar("Velho", "K0Y2AgDP4jAQA", self.arq)
        self.assertTrue(roda.renomear(r["id"], "Novo", self.arq))
        self.assertEqual(roda.obter(r["id"], self.arq)["titulo"], "Novo")
        self.assertFalse(roda.renomear("nao-existe", "Y", self.arq))

    def test_arquivo_corrompido(self):
        with open(self.arq, "w") as f:
            f.write("{quebrado")
        self.assertEqual(roda.listar(self.arq), [])

    def test_normalizar_roda_da_hunt(self):
        self.assertIsNone(roda.normalizar_roda(None))
        self.assertEqual(roda.normalizar_roda({"titulo": " Beam ", "codigo": "S0Y2AgDP4jAQA", "extra": 1}),
                         {"titulo": "Beam", "codigo": "S0Y2AgDP4jAQA"})
        self.assertEqual(roda.normalizar_roda({"titulo": "", "codigo": "K0Y2AgDP4jAQA"}), {"titulo": "Roda Knight", "codigo": "K0Y2AgDP4jAQA"})
        self.assertEqual(roda.normalizar_roda("lixo"), {})          # {} = "sem roda" (informado); None = não informada
        self.assertEqual(roda.normalizar_roda({"codigo": "ruim"}), {})
        self.assertEqual(roda.rotulo_roda(None), "Roda não informada")
        self.assertEqual(roda.rotulo_roda({}), "Sem roda")
        self.assertEqual(roda.rotulo_roda({"titulo": "Beam", "codigo": "S0Y2AgDP4jAQA"}), "Roda: Beam")


class TestArquivosDoPlanner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pasta = os.path.join(self.tmp.name, "cache_roda")
        self.baixados = []

    def tearDown(self):
        self.tmp.cleanup()

    def _baixar(self, url):
        self.baixados.append(url)
        return b"createModule runWodPlanner SmallPerkInfos jQuery"   # tem o marcador que cada arquivo precisa ter

    def test_baixa_uma_vez_e_usa_o_cache(self):
        r = roda.arquivos_planner(self.pasta, self._baixar)
        self.assertTrue(r["ok"])
        self.assertEqual(set(r["arquivos"]), set(roda.ARQUIVOS))
        self.assertEqual(len(self.baixados), len(roda.ARQUIVOS))
        self.assertTrue(all(u.startswith("https://static.tibia.com/") for u in self.baixados))
        roda.arquivos_planner(self.pasta, self._baixar)
        self.assertEqual(len(self.baixados), len(roda.ARQUIVOS))      # segunda vez: tudo do cache

    def test_cache_velho_e_sem_internet_usa_o_que_tem(self):
        roda.arquivos_planner(self.pasta, self._baixar)
        velho = time.time() - roda.VALIDADE - 10
        for nome in roda.ARQUIVOS:
            os.utime(os.path.join(self.pasta, nome), (velho, velho))

        def sem_internet(url):
            raise OSError("sem internet")
        r = roda.arquivos_planner(self.pasta, sem_internet)
        self.assertTrue(r["ok"])
        self.assertIn("skillgrid.js", r["arquivos"])

    def test_recusa_pagina_de_erro_no_lugar_do_script(self):
        def pagina_de_verificacao(url):
            return b"<html>Just a moment... verificando seu navegador</html>"
        r = roda.arquivos_planner(self.pasta, pagina_de_verificacao)
        self.assertFalse(r["ok"])
        self.assertEqual(os.listdir(self.pasta), [])      # nada foi guardado

    def test_sem_cache_e_sem_internet_avisa(self):
        def sem_internet(url):
            raise OSError("sem internet")
        r = roda.arquivos_planner(self.pasta, sem_internet)
        self.assertFalse(r["ok"])
        self.assertIn("internet", r["erro"].lower())


if __name__ == "__main__":
    unittest.main()
