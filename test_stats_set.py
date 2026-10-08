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
        self.assertEqual(self.s["resist"], {"energy": 8, "physical": 3, "ice": -2, "fire": 5, "death": 14.5})   # trinket 5 e Lich Shroud 10 combinam multiplicando: 1 - (0,95 x 0,90)
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


class TestProficiencia(unittest.TestCase):
    COLS = [[{"tipo": "Type_Critical_Dmg", "texto": "+5.00% critical extra damage"}],
            [{"tipo": "Type_Skill_Magic", "texto": "+1 Magic Level"}, {"tipo": "X", "texto": "+7.50% critical extra damage para Death spells e runes"}],
            [{"tipo": "Type_Critical_Chance", "texto": "+1.00% critical hit chance"}],
            [{"tipo": "Type_Life", "texto": "+2% life leech"}],
            [{"tipo": "Type_Attack", "texto": "+3 attack"}]]

    def _set(self, prof=None):
        arma = {"nome": "Soultainter", "perks": self.COLS, "attrib": "magic level +4"}
        if prof is not None:
            arma["prof"] = prof
        return sets.normalizar_set({"titulo": "x", "itens": {"arma": arma, "anel": {"nome": "R", "attrib": "magic level +1"}}})

    def test_perks_globais_somam_nas_linhas_normais(self):
        s = ss.somar(self._set())
        self.assertEqual(s["crit"], {"dano": 5, "chance": 1})
        self.assertEqual(s["leech"], {"life": 2})
        self.assertEqual(s["attack"], 3)
        self.assertEqual(s["skills"], {"magic level": 6})                    # 4 do item + 1 do anel + 1 do perk da coluna 2 (1ª opção)

    def test_perks_condicionais_ficam_a_parte(self):
        s = ss.somar(self._set({"nivel": 7, "escolhas": [0, 1]}))
        self.assertEqual(s["perks"], {"critical extra damage para Death spells e runes": {"valor": 7.5, "unidade": "%"}})
        self.assertEqual(s["skills"], {"magic level": 5})                    # escolheu a opção 2 da coluna 2: sem o +1 Magic Level
        linhas = {l["chave"]: l for l in ss.linhas(s)}
        l = linhas["perk:critical extra damage para Death spells e runes"]
        self.assertEqual((l["grupo"], l["misc"], l["rotulo"], l["texto"]), ("Ataque", True, "Critical extra damage para Death spells e runes", "+7.5%"))

    def test_nivel_e_trocas_mudam_a_soma(self):
        self.assertEqual(ss.somar(self._set({"nivel": 1}))["crit"], {"dano": 5})
        op = {"nome": "Armor Penetration", "perk": "", "voc": "", "descricao": "", "rank0": "+4% de penetração de armadura", "rank10": "+10% de penetração de armadura"}
        s = ss.somar(self._set({"nivel": 3, "trocas": [{"coluna": 3, "opcao": "Armor Penetration", "rank": 10}]}), opcoes=[op])
        self.assertEqual(s["perks"], {"penetração de armadura": {"valor": 10, "unidade": "%"}})
        self.assertNotIn("chance", s["crit"])                                # a coluna 3 foi trocada


class TestHunt(unittest.TestCase):
    def _l(self, set_=None, prey=None, charms=None, roda=None):
        return {l["chave"]: l for l in ss.linhas_hunt(set_, prey, charms, roda)}

    def test_prey(self):
        l = self._l(prey=[{"tipo": "ataque", "estrelas": 10, "criatura": "Gloom Maw"}, {"tipo": "xp", "estrelas": 7}, {"tipo": "defesa", "estrelas": 1}])
        self.assertEqual((l["prey:ataque"]["valor"], l["prey:ataque"]["texto"], l["prey:ataque"]["grupo"]), (25, "+25%", "Prey"))
        self.assertIn("Gloom Maw", l["prey:ataque"]["detalhe"])
        self.assertEqual((l["prey:xp"]["valor"], l["prey:defesa"]["valor"]), (31, 12))
        self.assertEqual(l["prey:defesa"]["texto"], "-12%")                    # defesa: menos dano recebido
        self.assertNotIn("prey:loot", l)

    def test_charms(self):
        l = self._l(charms=[{"nome": "Low Blow", "criatura": "Varg", "nivel": 3}, {"nome": "Wound", "criatura": "Gloom Maw", "nivel": 1}, {"nome": "Inexistente", "nivel": 1}])
        self.assertEqual((l["charm:Low Blow"]["valor"], l["charm:Low Blow"]["texto"], l["charm:Low Blow"]["grupo"]), (9, "9%", "Charms"))
        self.assertIn("Varg", l["charm:Low Blow"]["detalhe"])
        self.assertIn("nível 3", l["charm:Low Blow"]["detalhe"])
        self.assertEqual(l["charm:Wound"]["valor"], 5)
        self.assertNotIn("charm:Inexistente", l)

    def test_roda_a_partir_do_resumo_do_planner(self):
        secoes = [{"titulo": "Dedication Perks", "linhas": ["Hit Points", "+1,500", "Mana", "+350", "Mitigation Multiplier", "22.50%"]},
                  {"titulo": "Conviction Perks", "linhas": ["Battle Instinct", "Weapon Skill Boost", "+1", "Life Leech", "+0.75%", "Augmented Shield Slam", "I", "Mana Leech", "+0.25%", "Vessel Resonance Top Left", "III"]},
                  {"titulo": "Revelation Perks", "linhas": ["Damage and Healing", "+20", "Avatar of Steel", "Locked", "Gift of Life", "Stage 3"]},
                  {"titulo": "Vessels", "linhas": ["none"]}]
        l = self._l(roda=secoes)
        self.assertEqual((l["roda:Hit Points"]["valor"], l["roda:Hit Points"]["texto"], l["roda:Hit Points"]["grupo"]), (1500, "+1,500", "Roda"))
        self.assertEqual((l["roda:Mitigation Multiplier"]["valor"], l["roda:Mitigation Multiplier"]["texto"]), (22.5, "22.50%"))
        self.assertEqual(l["roda:Weapon Skill Boost"]["valor"], 1)
        self.assertEqual(l["leech:life"]["valor"], 0.75)                       # leech e "Damage and Healing" da roda vão para os totais
        self.assertEqual(l["flat"]["valor"], 20)
        self.assertNotIn("roda:Life Leech", l)
        self.assertNotIn("roda:Damage and Healing", l)
        self.assertEqual((l["roda:Augmented Shield Slam"]["valor"], l["roda:Augmented Shield Slam"]["texto"]), (None, "I"))   # só texto
        self.assertEqual((l["roda:Battle Instinct"]["valor"], l["roda:Battle Instinct"]["texto"]), (None, "ativo"))
        self.assertEqual(l["roda:Gift of Life"]["texto"], "Stage 3")
        self.assertEqual((l["roda:Avatar of Steel"]["valor"], l["roda:Avatar of Steel"]["pontos"]), (None, {"tipo": "revelacao", "n": 0, "de": 3}))   # "Locked": aparece com as bolinhas vazias
        self.assertEqual(l["roda:Gift of Life"]["pontos"], {"tipo": "revelacao", "n": 3, "de": 3})               # "Stage 3": 3 de 3
        self.assertEqual(l["roda:Augmented Shield Slam"]["pontos"], {"tipo": "aumento", "n": 1, "de": 3})        # "I": 1 de 3 losangos
        self.assertEqual(l["roda:Vessel Resonance Top Left"]["pontos"], {"tipo": "gema", "n": 3, "de": 3})
        self.assertNotIn("pontos", l["roda:Hit Points"])
        self.assertNotIn("roda:none", l)

    def test_junta_com_o_set(self):
        s = sets.normalizar_set({"titulo": "x", "itens": {"cabeca": {"nome": "H", "armor": 8}}})
        l = self._l(set_=s, prey=[{"tipo": "xp", "estrelas": 1}])
        self.assertEqual((l["armor"]["valor"], l["prey:xp"]["valor"]), (8, 13))
        grupos = [x["grupo"] for x in ss.linhas_hunt(s, [{"tipo": "xp", "estrelas": 1}], [{"nome": "Wound", "nivel": 1}], [{"titulo": "t", "linhas": ["Mana", "+1"]}])]
        self.assertEqual(grupos, sorted(grupos, key=["Defesa", "Ataque", "Skills", "Perks da arma", "Prey", "Charms", "Roda", "Outros"].index))


class TestLinhas(unittest.TestCase):
    def test_linhas_para_a_tela(self):
        linhas = {l["chave"]: l for l in ss.linhas(ss.somar(SET))}
        self.assertEqual((linhas["armor"]["rotulo"], linhas["armor"]["valor"], linhas["armor"]["texto"]), ("Armor Value", 23, "23"))
        self.assertEqual((linhas["resist:energy"]["rotulo"], linhas["resist:energy"]["texto"]), ("Energy", "+8%"))
        self.assertEqual(linhas["resist:ice"]["texto"], "-2%")
        self.assertEqual((linhas["skill:magic level"]["rotulo"], linhas["skill:magic level"]["texto"]), ("Magic Level", "+2"))
        self.assertEqual(linhas["leech:mana"]["texto"], "8%")
        self.assertEqual(linhas["crit:dano"]["rotulo"], "Critical Hit: Extra Damage")
        self.assertEqual(linhas["conv:fire"]["texto"], "50%")
        self.assertEqual(linhas["atk_elem:ice"]["valor"], 46)
        self.assertEqual(linhas["extra:faster regeneration"]["texto"], "Faster Regeneration")
        self.assertEqual((linhas["resist:holy"]["rotulo"], linhas["resist:holy"]["texto"]), ("Holy", "+0%"))   # como o Tibia: os 7 elementos sempre aparecem
        grupos = [l["grupo"] for l in ss.linhas(ss.somar(SET))]
        self.assertEqual(grupos, sorted(grupos, key=["Defesa", "Ataque", "Skills", "Perks da arma", "Outros"].index))   # agrupadas na ordem da tela


if __name__ == "__main__":
    unittest.main()
