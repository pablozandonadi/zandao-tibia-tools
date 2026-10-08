"""Testes das posturas (stance spells) da hunt.  Rodar: python -m unittest"""

import unittest

import posturas as po


class TestPosturas(unittest.TestCase):
    def test_lista_por_vocacao(self):
        self.assertEqual([p["nome"] for p in po.listar("sorcerer")], ["Master of Decay", "Master of Flames", "Master of Thunder"])
        self.assertEqual([p["nome"] for p in po.listar("knight")], ["Blood Rage", "Protector"])
        self.assertEqual(len(po.listar("druid")), 4)
        self.assertEqual(len(po.listar("paladin")), 3)
        self.assertEqual(len(po.listar("monk")), 3)
        self.assertEqual(len(po.listar("")), 15)                         # sem vocação: todas
        self.assertEqual(len(po.listar("mago")), 15)

    def test_normalizar(self):
        self.assertIsNone(po.normalizar_postura(None))                   # None = não informada (hunts antigas)
        self.assertEqual(po.normalizar_postura(""), "")                  # "" = sem postura
        self.assertEqual(po.normalizar_postura("Master of Decay"), "Master of Decay")
        self.assertEqual(po.normalizar_postura("  master of decay "), "Master of Decay")   # acha sem diferenciar maiúsculas
        self.assertEqual(po.normalizar_postura("Inexistente"), "")
        self.assertEqual(po.normalizar_postura(7), "")
        self.assertEqual(po.rotulo_postura(None), "Postura não informada")
        self.assertEqual(po.rotulo_postura(""), "Sem postura")
        self.assertEqual(po.rotulo_postura("Blood Rage"), "Postura: Blood Rage")

    def test_linhas_do_combat_stats(self):
        l = {x["chave"]: x for x in po.linhas("Master of Decay")}
        self.assertEqual(l["postura:crit_dano_death"]["valor"], 30)
        self.assertEqual((l["postura:crit_dano_death"]["grupo"], l["postura:crit_dano_death"]["texto"]), ("Postura", "+30%"))
        self.assertIn("Death", l["postura:crit_dano_death"]["rotulo"])
        self.assertIn("próxima spell", l["postura:crit_dano_death"]["detalhe"])   # o efeito completo vai no detalhe
        b = {x["chave"]: x["valor"] for x in po.linhas("Blood Rage")}
        self.assertEqual(b, {"postura:skill_melee": 25, "postura:dano_recebido": 15})
        p = {x["chave"]: x["valor"] for x in po.linhas("Protector")}
        self.assertEqual(p, {"postura:shielding": 30, "postura:dano_recebido": -15, "postura:dano_causado": -15})
        self.assertEqual(po.linhas(""), [])
        self.assertEqual(po.linhas(None), [])
        sniper = po.linhas("Sniper")                                      # a wiki não descreve o efeito: só mostra a postura
        self.assertEqual([x["valor"] for x in sniper], [None])


if __name__ == "__main__":
    unittest.main()
