"""Testes do cálculo com os números da planilha calculadora_embuiment.  Rodar: python -m unittest"""

import os
import unittest

import embuimentos as e

IMBS = {i["id"]: i for i in e.carregar_imbuements(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "imbuements.json"))}


def estado_planilha():
    k = e.item_key
    return {
        "precos": {
            k("Rope Belt"): 5286, k("Silencer Claws"): 4497, k("Some Grimeleech Wings"): 3098,
            k("Vampire Teeth"): 319, k("Bloody Pincers"): 13998, k("Piece of Dead Brain"): 29998,
            k("Protective Charm"): 4313, k("Sabretooth"): 7500, k("Vexclaw Talon"): 1215,
            e.scroll_key("void"): 550090, e.scroll_key("vampirism"): 639090, e.scroll_key("strike"): 525090,
        },
        "inventario": {k("Protective Charm"): 9, k("Sabretooth"): 4},
        "token": 53805, "taxa": 250000, "blank": 25000, "fazer_scroll": False,
    }


class TestPlanilha(unittest.TestCase):
    def test_void(self):
        r = e.calcular(IMBS["void"], estado_planilha())
        self.assertEqual(r["total_itens"], 260065)
        self.assertEqual(e.rota(r, "market")["custo"], 510065)
        self.assertEqual(e.rota(r, "tokens_full")["custo"], 572830)
        self.assertEqual(e.rota(r, "tokens_partial")["custo"], 480710)
        self.assertEqual(r["melhor"]["kind"], "tokens_partial")
        self.assertIn("comprar os 5 Some Grimeleech Wings", e.o_que_fazer(r, r["melhor"], False))

    def test_vampirism(self):
        r = e.calcular(IMBS["vampirism"], estado_planilha())
        self.assertEqual(e.rota(r, "market")["custo"], 617935)
        self.assertEqual(e.rota(r, "tokens_partial")["custo"], 615210)
        self.assertEqual(r["melhor"]["kind"], "tokens_full")

    def test_strike_com_inventario(self):
        r = e.calcular(IMBS["strike"], estado_planilha())
        self.assertEqual([i["comprar"] for i in r["itens"]], [11, 21, 5])
        self.assertEqual(e.rota(r, "market")["custo"], 461018)
        self.assertEqual(e.rota(r, "tokens_partial")["custo"], 471295)
        self.assertEqual(r["melhor"]["kind"], "market")

    def test_plano(self):
        st = estado_planilha()
        res = [e.calcular(IMBS[i], st) for i in ("void", "vampirism", "strike")]
        pl = e.plano(res)
        self.assertEqual(pl["recomendado"], 1514558)
        self.assertEqual(pl["tokens"], 10)
        self.assertEqual(pl["tudo_market"], 1589018)
        self.assertEqual(pl["tudo_scroll"], 550090 + 639090 + 525090)

    def test_blank_scroll(self):
        st = estado_planilha()
        st["fazer_scroll"] = True
        r = e.calcular(IMBS["void"], st)
        self.assertEqual(e.rota(r, "market")["custo"], 510065 + 25000)
        self.assertEqual(e.rota(r, "scroll")["custo"], 550090)

    def test_sem_token_nao_tem_rota_de_token(self):
        r = e.calcular(IMBS["featherweight"], estado_planilha())
        self.assertEqual([x["kind"] for x in r["rotas"]], ["scroll", "market"])

    def test_preco_faltando(self):
        st = estado_planilha()
        st["token"] = None
        self.assertEqual(e.campos_faltando([IMBS["void"]], st), ["Preço do Gold Token"])
        r = e.calcular(IMBS["void"], st)
        self.assertIsNone(e.rota(r, "tokens_full")["custo"])
        self.assertEqual(r["melhor"]["kind"], "market")

    def test_parse_e_fmt(self):
        self.assertEqual(e.parse_num("4.475"), 4475)
        self.assertEqual(e.parse_num("4,475 gp"), 4475)
        self.assertEqual(e.parse_num("4,5k"), 4500)
        self.assertEqual(e.parse_num("1.5kk"), 1500000)
        self.assertIsNone(e.parse_num(" "))
        self.assertEqual(e.fmt(1514558), "1.514.558")
        self.assertEqual(e.fmt(-25000), "-25.000")


if __name__ == "__main__":
    unittest.main()
