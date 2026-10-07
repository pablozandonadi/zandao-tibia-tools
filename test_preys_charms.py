"""Testes das tabelas de prey e charms.  Rodar: python -m unittest"""

import unittest

import preys_charms as pc


class TestPrey(unittest.TestCase):
    def test_bonus_por_estrela(self):
        self.assertEqual(pc.bonus_prey("ataque", 10), 25)   # Damage Boost 10★ = +25% (igual ao jogo)
        self.assertEqual(pc.bonus_prey("ataque", 1), 7)
        self.assertEqual(pc.bonus_prey("defesa", 1), 12)
        self.assertEqual(pc.bonus_prey("defesa", 10), 30)
        self.assertEqual(pc.bonus_prey("xp", 10), 40)
        self.assertEqual(pc.bonus_prey("loot", 1), 13)
        self.assertIsNone(pc.bonus_prey("xp", 11))
        self.assertIsNone(pc.bonus_prey("magia", 5))


class TestCharms(unittest.TestCase):
    def test_tabela(self):
        self.assertEqual(len(pc.CHARMS["major"]), 14)
        self.assertEqual(len(pc.CHARMS["minor"]), 11)
        self.assertEqual(pc.porcentagem_charm("Carnage", 3), 22)
        self.assertEqual(pc.porcentagem_charm("Scavenge", 2), 90)
        self.assertEqual(pc.porcentagem_charm("Void's Call", 1), 0.8)
        self.assertIsNone(pc.porcentagem_charm("Carnage", 4))

    def test_normalizar(self):
        self.assertIsNone(pc.normalizar_charms(None))
        self.assertEqual(pc.normalizar_charms("lixo"), [])
        self.assertEqual(pc.normalizar_charms([
            {"nome": "Carnage", "criatura": " Gloom Maw ", "nivel": "3"},
            {"nome": "Carnage", "criatura": "Varg", "nivel": 1},          # repetido: fica o primeiro
            {"nome": "Inventado", "nivel": 2},                            # charm que não existe
            {"nome": "Low Blow", "nivel": 0},                             # nível fora de 1..3
            {"nome": "Scavenge", "nivel": 2},                             # sem criatura vale
        ]), [{"nome": "Carnage", "criatura": "Gloom Maw", "nivel": 3}, {"nome": "Scavenge", "criatura": "", "nivel": 2}])

    def test_criatura_unica_por_categoria(self):
        # major + minor podem repetir a criatura; duas majors (ou duas minors) não: a repetida perde a criatura
        r = pc.normalizar_charms([
            {"nome": "Carnage", "criatura": "Varg", "nivel": 1},
            {"nome": "Curse", "criatura": "varg", "nivel": 2},
            {"nome": "Bless", "criatura": "Varg", "nivel": 1},
            {"nome": "Gut", "criatura": "VARG", "nivel": 2},
            {"nome": "Zap", "criatura": "Gloom Maw", "nivel": 3},
        ])
        self.assertEqual([(c["nome"], c["criatura"]) for c in r],
                         [("Carnage", "Varg"), ("Curse", ""), ("Bless", "Varg"), ("Gut", ""), ("Zap", "Gloom Maw")])
        self.assertEqual(pc.categoria_charm("Carnage"), "major")
        self.assertEqual(pc.categoria_charm("Scavenge"), "minor")
        self.assertIsNone(pc.categoria_charm("Inventado"))

    def test_icones_com_cache(self):
        import json
        import os
        import tempfile
        chamadas = []

        def falso(nomes):
            chamadas.append(len(nomes))
            return {n: f"https://wiki/{n}.png" for n in nomes}
        with tempfile.TemporaryDirectory() as tmp:
            cache = os.path.join(tmp, "c.json")
            u = pc.icones_charms(cache, falso)
            self.assertEqual(len(u), 25)
            self.assertEqual(u["Carnage"], "https://wiki/Carnage.png")
            pc.icones_charms(cache, falso)           # segunda vez vem do cache: não busca de novo
            self.assertEqual(chamadas, [25])

            def sem_internet(nomes):
                raise OSError("sem internet")
            with open(cache, "r+", encoding="utf-8") as f:   # cache vencido: usa o velho se a busca falhar
                d = json.load(f)
                d["t"] = 0
                f.seek(0)
                f.truncate()
                json.dump(d, f)
            self.assertEqual(len(pc.icones_charms(cache, sem_internet)), 25)
            self.assertEqual(pc.icones_charms(os.path.join(tmp, "nao_existe.json"), sem_internet), {})

    def test_rotulo(self):
        self.assertEqual(pc.rotulo_charms(None), "Charms não informados")
        self.assertEqual(pc.rotulo_charms([]), "Sem charms")
        self.assertEqual(pc.rotulo_charms([{"nome": "Carnage", "criatura": "", "nivel": 3}]), "1 charm")
        self.assertEqual(pc.rotulo_charms([{"nome": "Carnage", "criatura": "", "nivel": 3},
                                           {"nome": "Zap", "criatura": "", "nivel": 1}]), "2 charms")

    def test_tabelas_para_a_tela(self):
        t = pc.tabelas()
        self.assertEqual([p["tipo"] for p in t["prey"]], ["xp", "ataque", "defesa", "loot"])
        self.assertEqual(t["prey"][1]["rotulo"], "Damage Boost")
        self.assertEqual(len(t["prey"][1]["bonus"]), 10)
        self.assertEqual(t["charms"]["major"][0], {"nome": "Carnage", "pct": [10, 20, 22]})


if __name__ == "__main__":
    unittest.main()
