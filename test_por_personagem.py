"""Rodas, sets e timers pertencem a um personagem (o que o usuário cadastrou fica vinculado a ele).  Rodar: python -m unittest"""

import os
import tempfile
import unittest

import audio_timers
import roda
import sets

COD_K = "K0Y2AgDP4jAQA"
COD_S = "S0Y2AgDP4jAQA"
VARINHA = {"nome": "Wand of Defiance", "imbue": 3, "imbues": ["Powerful Void"]}
ESPADA = {"nome": "Magic Sword"}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arq = os.path.join(self.tmp.name, "dados.json")

    def tearDown(self):
        self.tmp.cleanup()


class TestRodaPorPersonagem(Base):
    def test_adicionar_vinculado(self):
        r = roda.adicionar("EK energy", COD_K, self.arq, "Elite Nestos")
        self.assertEqual(r["personagem"], "Elite Nestos")
        self.assertEqual(roda.obter(r["id"], self.arq)["personagem"], "Elite Nestos")

    def test_sem_personagem_continua_funcionando(self):
        r = roda.adicionar("antiga", COD_K, self.arq)
        self.assertEqual(r.get("personagem", ""), "")

    def test_vincular_e_desvincular(self):
        r = roda.adicionar("antiga", COD_K, self.arq)
        self.assertTrue(roda.vincular(r["id"], "Elite Nestos", self.arq))
        self.assertEqual(roda.obter(r["id"], self.arq)["personagem"], "Elite Nestos")
        self.assertTrue(roda.vincular(r["id"], "", self.arq))
        self.assertEqual(roda.obter(r["id"], self.arq).get("personagem", ""), "")
        self.assertFalse(roda.vincular("nao-existe", "X", self.arq))

    def test_editar_nao_perde_o_vinculo(self):
        r = roda.adicionar("EK", COD_K, self.arq, "Elite Nestos")
        roda.renomear(r["id"], "EK novo", self.arq)
        roda.atualizar_codigo(r["id"], "K0Y2AgDP4jAQB", self.arq)
        self.assertEqual(roda.obter(r["id"], self.arq)["personagem"], "Elite Nestos")

    def test_api(self):
        import web_api
        api = object.__new__(web_api.API)
        orig = roda.RODAS_PATH
        roda.RODAS_PATH = self.arq
        try:
            r = api.roda_adicionar("MS", COD_S, "Zandao")["roda"]
            self.assertEqual(r["personagem"], "Zandao")
            self.assertTrue(api.roda_vincular(r["id"], "Its Tokyo"))
            self.assertEqual(api.roda_listar()[0]["personagem"], "Its Tokyo")
        finally:
            roda.RODAS_PATH = orig


class TestSetPorPersonagem(Base):
    def test_salvar_vinculado_e_editar_mantem(self):
        a = sets.salvar({"titulo": "Tokyo", "itens": {"arma": VARINHA}, "personagem": "Its Tokyo"}, self.arq)
        self.assertEqual(a["personagem"], "Its Tokyo")
        b = sets.salvar({"id": a["id"], "titulo": "Tokyo 2", "itens": {"arma": VARINHA}}, self.arq)   # a tela não manda o campo: mantém
        self.assertEqual(b["personagem"], "Its Tokyo")
        self.assertEqual(sets.obter(a["id"], self.arq)["personagem"], "Its Tokyo")

    def test_set_antigo_sem_personagem(self):
        a = sets.salvar({"titulo": "Velho", "itens": {"arma": ESPADA}}, self.arq)
        self.assertEqual(sets.obter(a["id"], self.arq).get("personagem", ""), "")

    def test_vincular(self):
        a = sets.salvar({"titulo": "Velho", "itens": {"arma": ESPADA}}, self.arq)
        self.assertTrue(sets.vincular(a["id"], "Elite Nestos", self.arq))
        self.assertEqual(sets.obter(a["id"], self.arq)["personagem"], "Elite Nestos")
        self.assertFalse(sets.vincular("x", "Elite Nestos", self.arq))

    def test_o_set_que_vai_para_a_hunt_nao_carrega_o_vinculo(self):
        a = sets.salvar({"titulo": "Tokyo", "itens": {"arma": VARINHA}, "personagem": "Its Tokyo"}, self.arq)
        self.assertNotIn("personagem", sets.normalizar_set(a))

    def test_api(self):
        import web_api
        api = object.__new__(web_api.API)
        orig = sets.SETS_PATH
        sets.SETS_PATH = self.arq
        try:
            r = api.set_salvar({"titulo": "T", "itens": {"arma": VARINHA}, "personagem": "Zandao"})
            self.assertTrue(api.set_vincular(r["set"]["id"] if "set" in r else r["id"], "Its Tokyo"))
            self.assertEqual(api.set_listar()[0]["personagem"], "Its Tokyo")
        finally:
            sets.SETS_PATH = orig


class TestTimerPorPersonagem(unittest.TestCase):
    def test_normalizar_guarda_o_personagem(self):
        t = audio_timers.normalizar({"nome": "Poção", "personagem": "Elite Nestos"})
        self.assertEqual(t["personagem"], "Elite Nestos")
        self.assertEqual(audio_timers.normalizar({"nome": "Velho"})["personagem"], "")

    def test_ativos_so_os_do_personagem_em_uso(self):
        timers = [{"id": "a", "personagem": "Elite Nestos"}, {"id": "b", "personagem": "Its Tokyo"}, {"id": "c", "personagem": ""}]
        self.assertEqual([t["id"] for t in audio_timers.ativos(timers, "Elite Nestos")], ["a"])
        self.assertEqual([t["id"] for t in audio_timers.ativos(timers, "Its Tokyo")], ["b"])
        self.assertEqual(audio_timers.ativos(timers, ""), [])          # sem personagem em uso e sem vínculo: nenhum dispara
        self.assertEqual(audio_timers.ativos(timers, "Outro"), [])


if __name__ == "__main__":
    unittest.main()
