"""Testes do Combat Stats no formato do Tibia: de onde vem cada valor, resistências que multiplicam e itens "misc".  Rodar: python -m unittest"""

import unittest
from unittest import mock

import sets
import stats_set as ss

EK = sets.normalizar_set({"titulo": "EK", "itens": {
    "cabeca": {"nome": "Zaoan Helmet", "armor": 9, "resist": {"physical": 5}, "imbue": 1, "imbues": ["Powerful Void"]},
    "armadura": {"nome": "Prismatic Armor", "armor": 15, "attrib": "speed +15", "resist": {"physical": 5}, "imbue": 1, "imbues": ["Powerful Vampirism"]},
    "pernas": {"nome": "Zaoan Legs", "armor": 8, "resist": {"physical": 2}},
    "botas": {"nome": "Depth Calcei", "armor": 3, "attrib": "speed -5", "resist": {"physical": 5}},
    "amuleto": {"nome": "Lightning Pendant", "resist": {"energy": 20, "earth": -10}},
    "anel": {"nome": "Sword Ring", "attrib": "sword fighting +4"},
    "arma": {"nome": "Havoc Blade", "tipo": "Sword Weapons", "attack": 49, "defense": 34, "imbue": 3, "imbues": ["Powerful Void", "Powerful Strike", "Powerful Vampirism"],
             "perks": [[{"tipo": "T", "texto": "+4.00% do seu Sword Fighting como extra damage para auto-attacks"}],
                       [{"tipo": "T", "texto": "+2.00% critical extra damage"}],
                       [{"tipo": "T", "texto": "+3.00% critical extra damage"}],
                       [{"tipo": "T", "aug": "Critical_Chance", "texto": "+5% critical hit chance para Front Sweep"}]],
             "prof": {"nivel": 4, "escolhas": [0, 0, 0, 0], "trocas": []}},
}})


class TestResistenciasMultiplicam(unittest.TestCase):
    def test_como_no_tibia(self):
        s = ss.somar(EK)
        self.assertEqual(s["resist"]["physical"], 15.98)             # 1 - (0,95 x 0,95 x 0,98 x 0,95), como o Tibia mostra
        self.assertEqual((s["resist"]["energy"], s["resist"]["earth"]), (20, -10))
        l = {x["chave"]: x for x in ss.linhas(s)}
        self.assertEqual(l["resist:physical"]["texto"], "+15.98%")
        self.assertEqual([f["valor"] for f in l["resist:physical"]["fontes"]], [15.98])        # uma origem só: o equipamento
        self.assertEqual({f["origem"] for f in l["resist:physical"]["fontes"]}, {"Equipamento"})

    def test_roda_e_embuimento_tambem_multiplicam(self):
        s = ss.somar(EK, extras=[("Roda", {"resist": {"energy": 2}})])
        self.assertEqual(s["resist"]["energy"], 21.6)                # 1 - (0,80 x 0,98)
        com_imb = sets.normalizar_set({"titulo": "x", "itens": {"armadura": {"nome": "A", "resist": {"fire": 10}, "imbue": 1, "imbues": ["Powerful Dragon Hide"]}}})
        self.assertEqual(ss.somar(com_imb)["resist"]["fire"], 23.5)   # 1 - (0,90 x 0,85)
        l = {x["chave"]: x for x in ss.linhas(ss.somar(com_imb))}
        self.assertEqual([f["origem"] for f in l["resist:fire"]["fontes"]], ["Equipamento", "Embuimento"])


class TestFontes(unittest.TestCase):
    def test_critico_com_a_origem_de_cada_parte(self):
        s = ss.somar(EK)
        l = {x["chave"]: x for x in ss.linhas(s)}
        self.assertEqual(l["crit:dano"]["valor"], 45)                # 40 do embuimento + 2 + 3 da proficiência
        self.assertEqual([(f["origem"], f["valor"]) for f in l["crit:dano"]["fontes"]], [("Embuimento", 40), ("Proficiência", 5)])
        self.assertEqual([(f["origem"], f["valor"]) for f in l["leech:life"]["fontes"]], [("Embuimento", 50)])
        self.assertEqual([(f["origem"], f["valor"]) for f in l["leech:mana"]["fontes"]], [("Embuimento", 16)])
        self.assertEqual([(f["origem"], f["valor"]) for f in l["skill:speed"]["fontes"]], [("Equipamento", 10)])

    def test_perk_de_spell_especifica_e_misc(self):
        l = {x["chave"]: x for x in ss.linhas(ss.somar(EK))}
        misc = l["perk:critical hit chance para Front Sweep"]
        self.assertEqual((misc["grupo"], misc["misc"], misc["valor"], misc["texto"]), ("Ataque", True, 5, "+5%"))   # no Tibia fica em Misc; aqui fica no ataque, marcado
        self.assertEqual(misc["fontes"][0]["origem"], "Proficiência")
        auto = l["perk:do seu Sword Fighting como extra damage para auto-attacks"]
        self.assertTrue(auto["misc"])
        self.assertFalse(l["crit:dano"].get("misc"))


class TestNomesEOrdemDoTibia(unittest.TestCase):
    def test_mesmos_nomes_e_ordem_da_aba_do_tibia(self):
        rot = [(x["chave"], x["rotulo"]) for x in ss.linhas_hunt(EK, nivel=170) if x["grupo"] in ("Defesa", "Ataque") and not x.get("misc")]
        defesa = [r for r in rot if r[0] in ("armor", "defense") or r[0].startswith("resist:")]
        self.assertEqual([r[1] for r in defesa], ["Defence Value", "Armor Value", "Physical", "Fire", "Earth", "Energy", "Ice", "Holy", "Death"])
        ataque = [r[1] for r in rot if r[0] in ("flat", "leech:life", "leech:mana", "crit:chance", "crit:dano")]
        self.assertEqual(ataque, ["Flat Damage and Healing", "Life Leech", "Mana Leech", "Critical Hit: Chance", "Critical Hit: Extra Damage"])

    def test_com_skills_defence_value_vem_antes_do_armor_e_attack_value_depois_do_flat(self):
        l = ss.linhas_hunt(EK, nivel=170, skills={"base": {"sword fighting": 112}})
        chaves = [x["chave"] for x in l if x["grupo"] in ("Defesa", "Ataque") and not x.get("misc")]
        self.assertLess(chaves.index("defencevalue"), chaves.index("armor"))
        self.assertLess(chaves.index("flat"), chaves.index("attackvalue"))
        self.assertLess(chaves.index("attackvalue"), chaves.index("leech:life"))
        self.assertNotIn("attack", chaves)                                   # o Attack Value substitui o ataque simples da arma


class TestBonusFixoEFlat(unittest.TestCase):
    def test_bonus_fixo_do_personagem_e_flat_damage(self):
        l = {x["chave"]: x for x in ss.linhas_hunt(EK, nivel=170)}
        self.assertEqual((l["crit:chance"]["valor"], l["crit:dano"]["valor"]), (10, 55))             # 5/10 do bônus fixo + embuimento + proficiência
        self.assertEqual([(f["origem"], f["valor"]) for f in l["crit:chance"]["fontes"]], [("Bônus fixo", 5), ("Embuimento", 5)])
        self.assertEqual([(f["origem"], f["valor"]) for f in l["crit:dano"]["fontes"]], [("Bônus fixo", 10), ("Embuimento", 40), ("Proficiência", 5)])
        self.assertEqual(l["flat"]["valor"], 34)                                                      # nível 170 / 5
        self.assertEqual([(f["origem"], f["valor"]) for f in l["flat"]["fontes"]], [("Nível", 34)])
        sem_nivel = {x["chave"]: x for x in ss.linhas_hunt(EK)}
        self.assertNotIn("flat", sem_nivel)

    def test_roda_entra_nos_totais(self):
        roda = [{"titulo": "Vessels", "linhas": ["Damage and Healing", "+1", "Energy Resistance", "+2%"]},
                {"titulo": "Conviction Perks", "linhas": ["Life Leech", "+0.75%", "Mana Leech", "+0.25%"]},
                {"titulo": "Revelation Perks", "linhas": ["Damage and Healing", "+0"]}]
        l = {x["chave"]: x for x in ss.linhas_hunt(EK, roda=roda, nivel=170)}
        self.assertEqual(l["flat"]["valor"], 35)                                                      # 34 do nível + 1 da roda
        self.assertEqual([(f["origem"], f["valor"]) for f in l["flat"]["fontes"]], [("Nível", 34), ("Roda", 1)])
        self.assertEqual(l["resist:energy"]["valor"], 21.6)                                           # 20 do equipamento + 2 da roda, multiplicando
        self.assertEqual(l["leech:life"]["valor"], 50.75)
        self.assertEqual(l["leech:mana"]["valor"], 16.25)
        for ja_somado in ("roda:Damage and Healing", "roda:Energy Resistance", "roda:Life Leech", "roda:Mana Leech"):
            self.assertNotIn(ja_somado, l)                                                            # não aparecem duas vezes

    def test_augment_da_roda_vira_misc_com_o_texto_do_planner(self):
        strings = {"MediumPerkInfos": {"12": {"Aug1Info": "+40% Base Damage", "Aug2Info": "Expanded Shape", "Name": "Augmented Front Sweep|Aug. Front Sweep"}}}
        roda = [{"titulo": "Conviction Perks", "linhas": ["Augmented Front Sweep", "I"]}]
        with mock.patch.object(ss, "_strings_roda", return_value=strings):
            l = {x["chave"]: x for x in ss.linhas_hunt(None, roda=roda)}
            self.assertEqual((l["aug:Front Sweep:Base Damage"]["valor"], l["aug:Front Sweep:Base Damage"]["misc"], l["aug:Front Sweep:Base Damage"]["grupo"]), (40, True, "Ataque"))
            self.assertEqual(l["aug:Front Sweep:Base Damage"]["fontes"][0]["origem"], "Roda (augment)")
            self.assertNotIn("aug:Front Sweep:Expanded Shape", l)                                     # nível I = só o 1º efeito
            nivel2 = [{"titulo": "Conviction Perks", "linhas": ["Augmented Front Sweep", "II"]}]
            l2 = {x["chave"]: x for x in ss.linhas_hunt(None, roda=nivel2)}
            self.assertIn("aug:Front Sweep:Expanded Shape", l2)                                       # nível II = os dois
            self.assertIsNone(l2["aug:Front Sweep:Expanded Shape"]["valor"])


if __name__ == "__main__":
    unittest.main()
