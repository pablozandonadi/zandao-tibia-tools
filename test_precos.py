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

    def test_arquivo_corrompido(self):
        with open(self.arq, "w") as f:
            f.write("{quebrado")
        self.assertEqual(precos.carregar(self.arq), {})


if __name__ == "__main__":
    unittest.main()
