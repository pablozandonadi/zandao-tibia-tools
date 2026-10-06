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
        self.assertEqual([p["imbuement"] for p in r["protecoes"]], ["lichshroud", "dragonhide"])
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

    def test_filtro_tamanho(self):
        self.assertTrue(historico.do_tamanho(self._h("a", "A", 4, 60, 1, 1), "4"))
        self.assertFalse(historico.do_tamanho(self._h("a", "A", 3, 60, 1, 1), "4"))
        self.assertTrue(historico.do_tamanho(self._h("a", "A", 6, 60, 1, 1), "5+"))
        self.assertTrue(historico.do_tamanho({"resumo": {}}, "1"))


class TestPanorama(unittest.TestCase):
    def _reg(self, id_, inicio, duracao, k, mons):
        party = (PARTY.replace("2026-10-05, 10:19:15", inicio).replace("Session: 02:47h", f"Session: {duracao}")
                 .replace("12,846,796", f"{12846796 * k:,}"))
        e = {"party": party, "solo": "", "dano": ""}
        a = hunt.montar(e)
        return {"id": id_, "nome": id_, "entrada": e, "resumo": a["resumo"], "data_hunt": a["data"],
                "monstros": [{"nome": m, "kills": 10} for m in mons]}

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
