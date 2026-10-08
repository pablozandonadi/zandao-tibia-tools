"""Testes dos Character Sets: cadastro, cópia na hunt e diferenças entre sets.  Rodar: python -m unittest"""

import os
import tempfile
import unittest

import sets

CAPACETE = {"nome": "Gnome Helmet", "imagem": "https://static.wikia.nocookie.net/x/Gnome_Helmet.gif", "imbue": 2, "armor": 8,
            "attrib": "magic level +2", "resist": {"energy": 8}, "desc": "Arm: 8, Magic Level +2, Energy +8%",
            "imbues": ["Powerful Void", "Powerful Strike", "Powerful Epiphany"]}
VARINHA = {"nome": "Wand of Defiance", "imbue": 3, "imbues": ["Powerful Void"]}


class TestNormalizar(unittest.TestCase):
    def test_normaliza_o_set(self):
        s = sets.normalizar_set({"titulo": "  Hunt Tokyo ", "itens": {"cabeca": CAPACETE, "arma": VARINHA}, "consumiveis": [" Mana Potion ", "", "Mana Potion"], "lixo": 1})
        self.assertEqual(s["titulo"], "Hunt Tokyo")
        self.assertEqual(set(s["itens"]), {"cabeca", "arma"})
        self.assertEqual(s["itens"]["cabeca"]["nome"], "Gnome Helmet")
        self.assertEqual(s["itens"]["cabeca"]["resist"], {"energy": 8})        # os stats ficam (a soma da fase D2 usa)
        self.assertEqual(s["consumiveis"], ["Mana Potion"])                   # sem vazio e sem repetido
        self.assertNotIn("lixo", s)

    def test_embuimentos_limitados_as_vagas_do_item(self):
        s = sets.normalizar_set({"titulo": "x", "itens": {"cabeca": CAPACETE}})
        self.assertEqual(s["itens"]["cabeca"]["imbues"], ["Powerful Void", "Powerful Strike"])   # 2 vagas
        sem_vaga = dict(VARINHA, imbue=0)
        self.assertEqual(sets.normalizar_set({"titulo": "x", "itens": {"arma": sem_vaga}})["itens"]["arma"]["imbues"], [])
        repetido = dict(VARINHA, imbues=["Powerful Void", "Powerful Void", "Powerful Strike"])
        self.assertEqual(sets.normalizar_set({"titulo": "x", "itens": {"arma": repetido}})["itens"]["arma"]["imbues"], ["Powerful Void", "Powerful Strike"])

    def test_descarta_o_que_nao_presta(self):
        s = sets.normalizar_set({"titulo": "x", "itens": {"cabelo": CAPACETE, "cabeca": {"imbue": 1}, "botas": "lixo",
                                                          "arma": dict(VARINHA, imagem="javascript:alert(1)")}})
        self.assertEqual(set(s["itens"]), {"arma"})                            # slot inexistente, item sem nome, item que não é dict
        self.assertNotIn("imagem", s["itens"]["arma"])                         # só imagem http(s)

    def test_vazio_nulo_e_rotulo(self):
        self.assertIsNone(sets.normalizar_set(None))                           # None = não informado (hunts antigas)
        self.assertEqual(sets.normalizar_set("lixo"), {})                      # {} = sem set
        self.assertEqual(sets.normalizar_set({"titulo": "x", "itens": {}, "consumiveis": []}), {})
        self.assertEqual(sets.rotulo_set(None), "Set não informado")
        self.assertEqual(sets.rotulo_set({}), "Sem set")
        self.assertEqual(sets.rotulo_set({"titulo": "Hunt Tokyo", "itens": {"arma": VARINHA}}), "Set: Hunt Tokyo")
        self.assertEqual(sets.normalizar_set({"itens": {"arma": VARINHA}})["titulo"], "Set sem título")


class TestCadastro(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arq = os.path.join(self.tmp.name, "sets.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_salvar_listar_obter_remover(self):
        self.assertEqual(sets.listar(self.arq), [])
        a = sets.salvar({"titulo": "Tokyo", "itens": {"arma": VARINHA}}, self.arq)
        self.assertTrue(a["id"])
        b = sets.salvar({"titulo": "Ingol", "itens": {"cabeca": CAPACETE}}, self.arq)
        self.assertEqual([x["titulo"] for x in sets.listar(self.arq)], ["Tokyo", "Ingol"])
        self.assertEqual(sets.obter(b["id"], self.arq)["itens"]["cabeca"]["nome"], "Gnome Helmet")
        # salvar com o mesmo id edita em vez de duplicar
        a2 = sets.salvar({"id": a["id"], "titulo": "Tokyo 2", "itens": {"arma": VARINHA}}, self.arq)
        self.assertEqual(a2["id"], a["id"])
        self.assertEqual([x["titulo"] for x in sets.listar(self.arq)], ["Tokyo 2", "Ingol"])
        self.assertTrue(sets.remover(a["id"], self.arq))
        self.assertFalse(sets.remover(a["id"], self.arq))
        self.assertEqual(len(sets.listar(self.arq)), 1)

    def test_set_vazio_nao_e_salvo(self):
        with self.assertRaises(ValueError):
            sets.salvar({"titulo": "Vazio", "itens": {}}, self.arq)
        self.assertEqual(sets.listar(self.arq), [])

    def test_arquivo_corrompido(self):
        with open(self.arq, "w") as f:
            f.write("{quebrado")
        self.assertEqual(sets.listar(self.arq), [])

    def test_copia_para_a_hunt_nao_leva_o_id(self):
        a = sets.salvar({"titulo": "Tokyo", "itens": {"arma": VARINHA}, "consumiveis": ["Mana Potion"]}, self.arq)
        copia = sets.copia_para_hunt(a)
        self.assertNotIn("id", copia)
        self.assertEqual(copia, sets.normalizar_set(copia))                    # já é a forma normalizada


class TestDiferencas(unittest.TestCase):
    def test_lista_so_o_que_mudou(self):
        a = sets.normalizar_set({"titulo": "A", "itens": {"cabeca": CAPACETE, "arma": VARINHA}, "consumiveis": ["Mana Potion"]})
        igual_outro_titulo = sets.normalizar_set({"titulo": "B", "itens": {"cabeca": CAPACETE, "arma": VARINHA}, "consumiveis": ["Mana Potion"]})
        self.assertEqual(sets.diferencas(a, igual_outro_titulo), [])           # o título não conta
        outro = sets.normalizar_set({"titulo": "C", "itens": {"cabeca": dict(CAPACETE, imbues=["Powerful Void"]), "arma": VARINHA, "botas": {"nome": "Boots of Haste"}},
                                     "consumiveis": ["Mana Potion", "Health Potion"]})
        self.assertEqual(sets.diferencas(a, outro), ["Capacete", "Botas", "Consumíveis"])   # na ordem dos slots

    def test_item_trocado_conta(self):
        a = sets.normalizar_set({"titulo": "A", "itens": {"arma": VARINHA}})
        b = sets.normalizar_set({"titulo": "B", "itens": {"arma": {"nome": "Wand of Starstorm", "imbue": 3}}})
        self.assertEqual(sets.diferencas(a, b), ["Arma"])

    def test_sem_set_informado(self):
        a = sets.normalizar_set({"titulo": "A", "itens": {"arma": VARINHA}})
        self.assertEqual(sets.diferencas(a, {}), ["Arma"])                     # com set x sem set
        self.assertEqual(sets.diferencas({}, {}), [])


if __name__ == "__main__":
    unittest.main()
