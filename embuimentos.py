"""Cálculo dos embuimentos Powerful (mesmas regras da planilha calculadora_embuiment).

Rotas:
  scroll          - comprar o scroll pronto (não paga taxa de embuir)
  market          - comprar só os itens que faltam + taxa (+ blank scroll)
  tokens_full     - 6 gold tokens = os 3 itens + taxa (+ blank scroll)
  tokens_partial  - 4 tokens = 2 primeiros itens; o último é comprado + taxa (+ blank)
As rotas de token só existem para embuimentos com has_token.
Preços são digitados à mão (preço unitário em gp); None = não preenchido.
"""

import json
import re

GROUPS = ["Com token", "Utilidades", "Proteções", "Skillboost", "Dano"]
TOKEN_NAME = "Gold Token"
DEFAULT_FEE = 250000
DEFAULT_BLANK = 25000

ROUTE_LABEL = {
    "scroll": "Scroll pronto",
    "market": "Itens no market",
    "tokens_full": "6 tokens",
    "tokens_partial": "4 tokens + último item",
}


def carregar_imbuements(caminho):
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def item_key(nome):
    return "item:" + re.sub(r"\s+", " ", nome.strip().lower())


def scroll_key(imb_id):
    return "scroll:" + imb_id


def label(imb):
    return f"{imb['name']} ({imb['subtitle']})" if imb.get("subtitle") else imb["name"]


# ---------- formatação ----------
def fmt(n):
    """1410505 -> '1.410.505'; None -> '—'."""
    if n is None:
        return "—"
    r = round(n)
    s = f"{abs(r):,}".replace(",", ".")
    return f"-{s}" if r < 0 else s


def gp(n):
    return f"{fmt(n)} gp"


def parse_num(s):
    """'1.234', '1,234', '1234 gp', '4,5k', '1kk' -> int. Vazio -> None."""
    s = (s or "").strip().lower()
    if not s:
        return None
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(k{1,2})", s)
    if m:
        valor = float(m.group(1).replace(",", "."))
        return round(valor * (1000 if len(m.group(2)) == 1 else 1000000))
    digitos = re.sub(r"\D", "", s)
    return int(digitos) if digitos else None


# ---------- cálculo ----------
def _soma(*xs):
    return None if any(x is None for x in xs) else sum(xs)


def custo(preco, qtd):
    if qtd <= 0:
        return 0
    return None if preco is None else preco * qtd


def calcular(imb, estado):
    """estado = {'precos': {key: int|None}, 'inventario': {key: int},
                 'token': int|None, 'taxa': int|None, 'blank': int|None, 'fazer_scroll': bool}"""
    precos = estado["precos"]
    itens = []
    for d in imb["items"]:
        k = item_key(d["name"])
        tem = max(0, int(estado["inventario"].get(k) or 0))
        comprar = max(0, d["qty"] - tem)
        itens.append({
            "nome": d["name"], "key": k, "qtd": d["qty"], "tem": tem,
            "comprar": comprar, "preco": precos.get(k), "custo": custo(precos.get(k), comprar),
        })

    taxa = estado["taxa"]
    blank = estado["blank"] if estado["fazer_scroll"] else 0
    total_itens = _soma(*(i["custo"] for i in itens))

    rotas = [
        {"kind": "scroll", "custo": precos.get(scroll_key(imb["id"])), "tokens": 0},
        {"kind": "market", "custo": _soma(total_itens, taxa, blank), "tokens": 0},
    ]
    if imb["has_token"]:
        token = estado["token"]
        ultimo = itens[imb["partial_buys_item"]]
        rotas.append({"kind": "tokens_full", "tokens": imb["tokens_full"],
                      "custo": _soma(custo(token, imb["tokens_full"]), taxa, blank)})
        rotas.append({"kind": "tokens_partial", "tokens": imb["tokens_partial"],
                      "custo": _soma(custo(token, imb["tokens_partial"]), ultimo["custo"], taxa, blank)})

    validas = [r for r in rotas if r["custo"] is not None]
    melhor = min(validas, key=lambda r: r["custo"]) if validas else None
    for r in rotas:
        r["label"] = ROUTE_LABEL[r["kind"]]
        r["diff"] = r["custo"] - melhor["custo"] if melhor and r["custo"] is not None else None

    return {"imb": imb, "itens": itens, "total_itens": total_itens, "rotas": rotas, "melhor": melhor}


def rota(res, kind):
    return next((r for r in res["rotas"] if r["kind"] == kind), None)


def custo_melhor(res):
    return res["melhor"]["custo"] if res["melhor"] else None


def economia_vs_scroll(res):
    s = rota(res, "scroll")["custo"]
    m = custo_melhor(res)
    return s - m if s is not None and m is not None else None


def _juntar(partes):
    if len(partes) <= 1:
        return "".join(partes)
    return ", ".join(partes[:-1]) + " e " + partes[-1]


def o_que_fazer(res, r, fazer_scroll):
    imb = res["imb"]
    depois = " (fazendo o scroll para usar depois)" if fazer_scroll else ""
    if r["kind"] == "scroll":
        return "Comprar o scroll pronto"
    if r["kind"] == "market":
        compra = [f"{i['comprar']} {i['nome']}" for i in res["itens"] if i["comprar"] > 0]
        if not compra:
            return f"Você já tem todos os itens: só embuir{depois}"
        return f"Comprar no market só o que falta ({_juntar(compra)}) e embuir{depois}"
    if r["kind"] == "tokens_full":
        return f"Comprar {imb['tokens_full']} tokens e trocar pelos 3 itens, depois embuir{depois}"
    ultimo = res["itens"][imb["partial_buys_item"]]
    n = imb["tokens_partial"]
    if ultimo["comprar"] > 0:
        return (f"Comprar {n} tokens, trocar pelos 2 primeiros itens, "
                f"comprar os {ultimo['comprar']} {ultimo['nome']} e embuir{depois}")
    return (f"Comprar {n} tokens, trocar pelos 2 primeiros itens, "
            f"usar os {ultimo['nome']} que você já tem e embuir{depois}")


def plano(resultados):
    def c(res, k):
        r = rota(res, k)
        return r["custo"] if r else None

    def reserva(res):
        v = [x for x in (c(res, "market"), c(res, "scroll")) if x is not None]
        return min(v) if v else None

    def tudo_token(kind):
        return _soma(*(c(r, kind) if r["imb"]["has_token"] else reserva(r) for r in resultados))

    recomendado = _soma(*(custo_melhor(r) for r in resultados))
    tudo_scroll = _soma(*(c(r, "scroll") for r in resultados))
    economia = tudo_scroll - recomendado if None not in (recomendado, tudo_scroll) else None
    return {
        "recomendado": recomendado,
        "tokens": sum(r["melhor"]["tokens"] for r in resultados if r["melhor"]),
        "tudo_market": _soma(*(c(r, "market") for r in resultados)),
        "tudo_6": tudo_token("tokens_full"),
        "tudo_4": tudo_token("tokens_partial"),
        "tudo_scroll": tudo_scroll,
        "economia": economia,
    }


def campos_faltando(selecionados, estado):
    """Textos dos preços obrigatórios ainda vazios."""
    falta = []
    if estado["taxa"] is None:
        falta.append("Taxa de embuir")
    if estado["fazer_scroll"] and estado["blank"] is None:
        falta.append("Preço do blank scroll")
    if any(i["has_token"] for i in selecionados) and estado["token"] is None:
        falta.append(f"Preço do {TOKEN_NAME}")
    vistos = set()
    for imb in selecionados:
        for d in imb["items"]:
            k = item_key(d["name"])
            tem = int(estado["inventario"].get(k) or 0)
            if k not in vistos and tem < d["qty"] and estado["precos"].get(k) is None:
                vistos.add(k)
                falta.append(f"Preço de {d['name']}")
        if estado["precos"].get(scroll_key(imb["id"])) is None:
            falta.append(f"Scroll pronto de {imb['name']}")
    return falta


def texto_resultado(resultados, pl, fazer_scroll):
    linhas = ["ZANDAO TIBIA TOOLS - EMBUIMENTOS", "", "FAÇA ASSIM"]
    for r in resultados:
        o = o_que_fazer(r, r["melhor"], fazer_scroll) if r["melhor"] else "faltam preços"
        linhas.append(f"- {label(r['imb'])}: {o} | Custo final: {gp(custo_melhor(r))}"
                      f" | Economia vs scroll pronto: {gp(economia_vs_scroll(r))}")
    linhas += [
        f"Total do plano: {gp(pl['recomendado'])}", "", "COMPARAÇÃO DO PLANO INTEIRO",
        f"- Plano recomendado: {gp(pl['recomendado'])}",
        f"- Tudo no market: {gp(pl['tudo_market'])}",
        f"- Tudo com 6 tokens: {gp(pl['tudo_6'])}",
        f"- Tudo com 4 tokens + último item: {gp(pl['tudo_4'])}",
        f"- Tudo scroll pronto: {gp(pl['tudo_scroll'])}",
        "", f"Economia vs tudo scroll pronto: {gp(pl['economia'])}",
        f"Gold tokens a comprar: {fmt(pl['tokens'])}",
    ]
    return "\n".join(linhas)
