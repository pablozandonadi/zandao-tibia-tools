"""Testes dos itens do Character Set (TibiaWiki).  Rodar: python -m unittest"""

import json
import os
import tempfile
import time
import unittest

import itens_set as it

CAPACETE = """{{Infobox Object
| name = Gnome Helmet
| primarytype = Helmets
| slot = Head
| levelrequired = 200
| vocrequired = sorcerers and druids
| imbueslots = 2
| attrib = magic level +2
| armor = 8
| resist = physical +3%, energy +8%, ice -2%
| weight = 24.00
}}"""

VARINHA = """{{Infobox Object
| name = Wand of Defiance
| primarytype = Wands
| slot = Weapon Hand
| levelrequired = 65
| vocrequired = sorcerers
| imbueslots = 3
| attack = 0
| attrib =
| weight = 37.00
}}"""

LIVRO = """{{Infobox Object
| name = Spellbook of Mind Control
| primarytype = Spellbooks
| slot = Shield Hand
| levelrequired = 50
| vocrequired = sorcerers and druids
| defense = 26
| attrib = magic level +2
}}"""

ANEL = """{{Infobox Object
| name = Ring of Healing
| primarytype = Rings
| slot = Finger
| attrib = faster regeneration
}}"""


MACHADO = """{{Infobox Object
| name = Amber Axe
| slot = Weapon Hand
| levelrequired = 330
| vocrequired = knights
| attack =
| ice_attack = 46
| defense = 32
| imbueslots = 2
| attrib = axe fighting +3
}}"""

ESCUDO = """{{Infobox Object
| name = Adamant Shield
| slot = Shield
| defense = 35
}}"""


class TestItemDoWikitext(unittest.TestCase):
    def test_capacete(self):
        i = it.item_do_wikitext("Gnome Helmet", CAPACETE, "cabeca")
        self.assertEqual((i["nome"], i["slot"], i["level"], i["imbue"], i["armor"]), ("Gnome Helmet", "cabeca", 200, 2, 8))
        self.assertEqual(i["vocs"], ["sorcerer", "druid"])
        self.assertEqual(i["resist"], {"physical": 3, "energy": 8, "ice": -2})
        self.assertEqual(i["attrib"], "magic level +2")
        self.assertEqual(it.descricao(i), "Arm: 8, Magic Level +2, Energy +8%, Physical +3%, Ice -2%")

    def test_arma_livro_e_anel(self):
        v = it.item_do_wikitext("Wand of Defiance", VARINHA, "arma")
        self.assertEqual((v["slot"], v["imbue"], v["level"]), ("arma", 3, 65))
        self.assertEqual(it.descricao(v), "")                                   # sem atributo para mostrar
        l = it.item_do_wikitext("Spellbook of Mind Control", LIVRO, "mao")
        self.assertEqual((l["slot"], l["defense"]), ("mao", 26))
        self.assertEqual(it.descricao(l), "Def: 26, Magic Level +2")
        a = it.item_do_wikitext("Ring of Healing", ANEL, "anel")
        self.assertEqual((a["slot"], a["imbue"], a["vocs"]), ("anel", 0, list(it.VOCACOES)))   # sem vagas de embuimento; qualquer vocação

    def test_o_slot_do_campo_vence_o_da_categoria(self):
        # a categoria "Weapons" mistura coisas; quem decide é o campo slot da própria página
        self.assertEqual(it.item_do_wikitext("X", CAPACETE, "arma")["slot"], "cabeca")
        self.assertEqual(it.item_do_wikitext("Y", CAPACETE.replace("slot = Head", "slot = Two-Handed"), "arma")["slot"], "arma")

    def test_ataque_elemental_e_slot_shield(self):
        m = it.item_do_wikitext("Amber Axe", MACHADO, "arma")
        self.assertEqual(m["atk_elem"], {"ice": 46})
        self.assertEqual(it.descricao(m), "Def: 32, Ice Atk: 46, Axe Fighting +3")
        self.assertEqual(it.item_do_wikitext("Adamant Shield", ESCUDO, "mao")["slot"], "mao")
        self.assertEqual(it.item_do_wikitext("Adamant Shield", ESCUDO, "arma")["slot"], "mao")

    def test_pagina_sem_infobox(self):
        self.assertIsNone(it.item_do_wikitext("Lixo", "texto qualquer sem infobox", "cabeca"))


class TestCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arq = os.path.join(self.tmp.name, "c.json")
        self.chamadas = []

    def tearDown(self):
        self.tmp.cleanup()

    def _buscar(self, slot):
        self.chamadas.append(slot)
        return [{"nome": "Zeta", "slot": slot, "level": 10}, {"nome": "Alfa", "slot": slot, "level": 50}, {"nome": "Alfa", "slot": slot, "level": 50}]

    def test_ordena_sem_repetir_e_usa_cache_por_slot(self):
        r = it.itens_do_slot("cabeca", self.arq, self._buscar)
        self.assertEqual([x["nome"] for x in r], ["Alfa", "Zeta"])              # sem repetir, por nome
        it.itens_do_slot("cabeca", self.arq, self._buscar)
        self.assertEqual(self.chamadas, ["cabeca"])                             # 2ª vez: cache
        it.itens_do_slot("botas", self.arq, self._buscar)
        self.assertEqual(self.chamadas, ["cabeca", "botas"])                    # cada slot tem o seu cache

    def test_cache_vencido_e_sem_internet_usa_o_velho(self):
        it.itens_do_slot("cabeca", self.arq, self._buscar)
        d = json.load(open(self.arq, encoding="utf-8"))
        d["slots"]["cabeca"]["t"] = time.time() - it.VALIDADE - 10
        json.dump(d, open(self.arq, "w", encoding="utf-8"))

        def sem_internet(slot):
            raise OSError("sem internet")
        self.assertEqual(len(it.itens_do_slot("cabeca", self.arq, sem_internet)), 2)
        self.assertEqual(it.itens_do_slot("anel", self.arq, sem_internet), [])  # nunca baixou e sem internet: lista vazia

    def test_slot_desconhecido(self):
        self.assertEqual(it.itens_do_slot("cabelo", self.arq, self._buscar), [])
        self.assertEqual(self.chamadas, [])


if __name__ == "__main__":
    unittest.main()
