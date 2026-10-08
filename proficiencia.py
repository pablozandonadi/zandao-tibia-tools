"""Proficiência de arma (Weapon Proficiency) e Perk Shaping Options, da TibiaWiki em português (tibiawiki.com.br).

- Cada arma tem 7 níveis (colunas) de perks, com 1 a 3 opções por coluna: o jogador usa UMA por coluna (a 1ª é o padrão).
- Perk Shaping (Summer Update 2026): troca o perk de uma coluna por uma das ~184 opções, com rank de 0 a 10.
  Troca 1 exige ao menos 1 nível de proficiência; a Troca 2 exige Maestria. Valor no rank r = reta entre o rank 0 e o rank 10.
- Na arma do set: item["perks"] (colunas lidas da wiki) e item["prof"] = {"nivel": 0..7, "maestria": bool,
  "escolhas": [índice da opção por coluna], "trocas": [{"coluna", "opcao", "rank"}]}.
Quem usa: stats_set.somar (soma no Combat Stats), web_api (set_perks / set_shaping), web/sets.js (editor da arma).
"""

import json
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request

import monstros

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CACHE_PATH = os.path.join(BASE_DIR, "cache_proficiencia.json")
VALIDADE = 30 * 86400
VERSAO_CACHE = 1
WIKI = "https://www.tibiawiki.com.br/api.php"
HEADERS = {"User-Agent": "ZandaoTibiaTools/1.0 (+desktop app)"}
NIVEIS = 7
MAX_RANK = 10
_PERK = re.compile(r"\{\{Weapon Perk\|([^|{}]*)\|[^|{}]*\|(.*?)\}\}", re.S)
_NUMERO = re.compile(r"^\s*([+-]?\d+(?:[.,]\d+)?)(%?)\s*(.*)$", re.S)
_trava = threading.Lock()


# ---------------------------------------------------------------------------
# leitura do texto da wiki
# ---------------------------------------------------------------------------
def perks_da_wikitext(wikitext):
    """Colunas de perks de uma arma: [[{"tipo", "texto"}, ...], ...] (uma lista por nível); [] se a página não tem proficiência."""
    campos = monstros._campos_infobox(wikitext, "Infobox_Item") or monstros._campos_infobox(wikitext, "Infobox Item")
    colunas = []
    for k in range(1, NIVEIS + 1):
        opcoes = [{"tipo": t.strip(), "texto": monstros._sem_links(x).strip()} for t, x in _PERK.findall(campos.get(f"perk{k}", ""))]
        colunas.append(opcoes)
    while colunas and not colunas[-1]:
        colunas.pop()
    return colunas if any(colunas) else []


def _numero(txt):
    v = float(txt.replace(",", "."))
    return int(v) if v.is_integer() else v


def valor_e_rotulo(texto):
    """"+7.50% critical extra damage para Death spells e runes" -> (7.5, "%", "critical extra damage para Death spells e runes"); None se não começar por número."""
    m = _NUMERO.match(texto or "")
    return (_numero(m.group(1)), m.group(2), m.group(3).strip()) if m else None


def opcao_do_wikitext(titulo, wikitext):
    """Opção do Perk Shaping: {"nome", "perk", "voc", "descricao", "rank0", "rank10"}; None se a página não for uma."""
    f = monstros._campos_infobox(wikitext, "Infobox Perk Option")
    if not f or not f.get("rank0") or not f.get("rank10"):
        return None
    return {"nome": f.get("name") or titulo, "perk": f.get("perk", ""), "voc": (f.get("voc") or "").strip().lower(),
            "descricao": monstros._sem_links(f.get("description", "")), "rank0": monstros._sem_links(f["rank0"]), "rank10": monstros._sem_links(f["rank10"])}


def _fmt(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s or "0"


def texto_no_rank(opcao, rank):
    """Texto da opção no rank pedido (0 a 10): reta entre o rank 0 e o rank 10 da wiki."""
    a, b = valor_e_rotulo(opcao["rank0"]), valor_e_rotulo(opcao["rank10"])
    if not a or not b:
        return opcao["rank0"] if not rank else opcao["rank10"]
    rank = max(0, min(MAX_RANK, int(rank)))
    v = a[0] + (b[0] - a[0]) * rank / MAX_RANK
    return f"{'-' if v < 0 else '+'}{_fmt(abs(v))}{a[1]} {a[2]}".strip()


# ---------------------------------------------------------------------------
# efeitos da arma (o que entra no Combat Stats)
# ---------------------------------------------------------------------------
def _trocas_validas(prof, opcoes, nivel):
    por_nome = {o["nome"]: o for o in opcoes}
    saida = {}
    for i, t in enumerate((prof.get("trocas") or [])[:2]):
        if not isinstance(t, dict) or nivel < 1 or (i == 1 and not prof.get("maestria")):
            continue                                   # Troca 1: 1 nível de proficiência; Troca 2: Maestria
        coluna, op = t.get("coluna"), por_nome.get(t.get("opcao"))
        if isinstance(coluna, int) and 1 <= coluna <= nivel and op:
            saida[coluna] = texto_no_rank(op, t.get("rank") or 0)
    return saida


def efeitos(arma, opcoes=()):
    """Perks ativos da arma: {"lista": [{"rotulo", "valor", "unidade"}]} com os iguais somados.
    Usa o nível (padrão 7), a opção escolhida em cada coluna (padrão: a primeira) e as trocas do Perk Shaping."""
    prof = arma.get("prof") or {}
    colunas = arma.get("perks") or []
    nivel = prof.get("nivel", NIVEIS)
    nivel = max(0, min(NIVEIS, nivel if isinstance(nivel, int) else NIVEIS))
    escolhas = prof.get("escolhas") or []
    trocas = _trocas_validas(prof, opcoes, nivel)
    textos = []
    for c in range(1, min(nivel, len(colunas)) + 1):
        if c in trocas:
            textos.append(trocas[c])
        elif colunas[c - 1]:
            i = escolhas[c - 1] if c - 1 < len(escolhas) and isinstance(escolhas[c - 1], int) and 0 <= escolhas[c - 1] < len(colunas[c - 1]) else 0
            textos.append(colunas[c - 1][i]["texto"])
    soma, sem_numero = {}, []
    for t in textos:
        vr = valor_e_rotulo(t)
        if vr:
            valor, unidade, rotulo = vr
            rotulo = re.sub(r"^de ", "", rotulo)           # as opções do Perk Shaping vêm como "+4% de penetração de armadura"
            soma[(rotulo, unidade)] = soma.get((rotulo, unidade), 0) + valor
        elif t not in sem_numero:
            sem_numero.append(t)       # perk só em texto (sem número para somar)
    return {"lista": [{"rotulo": r, "valor": round(v, 4), "unidade": u} for (r, u), v in soma.items()], "textos": sem_numero}


# ---------------------------------------------------------------------------
# download (TibiaWiki em português) e cache
# ---------------------------------------------------------------------------
def _get(params):
    url = WIKI + "?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
        return json.load(r)


def _paginas(categoria):
    titulos, cont = [], {}
    while True:
        r = _get({"action": "query", "list": "categorymembers", "cmtitle": "Category:" + categoria, "cmlimit": "500", **cont})
        titulos += [m["title"] for m in r["query"]["categorymembers"]]
        if "continue" not in r:
            break
        cont = r["continue"]
    for i in range(0, len(titulos), 50):
        r = _get({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "titles": "|".join(titulos[i:i + 50])})
        for p in r["query"]["pages"].values():
            try:
                yield p["title"], p["revisions"][0]["slots"]["main"]["*"]
            except (KeyError, IndexError):
                continue


def _baixar():
    armas = {}
    for titulo, texto in _paginas("Arma com Proficiência"):
        colunas = perks_da_wikitext(texto)
        if colunas:
            armas[titulo] = colunas
    opcoes = [o for t, x in _paginas("Perk Shaping Options") if (o := opcao_do_wikitext(t, x))]
    return {"armas": armas, "opcoes": sorted(opcoes, key=lambda o: o["nome"])}


def carregar(caminho=None, buscar=None):
    """{"armas": {nome: colunas}, "opcoes": [...]} com cache de 30 dias; sem internet usa o cache velho (ou vazio)."""
    caminho = caminho or CACHE_PATH
    with _trava:
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except (OSError, json.JSONDecodeError):
            cache = {}
        if cache.get("v") == VERSAO_CACHE and cache.get("armas") and time.time() - cache.get("t", 0) < VALIDADE:
            return {"armas": cache["armas"], "opcoes": cache.get("opcoes", [])}
        try:
            dados = (buscar or _baixar)()
            if dados.get("armas"):
                try:
                    with open(caminho, "w", encoding="utf-8") as f:
                        json.dump({"v": VERSAO_CACHE, "t": time.time(), **dados}, f, ensure_ascii=False)
                except OSError:
                    pass
                return dados
        except Exception:
            pass
        return {"armas": cache.get("armas") or {}, "opcoes": cache.get("opcoes") or []}
