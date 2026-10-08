"""Testes do histórico de preços dos embuimentos.  Rodar: python -m unittest"""

import os
import tempfile
import unittest

import precos


class TestPrecos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arq = os.path.join(self.tmp.name, "p.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_registrar_substitui_no_mesmo_dia_e_ignora_vazios(self):
        self.assertEqual(precos.registrar({"item:rope belt": 4600, "token": None, "blank": 0}, "2026-10-03", self.arq), 1)
        precos.registrar({"item:rope belt": 4700}, "2026-10-03", self.arq)
        precos.registrar({"item:rope belt": 4973}, "2026-10-07", self.arq)
        h = precos.carregar(self.arq)
        self.assertEqual(h["item:rope belt"], [{"data": "2026-10-03", "preco": 4700}, {"data": "2026-10-07", "preco": 4973}])
        self.assertNotIn("token", h)

    def test_registro_fora_de_ordem_fica_ordenado(self):
        precos.registrar({"blank": 25000}, "2026-10-07", self.arq)
        precos.registrar({"blank": 24000}, "2026-10-01", self.arq)
        self.assertEqual([p["data"] for p in precos.carregar(self.arq)["blank"]], ["2026-10-01", "2026-10-07"])

    def test_campo_vazio_nao_apaga_historico(self):
        precos.registrar({"item:rope belt": 4600}, "2026-10-03", self.arq)
        precos.registrar({"item:rope belt": None}, "2026-10-07", self.arq)
        self.assertEqual(len(precos.carregar(self.arq)["item:rope belt"]), 1)

    def test_variacao(self):
        h = {"item:rope belt": [{"data": "2026-10-03", "preco": 4600}, {"data": "2026-10-07", "preco": 4973}]}
        v = precos.variacao(4973, "item:rope belt", "2026-10-07", h)  # registro de hoje é ignorado
        self.assertEqual((v["sentido"], v["antes"], v["data"]), ("subiu", 4600, "2026-10-03"))
        self.assertAlmostEqual(v["pct"], 8.1, places=1)
        self.assertEqual(precos.variacao(4370, "item:rope belt", "2026-10-07", h)["sentido"], "caiu")
        self.assertIsNone(precos.variacao(4600, "item:rope belt", "2026-10-07", h))  # igual
        self.assertIsNone(precos.variacao(None, "item:rope belt", "2026-10-07", h))  # vazio
        self.assertIsNone(precos.variacao(5000, "item:outro", "2026-10-07", h))  # sem histórico

    def test_serie_e_apagar(self):
        for d, p in (("2026-10-01", 100), ("2026-10-02", 300), ("2026-10-03", 200)):
            precos.registrar({"token": p}, d, self.arq)
        s = precos.serie(precos.carregar(self.arq), "token")
        self.assertEqual((s["min"], s["max"], s["media"]), (100, 300, 200))
        self.assertTrue(precos.apagar("token", "2026-10-02", self.arq))
        self.assertFalse(precos.apagar("token", "2026-10-02", self.arq))
        self.assertEqual([p["preco"] for p in precos.carregar(self.arq)["token"]], [100, 200])
        self.assertEqual(precos.serie({}, "token"), {"pontos": [], "min": None, "max": None, "media": None})

    def test_registros_malformados_sao_filtrados(self):
        import json
        ruim = {"ok": [{"data": "2026-10-01", "preco": 100}, {"data": "2026-10-02", "preco": "x"}, {"preco": 5}, {"data": "2026-10-03", "preco": -3}, "lixo", {"data": 9, "preco": 4}],
                "so_lixo": ["a", None], "nao_lista": 7}
        with open(self.arq, "w", encoding="utf-8") as f:
            json.dump(ruim, f)
        self.assertEqual(precos.carregar(self.arq), {"ok": [{"data": "2026-10-01", "preco": 100}]})   # o app não quebra com um registro estragado
        self.assertEqual(precos.serie(precos.carregar(self.arq), "ok")["max"], 100)

    def test_arquivo_corrompido(self):
        with open(self.arq, "w") as f:
            f.write("{quebrado")
        self.assertEqual(precos.carregar(self.arq), {})


class TestApiPrecos(unittest.TestCase):
    def setUp(self):
        import web_api
        self.tmp = tempfile.TemporaryDirectory()
        self.api = object.__new__(web_api.API)
        self.api._precos_path = os.path.join(self.tmp.name, "p.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_registrar_aceita_formatos_do_tibia(self):
        import embuimentos as emb
        self.api._hoje = lambda: "2026-10-07"
        self.assertEqual(self.api.precos_registrar({"item:rope belt": "4.5k", "scroll:void": "1,2kk", "token": "55554", "blank": ""}),
                         {"gravados": 3})
        h = precos.carregar(self.api._precos_path)
        self.assertEqual(h["item:rope belt"][0]["preco"], emb.parse_num("4.5k"))
        self.assertEqual(h["scroll:void"][0]["preco"], emb.parse_num("1,2kk"))

    def test_variacoes_serie_apagar(self):
        self.api._hoje = lambda: "2026-10-03"
        self.api.precos_registrar({"token": "50000"})
        self.api._hoje = lambda: "2026-10-07"
        v = self.api.precos_variacoes({"token": "55000", "blank": "25000"})
        self.assertEqual(v["token"]["sentido"], "subiu")
        self.assertIsNone(v["blank"])
        self.assertEqual(self.api.precos_serie("token")["max"], 50000)
        self.assertEqual(self.api.precos_apagar("token", "2026-10-03")["pontos"], [])

    def test_apagar_com_erro_de_gravacao_avisa(self):
        from unittest import mock
        self.api._hoje = lambda: "2026-10-03"
        self.api.precos_registrar({"token": "50000"})
        with mock.patch.object(precos, "_gravar", side_effect=OSError("disco cheio")):
            r = self.api.precos_apagar("token", "2026-10-03")
        self.assertIn("erro", r)                                              # a tela mostra o aviso em vez de fingir que apagou
        self.assertEqual(len(precos.carregar(self.api._precos_path)["token"]), 1)

    def test_backup_inclui_precos(self):
        import backup
        self.assertIn("precos", backup.ITENS)
        self.assertEqual(self.api._caminhos_backup()["precos"], precos.PRECOS_PATH)
        orig = {"precos": os.path.join(self.tmp.name, "orig.json")}
        precos.registrar({"token": 55554}, "2026-10-07", orig["precos"])
        pacote = backup.exportar(orig, "9.9.9")
        dest = {"precos": os.path.join(self.tmp.name, "dest.json")}
        backup.importar(pacote, dest)
        self.assertEqual(precos.carregar(dest["precos"]), {"token": [{"data": "2026-10-07", "preco": 55554}]})


if __name__ == "__main__":
    unittest.main()
