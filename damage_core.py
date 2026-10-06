"""Análise de dano recebido (porte do Tibia Damage).

- parse_damage_input: lê o texto do "Received Damage" (Damage Input) copiado do cliente do Tibia.
- analisar: junta o log real com os ataques/resistências da TibiaWiki e devolve a distribuição
  de dano por elemento, as proteções recomendadas (embuimentos Powerful) e o ranking de
  elemento para atacar.

Diferenças em relação ao site:
- o peso de cada monstro vem das kills do Hunt Analyser (o site usava a ordem arrastada);
- as proteções usam os embuimentos certos da aba Embuimentos (Dragon Hide = fogo,
  Cloud Fabric = energia, Quara Scale = gelo, Snake Skin = terra, Lich Shroud = morte,
  Demon Presence = sagrado). Físico não tem embuimento de proteção.
"""

import re

ELEMENTOS = ["physical", "fire", "earth", "energy", "ice", "death", "holy",
             "drowning", "lifedrain", "manadrain", "healing"]
OFENSIVOS = ["physical", "fire", "ice", "earth", "energy", "death", "holy"]
RESISTENCIAS = ["physical", "fire", "ice", "earth", "energy", "death", "holy",
                "lifedrain", "manadrain", "drowning", "healing"]

ROTULO = {
    "physical": "Físico", "fire": "Fogo", "earth": "Terra", "energy": "Energia", "ice": "Gelo",
    "death": "Morte", "holy": "Sagrado", "drowning": "Afogamento", "lifedrain": "Life Drain",
    "manadrain": "Mana Drain", "healing": "Cura",
}

# elemento -> (id em data/imbuements.json, redução do Powerful)
PROTECAO = {
    "fire": ("dragonhide", 0.15), "energy": ("cloudfabric", 0.15), "ice": ("quarascale", 0.15),
    "earth": ("snakeskin", 0.15), "death": ("lichshroud", 0.15), "holy": ("demonpresence", 0.15),
}

_TIPOS = {
    "physical": "physical", "fire": "fire", "ice": "ice", "energy": "energy", "earth": "earth",
    "death": "death", "holy": "holy", "drowning": "drowning", "drown": "drowning",
    "life drain": "lifedrain", "lifedrain": "lifedrain", "hpdrain": "lifedrain",
    "mana drain": "manadrain", "manadrain": "manadrain",
}


def _num(s):
    d = re.sub(r"[^\d]", "", s or "")
    return int(d) if d else 0


def parse_damage_input(texto):
    """{'total', 'max_dps', 'tipos': {el: {'valor', 'pct'}}, 'fontes': [{'nome', 'valor', 'pct'}]}"""
    out = {"total": None, "max_dps": None, "tipos": {}, "fontes": []}
    secao = None
    for bruto in (texto or "").splitlines():
        linha = bruto.strip()
        if not linha:
            continue
        low = linha.lower()
        if re.match(r"^total\s*:", low):
            out["total"] = _num(linha.split(":", 1)[1]); continue
        if re.match(r"^max[-\s]?dps\s*:", low):
            out["max_dps"] = _num(linha.split(":", 1)[1]); continue
        if low.rstrip(":") == "damage types":
            secao = "tipos"; continue
        if low.rstrip(":") == "damage sources":
            secao = "fontes"; continue
        if low.rstrip(":") in ("received damage", "damage input"):
            secao = None; continue
        m = re.match(r"^(.+?)\s+([\d.,]+)\s*\(([\d.,]+)\s*%\)\s*$", linha)
        if not m or not secao:
            continue
        rotulo, valor, pct = m.group(1).strip(), _num(m.group(2)), float(m.group(3).replace(",", "."))
        if secao == "tipos":
            el = _TIPOS.get(rotulo.lower())
            if el:
                out["tipos"][el] = {"valor": valor, "pct": pct}
        else:
            out["fontes"].append({"nome": rotulo, "valor": valor, "pct": pct})
    return out


def eh_damage_input(texto):
    low = (texto or "").lower()
    return "damage types" in low or "damage sources" in low or "received damage" in low or "max-dps" in low


# ---------------------------------------------------------------------------
def classificar(v):
    if v is None:
        return "desconhecido"
    if v < 0:
        return "absorve"
    if v == 0:
        return "imune"
    if v > 100:
        return "fraqueza"
    if v < 100:
        return "resistente"
    return "normal"


def parte_por_elemento(k):
    """Fração do dano do monstro em cada elemento, só pelos ataques da wiki.
    Ataque sem dano conhecido conta com a mediana dos conhecidos (nunca um número inventado)."""
    if not k:
        return {}
    ofens = [a for a in k.get("ataques", []) if not a.get("cura") and a["elemento"] != "healing"]
    if not ofens:
        return {}
    conhecidos = sorted(((a.get("min") or 0) + a["max"]) / 2 for a in ofens if a.get("max") is not None)
    mediana = conhecidos[len(conhecidos) // 2] if conhecidos else 1
    por, total = {}, 0.0
    for a in ofens:
        v = ((a.get("min") or 0) + a["max"]) / 2 if a.get("max") is not None else mediana
        p = v * ((a.get("chance") if a.get("chance") is not None else 100) / 100)
        por[a["elemento"]] = por.get(a["elemento"], 0) + p
        total += p
    return {el: v / total for el, v in por.items()} if total else {}


def ranking_ofensivo(entradas):
    """entradas: [(ficha ou None, peso)]. Maior modificador médio = melhor elemento para atacar."""
    peso_total = sum(p for _, p in entradas) or 1
    out = []
    for el in OFENSIVOS:
        soma = psoma = 0.0
        imunes = 0
        for k, p in entradas:
            v = (k or {}).get("resist", {}).get(el)
            if v is None:
                continue
            if v <= 0:
                imunes += 1
            soma += v * p
            psoma += p
        media = soma / psoma if psoma else 100.0
        delta = media - 100
        if psoma == 0:
            motivo = "sem dados na wiki"
        elif imunes:
            motivo = f"{imunes} monstro(s) imune/absorve, evite"
        elif delta > 0.5:
            motivo = f"fraqueza média de {delta:.0f}%"
        elif delta < -0.5:
            motivo = f"resistência média de {-delta:.0f}%"
        else:
            motivo = "dano normal (100%)"
        out.append({"elemento": el, "rotulo": ROTULO[el], "media": round(media, 1), "delta": round(delta, 1),
                    "cobertura": round(psoma / peso_total, 3), "imunes": imunes, "motivo": motivo,
                    "sem_dados": psoma == 0})
    out.sort(key=lambda x: (-x["media"], x["elemento"]))
    return out


def analisar(monstros, dano, singular=lambda s: s.lower()):
    """monstros: [{'nome', 'kills' (int|None), 'ficha' (dict|None)}]
    dano: resultado de parse_damage_input ou None.
    singular: função que normaliza nomes (para casar fontes do log com os monstros)."""
    avisos = []
    n = len(monstros)
    if n == 0 and not (dano and dano["tipos"]):
        return None

    # 1. peso de cada monstro: kills, misturadas com o dano real de cada fonte do log
    total_kills = sum(m.get("kills") or 0 for m in monstros)
    base = [((m.get("kills") or 0) / total_kills) if total_kills else (1 / n) for m in monstros] if n else []
    fonte_peso = ["kills" if total_kills else "igual"] * n
    fontes = (dano or {}).get("fontes") or []
    fontes_mon = [f for f in fontes if any(singular(f["nome"]) == singular(m["nome"]) for m in monstros)]
    if fontes_mon and n:
        total_log = sum(f["valor"] for f in fontes_mon) or 1
        pesos = []
        for i, m in enumerate(monstros):
            achou = next((f for f in fontes_mon if singular(f["nome"]) == singular(m["nome"])), None)
            log = achou["valor"] / total_log if achou else 0
            pesos.append(0.6 * log + 0.4 * base[i])
            if achou:
                fonte_peso[i] = "kills + log" if total_kills else "log"
        s = sum(pesos) or 1
        pesos = [p / s for p in pesos]
    else:
        pesos = base

    sem_wiki = [m["nome"] for m in monstros if not ((m.get("ficha") or {}).get("fontes") or {}).get("wiki")]
    if sem_wiki:
        avisos.append("Sem ficha na TibiaWiki: " + ", ".join(sem_wiki) + ".")

    # 2. distribuição prevista pelos ataques da wiki
    prev = {el: 0.0 for el in ELEMENTOS}
    contrib = {}
    for i, m in enumerate(monstros):
        for el, s in parte_por_elemento(m.get("ficha")).items():
            c = pesos[i] * s
            prev[el] += c
            contrib.setdefault(el, []).append({"nome": m["nome"], "parte": c})
    soma_prev = sum(prev.values())

    # 3. distribuição: o Damage Input é o dano medido nesta hunt e vale sozinho. A previsão pela
    #    wiki só entra sem ele (o site misturava 65/35, mas com poucos monstros com ataques na wiki
    #    um único monstro dominava a previsão e distorcia o resultado).
    real = {el: v["pct"] / 100 for el, v in ((dano or {}).get("tipos") or {}).items()}
    tem_real, tem_prev = bool(real), soma_prev > 0
    final = {el: (real.get(el, 0) if tem_real else (prev[el] / soma_prev if tem_prev else 0)) for el in ELEMENTOS}
    if not tem_real and tem_prev:
        com_ataques = [m["nome"] for m in monstros if parte_por_elemento(m.get("ficha"))]
        if len(com_ataques) < n:
            avisos.append(f"Distribuição estimada só pelos ataques da wiki de {len(com_ataques)} de {n} monstros "
                          f"({', '.join(com_ataques)}). Cole o Damage Input para usar o dano real.")
    mantidos = [(el, v) for el, v in final.items() if v > 0.005 and el != "healing"]
    s = sum(v for _, v in mantidos) or 1
    elementos = sorted(
        ({"elemento": el, "rotulo": ROTULO[el], "parte": v / s, "real": el in real} for el, v in mantidos),
        key=lambda e: -e["parte"],
    )
    if not elementos:
        avisos.append("Sem ataques na wiki e sem Damage Input: cole o Received Damage para ver a distribuição.")

    detalhe = {}
    for el, lst in contrib.items():
        t = sum(x["parte"] for x in lst) or 1
        detalhe[el] = sorted(({"nome": x["nome"], "parte": x["parte"] / t} for x in lst), key=lambda x: -x["parte"])

    # quem mais dá cada elemento (pelos ataques da wiki: o Damage Input não separa monstro x elemento)
    for e in elementos:
        top = (detalhe.get(e["elemento"]) or [None])[0]
        e["top"] = {"nome": top["nome"], "parte": top["parte"]} if top else None

    # 4. proteções recomendadas: na MESMA ordem da distribuição (o elemento que mais bate vem primeiro).
    #    Elementos sem embuimento de proteção (Físico, Life Drain...) entram também: a proteção é pelos itens.
    protecoes = []
    for e in elementos:
        el = e["elemento"]
        imb, red = PROTECAO.get(el, (None, 0))
        top = (detalhe.get(el) or [None])[0]
        motivo = f"{e['parte'] * 100:.1f}% do dano recebido é {ROTULO[el]}"
        if top:
            motivo += f". Maior responsável: {top['nome']} ({top['parte'] * 100:.0f}% desse elemento)"
        motivo += " · confirmado pelo Damage Input" if e["real"] else " · estimado pelos ataques da wiki"
        protecoes.append({"elemento": el, "rotulo": ROTULO[el], "parte": e["parte"], "imbuement": imb,
                          "ganho": e["parte"] * red, "motivo": motivo})

    return {
        "elementos": elementos,
        "protecoes": protecoes,
        "ofensivo": ranking_ofensivo([(m.get("ficha"), pesos[i]) for i, m in enumerate(monstros)]),
        "pesos": [{"nome": m["nome"], "peso": pesos[i], "fonte": fonte_peso[i]} for i, m in enumerate(monstros)],
        "avisos": avisos,
        "total": (dano or {}).get("total"),
        "max_dps": (dano or {}).get("max_dps"),
        "fontes": fontes,
    }
