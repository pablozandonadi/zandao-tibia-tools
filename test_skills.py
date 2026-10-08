"""Testes das skills do personagem (base, sem itens) e do que sai delas: Attack Value, Defence Value e auto-attack.  Rodar: python -m unittest"""

import os
import tempfile
import unittest

import personagens
import posturas
import sets
import stats_set as ss

# o set do print do Tibia (Elite Knight level 170): Havoc Blade 49/34 e Sword Ring +4
SET = sets.normalizar_set({"titulo": "EK", "itens": {
    "arma": {"nome": "Havoc Blade", "tipo": "Sword Weapons", "attack": 49, "defense": 34,
             "perks": [[{"tipo": "T", "texto": "+4.00% do seu Sword Fighting como extra damage para auto-attacks"}]], "prof": {"nivel": 1}},
    "anel": {"nome": "Sword Ring", "attrib": "sword fighting +4"},
}})


class TestSkillsDoPersonagem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arq = os.path.join(self.tmp.name, "p.json")
        personagens._gravar({"lista": [{"nome": "Elite Nestos", "level": 170, "vocacao": "Elite Knight"}], "atual": "Elite Nestos"}, self.arq)

    def tearDown(self):
        self.tmp.cleanup()

    def test_salvar_e_ler(self):
        d = personagens.salvar_skills("elite nestos", {"sword fighting": 112, "shielding": "109", "lixo": 5, "axe fighting": -3, "club fighting": "x"}, "balanced", self.arq)
        p = d["lista"][0]
        self.assertEqual(p["skills"], {"sword fighting": 112, "shielding": 109})       # só skills conhecidas, números válidos
        self.assertEqual(p["modo"], "balanced")
        self.assertEqual(personagens.carregar(self.arq)["lista"][0]["skills"]["sword fighting"], 112)
        self.assertEqual(personagens.salvar_skills("Elite Nestos", {}, "qualquer", self.arq)["lista"][0]["modo"], "offensive")   # modo inválido volta ao padrão
        self.assertIsNone(personagens.salvar_skills("Ninguém", {"sword fighting": 1}, "offensive", self.arq))

    def test_atualizar_level_nao_apaga_as_skills(self):
        personagens.salvar_skills("Elite Nestos", {"sword fighting": 112}, "offensive", self.arq)
        d = personagens.atualizar_levels(self.arq, forcar=True, buscar_varios=lambda nomes: {"Elite Nestos": {"nome": "Elite Nestos", "level": 171, "vocacao": "Elite Knight"}})
        self.assertEqual((d["lista"][0]["level"], d["lista"][0]["skills"]), (171, {"sword fighting": 112}))
        d = personagens.adicionar("Elite Nestos", self.arq, buscar=lambda n: {"nome": "Elite Nestos", "level": 172, "vocacao": "Elite Knight"})[0]
        self.assertEqual(d["lista"][0]["skills"], {"sword fighting": 112})                # re-adicionar também preserva


class TestPelaApiEPeloComparativo(unittest.TestCase):
    def test_api_usa_as_skills_do_personagem(self):
        from unittest import mock
        import web_api
        api = object.__new__(web_api.API)
        dados = {"lista": [{"nome": "Elite Nestos", "level": 170, "skills": {"sword fighting": 112}, "modo": "offensive"}], "atual": "Elite Nestos"}
        with mock.patch.object(personagens, "carregar", return_value=dados):
            l = {x["chave"]: x for x in api.hunt_stats(SET, [], [], None, "", 170, "elite nestos")}
            self.assertEqual((l["attackvalue"]["valor"], l["defencevalue"]["valor"]), (282, 107))    # sem a roda o flat é 34 (e não 35): 34 + 248
            sem = {x["chave"] for x in api.hunt_stats(SET, [], [], None, "", 170, "Outro")}          # personagem sem skills: como antes
            self.assertNotIn("attackvalue", sem)
            r = api.personagem_skills("Elite Nestos", {"sword fighting": 120}, "balanced")
        self.assertIsNotNone(r)

    def test_comparativo_usa_as_skills_de_cada_personagem(self):
        from unittest import mock
        import historico
        a = {"id": "a", "nome": "A", "personagem": "Elite Nestos", "set": SET, "resumo": {"minutos": 60, "membros": 1}, "monstros": []}
        dados = {"lista": [{"nome": "Elite Nestos", "level": 170, "skills": {"sword fighting": 112}, "modo": "offensive"}], "atual": ""}
        with mock.patch.object(personagens, "carregar", return_value=dados):
            linhas = {l["chave"]: l for l in historico.comparar([a, dict(a, id="b", nome="B")])["stats_set"]}
        self.assertEqual(linhas["attackvalue"]["valores"], [282, 282])


class TestAttackEDefence(unittest.TestCase):
    def _l(self, base, postura="", nivel=170, modo="offensive", roda=None):
        return {x["chave"]: x for x in ss.linhas_hunt(SET, postura=postura, nivel=nivel, roda=roda, skills={"base": base, "modo": modo})}

    def test_bate_com_os_prints_do_tibia(self):
        l = self._l({"sword fighting": 146}, roda=[{"titulo": "Vessels", "linhas": ["Damage and Healing", "+1"]}])
        self.assertEqual(l["skillfinal:sword fighting"]["valor"], 150)                 # 146 base + 4 do anel
        self.assertEqual(l["attackvalue"]["valor"], 354)                                # print 1: 35 flat + 49 equipamento + 220 skill + 50 tática
        self.assertEqual([(f["origem"], f["valor"]) for f in l["attackvalue"]["fontes"]],
                         [("Bônus fixo", 35), ("Equipamento", 49), ("Skill", 220), ("Tática de combate", 50)])
        self.assertEqual(l["defencevalue"]["valor"], 136)                               # print 2: 34 do equipamento + 102 do Sword Fighting
        self.assertEqual([(f["origem"], f["valor"]) for f in l["defencevalue"]["fontes"]], [("Equipamento", 34), ("Skill", 102)])
        self.assertNotIn("defense", l)                                                  # o Defence Value substitui a soma simples
        l2 = self._l({"sword fighting": 112}, roda=[{"titulo": "Vessels", "linhas": ["Damage and Healing", "+1"]}])
        self.assertEqual((l2["attackvalue"]["valor"], l2["defencevalue"]["valor"]), (283, 107))   # prints com o Sword em 116
        self.assertEqual(l2["autoextra"]["valor"], 5)                                   # 4% de 116 = 4,64 -> 5 (no print: 5 from Sword Fighting)
        self.assertEqual(self._l({"sword fighting": 146})["autoextra"]["valor"], 6)     # 4% de 150 = 6

    def test_modos_de_combate_e_postura(self):
        self.assertEqual(self._l({"sword fighting": 112}, modo="balanced")["attackvalue"]["valor"], 34 + 210)   # 34 do nível + 49 x 120 / 28
        self.assertEqual(self._l({"sword fighting": 112}, modo="defensive")["attackvalue"]["valor"], 34 + int(30 * 120 / 28))   # ceil(0,6 x 49) = 30
        l = self._l({"sword fighting": 112}, postura="Blood Rage")                      # print: Sword 116 -> 145 com a postura
        self.assertEqual(l["skillfinal:sword fighting"]["valor"], 145)
        self.assertEqual([(f["origem"], f["valor"]) for f in l["skillfinal:sword fighting"]["fontes"]], [("Base", 112), ("Equipamento", 4), ("Postura", 29)])
        self.assertEqual(l["defencevalue"]["valor"], 131)                               # 34 x (145 + 10) / 40

    def test_com_escudo_vale_o_shielding(self):
        com_escudo = sets.normalizar_set({"titulo": "x", "itens": {"arma": {"nome": "Espada", "tipo": "Sword Weapons", "attack": 40, "defense": 10},
                                                                   "mao": {"nome": "Escudo", "defense": 30}}})
        l = {x["chave"]: x for x in ss.linhas_hunt(com_escudo, postura="Protector", nivel=100, skills={"base": {"sword fighting": 100, "shielding": 109}})}
        self.assertEqual(l["skillfinal:shielding"]["valor"], 141)                       # 109 x 1,3 (postura Protector)
        self.assertEqual(l["defencevalue"]["valor"], 113)                               # com escudo só ele conta: 30 x (141 + 10) / 40

    def test_sem_skills_continua_como_antes(self):
        l = {x["chave"]: x for x in ss.linhas_hunt(SET, nivel=170)}
        self.assertNotIn("attackvalue", l)
        self.assertEqual(l["defense"]["valor"], 34)


if __name__ == "__main__":
    unittest.main()
