"""Testes da proficiência de arma e do Perk Shaping.  Rodar: python -m unittest"""

import unittest

import proficiencia as pf

SOULTAINTER = """{{Infobox_Item
| name           = Soultainter
| perk1          = {{Weapon Perk|Type_Critical_Dmg||+5.00% critical extra damage}}
| perk2          = {{Weapon Perk|Type_Element_Critical_Dmg_Death||+7.50% critical extra damage para Death spells e runes}}<br/>{{Weapon Perk|Type_Skill_Magic||+1 Magic Level}}
| perk3          = {{Weapon Perk|Spell_Great_Death_Beam|Critical_Chance|+2% critical hit chance para Great Death Beam}}<br/>{{Weapon Perk|Type_Critical_Dmg||+5.00% critical extra damage}}<br/>{{Weapon Perk|Type_Bestiary_Dmg_Inkborn||+3.00% damage contra Inkborn}}
| perk4          = {{Weapon Perk|Type_Element_Critical_Chance_Death||+1.50% critical hit chance para Death spells e runes}}<br/>{{Weapon Perk|Spell_Great_Death_Beam|Critical_Dmg|+10% critical extra damage para Great Death Beam}}<br/>{{Weapon Perk|Type_Rune_Critical_Chance||+1.00% critical hit chance para offensive runes}}
| perk5          = {{Weapon Perk|Type_Magic_Boost_Death||+2 Death Magic Level}}<br/>{{Weapon Perk|Type_Skill_Magic||+1 Magic Level}}
| perk6          = {{Weapon Perk|Type_Critical_Dmg||+10.00% critical extra damage}}<br/>{{Weapon Perk|Type_Rune_Critical_Dmg||+12.00% critical extra damage para offensive runes}}
| perk7          = {{Weapon Perk|Type_Critical_Chance||+1.00% critical hit chance}}
| notes          = nada
}}"""

OPCAO = """{{Infobox Perk Option
| name        = Armor Penetration
| perk        = Type_Armor_Penetration
| description = Aumenta a penetração de armadura dos seus ataques.
| rank0       = +4% de penetração de armadura
| rank10      = +10% de penetração de armadura
| perlevel    = +1,00% de penetração de armadura aproximadamente por nível
}}"""
OPCAO_VOC = """{{Infobox Perk Option
| name        = Spell Augment Death Echo Life Leech
| perk        = Spell_Death_Echo
| modifier    = Life_Leech
| voc         = Sorcerer
| rank0       = +1% de life leech para Death Echo
| rank10      = +12% de life leech para Death Echo
}}"""


class TestLeitura(unittest.TestCase):
    def test_perks_da_arma(self):
        cols = pf.perks_da_wikitext(SOULTAINTER)
        self.assertEqual(len(cols), 7)
        self.assertEqual([len(c) for c in cols], [1, 2, 3, 3, 2, 2, 1])
        self.assertEqual(cols[1][0], {"tipo": "Type_Element_Critical_Dmg_Death", "texto": "+7.50% critical extra damage para Death spells e runes"})
        self.assertEqual(cols[1][1]["texto"], "+1 Magic Level")
        self.assertEqual(pf.perks_da_wikitext("sem perks"), [])

    def test_valor_e_rotulo(self):
        self.assertEqual(pf.valor_e_rotulo("+7.50% critical extra damage para Death spells e runes"), (7.5, "%", "critical extra damage para Death spells e runes"))
        self.assertEqual(pf.valor_e_rotulo("+1 Magic Level"), (1, "", "Magic Level"))
        self.assertEqual(pf.valor_e_rotulo("+1,00% de penetração de armadura aproximadamente"), (1.0, "%", "de penetração de armadura aproximadamente"))
        self.assertEqual(pf.valor_e_rotulo("-20% algo"), (-20, "%", "algo"))
        self.assertIsNone(pf.valor_e_rotulo("texto sem número"))

    def test_opcao_de_shaping_e_valor_por_rank(self):
        o = pf.opcao_do_wikitext("Armor Penetration", OPCAO)
        self.assertEqual((o["nome"], o["voc"], o["rank0"], o["rank10"]), ("Armor Penetration", "", "+4% de penetração de armadura", "+10% de penetração de armadura"))
        self.assertEqual(pf.texto_no_rank(o, 0), "+4% de penetração de armadura")
        self.assertEqual(pf.texto_no_rank(o, 10), "+10% de penetração de armadura")
        self.assertEqual(pf.texto_no_rank(o, 5), "+7% de penetração de armadura")          # reta entre o rank 0 e o rank 10
        v = pf.opcao_do_wikitext("Spell Augment Death Echo Life Leech", OPCAO_VOC)
        self.assertEqual(v["voc"], "sorcerer")
        self.assertEqual(pf.texto_no_rank(v, 5), "+6.5% de life leech para Death Echo")
        self.assertIsNone(pf.opcao_do_wikitext("X", "sem infobox"))


class TestEfeitos(unittest.TestCase):
    def setUp(self):
        self.cols = pf.perks_da_wikitext(SOULTAINTER)
        self.arma = {"nome": "Soultainter", "perks": self.cols}

    def _soma(self, prof, opcoes=()):
        return pf.efeitos({**self.arma, "prof": prof}, opcoes)

    def test_padrao_primeira_opcao_de_cada_coluna(self):
        e = pf.efeitos(self.arma)                                                    # sem "prof": nível 7, primeira opção
        rotulos = {x["rotulo"]: x["valor"] for x in e["lista"]}
        self.assertEqual(rotulos["critical extra damage"], 15)                       # 5 (coluna 1) + 10 (coluna 6)
        self.assertEqual(rotulos["critical hit chance"], 1)
        self.assertEqual(rotulos["Death Magic Level"], 2)
        self.assertEqual(rotulos["critical extra damage para Death spells e runes"], 7.5)
        self.assertEqual(rotulos["critical hit chance para Great Death Beam"], 2)
        self.assertEqual(rotulos["critical hit chance para Death spells e runes"], 1.5)

    def test_nivel_libera_so_as_primeiras_colunas(self):
        rotulos = {x["rotulo"] for x in self._soma({"nivel": 1})["lista"]}
        self.assertEqual(rotulos, {"critical extra damage"})                         # só a coluna 1
        self.assertEqual(self._soma({"nivel": 0})["lista"], [])

    def test_escolha_por_coluna(self):
        rotulos = {x["rotulo"]: x["valor"] for x in self._soma({"nivel": 2, "escolhas": [0, 1]})["lista"]}
        self.assertEqual(rotulos, {"critical extra damage": 5, "Magic Level": 1})
        fora = {x["rotulo"] for x in self._soma({"nivel": 2, "escolhas": [0, 9]})["lista"]}   # escolha inválida volta para a primeira
        self.assertIn("critical extra damage para Death spells e runes", fora)

    def test_trocas_do_perk_shaping(self):
        op = pf.opcao_do_wikitext("Armor Penetration", OPCAO)
        t1 = {"coluna": 2, "opcao": "Armor Penetration", "rank": 10}
        r = {x["rotulo"]: x["valor"] for x in self._soma({"nivel": 2, "trocas": [t1]}, [op])["lista"]}
        self.assertEqual(r, {"critical extra damage": 5, "penetração de armadura": 10})   # trocou o perk da coluna 2
        t2 = {"coluna": 1, "opcao": "Armor Penetration", "rank": 0}
        sem_maestria = self._soma({"nivel": 2, "trocas": [t1, t2]}, [op])["lista"]
        self.assertEqual(len(sem_maestria), 2)                                       # a 2ª troca exige Maestria: ignorada
        com = {x["rotulo"]: x["valor"] for x in self._soma({"nivel": 2, "maestria": True, "trocas": [t1, t2]}, [op])["lista"]}
        self.assertEqual(com, {"penetração de armadura": 14})                     # 10 (rank 10) + 4 (rank 0), colunas 1 e 2 trocadas
        nivel0 = self._soma({"nivel": 0, "trocas": [t1]}, [op])["lista"]
        self.assertEqual(nivel0, [])                                                 # troca exige ao menos 1 nível
        fora = self._soma({"nivel": 1, "trocas": [t1]}, [op])["lista"]               # coluna 2 ainda não liberada
        self.assertEqual({x["rotulo"] for x in fora}, {"critical extra damage"})


if __name__ == "__main__":
    unittest.main()
