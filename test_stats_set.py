"""Testes da soma dos stats do set (Combat Stats).  Rodar: python -m unittest"""

import unittest

import sets
import stats_set as ss

SET = sets.normalizar_set({"titulo": "Teste", "itens": {
    "cabeca": {"nome": "Gnome Helmet", "imbue": 2, "armor": 8, "attrib": "magic level +2", "resist": {"energy": 8, "physical": 3, "ice": -2},
               "imbues": ["Powerful Void", "Powerful Lich Shroud"]},
    "armadura": {"nome": "Armadura X", "imbue": 1, "armor": 15, "resist": {"fire": 5}, "imbues": []},
    "arma": {"nome": "Amber Axe", "imbue": 3, "attack": 40, "defense": 20, "atk_elem": {"ice": 46}, "attrib": "axe fighting +3",
             "imbues": ["Powerful Scorch", "Powerful Strike"]},
    "mao": {"nome": "Escudo Y", "imbue": 1, "defense": 35, "imbues": ["Powerful Blockade"]},
    "botas": {"nome": "Botas Z", "imbue": 2, "attrib": "speed +10", "imbues": ["Powerful Swiftness", "Powerful Vibrancy"]},
    "anel": {"nome": "Ring of Healing", "attrib": "faster regeneration"},
    "trinket": {"nome": "Moon Mirror", "resist": {"death": 5}},
}})


class TestSomar(unittest.TestCase):
    def setUp(self):
        self.s = ss.somar(SET)

    def test_numeros_dos_itens(self):
        self.assertEqual((self.s["armor"], self.s["defense"], self.s["attack"]), (23, 55, 40))
        self.assertEqual(self.s["atk_elem"], {"ice": 46})
        self.assertEqual(self.s["resist"], {"energy": 8, "physical": 3, "ice": -2, "fire": 5, "death": 15})   # 5 do trinket + 10 do Lich Shroud
        self.assertEqual(self.s["skills"], {"magic level": 2, "axe fighting": 3, "shielding": 4, "speed": 40})  # speed 10 do item + 30 do Swiftness

    def test_efeitos_dos_embuimentos_powerful(self):
        self.assertEqual(self.s["leech"], {"mana": 8})
        self.assertEqual(self.s["crit"], {"chance": 5, "dano": 40})
        self.assertEqual(self.s["conversao"], {"fire": 50})
        self.assertEqual(self.s["paralisia"], 50)
        self.assertEqual(self.s["extras"], ["Faster Regeneration"])

    def test_tabela_dos_24_powerful_bate_com_a_wiki(self):
        import json, os
        nomes = {i["name"] for i in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "imbuements.json"), encoding="utf-8"))}
        self.assertEqual(set(ss.IMBUEMENTS), nomes)                           # os 24 que o app oferece, nenhum esquecido
        for nome, esperado in (("Powerful Vampirism", ("leech", "life", 25)), ("Powerful Epiphany", ("skill", "magic level", 4)),
                               ("Powerful Dragon Hide", ("resist", "fire", 15)), ("Powerful Electrify", ("conv", "energy", 50)),
                               ("Powerful Featherweight", ("capacidade", None, 15))):
            self.assertIn(esperado, ss.IMBUEMENTS[nome], nome)

    def test_atributos_do_item(self):
        s = ss.somar(sets.normalizar_set({"titulo": "x", "itens": {
            "anel": {"nome": "A", "attrib": "life leech +2%, critical hit chance 1%, fire magic level +2, 13 damage reflection"},
            "amuleto": {"nome": "B", "attrib": "magic level +1, life leech +3%"}}}))
        self.assertEqual(s["leech"], {"life": 5})
        self.assertEqual(s["crit"], {"chance": 1})
        self.assertEqual(s["skills"], {"fire magic level": 2, "magic level": 1})
        self.assertEqual(s["extras"], ["13 Damage Reflection"])              # o que não dá para somar vira texto

    def test_vazio_e_embuimento_desconhecido(self):
        self.assertEqual(ss.somar({})["armor"], 0)
        self.assertEqual(ss.somar(None)["resist"], {})
        s = ss.somar(sets.normalizar_set({"titulo": "x", "itens": {"cabeca": {"nome": "H", "imbue": 1, "imbues": ["Basic Void"]}}}))
        self.assertEqual(s["leech"], {})                                      # só os Powerful contam (o app só oferece esses)


class TestLinhas(unittest.TestCase):
    def test_linhas_para_a_tela(self):
        linhas = {l["chave"]: l for l in ss.linhas(ss.somar(SET))}
        self.assertEqual((linhas["armor"]["rotulo"], linhas["armor"]["valor"], linhas["armor"]["texto"]), ("Armor", 23, "23"))
        self.assertEqual((linhas["resist:energy"]["rotulo"], linhas["resist:energy"]["texto"]), ("Energy", "+8%"))
        self.assertEqual(linhas["resist:ice"]["texto"], "-2%")
        self.assertEqual((linhas["skill:magic level"]["rotulo"], linhas["skill:magic level"]["texto"]), ("Magic Level", "+2"))
        self.assertEqual(linhas["leech:mana"]["texto"], "8%")
        self.assertEqual(linhas["crit:dano"]["rotulo"], "Critical extra damage")
        self.assertEqual(linhas["conv:fire"]["texto"], "50%")
        self.assertEqual(linhas["atk_elem:ice"]["valor"], 46)
        self.assertEqual(linhas["extra:faster regeneration"]["texto"], "Faster Regeneration")
        self.assertNotIn("resist:holy", linhas)                              # zerado não aparece
        grupos = [l["grupo"] for l in ss.linhas(ss.somar(SET))]
        self.assertEqual(grupos, sorted(grupos, key=["Defesa", "Ataque", "Skills", "Outros"].index))   # agrupadas na ordem da tela


if __name__ == "__main__":
    unittest.main()
