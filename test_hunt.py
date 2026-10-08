"""Testes do Hunt Analyser (Loot Split + Dano + histórico).  Rodar: python -m unittest

Os números da party batem com a hunt 'norfectarus pt 4x' mostrada no hunt-analyser.com:
lucro por membro 1,400,580, balance/h 2,012,809 e as três transferências do Druid Bravo.
"""

import json
import os
import tempfile
import unittest

import damage_core as dc
import historico
import hunt
import monstros

PARTY = """Session data: From 2026-10-05, 10:19:15 to 2026-10-05, 13:06:15
Session: 02:47h
Loot Type: Market
Loot: 10,743,227
Supplies: 5,140,907
Balance: 5,602,320
Knight Alfa
\tLoot: 18,814
\tSupplies: 885,395
\tBalance: -866,581
\tDamage: 12,846,796
\tHealing: 3,120,299
Druid Bravo (Leader)
\tLoot: 7,953,045
\tSupplies: 2,001,434
\tBalance: 5,951,611
\tDamage: 7,271,000
\tHealing: 2,401,000
Zandao
\tLoot: 208,950
\tSupplies: 939,992
\tBalance: -731,042
\tDamage: 11,706,807
\tHealing: 2,180,574
Paladin Charlie
\tLoot: 2,562,418
\tSupplies: 1,314,086
\tBalance: 1,248,332
\tDamage: 9,221,867
\tHealing: 1,727,574
"""

SOLO = """Session data: From 2026-10-05, 10:19:15 to 2026-10-05, 13:06:15
Session: 02:47h
Raw XP Gain: 20,487,822
XP Gain: 43,166,751
Raw XP/h: 7,360,894
XP/h: 15,509,012
Loot: 208,950
Supplies: 939,992
Balance: -731,042
Damage: 11,706,807
Damage/h: 4,206,038
Healing: 2,180,574
Healing/h: 783,439
Killed Monsters:
  1262x norcferatu heartless
  1069x norcferatu nightweaver
  894x gloom maws
Looted Items:
  12x a vampire teeth
"""

DANO = """Received Damage
Total: 1,000,000
Max-DPS: 9,876
Damage Types
  Physical 500,000 (50.0%)
  Death 300,000 (30.0%)
  Fire 200,000 (20.0%)
Damage Sources
  Norcferatu Heartless 600,000 (60.0%)
  Gloom Maw 400,000 (40.0%)
"""


class TestParty(unittest.TestCase):
    def test_numeros_do_hunt_analyser(self):
        a = hunt.montar({"party": PARTY, "solo": SOLO, "personagem": "Zandao"})
        r = a["resumo"]
        self.assertEqual(r["lucro"], 1_400_580)
        self.assertEqual(r["balance"], 5_602_320)
        self.assertEqual(r["balance_h"], 2_012_809)
        self.assertEqual(r["xp"], 43_166_751)
        self.assertEqual(r["xp_h"], 15_509_012)
        self.assertEqual(r["top_dano_nome"], "Knight Alfa")
        self.assertEqual(a["data"], "2026-10-05 10:19")
        self.assertEqual(
            [(t["pagador"], t["recebedor"], t["valor"]) for t in a["transferencias"]],
            [("Druid Bravo", "Knight Alfa", 2_267_161), ("Druid Bravo", "Zandao", 2_131_622),
             ("Druid Bravo", "Paladin Charlie", 152_248)],
        )
        self.assertEqual(a["transferencias"][0]["comando"], "transfer 2267161 to Knight Alfa")
        self.assertEqual([m["nome"] for m in a["membros"]], ["Knight Alfa", "Zandao", "Paladin Charlie", "Druid Bravo"])
        self.assertAlmostEqual(a["membros"][0]["dano_pct"], 31.3, places=1)
        zandao = next(d for d in a["detalhes"] if d["nome"] == "Zandao")
        self.assertTrue(zandao["hunt"])  # o Hunting Analyser colado fica ligado ao personagem escolhido
        self.assertEqual(zandao["fica_com"], 1_400_580)
        self.assertEqual(a["kills"][0], {"nome": "norcferatu heartless", "kills": 1262})

    def test_por_hora_dos_membros(self):
        a = hunt.montar({"party": PARTY})
        knight = next(m for m in a["membros"] if m["nome"] == "Knight Alfa")
        self.assertEqual(knight["dano_h"], 12_846_796 * 60 // 167)  # Session 02:47h = 167 min
        self.assertEqual(knight["cura_h"], 3_120_299 * 60 // 167)
        self.assertEqual(knight["balance_h"], -866_581 * 60 // 167)
        self.assertEqual(a["resumo"]["lucro_h"], 1_400_580 * 60 // 167)

    def test_parse_duracao(self):
        for txt, esperado in (("1:33", 93), ("01:33h", 93), ("1h33", 93), ("1h", 60), ("1h 33min", 93), ("45min", 45), ("93m", 93),
                              ("2:05:40", 125), (" 1:33 ", 93), ("2", None), ("abc", None), ("", None), (None, None),
                              ("1:75", None), ("0:00", None), ("0h", None)):
            self.assertEqual(hunt.parse_duracao(txt), esperado, txt)
        self.assertEqual(hunt.formatar_duracao(93), "01:33h")
        self.assertEqual(hunt.formatar_duracao(600), "10:00h")

    def test_tempo_real_corrige_tudo_por_hora(self):
        # as sessões coladas têm 02:47h; o tempo real foi 1h: todos os "/h" passam a ser o total
        a = hunt.montar({"party": PARTY, "solo": SOLO, "personagem": "Zandao", "duracao": "1:00"})
        r = a["resumo"]
        self.assertEqual((r["minutos"], r["duracao"], r["duracao_original"]), (60, "01:00h", "02:47h"))
        self.assertEqual(r["xp_h"], 43_166_751)             # em vez do XP/h de 02:47h colado do Tibia
        self.assertEqual(r["xp_raw_h"], 20_487_822)
        self.assertEqual(r["balance_h"], 5_602_320)
        self.assertEqual(r["lucro_h"], 1_400_580)
        self.assertEqual(a["solo"]["dano_h"], 11_706_807)
        self.assertEqual(a["solo"]["cura_h"], 2_180_574)
        knight = next(m for m in a["membros"] if m["nome"] == "Knight Alfa")
        self.assertEqual((knight["dano_h"], knight["cura_h"]), (12_846_796, 3_120_299))
        self.assertEqual(a["sessoes"], {"party": "02:47h", "solo": "02:47h"})
        # só o hunting analyser (solo): o balance/h também é recalculado
        b = hunt.montar({"solo": SOLO, "duracao": "1h"})
        self.assertEqual((b["resumo"]["balance_h"], b["resumo"]["minutos"]), (-731_042, 60))

    def test_sem_tempo_real_ou_invalido_usa_o_colado(self):
        sem = hunt.montar({"party": PARTY, "solo": SOLO})
        for ruim in ("", "   ", "abc", "2", "1:75"):
            com = hunt.montar({"party": PARTY, "solo": SOLO, "duracao": ruim})
            self.assertEqual(com["resumo"], sem["resumo"], ruim)
        self.assertEqual(sem["resumo"]["xp_h"], 15_509_012)          # o do Tibia, como sempre foi
        self.assertEqual(sem["resumo"]["duracao"], "02:47h")
        self.assertNotIn("duracao_original", sem["resumo"])

    def test_sessoes_diferentes_aparecem(self):
        solo_longo = SOLO.replace("Session: 02:47h", "Session: 02:53h")
        a = hunt.montar({"party": PARTY, "solo": solo_longo})
        self.assertEqual(a["sessoes"], {"party": "02:47h", "solo": "02:53h"})
        self.assertEqual(hunt.montar({"party": PARTY})["sessoes"], {"party": "02:47h", "solo": ""})

    def test_inicios_das_sessoes(self):
        # o Hunting Analyser conta desde o login; o Party começa quando o líder inicia: diferença é normal, só mostramos
        a = hunt.montar({"party": PARTY, "solo": SOLO.replace("From 2026-10-05, 10:19:15", "From 2026-10-05, 09:00:15")})
        self.assertEqual(a["inicios"], {"party": "10:19", "solo": "09:00", "solo_antes_min": 79})
        self.assertEqual(hunt.montar({"party": PARTY, "solo": SOLO})["inicios"]["solo_antes_min"], 0)
        depois = hunt.montar({"party": PARTY, "solo": SOLO.replace("From 2026-10-05, 10:19:15", "From 2026-10-05, 10:29:15")})
        self.assertEqual(depois["inicios"]["solo_antes_min"], -10)   # o Hunting Analyser começou depois do Party
        so_party = hunt.montar({"party": PARTY})["inicios"]
        self.assertEqual((so_party["party"], so_party["solo"], so_party["solo_antes_min"]), ("10:19", "", None))

    def test_por_hora_sem_duracao(self):
        a = hunt.montar({"party": PARTY.replace("Session: 02:47h", "Session: 00:00h")})
        self.assertTrue(all(m["dano_h"] is None and m["cura_h"] is None and m["balance_h"] is None for m in a["membros"]))
        self.assertIsNone(a["resumo"]["lucro_h"])

    def test_despesa_extra_e_excluido(self):
        a = hunt.montar({"party": PARTY, "despesas": [{"descricao": "boat", "valor": "400k", "pago_por": "Zandao"}]})
        self.assertEqual(a["resumo"]["despesas"], 400_000)
        self.assertEqual(a["resumo"]["lucro"], (5_602_320 - 400_000) // 4)
        b = hunt.montar({"party": PARTY, "excluidos": ["Paladin Charlie"]})
        self.assertEqual(b["resumo"]["membros"], 3)
        self.assertTrue(next(m for m in b["membros"] if m["nome"] == "Paladin Charlie")["excluido"])

    def test_detectar(self):
        self.assertEqual(hunt.detectar(PARTY), "party")
        self.assertEqual(hunt.detectar(SOLO), "solo")
        self.assertEqual(hunt.detectar(DANO), "dano")
        self.assertIsNone(hunt.detectar("bom dia"))

    def test_so_solo_e_erro(self):
        a = hunt.montar({"solo": SOLO})
        self.assertFalse(a["tem"]["party"])
        self.assertEqual(a["resumo"]["lucro"], -731_042)
        b = hunt.montar({"party": "texto qualquer"})
        self.assertTrue(b["vazio"])
        self.assertIn("party", b["erros"])


class TestDano(unittest.TestCase):
    def test_parse(self):
        d = dc.parse_damage_input(DANO)
        self.assertEqual(d["total"], 1_000_000)
        self.assertEqual(d["max_dps"], 9_876)
        self.assertEqual(d["tipos"]["death"]["pct"], 30.0)
        self.assertEqual([f["nome"] for f in d["fontes"]], ["Norcferatu Heartless", "Gloom Maw"])

    def test_analise_usa_embuimentos_certos(self):
        fichas = {
            "Norcferatu Heartless": {"resist": {"physical": 90, "earth": 110, "death": 70, "holy": 105}, "ataques": [],
                                     "fontes": {"wiki": True}},
            "Gloom Maw": {"resist": {"physical": 100, "earth": 110, "death": 75, "holy": 105}, "ataques": [],
                          "fontes": {"wiki": True}},
        }
        mons = [{"nome": n, "kills": k, "ficha": fichas[n]} for n, k in (("Norcferatu Heartless", 1262), ("Gloom Maw", 894))]
        r = dc.analisar(mons, dc.parse_damage_input(DANO), monstros.singularizar)
        self.assertEqual([e["elemento"] for e in r["elementos"]], ["physical", "death", "fire"])
        # mesma ordem da distribuição; Físico entra sem embuimento (a proteção é pelos itens)
        self.assertEqual([(p["elemento"], p["imbuement"]) for p in r["protecoes"]],
                         [("physical", None), ("death", "lichshroud"), ("fire", "dragonhide")])
        self.assertEqual(r["ofensivo"][0]["elemento"], "earth")
        self.assertEqual(r["ofensivo"][-1]["elemento"], "death")
        self.assertEqual(r["pesos"][0]["fonte"], "kills + log")
        self.assertAlmostEqual(sum(p["peso"] for p in r["pesos"]), 1.0)

    def test_damage_input_manda_mesmo_com_ataques_da_wiki(self):
        # um só monstro com ataque na wiki (Life Drain) não pode inventar Life Drain se o log real não tem
        ficha = {"resist": {}, "fontes": {"wiki": True},
                 "ataques": [{"nome": "Life Drain", "elemento": "lifedrain", "min": 0, "max": 625}]}
        mons = [{"nome": "Dworc Shadowstalker", "kills": 686, "ficha": ficha},
                {"nome": "Gloom Maw", "kills": 894, "ficha": {"resist": {}, "ataques": [], "fontes": {"wiki": True}}}]
        r = dc.analisar(mons, dc.parse_damage_input(DANO), monstros.singularizar)
        self.assertEqual([e["elemento"] for e in r["elementos"]], ["physical", "death", "fire"])
        sem_log = dc.analisar(mons, None, monstros.singularizar)
        self.assertEqual([e["elemento"] for e in sem_log["elementos"]], ["lifedrain"])
        self.assertTrue(any("1 de 2 monstros" in a for a in sem_log["avisos"]))

    def test_previsao_pelos_ataques_da_wiki(self):
        ficha = monstros.ficha_do_wikitext(WIKI_DRAGAO, "Dragon")
        self.assertEqual(ficha["hp"], 1000)
        self.assertEqual(ficha["resist"]["fire"], 0)
        self.assertEqual([a["elemento"] for a in ficha["ataques"]], ["physical", "fire", "fire"])
        self.assertEqual((ficha["ataques"][1]["min"], ficha["ataques"][1]["max"]), (100, 170))
        partes = dc.parte_por_elemento(ficha)
        self.assertAlmostEqual(sum(partes.values()), 1.0)
        self.assertGreater(partes["fire"], partes["physical"])


WIKI_DRAGAO = """{{Infobox Creature|List={{{1|}}}
| name = Dragon
| hp = 1000
| exp = 700
| abilities = {{Ability List|{{Melee|0-120}}|{{Ability|Invisibility|5|scene=}}|{{Ability|Fire Wave|100-170|fire|scene={{Scene|spell=5sqmwave}}}}|{{Ability|[[Great Fireball]]|60-140|fire}}}}
| physicalDmgMod = 100%
| fireDmgMod = 0%
| iceDmgMod = 110%
| earthDmgMod = 80%
}}"""


class TestNomes(unittest.TestCase):
    def test_singular_e_casamento(self):
        self.assertEqual(monstros.singularizar("Norcferatu Heartlesses"), "norcferatu heartless")
        self.assertEqual(monstros.singularizar("gloom maws"), "gloom maw")
        self.assertEqual(monstros.singularizar("furies"), "fury")
        lista = [{"name": "Gloom Maws", "race": "gloommaw"}, {"name": "Varg", "race": "varg"}]
        self.assertEqual(monstros.casar_criatura("gloom maw", lista)["race"], "gloommaw")
        self.assertEqual(monstros.casar_criatura("vargs", lista)["race"], "varg")
        self.assertIsNone(monstros.casar_criatura("Zandao", lista))
        self.assertIsNone(monstros.casar_criatura("Zandao", [{"name": "Pandas", "race": "panda"}]))


class TestHistorico(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arq = os.path.join(self.tmp.name, "h.json")

    def tearDown(self):
        self.tmp.cleanup()

    def _reg(self, party=PARTY, nome="pt 4x"):
        e = {"party": party, "solo": "", "dano": ""}
        return {"nome": nome, "assinatura": hunt.assinatura(e), "entrada": e, "membros": ["Zandao"],
                "personagem": "Zandao", "resumo": {"lucro": 100, "minutos": 60, "xp": 10}}

    def test_mesma_hunt_nao_duplica_e_mantem_pagos(self):
        h1 = historico.salvar(self._reg(), self.arq)
        historico.atualizar(h1["id"], self.arq, pagos=["Druid Bravo>Zandao"])
        h2 = historico.salvar(self._reg(nome="renomeada"), self.arq)
        self.assertEqual(h1["id"], h2["id"])
        todas = historico.carregar(self.arq)
        self.assertEqual(len(todas), 1)
        self.assertEqual(todas[0]["nome"], "renomeada")
        self.assertEqual(todas[0]["pagos"], ["Druid Bravo>Zandao"])

    def test_exportar_importar(self):
        historico.salvar(self._reg(), self.arq)
        historico.salvar(self._reg(party=PARTY + "\nZ", nome="outra"), self.arq)
        pacote = historico.exportar(caminho=self.arq)
        self.assertEqual(len(pacote["hunts"]), 2)
        json.dumps(pacote)  # precisa ser serializável
        destino = os.path.join(self.tmp.name, "d.json")
        self.assertEqual(historico.importar(pacote, caminho=destino), (2, 0))
        self.assertEqual(historico.importar(pacote, caminho=destino), (0, 2))  # somar não duplica
        self.assertEqual(historico.importar({"formato": historico.FORMATO, "hunts": pacote["hunts"][:1]},
                                            substituir=True, caminho=destino), (1, 0))
        self.assertEqual(len(historico.carregar(destino)), 1)
        with self.assertRaises(ValueError):
            historico.importar({"formato": "zandonadi-radar-export"}, caminho=destino)
        self.assertEqual(historico.totais(historico.carregar(self.arq))["lucro_h"], 100)


class TestComparar(unittest.TestCase):
    def _h(self, id_, nome, membros, minutos, lucro, balance, xp_h=None, mons=("gloom maw",), personagem="Zandao"):
        return {"id": id_, "nome": nome, "personagem": personagem, "data_hunt": "2026-10-05 10:00",
                "monstros": [{"nome": m, "kills": 100} for m in mons],
                "resumo": {"duracao": f"{minutos // 60:02d}:{minutos % 60:02d}h", "minutos": minutos, "membros": membros,
                           "lucro": lucro, "balance": balance, "loot": balance * 2, "supplies": balance, "xp_h": xp_h}}

    def test_normaliza_por_hora_e_membro(self):
        # B lucrou menos no total, mas em metade do tempo: por hora, B é melhor
        a = self._h("a", "A", 4, 120, 1_000_000, 4_000_000, xp_h=10_000_000)
        b = self._h("b", "B", 4, 60, 700_000, 2_800_000, xp_h=12_000_000)
        r = historico.comparar([a, b])
        linha = {l["chave"]: l for l in r["linhas"]}
        self.assertEqual(linha["lucro_membro_h"]["valores"], [500_000, 700_000])
        self.assertEqual(linha["lucro_membro_h"]["melhor"], 1)
        self.assertEqual(linha["lucro_membro"]["melhor"], 0)
        self.assertEqual(linha["supplies_membro_h"]["valores"], [500_000, 700_000])
        self.assertEqual(linha["supplies_membro_h"]["melhor"], 0)  # gastar menos é melhor
        self.assertTrue(any("Durações diferentes" in x for x in r["avisos"]))
        self.assertFalse(any("tamanhos" in x for x in r["avisos"]))
        self.assertIn('"B" rendeu 40% a mais de lucro por membro por hora que "A".', r["veredito"])

    def test_avisos_party_personagem_spawn(self):
        a = self._h("a", "A", 4, 60, 1, 4)
        b = self._h("b", "B", 3, 60, 1, 3, mons=("dragon lord", "dragon"), personagem="Outro")
        r = historico.comparar([a, b])
        texto = " ".join(r["avisos"])
        self.assertIn("4 x 3 membros", texto)
        self.assertIn("Personagens diferentes", texto)
        self.assertIn("outro spawn", texto)
        self.assertFalse(any("Durações" in x for x in r["avisos"]))

    def test_ranking_igual_ao_panorama(self):
        a = _reg_party("a", "2026-10-01, 10:00:00", "01:17h", 1, ["gloom maws"])
        b = _reg_party("b", "2026-10-02, 10:00:00", "02:00h", 2, ["gloom maws"])
        self.assertEqual(historico.comparar([a, b])["ranking"], historico.panorama([a, b])["jogadores"])
        self.assertEqual(historico.ranking_jogadores([a, b]), historico.panorama([a, b])["jogadores"])

    def test_ranking_usa_so_o_tempo_de_quem_estava(self):
        a = _reg_party("a", "2026-10-01, 10:00:00", "01:00h", 1, ["varg"])
        b = _reg_party("b", "2026-10-02, 10:00:00", "02:00h", 1, ["varg"])
        b["entrada"]["party"] = b["entrada"]["party"].replace("Knight Alfa", "Knight Zulu")
        r = {j["nome"]: j for j in historico.comparar([a, b])["ranking"]}
        self.assertEqual((r["Knight Alfa"]["hunts"], r["Knight Alfa"]["minutos"]), (1, 60))
        self.assertEqual(r["Knight Alfa"]["dano_h"], 12_846_796)
        self.assertEqual(r["Zandao"]["minutos"], 180)

    def _solo(self, id_, nome, minutos, xp_h, lucro, prey=None):
        h = self._h(id_, nome, 1, minutos, lucro, lucro, xp_h=xp_h)
        h["entrada"] = {"party": "", "solo": SOLO, "dano": ""}
        if prey is not None:
            h["prey"] = prey
        return h

    def test_so_hunt_analyser_nao_mostra_dados_de_party(self):
        a, b = self._solo("a", "A", 60, 10_000_000, 500_000), self._solo("b", "B", 60, 12_000_000, 600_000)
        r = historico.comparar([a, b])
        chaves = {l["chave"] for l in r["linhas"]}
        for so_party in ("membros", "balance_h", "balance", "dano_membro_h", "loot_total", "supplies_total",
                         "top_dano", "top_cura", "top_supplies", "top_loot", "top_balance"):
            self.assertNotIn(so_party, chaves, so_party)
        self.assertIn("xp_h", chaves)
        self.assertEqual(r["ranking"], [])                                   # sem ranking nem detalhe por jogador
        self.assertEqual(r["jogadores"], [])
        rotulos = {l["chave"]: l["rotulo"] for l in r["linhas"]}
        self.assertEqual((rotulos["dano_h"], rotulos["cura_h"]), ("Dano / hora", "Cura / hora"))   # não é "da party"
        self.assertTrue(all(not h["party"] for h in r["hunts"]))
        self.assertFalse(any("party" in v.lower() for v in r["veredito"]))

    def test_com_party_mantem_tudo_e_misto_nao_inventa_top(self):
        a = _reg_party("a", "2026-10-01, 10:00:00", "01:00h", 1, ["varg"])
        b = _reg_party("b", "2026-10-02, 10:00:00", "01:00h", 2, ["varg"])
        r = historico.comparar([a, b])
        chaves = {l["chave"] for l in r["linhas"]}
        self.assertTrue({"membros", "balance_h", "dano_membro_h", "top_dano", "top_cura"} <= chaves)
        self.assertTrue(r["ranking"] and all(h["party"] for h in r["hunts"]))
        solo = self._solo("s", "S", 60, 9_000_000, 400_000)
        solo["monstros"] = [{"nome": "varg", "kills": 10}]
        m = historico.comparar([a, solo])
        linha = {l["chave"]: l for l in m["linhas"]}
        self.assertIsNone(linha["top_dano"]["valores"][1])                   # quem solo bateu mais é sempre o mesmo: sem destaque
        self.assertEqual([h["party"] for h in m["hunts"]], [True, False])
        self.assertEqual(linha["dano_total"]["rotulo"], "Dano total da party")

    def test_efeito_da_prey_no_comparativo(self):
        import preys_charms
        a = self._solo("a", "A", 60, 10_000_000, 500_000, prey=[])
        b = self._solo("b", "B", 60, 12_500_000, 500_000, prey=[{"tipo": "xp", "estrelas": 7}])
        bonus = preys_charms.bonus_prey("xp", 7)
        r = historico.comparar([a, b])
        self.assertEqual(len(r["efeito_prey"]), 1)
        txt = r["efeito_prey"][0]
        self.assertIn('"B" com Prey XP ★7 (+%d%%) contra "A" sem Prey XP' % bonus, txt)
        self.assertIn("XP/h de \"B\" é 25% maior", txt)                       # 12,5M contra 10M
        self.assertIn("só pela prey seria cerca de %d%%" % round(bonus), txt)

    def test_efeito_da_prey_loot_ataque_e_defesa(self):
        a = self._solo("a", "A", 60, 10_000_000, 500_000, prey=[{"tipo": "loot", "estrelas": 3}])
        b = self._solo("b", "B", 60, 10_000_000, 500_000, prey=[{"tipo": "loot", "estrelas": 9}, {"tipo": "ataque", "estrelas": 10}, {"tipo": "defesa", "estrelas": 10}])
        textos = historico.comparar([a, b])["efeito_prey"]
        self.assertEqual([t.split(":")[0] for t in textos], ["Prey Loot", "Prey Ataque", "Prey Defesa"])
        self.assertIn('"A" com Prey Loot ★3', textos[0])
        self.assertIn("dano recebido", textos[2])                               # defesa: o app não mede o dano recebido

    def test_efeito_da_prey_so_quando_muda_e_esta_informada(self):
        igual = [{"tipo": "xp", "estrelas": 7}]
        a, b = self._solo("a", "A", 60, 1, 1, prey=igual), self._solo("b", "B", 60, 2, 1, prey=igual)
        self.assertEqual(historico.comparar([a, b])["efeito_prey"], [])        # mesma prey: nada a explicar
        c = self._solo("c", "C", 60, 2, 1)                                      # prey não informada: não dá para afirmar
        self.assertEqual(historico.comparar([a, c])["efeito_prey"], [])

    def test_filtro_tamanho(self):
        self.assertTrue(historico.do_tamanho(self._h("a", "A", 4, 60, 1, 1), "4"))
        self.assertFalse(historico.do_tamanho(self._h("a", "A", 3, 60, 1, 1), "4"))
        self.assertTrue(historico.do_tamanho(self._h("a", "A", 6, 60, 1, 1), "5+"))
        self.assertTrue(historico.do_tamanho({"resumo": {}}, "1"))


class TestPrey(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arq = os.path.join(self.tmp.name, "h.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_normalizar_e_rotulo(self):
        self.assertIsNone(historico.normalizar_prey(None))
        self.assertEqual(historico.normalizar_prey([{"tipo": "xp", "estrelas": 11}, {"tipo": "x", "estrelas": 3},
                                                    {"tipo": "loot", "estrelas": 0}, {"tipo": "ataque", "estrelas": "5"},
                                                    {"tipo": "defesa", "estrelas": 2}]),
                         [{"tipo": "xp", "estrelas": 10}, {"tipo": "loot", "estrelas": 1}, {"tipo": "ataque", "estrelas": 5}])
        self.assertEqual(historico.normalizar_prey("lixo"), [])
        self.assertEqual(historico.rotulo_prey([{"tipo": "xp", "estrelas": 7}]), "Prey XP ★7")
        self.assertEqual(historico.rotulo_prey([{"tipo": "xp", "estrelas": 7}, {"tipo": "loot", "estrelas": 4}]),
                         "Prey XP ★7 + Prey Loot ★4")
        self.assertEqual(historico.rotulo_prey([]), "Sem prey")
        self.assertEqual(historico.rotulo_prey(None), "Prey não informada")

    def test_salvar_sem_prey_preserva_a_gravada(self):
        reg = TestHistorico._reg(self)
        h = historico.salvar({**reg, "prey": [{"tipo": "xp", "estrelas": 7}]}, self.arq)
        historico.salvar({**reg, "id": h["id"]}, self.arq)  # re-salvar sem o campo prey (hunt aberta e salva)
        self.assertEqual(historico.obter(h["id"], self.arq)["prey"], [{"tipo": "xp", "estrelas": 7}])
        historico.salvar({**reg, "id": h["id"], "prey": []}, self.arq)  # marcar "sem prey" é explícito
        self.assertEqual(historico.obter(h["id"], self.arq)["prey"], [])
        antiga = historico.salvar(TestHistorico._reg(self, party=PARTY + "\nY", nome="antiga"), self.arq)
        self.assertNotIn("prey", historico.obter(antiga["id"], self.arq))  # nunca inventa prey

    def test_prey_com_criatura(self):
        self.assertEqual(historico.normalizar_prey([{"tipo": "xp", "estrelas": 7, "criatura": " Gloom Maw "}]),
                         [{"tipo": "xp", "estrelas": 7, "criatura": "Gloom Maw"}])
        prey = [{"tipo": "xp", "estrelas": 7, "criatura": "Gloom Maw"}, {"tipo": "ataque", "estrelas": 10, "criatura": "Varg"}]
        self.assertEqual(historico.rotulo_prey(prey), "Prey XP ★7 + Prey Ataque ★10")  # chip do histórico: só tipo e estrelas
        self.assertEqual(historico.rotulo_prey(prey, com_criatura=True), "Prey XP ★7 · Gloom Maw + Prey Ataque ★10 · Varg")
        a, b = TestComparar._h(self, "a", "A", 4, 60, 1, 4), TestComparar._h(self, "b", "B", 4, 60, 1, 4)
        a["prey"] = [{"tipo": "xp", "estrelas": 7, "criatura": "Gloom Maw"}]
        b["prey"] = [{"tipo": "xp", "estrelas": 7, "criatura": "Varg"}]  # mesma prey em outra criatura
        self.assertTrue(any(x.startswith("Prey diferente") and x.endswith("A XP/h não é comparável diretamente.")
                            for x in historico.comparar([a, b])["avisos"]))

    def test_mesma_criatura_nao_repete_em_duas_preys(self):
        r = historico.normalizar_prey([{"tipo": "xp", "estrelas": 7, "criatura": "Varg"},
                                       {"tipo": "loot", "estrelas": 5, "criatura": "varg"},
                                       {"tipo": "ataque", "estrelas": 3, "criatura": "Gloom Maw"}])
        self.assertEqual([p.get("criatura") for p in r], ["Varg", None, "Gloom Maw"])
        self.assertEqual(len(r), 3)  # a prey repetida continua; só perde a criatura

    def test_roda_salva_preservada_e_no_comparativo(self):
        reg = TestHistorico._reg(self)
        beam = {"titulo": " Beam ", "codigo": "S0Y2AgDP4jAQA", "lixo": 1}
        h = historico.salvar({**reg, "roda": beam}, self.arq)
        self.assertEqual(historico.obter(h["id"], self.arq)["roda"], {"titulo": "Beam", "codigo": "S0Y2AgDP4jAQA"})
        historico.salvar({**reg, "id": h["id"]}, self.arq)               # re-salvar sem o campo mantém a gravada
        self.assertEqual(historico.obter(h["id"], self.arq)["roda"]["titulo"], "Beam")
        historico.salvar({**reg, "id": h["id"], "roda": {"codigo": "ruim"}}, self.arq)  # código inválido = "sem roda"
        self.assertEqual(historico.obter(h["id"], self.arq)["roda"], {})
        antiga = historico.salvar(TestHistorico._reg(self, party=PARTY + "\nW", nome="antiga"), self.arq)
        self.assertNotIn("roda", historico.obter(antiga["id"], self.arq))   # nunca inventa roda

    def test_aviso_roda_diferente(self):
        a, b = TestComparar._h(self, "a", "A", 4, 60, 1, 4), TestComparar._h(self, "b", "B", 4, 60, 1, 4)
        a["roda"] = {"titulo": "Beam", "codigo": "S0Y2AgDP4jAQA"}
        b["roda"] = {"titulo": "Fire", "codigo": "S0OzEthYGBYVqKN5"}
        r = historico.comparar([a, b])
        self.assertIn('Roda diferente: "A" com Roda: Beam, "B" com Roda: Fire. O dano e a cura podem não ser comparáveis diretamente.', r["avisos"])
        self.assertEqual([h["roda"] for h in r["hunts"]], ["Roda: Beam", "Roda: Fire"])
        b["roda"] = {"titulo": "Outro nome", "codigo": "S0Y2AgDP4jAQA"}   # mesma roda (mesmo código): sem aviso
        self.assertFalse(any("Roda" in x for x in historico.comparar([a, b])["avisos"]))
        b["roda"] = {}                                                     # sem roda é diferente de ter roda
        self.assertIn('Roda diferente: "A" com Roda: Beam, "B" sem roda. O dano e a cura podem não ser comparáveis diretamente.',
                      historico.comparar([a, b])["avisos"])
        del b["roda"]                                                      # não informada: sem aviso
        r = historico.comparar([a, b])
        self.assertFalse(any("Roda" in x for x in r["avisos"]))
        self.assertEqual(r["hunts"][1]["roda"], "Roda não informada")

    def test_set_salvo_preservado_e_no_comparativo(self):
        reg = TestHistorico._reg(self)
        st = {"titulo": " Tokyo ", "itens": {"arma": {"nome": "Wand of Defiance", "imbue": 3, "imbues": ["Powerful Void"]}}, "lixo": 1}
        h = historico.salvar({**reg, "set": st}, self.arq)
        self.assertEqual(historico.obter(h["id"], self.arq)["set"]["titulo"], "Tokyo")
        historico.salvar({**reg, "id": h["id"]}, self.arq)               # re-salvar sem o campo mantém o gravado
        self.assertEqual(historico.obter(h["id"], self.arq)["set"]["titulo"], "Tokyo")
        historico.salvar({**reg, "id": h["id"], "set": "lixo"}, self.arq)  # inválido = "sem set"
        self.assertEqual(historico.obter(h["id"], self.arq)["set"], {})
        antiga = historico.salvar(TestHistorico._reg(self, party=PARTY + "\nW", nome="antiga"), self.arq)
        self.assertNotIn("set", historico.obter(antiga["id"], self.arq))   # nunca inventa set

    def test_aviso_set_diferente(self):
        a, b = TestComparar._h(self, "a", "A", 4, 60, 1, 4), TestComparar._h(self, "b", "B", 4, 60, 1, 4)
        cap = {"nome": "Gnome Helmet", "imbue": 2}
        a["set"] = {"titulo": "Tokyo", "itens": {"cabeca": cap, "arma": {"nome": "Wand of Defiance"}}}
        b["set"] = {"titulo": "Ingol", "itens": {"cabeca": cap, "arma": {"nome": "Wand of Starstorm"}}}
        r = historico.comparar([a, b])
        self.assertIn('Set diferente: "A" com Set: Tokyo, "B" com Set: Ingol (muda: Arma). O dano, a cura e o lucro podem não ser comparáveis diretamente.', r["avisos"])
        self.assertEqual([h["set"] for h in r["hunts"]], ["Set: Tokyo", "Set: Ingol"])
        b["set"] = {"titulo": "Outro nome", "itens": a["set"]["itens"]}      # mesmos itens: sem aviso
        self.assertFalse(any("Set" in x for x in historico.comparar([a, b])["avisos"]))
        del b["set"]                                                         # não informado: sem aviso
        r = historico.comparar([a, b])
        self.assertFalse(any("Set" in x for x in r["avisos"]))
        self.assertEqual(r["hunts"][1]["set"], "Set não informado")

    def test_charms_salvos_e_preservados(self):
        reg = TestHistorico._reg(self)
        h = historico.salvar({**reg, "charms": [{"nome": "Carnage", "criatura": "Varg", "nivel": "3"}, {"nome": "X", "nivel": 1}]}, self.arq)
        self.assertEqual(historico.obter(h["id"], self.arq)["charms"], [{"nome": "Carnage", "criatura": "Varg", "nivel": 3}])
        historico.salvar({**reg, "id": h["id"]}, self.arq)  # re-salvar sem charms mantém os gravados
        self.assertEqual(historico.obter(h["id"], self.arq)["charms"], [{"nome": "Carnage", "criatura": "Varg", "nivel": 3}])
        self.assertEqual(historico.comparar([historico.obter(h["id"], self.arq), TestComparar._h(self, "b", "B", 4, 60, 1, 4)])
                         ["hunts"][0]["charms"], "1 charm")

    def test_exportar_importar_mantem_prey(self):
        historico.salvar({**TestHistorico._reg(self), "prey": [{"tipo": "loot", "estrelas": 3}]}, self.arq)
        destino = os.path.join(self.tmp.name, "d.json")
        historico.importar(historico.exportar(caminho=self.arq), caminho=destino)
        self.assertEqual(historico.carregar(destino)[0]["prey"], [{"tipo": "loot", "estrelas": 3}])

    def test_aviso_prey(self):
        a, b = TestComparar._h(self, "a", "A", 4, 60, 1, 4), TestComparar._h(self, "b", "B", 4, 60, 1, 4)
        a["prey"], b["prey"] = [{"tipo": "xp", "estrelas": 7}], []
        r = historico.comparar([a, b])
        self.assertIn('Prey diferente: "A" com Prey XP ★7, "B" sem prey. A XP/h não é comparável diretamente.', r["avisos"])
        self.assertEqual([h["prey"] for h in r["hunts"]], ["Prey XP ★7", "Sem prey"])
        b["prey"] = [{"tipo": "loot", "estrelas": 2}]
        self.assertIn('Prey diferente: "A" com Prey XP ★7, "B" com Prey Loot ★2. A XP/h e o loot não são comparáveis diretamente.',
                      historico.comparar([a, b])["avisos"])
        a["prey"] = [{"tipo": "xp", "estrelas": 7}, {"tipo": "loot", "estrelas": 4}]  # mesma XP, loot diferente
        b["prey"] = [{"tipo": "xp", "estrelas": 7}, {"tipo": "loot", "estrelas": 5}]
        aviso = next(x for x in historico.comparar([a, b])["avisos"] if x.startswith("Prey diferente"))
        self.assertTrue(aviso.endswith("O loot não é comparável diretamente."), aviso)  # a XP/h continua comparável
        a["prey"] = [{"tipo": "xp", "estrelas": 7}]
        b["prey"] = [{"tipo": "xp", "estrelas": 7}]
        self.assertFalse(any("Prey" in x for x in historico.comparar([a, b])["avisos"]))
        del b["prey"]  # não informada: sem aviso
        r = historico.comparar([a, b])
        self.assertFalse(any("Prey" in x for x in r["avisos"]))
        self.assertEqual(r["hunts"][1]["prey"], "Prey não informada")


class TestApiPrey(unittest.TestCase):
    def setUp(self):
        from unittest import mock
        import web_api
        self.tmp = tempfile.TemporaryDirectory()
        self.trocar = mock.patch.object(historico, "HIST_PATH", os.path.join(self.tmp.name, "h.json"))
        self.trocar.start()
        self.api = object.__new__(web_api.API)
        self.api._dano_cache = {}
        self.api._emit = lambda *a, **k: None  # a análise de dano roda em segundo plano e avisaria a janela

    def tearDown(self):
        self.trocar.stop()
        self.tmp.cleanup()

    def test_salvar_abrir_e_ultima_prey(self):
        self.assertIsNone(self.api.hunt_ultima_prey("Zandao"))
        e = {"party": PARTY, "personagem": "Zandao", "prey": [{"tipo": "xp", "estrelas": 7}]}
        r = self.api.hunt_salvar(e)
        self.assertTrue(r["ok"])
        self.assertEqual(self.api.hunt_abrir(r["id"])["prey"], [{"tipo": "xp", "estrelas": 7}])
        self.assertEqual(self.api.hunt_ultima_prey("Zandao"), [{"tipo": "xp", "estrelas": 7}])
        lista = self.api.hunt_historico()["hunts"]
        self.assertEqual((lista[0]["prey"], lista[0]["prey_informada"]), ("Prey XP ★7", True))

    def test_tempo_real_vai_e_volta_pela_api(self):
        a = self.api.hunt_analisar({"party": PARTY, "duracao": "1:00"})
        self.assertEqual(a["analise"]["resumo"]["minutos"], 60)
        r = self.api.hunt_salvar({"party": PARTY, "personagem": "Zandao", "duracao": "1:00"})
        self.assertEqual(self.api.hunt_abrir(r["id"])["duracao"], "1:00")
        self.assertEqual((historico.obter(r["id"])["resumo"]["minutos"], historico.obter(r["id"])["resumo"]["duracao"]), (60, "01:00h"))
        # a análise por jogador (comparativo/ranking) também usa o tempo real
        knight = next(j for j in historico.ranking_jogadores([historico.obter(r["id"])]) if j["nome"] == "Knight Alfa")
        self.assertEqual((knight["minutos"], knight["dano_h"]), (60, 12_846_796))
        # hunt sem tempo digitado continua com o Session colado
        antiga = self.api.hunt_salvar({"party": PARTY + "\nZ", "personagem": "Zandao"})
        self.assertEqual(self.api.hunt_abrir(antiga["id"]).get("duracao") or "", "")
        self.assertEqual(historico.obter(antiga["id"])["resumo"]["minutos"], 167)

    def test_set_pela_api(self):
        import sets
        self.assertIsNone(self.api.hunt_ultimo_set("Zandao"))
        st = {"titulo": "Tokyo", "itens": {"arma": {"nome": "Wand of Defiance", "imbue": 3, "imbues": ["Powerful Void"]}}, "consumiveis": []}
        r = self.api.hunt_salvar({"party": PARTY, "personagem": "Zandao", "set": st})
        self.assertEqual(self.api.hunt_abrir(r["id"])["set"], sets.normalizar_set(st))
        self.assertEqual(self.api.hunt_ultimo_set("Zandao")["titulo"], "Tokyo")
        h = self.api.hunt_historico()["hunts"][0]
        self.assertEqual((h["set"], h["set_informado"]), ("Set: Tokyo", True))
        self.api.hunt_salvar({"party": PARTY, "personagem": "Zandao", "id": r["id"], "set": None})
        self.assertEqual(historico.obter(r["id"])["set"]["titulo"], "Tokyo")

    def test_hunt_salva_com_consumiveis_no_formato_antigo(self):
        r = self.api.hunt_salvar({"party": PARTY, "personagem": "Zandao", "set": {"titulo": "Velho", "itens": {"arma": {"nome": "Wand of Defiance"}}}})
        h = historico.obter(r["id"])
        h["set"]["consumiveis"] = ["Mana Potion"]                     # como a v1.0.8 gravava: só o texto
        historico.atualizar(r["id"], set=h["set"])
        self.assertEqual(self.api.hunt_abrir(r["id"])["set"]["consumiveis"], [{"nome": "Mana Potion"}])
        self.assertEqual(self.api.hunt_ultimo_set("Zandao")["consumiveis"], [{"nome": "Mana Potion"}])

    def test_cadastro_de_sets_pela_api(self):
        from unittest import mock
        import sets
        with mock.patch.object(sets, "SETS_PATH", os.path.join(self.tmp.name, "sets.json")):
            self.assertEqual(self.api.set_listar(), [])
            self.assertFalse(self.api.set_salvar({"titulo": "x", "itens": {}})["ok"])
            r = self.api.set_salvar({"titulo": "Tokyo", "itens": {"arma": {"nome": "Wand of Defiance"}}})
            self.assertTrue(r["ok"])
            self.assertEqual(self.api.set_listar()[0]["titulo"], "Tokyo")
            self.assertTrue(self.api.set_remover(r["set"]["id"]))
            self.assertEqual(self.api.set_listar(), [])

    def test_itens_do_set_pela_api(self):
        from unittest import mock
        import itens_set
        with mock.patch.object(itens_set, "itens_do_slot", return_value=[{"nome": "Gnome Helmet", "slot": "cabeca", "armor": 8, "attrib": "magic level +2"}]):
            r = self.api.set_itens("cabeca")
        self.assertEqual((r[0]["nome"], r[0]["desc"]), ("Gnome Helmet", "Arm: 8, Magic Level +2"))   # a descrição já vem pronta
        t = self.api.set_tabelas()
        self.assertEqual(t["slots"][0], ["cabeca", "Capacete"])
        self.assertIn("Powerful Void", [e["nome"] for e in t["embuimentos"]])

    def test_roda_pela_api(self):
        self.assertIsNone(self.api.hunt_ultima_roda("Zandao"))
        beam = {"titulo": "Beam", "codigo": "S0Y2AgDP4jAQA"}
        r = self.api.hunt_salvar({"party": PARTY, "personagem": "Zandao", "roda": beam})
        self.assertEqual(self.api.hunt_abrir(r["id"])["roda"], beam)
        self.assertEqual(self.api.hunt_ultima_roda("Zandao"), beam)
        h = self.api.hunt_historico()["hunts"][0]
        self.assertEqual((h["roda"], h["roda_informada"]), ("Roda: Beam", True))
        self.api.hunt_salvar({"party": PARTY, "personagem": "Zandao", "id": r["id"], "roda": None})   # hunt antiga salva sem mexer
        self.assertEqual(historico.obter(r["id"])["roda"], beam)
        outra = self.api.hunt_salvar({"party": PARTY + "\nW", "personagem": "Zandao"})
        h2 = next(x for x in self.api.hunt_historico()["hunts"] if x["id"] == outra["id"])
        self.assertEqual((h2["roda"], h2["roda_informada"]), ("Roda não informada", False))

    def test_charms_pela_api(self):
        self.assertIsNone(self.api.hunt_ultimos_charms("Zandao"))
        c = [{"nome": "Low Blow", "criatura": "Gloom Maw", "nivel": 2}]
        r = self.api.hunt_salvar({"party": PARTY, "personagem": "Zandao", "charms": c})
        self.assertEqual(self.api.hunt_abrir(r["id"])["charms"], c)
        self.assertEqual(self.api.hunt_ultimos_charms("Zandao"), c)
        h = self.api.hunt_historico()["hunts"][0]
        self.assertEqual((h["charms"], h["charms_informados"]), ("1 charm", True))
        self.api.hunt_salvar({"party": PARTY, "personagem": "Zandao", "id": r["id"], "charms": None})
        self.assertEqual(historico.obter(r["id"])["charms"], c)
        self.assertEqual(self.api.hunt_tabelas()["prey"][0]["tipo"], "xp")

    def test_ultima_prey_so_das_hunts_do_proprio_personagem(self):
        # hunt de um amigo (importada) em que o Zandao só aparece como membro: a prey é do amigo
        historico.salvar({"nome": "do amigo", "assinatura": "x", "entrada": {"party": PARTY}, "personagem": "Druid Bravo",
                          "membros": ["Zandao", "Druid Bravo"], "data_hunt": "2026-10-06 10:00", "resumo": {},
                          "prey": [{"tipo": "defesa", "estrelas": 9}]})
        self.assertIsNone(self.api.hunt_ultima_prey("Zandao"))
        self.assertEqual(self.api.hunt_ultima_prey("druid bravo"), [{"tipo": "defesa", "estrelas": 9}])

    def test_prey_estragada_no_arquivo_nao_derruba_o_historico(self):
        historico.salvar({"nome": "editada à mão", "assinatura": "y", "entrada": {"party": PARTY}, "personagem": "Zandao",
                          "resumo": {}}, historico.HIST_PATH)
        hs = historico.carregar()
        hs[0]["prey"] = [{"tipo": "magia", "estrelas": 3}, "lixo"]
        historico._gravar(hs)
        self.assertEqual(self.api.hunt_historico()["hunts"][0]["prey"], "Sem prey")

    def test_hunt_antiga_salva_sem_mexer_continua_igual(self):
        r = self.api.hunt_salvar({"party": PARTY, "personagem": "Zandao", "prey": [{"tipo": "loot", "estrelas": 2}]})
        self.api.hunt_salvar({"party": PARTY, "personagem": "Zandao", "id": r["id"], "prey": None})
        self.assertEqual(historico.obter(r["id"])["prey"], [{"tipo": "loot", "estrelas": 2}])
        outra = self.api.hunt_salvar({"party": PARTY + "\nZ", "personagem": "Zandao"})
        self.assertIsNone(self.api.hunt_abrir(outra["id"])["prey"])
        h = next(x for x in self.api.hunt_historico()["hunts"] if x["id"] == outra["id"])
        self.assertEqual((h["prey"], h["prey_informada"]), ("Prey não informada", False))


def _reg_party(id_, inicio, duracao, k, mons):
    """Hunt salva a partir do PARTY de exemplo, com outro início/duração e o dano do Knight Alfa multiplicado por k."""
    party = (PARTY.replace("2026-10-05, 10:19:15", inicio).replace("Session: 02:47h", f"Session: {duracao}")
             .replace("12,846,796", f"{12846796 * k:,}"))
    e = {"party": party, "solo": "", "dano": ""}
    a = hunt.montar(e)
    return {"id": id_, "nome": id_, "entrada": e, "resumo": a["resumo"], "data_hunt": a["data"],
            "monstros": [{"nome": m, "kills": 10} for m in mons]}


class TestPanorama(unittest.TestCase):
    _reg = staticmethod(_reg_party)

    def test_muitas_hunts(self):
        hs = [self._reg(f"h{i}", f"2026-10-0{i}, 10:00:00", "01:00h" if i % 2 else "02:00h", i, ["gloom maws", "varg"])
              for i in range(1, 8)]
        hs.append(self._reg("dragoes", "2026-10-09, 10:00:00", "01:00h", 1, ["dragon lord"]))
        r = historico.panorama(hs)
        self.assertEqual(r["total"]["hunts"], 8)
        self.assertEqual([l["id"] for l in r["linhas"]][0], "h1")  # em ordem de data (para o gráfico)
        lucros = [l["lucro_membro_h"] for l in r["linhas"]]
        st = r["stats"]["lucro_membro_h"]
        self.assertEqual((st["melhor"], st["pior"], st["media"]), (max(lucros), min(lucros), sum(lucros) // 8))
        self.assertEqual(r["stats"]["supplies_membro_h"]["melhor"], min(l["supplies_membro_h"] for l in r["linhas"]))
        knight = next(j for j in r["jogadores"] if j["nome"] == "Knight Alfa")
        self.assertEqual(knight["hunts"], 8)
        self.assertEqual(knight["dano"], sum(12846796 * k for k in range(1, 8)) + 12846796)
        self.assertEqual(r["jogadores"][0]["nome"], "Knight Alfa")  # maior dano/h primeiro

        # filtro por spawn: nomes no plural do Hunting Analyser viram o nome do monstro
        self.assertEqual(historico.opcoes_monstros(hs)[0], ("Gloom Maw", 7))
        self.assertEqual(len(historico.filtrar(hs, monstro="Gloom Maw")), 7)
        self.assertEqual([h["id"] for h in historico.filtrar(hs, monstro="Dragon Lord")], ["dragoes"])
        self.assertEqual(len(historico.filtrar(hs, tamanho="4", monstro="Varg")), 7)


class TestTibiaInfo(unittest.TestCase):
    def test_server_save_e_rashid(self):
        import tibia_info as t
        from datetime import datetime, timedelta, timezone
        br = timezone(timedelta(hours=-3))
        quando = lambda s: datetime.fromisoformat(s).replace(tzinfo=br).astimezone(timezone.utc)
        hora_br = lambda s: t.proximo_server_save(quando(s)).astimezone(br).strftime("%Y-%m-%d %H:%M")
        self.assertEqual(hora_br("2026-10-06T04:30"), "2026-10-06 05:00")   # CEST: 10h Berlim = 5h Brasil
        self.assertEqual(hora_br("2026-10-06T05:30"), "2026-10-07 05:00")
        self.assertEqual(hora_br("2026-11-02T05:30"), "2026-11-02 06:00")   # CET (sem horário de verão): 6h
        self.assertEqual(t.rashid(quando("2026-10-06T04:30")), "Svargrond")  # terça antes do SS: ainda segunda
        self.assertEqual(t.rashid(quando("2026-10-06T05:30")), "Liberty Bay")
        self.assertEqual(t.rashid(quando("2026-10-11T12:00")), "Carlin")    # domingo

    def test_boss_do_dia_espera_o_tibiadata_trocar(self):
        import tibia_info as t
        hoje = t.dia_tibia().isoformat()
        respostas = {"boss": "Boss Ontem", "cri": "Criatura Ontem"}
        falso = lambda url, timeout=12: ({"boostable_bosses": {"boosted": {"name": respostas["boss"], "image_url": "b"}}}
                                         if "boostablebosses" in url else
                                         {"creatures": {"boosted": {"name": respostas["cri"], "image_url": "c"}}})
        with tempfile.TemporaryDirectory() as tmp:
            orig = (t.CACHE_PATH, t._get_json)
            t.CACHE_PATH, t._get_json = os.path.join(tmp, "c.json"), falso
            try:
                with open(t.CACHE_PATH, "w", encoding="utf-8") as f:
                    json.dump({"dia": "2000-01-01", "boss": {"nome": "Boss Ontem"}, "criatura": {"nome": "Criatura Ontem"}}, f)
                r = t.boostados()
                self.assertTrue(r.get("aguardando"))                       # ainda os de ontem: não grava
                with open(t.CACHE_PATH, encoding="utf-8") as f:
                    self.assertEqual(json.load(f)["dia"], "2000-01-01")
                respostas.update(boss="Boss Novo", cri="Criatura Nova")      # o TibiaData trocou
                r = t.boostados()
                self.assertFalse(r.get("aguardando"))
                with open(t.CACHE_PATH, encoding="utf-8") as f:
                    self.assertEqual((r["boss"]["nome"], json.load(f)["dia"]), ("Boss Novo", hoje))
                respostas.update(boss="X", cri="Y")                          # mesmo dia: usa o cache, não consulta
                self.assertEqual(t.boostados()["boss"]["nome"], "Boss Novo")
            finally:
                t.CACHE_PATH, t._get_json = orig

    def test_shared_e_xp(self):
        import tibia_info as t
        self.assertEqual(t.faixa_shared(300), (200, 450))
        self.assertEqual(t.faixa_shared(483), (322, 724))
        self.assertTrue(t.verificar_shared({"A": 300, "B": 200, "C": 299})["ok"])   # 300 = 3/2 de 200: ainda divide
        self.assertFalse(t.verificar_shared({"A": 300, "B": 200, "C": 450})["ok"])  # 450 passa de 3/2 de 200
        r = t.verificar_shared({"A": 300, "B": 200, "C": 451})
        self.assertFalse(r["ok"])
        self.assertEqual((r["teto"], r["piso"], r["abaixo"]), (300, 301, ["B", "A"]))
        self.assertEqual(t.xp_total(8), 4200)
        self.assertEqual(t.xp_total(100), 15_694_800)
        self.assertEqual(t.level_da_xp(15_694_800), 100)
        self.assertEqual(t.level_da_xp(15_694_799), 99)


class TestMeusPersonagens(unittest.TestCase):
    def test_adicionar_trocar_remover(self):
        import personagens as ps
        fake = {"zandao": {"nome": "Zandao", "level": 483, "vocacao": "Master Sorcerer", "mundo": "Rasteibra"},
                "knight alfa": {"nome": "Knight Alfa", "level": 600, "vocacao": "Elite Knight", "mundo": "Antica"}}
        buscar = lambda n: fake.get(n.strip().lower())
        with tempfile.TemporaryDirectory() as tmp:
            arq = os.path.join(tmp, "p.json")
            d, erro = ps.adicionar("zandao", arq, buscar)          # grafia certa vem do tibia.com
            self.assertIsNone(erro)
            self.assertEqual((d["atual"], d["lista"][0]["level"]), ("Zandao", 483))
            d, erro = ps.adicionar("Nao Existe", arq, buscar)
            self.assertIsNone(d)
            self.assertIn("Não achei", erro)
            ps.adicionar("Knight Alfa", arq, buscar)
            self.assertEqual(ps.carregar(arq)["atual"], "Zandao")  # adicionar outro não troca o em uso
            self.assertEqual(ps.usar("Knight Alfa", arq)["atual"], "Knight Alfa")
            ps.adicionar("ZANDAO", arq, buscar)                     # de novo: atualiza, não duplica
            self.assertEqual(len(ps.carregar(arq)["lista"]), 2)
            d = ps.remover("Knight Alfa", arq)
            self.assertEqual((d["atual"], [p["nome"] for p in d["lista"]]), ("Zandao", ["Zandao"]))
            fake["zandao"] = {**fake["zandao"], "level": 490}         # upou: atualizar busca de novo
            d = ps.atualizar_levels(arq, forcar=True, buscar_varios=lambda ns: {n: buscar(n) for n in ns})
            self.assertEqual(d["lista"][0]["level"], 490)


class TestBackup(unittest.TestCase):
    def test_exporta_e_restaura_tudo(self):
        import backup
        with tempfile.TemporaryDirectory() as tmp:
            orig = {k: os.path.join(tmp, "a", n) for k, n in (("historico", "h.json"), ("personagens", "p.json"),
                    ("prints", "s.json"), ("teclas", "t.ini"), ("janela", "j.json"))}  # "teclas" saiu na v1.0.5
            os.makedirs(os.path.join(tmp, "a"))
            json.dump({"formato": historico.FORMATO, "hunts": [{"id": "x"}, {"id": "y"}]}, open(orig["historico"], "w", encoding="utf-8"))
            json.dump({"lista": [{"nome": "Zandao"}], "atual": "Zandao"}, open(orig["personagens"], "w", encoding="utf-8"))
            json.dump({"print-dir": "C:/x", "destination": "D:/y"}, open(orig["prints"], "w", encoding="utf-8"))
            ini = "[Config]\r\nBind1_Tecla=f\r\n".encode("utf-16")      # o AutoHotkey grava em UTF-16
            open(orig["teclas"], "wb").write(ini)
            pacote = json.loads(json.dumps(backup.exportar(orig, "9.9.9")))  # passa por JSON, como no arquivo
            self.assertEqual(sorted(pacote["arquivos"]), ["historico", "personagens", "prints"])  # janela não existia; teclas não entra mais
            self.assertIn("Histórico de hunts (2 hunts)", backup.resumo(pacote))

            dest = {k: c.replace(os.sep + "a" + os.sep, os.sep + "b" + os.sep) for k, c in orig.items()}
            os.makedirs(os.path.join(tmp, "b"))
            json.dump({"print-dir": "antigo"}, open(dest["prints"], "w", encoding="utf-8"))
            feitos = backup.importar(pacote, dest)
            self.assertEqual(len(feitos), 3)
            self.assertEqual(json.load(open(dest["prints"], encoding="utf-8"))["destination"], "D:/y")
            self.assertEqual(json.load(open(dest["prints"] + ".antes-do-backup", encoding="utf-8"))["print-dir"], "antigo")
            pacote_antigo = {**pacote, "arquivos": {**pacote["arquivos"], "teclas": {"base64": "AAAA"}}}
            self.assertEqual(len(backup.importar(pacote_antigo, dest)), 3)    # backup antigo com teclas: ignora
            self.assertFalse(os.path.exists(dest["teclas"]))
            with self.assertRaises(ValueError):
                backup.importar({"formato": historico.FORMATO, "hunts": []}, dest)  # export só de hunts não é backup

    def test_prints_comecam_em_branco(self):
        import organizer
        self.assertEqual((organizer.DEFAULTS["print-dir"], organizer.DEFAULTS["destination"]), ("", ""))
        self.assertTrue(organizer.PASTA_PADRAO_TIBIA.endswith("Tibia/packages/Tibia/screenshots"))
        with self.assertRaises(ValueError):
            organizer.organizar({**organizer.DEFAULTS, "destination": "x"}, print)


GNOME_HELMET = """{{Infobox Object|List={{{1|}}}|GetValue={{{GetValue|}}}
| name          = Gnome Helmet
| slot          = Head
| levelrequired = 200
| vocrequired   = sorcerers and druids
| attrib        = magic level +2
| armor         = 8
| resist        = physical +3%, energy +8%, ice -2%
}}"""


class TestEquipamentos(unittest.TestCase):
    def test_parse_e_recomendacao(self):
        import equipamentos as eq
        self.assertEqual(eq.parse_resist("physical +3%, energy +8%, ice -2%"), {"physical": 3, "energy": 8, "ice": -2})
        self.assertEqual(eq.parse_resist("Life Drain +4%, mana drain 2%"), {"lifedrain": 4, "manadrain": 2})
        gnome = eq.item_do_wikitext("Gnome Helmet", GNOME_HELMET, "cabeca")
        self.assertEqual((gnome["level"], gnome["vocs"], gnome["temporario"]), (200, ["sorcerer", "druid"], False))
        self.assertIsNone(eq.item_do_wikitext("X", "{{Infobox Object\n| name = X\n| armor = 5\n}}", "cabeca"))  # sem proteção
        itens = [gnome, gnome,  # a wiki às vezes repete: tem que aparecer uma vez só
                 {"nome": "Stag Helmet", "slot": "cabeca", "level": 350, "vocs": ["sorcerer"], "resist": {"physical": 2, "energy": 8}},
                 {"nome": "Tiara of Power", "slot": "cabeca", "level": 100, "vocs": ["sorcerer", "druid"], "resist": {"energy": 8}},
                 {"nome": "Knight Thing", "slot": "cabeca", "level": 50, "vocs": ["knight"], "resist": {"energy": 20}},
                 {"nome": "Fire Hat", "slot": "cabeca", "level": 10, "vocs": eq.VOCACOES, "resist": {"fire": 5}}]
        ms400 = eq.recomendar(itens, "Master Sorcerer", 400, {}, elemento="energy")["cabeca"]
        self.assertEqual([i["nome"] for i in ms400], ["Stag Helmet", "Gnome Helmet", "Tiara of Power"])  # todos, maior primeiro
        self.assertEqual([i["nome"] for i in eq.recomendar(itens, "Elder Druid", 250, {}, "energy")["cabeca"]],
                         ["Gnome Helmet", "Tiara of Power"])  # Stag é só sorcerer e pede 350
        self.assertEqual([i["nome"] for i in eq.recomendar(itens, "Elite Knight", 500, {}, "energy")["cabeca"]], ["Knight Thing"])
        # "esta hunt": 70% energy, 30% ice -> Gnome (8*.7 - 2*.3 = 5.0) fica atrás do Tiara (5.6)
        mix = eq.recomendar(itens, "Master Sorcerer", 400, {"energy": .7, "ice": .3})["cabeca"]
        self.assertEqual([(i["nome"], i["nota"]) for i in mix], [("Stag Helmet", 5.6), ("Tiara of Power", 5.6), ("Gnome Helmet", 5.0)])


class TestTimersAudio(unittest.TestCase):
    def _timer(self, modo, duracao=10, antes=0):
        import audio_timers as at
        return at.EstadoTimer(at.normalizar({"nome": "T", "tecla": {"vk": 75}, "duracao": duracao, "modo": modo, "antes": antes}))

    def test_reinicia_a_cada_aperto(self):
        t = self._timer("reinicia")
        t.apertou(0)
        self.assertFalse(t.tick(5))
        t.apertou(5)                      # apertou no meio: volta do começo (acaba em 15)
        self.assertFalse(t.tick(14))
        self.assertTrue(t.tick(15))
        self.assertFalse(t.rodando)

    def test_conta_ate_o_fim(self):
        t = self._timer("ignora")
        t.apertou(0)
        t.apertou(5)                      # ignorado: continua acabando em 10
        self.assertTrue(t.tick(10))
        self.assertFalse(t.rodando)
        t.apertou(12)                     # só recomeça com um novo aperto
        self.assertEqual(t.restante(12), 10)

    def test_loop_e_aviso_antes(self):
        t = self._timer("loop", antes=2)
        t.apertou(0)
        self.assertFalse(t.tick(7))
        self.assertTrue(t.tick(8))        # 2 s antes do fim da 1ª volta
        self.assertFalse(t.tick(9))       # não toca de novo na mesma volta
        self.assertFalse(t.tick(10))      # virou a volta: segue contando
        self.assertTrue(t.rodando)
        self.assertTrue(t.tick(18))       # 2 s antes do fim da 2ª volta
        t.apertou(19)                     # segundo aperto para o loop
        self.assertFalse(t.rodando)
        self.assertFalse(t.tick(40))

    def test_alerta_e_barra(self):
        import audio_timers as at
        import overlay as ov
        n = at.normalizar({"nome": "Poção", "alerta": 1, "barra": True, "cor": "roxo"})
        self.assertEqual((n["alerta"], n["barra"], n["cor"]), (True, True, "amarelo"))  # cor inválida -> amarelo
        b = ov.normalizar_barra({"largura": 5000, "espessura": 1, "x": 150})
        self.assertEqual((b["largura"], b["espessura"], b["x"], b["y"]), (1200, 4, 100, 78))
        # a barra nunca sai da janela do Tibia, mesmo com posição 100%
        x, y, larg, alt, _ = ov.layout_barras(2, ov.normalizar_barra({"largura": 300, "x": 100, "y": 100}), (0, 0, 1000, 800))
        self.assertTrue(0 <= x and x + larg <= 1000 and 0 <= y and y + alt <= 800)
        self.assertEqual((at.fmt_tempo(74.2), at.fmt_tempo(3), at.fmt_tempo(3725)), ("1:15", "0:03", "1:02:05"))

    def test_normalizar(self):
        import audio_timers as at
        n = at.normalizar({"duracao": "0", "modo": "xx", "volume": 300, "tecla": None})
        self.assertEqual((n["duracao"], n["modo"], n["volume"], n["tecla"]["vk"]), (60.0, "reinicia", 100, 0))
        self.assertEqual(at.texto_da_tecla({"vk": 75, "nome": "K", "ctrl": True, "shift": False, "alt": True}), "Ctrl+Alt+K")
        self.assertTrue(at.caminho_do_som("usuario:../../windows/x.mp3").endswith("bipe.wav"))  # não sai da pasta
        self.assertTrue(at.caminho_do_som("padrao:../x.mp3").endswith("bipe.wav"))
        self.assertEqual(n["som"], at.SOM_PADRAO)
        self.assertTrue(os.path.isfile(at.caminho_do_som(at.SOM_PADRAO)))  # o som padrão vem com o app
        self.assertIn(at.SOM_PADRAO, [s["id"] for s in at.lista_sons()])

    def test_alerta_personalizado(self):
        import audio_timers as at
        n = at.normalizar({"nome": "Poção", "antes": 3, "duracao": 10, "cor": "#ff00aa", "fonte": 500, "fixo": 1})
        self.assertEqual((n["cor"], n["fonte"], n["fixo"], n["mensagem"]), ("#FF00AA", 96, True, ""))
        self.assertEqual(at.texto_alerta(n), "Poção acaba em 3s")
        self.assertEqual(at.texto_alerta(at.normalizar({"nome": "X", "mensagem": "  BEBA!  "})), "BEBA!")
        self.assertEqual(at.normalizar({"cor": "#zzzzzz"})["cor"], "amarelo")

    def test_alerta_pisca_nos_ultimos_segundos(self):
        import audio_timers as at

        class AlertaFalso:
            def __init__(self):
                self.chamadas = []

            def mostrar(self, texto, cor, segundos, **kw):
                self.chamadas.append((texto, round(segundos, 2), kw.get("piscar", False)))

            def esconder(self):
                self.chamadas.append("esconder")

        m = at.Motor.__new__(at.Motor)
        m.alerta, m.cfg = AlertaFalso(), {"alerta": {"x": 50, "y": 30}}
        m._piscou, m._pisca_dono, m._alerta_fixo = {}, None, None
        e = at.EstadoTimer(at.normalizar({"id": "p", "nome": "Poção", "duracao": 10, "alerta": True, "piscar": 3}))
        e.apertou(0)
        self.assertFalse(m._talvez_piscar(e, 6.9))           # ainda faltam 3,1 s
        self.assertTrue(m._talvez_piscar(e, 7.0))            # últimos 3 s: começa a piscar até o fim
        self.assertTrue(m._talvez_piscar(e, 8.0))            # mesma volta: não chama de novo
        self.assertEqual(m.alerta.chamadas, [("Poção acabando!", 3.0, True)])
        self.assertEqual(at.normalizar({"piscar": 4})["piscar"], 0)   # só 1, 2, 3 ou 5


        import audio_timers as at
        with tempfile.TemporaryDirectory() as d:
            arq = os.path.join(d, "EK.audio.json")
            with open(arq, "w", encoding="utf-8-sig") as f:
                json.dump({"Timers": [
                    {"Name": "Utito", "Duration": 10, "HotkeyCode": 0x71, "HotkeyModifiers": 6, "RetriggerEnabled": False,
                     "SoundName": "Potion", "ShowVisualAlert": True, "AlertMessage": "Utito!", "AlertColor": "#00FF00",
                     "AlertFontSize": 40, "AlertStayUntilHotkey": True, "Volume": 70},
                    {"Name": "Food", "Duration": 600, "HotkeyCode": 0x72, "SoundName": "naoexiste"}]}, f)
            t1, t2 = at.timers_do_tibiavision(arq)
        self.assertEqual((t1["nome"], t1["duracao"], t1["modo"], t1["volume"]), ("Utito", 10.0, "ignora", 70))
        self.assertEqual((t1["tecla"]["vk"], t1["tecla"]["ctrl"], t1["tecla"]["shift"], t1["tecla"]["alt"]), (0x71, True, True, False))
        self.assertEqual((t1["alerta"], t1["mensagem"], t1["cor"], t1["fonte"], t1["fixo"]), (True, "Utito!", "#00FF00", 40, True))
        self.assertEqual(t1["som"], "padrao:Potion.mp3")
        self.assertEqual((t2["modo"], t2["som"]), ("reinicia", at.SOM_PADRAO))


class TestApiHunt(unittest.TestCase):
    """Fluxo da tela: analisar salva sozinho; limpar caixa não apaga o histórico; outra hunt vira outra entrada."""

    def setUp(self):
        import web_api
        self.web_api = web_api
        self.tmp = tempfile.TemporaryDirectory()
        self.orig = (historico.HIST_PATH, web_api.RASCUNHO_PATH, web_api.API._trabalho_dano)
        historico.HIST_PATH = os.path.join(self.tmp.name, "h.json")
        web_api.RASCUNHO_PATH = os.path.join(self.tmp.name, "r.json")
        web_api.API._trabalho_dano = lambda *a, **k: None  # sem internet nos testes
        self.api = web_api.API()

    def tearDown(self):
        historico.HIST_PATH, self.web_api.RASCUNHO_PATH, self.web_api.API._trabalho_dano = self.orig
        self.tmp.cleanup()

    def test_so_salva_quando_clica_em_salvar(self):
        api = self.api
        e = {"party": PARTY, "solo": SOLO, "dano": DANO, "personagem": "Zandao"}
        r1 = api.hunt_analisar(e)
        self.assertIsNone(r1["id"])
        self.assertEqual(api.hunt_historico()["hunts"], [])  # analisar não grava nada
        self.assertEqual(api.hunt_carregar()["entrada"], {"personagem": "Zandao"})  # só lembra o personagem

        s1 = api.hunt_salvar({**e, "nome": "norfectarus pt 4x"}, ["Druid Bravo>Zandao"])
        self.assertTrue(s1["ok"])
        h = historico.obter(s1["id"])
        self.assertEqual((h["nome"], h["pagos"]), ("norfectarus pt 4x", ["Druid Bravo>Zandao"]))

        # editou (tirou um membro) e salvou de novo: atualiza a mesma entrada, não duplica
        s2 = api.hunt_salvar({**e, "nome": "norfectarus pt 4x", "excluidos": ["Paladin Charlie"], "id": s1["id"]}, [])
        self.assertEqual(s2["id"], s1["id"])
        self.assertEqual(len(api.hunt_historico()["hunts"]), 1)
        self.assertEqual(historico.obter(s1["id"])["pagos"], [])

        # colou uma hunt de outro horário por cima de uma salva: a análise já vem sem id e salvar cria outra
        outra = SOLO.replace("10:19:15", "20:00:00")
        r3 = api.hunt_analisar({"solo": outra, "personagem": "Zandao", "nome": "norfectarus pt 4x", "id": s1["id"]})
        self.assertIsNone(r3["id"])
        self.assertEqual(r3["nome"], "Hunt 2026-10-05 20:00")
        s3 = api.hunt_salvar({"solo": outra, "personagem": "Zandao", "id": s1["id"]})
        self.assertNotEqual(s3["id"], s1["id"])
        self.assertEqual(len(api.hunt_historico()["hunts"]), 2)
        self.assertFalse(api.hunt_salvar({"party": "nada"})["ok"])

    def test_colar_preenche_os_tres(self):
        import web_api
        api = self.api
        for texto in (PARTY, SOLO, "minha senha 123", DANO):  # o que não é do Tibia é ignorado
            tipo = hunt.detectar(texto)
            if tipo:
                api._capturas[tipo] = {"texto": texto, "t": __import__("time").time()}
        orig = web_api.ler_clipboard
        web_api.ler_clipboard = lambda: "minha senha 123"
        try:
            r = api.hunt_colar()
        finally:
            web_api.ler_clipboard = orig
        self.assertEqual(sorted(r["textos"]), ["dano", "party", "solo"])
        self.assertEqual(r["textos"]["party"], PARTY)
        self.assertEqual(api._capturas, {})  # depois de colar, esvazia


class TestCompararJogadores(unittest.TestCase):
    def test_dano_cura_e_por_jogador(self):
        def reg(id_, party, nome):
            e = {"party": party, "solo": "", "dano": ""}
            a = hunt.montar(e)
            return {"id": id_, "nome": nome, "entrada": e, "resumo": a["resumo"], "monstros": []}
        menor = PARTY.replace("Session: 02:47h", "Session: 01:00h").replace("12,846,796", "6,000,000")
        r = historico.comparar([reg("a", PARTY, "A"), reg("b", menor, "B")])
        linha = {l["chave"]: l for l in r["linhas"]}
        self.assertEqual(linha["dano_total"]["valores"][0], 12_846_796 + 7_271_000 + 11_706_807 + 9_221_867)
        self.assertEqual(linha["top_dano"]["valores"][0], "Knight Alfa · 12,846,796 (31.3%)")
        self.assertTrue(linha["top_cura"]["valores"][0].startswith("Knight Alfa · 3,120,299"))
        self.assertTrue(linha["top_supplies"]["valores"][0].startswith("Druid Bravo · 2,001,434"))
        self.assertIsNotNone(linha["cura_h"]["melhor"])
        jog = {j["nome"]: j for j in r["jogadores"]}
        self.assertEqual(jog["Knight Alfa"]["em"], 2)
        self.assertEqual([v["dano"] for v in jog["Knight Alfa"]["valores"]], [12_846_796, 6_000_000])
        self.assertEqual(jog["Knight Alfa"]["melhor"]["dano"], 0)       # mais dano no total: hunt A
        self.assertEqual(jog["Knight Alfa"]["melhor"]["dano_h"], 1)     # mas por hora: hunt B (1h)
        self.assertEqual(jog["Zandao"]["melhor"]["supplies_h"], 0)      # mesmo supplies em mais tempo = gastou menos/h


if __name__ == "__main__":
    unittest.main()
