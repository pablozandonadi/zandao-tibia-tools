"""Itens recomendados: equipamentos com proteção contra o dano da hunt, filtrados pela vocação e level.

Dados da TibiaWiki (Infobox Object de cada item: levelrequired, vocrequired, resist, slot...), baixados
por categoria (Helmets, Armors, Legs, Boots, Shields, Spellbooks, Quivers, Amulets and Necklaces, Rings)
em lotes de 50 páginas e guardados em cache_itens.json por 30 dias.

Ordem dos itens:
- por um elemento (ex.: energy): a % de proteção nesse elemento;
- "esta hunt": soma de (proteção do item em cada elemento × parte do dano da hunt naquele elemento),
  ou seja, quanto o item reduz do dano TOTAL recebido nesta hunt (negativos contam contra).
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

CACHE_PATH = os.path.join(BASE_DIR, "cache_itens.json")
VALIDADE = 30 * 86400
VERSAO_CACHE = 2  # sobe quando o formato do cache muda (força baixar de novo)
WIKI = "https://tibia.fandom.com/api.php"
HEADERS = {"User-Agent": "ZandaoTibiaTools/1.0 (+desktop app)"}

# categoria da wiki -> slot no app
CATEGORIAS = {
    "Helmets": "cabeca", "Armors": "armadura", "Legs": "pernas", "Boots": "botas",
    "Shields": "mao", "Spellbooks": "mao", "Quivers": "mao",
    "Amulets and Necklaces": "amuleto", "Rings": "anel",
}
SLOTS = [("cabeca", "Capacete"), ("armadura", "Armadura"), ("pernas", "Calça"), ("botas", "Botas"),
         ("mao", "Escudo / Spellbook / Quiver"), ("amuleto", "Amuleto"), ("anel", "Anel")]

VOCACOES = ["knight", "paladin", "sorcerer", "druid", "monk"]

_ELEMENTOS = {"physical": "physical", "fire": "fire", "ice": "ice", "energy": "energy", "earth": "earth",
              "death": "death", "holy": "holy", "life drain": "lifedrain", "lifedrain": "lifedrain",
              "mana drain": "manadrain", "manadrain": "manadrain", "drowning": "drowning", "drown": "drowning",
              "healing": "healing"}

_trava = threading.Lock()


def vocacao_base(vocacao):
    """'Master Sorcerer' -> 'sorcerer'; 'Elite Knight' -> 'knight'... None se não reconhecer."""
    v = (vocacao or "").lower()
    return next((b for b in VOCACOES if b in v), None)


def _vocs_do_item(texto):
    t = (texto or "").lower()
    vocs = [b for b in VOCACOES if b in t]
    return vocs or list(VOCACOES)  # vazio / "--" / "none" = qualquer vocação


def parse_resist(texto):
    """'physical +3%, energy +8%, ice -2%' -> {'physical': 3, 'energy': 8, 'ice': -2}"""
    out = {}
    for nome, valor in re.findall(r"([a-z][a-z ]*?)\s*([+-]?\d+(?:\.\d+)?)\s*%", (texto or "").lower()):
        el = _ELEMENTOS.get(nome.strip())
        if el:
            v = float(valor)
            out[el] = int(v) if v.is_integer() else v
    return out


def _num(v):
    m = re.search(r"\d+", v or "")
    return int(m.group(0)) if m else 0


def item_do_wikitext(titulo, wikitext, slot):
    """Item a partir do wikitext da página. None se não for um equipamento com proteção."""
    f = monstros._campos_infobox(wikitext, "Infobox Object")
    resist = parse_resist(f.get("resist"))
    if not resist:
        return None
    nome = f.get("name") or titulo
    return {
        "nome": nome, "slot": slot, "level": _num(f.get("levelrequired")), "vocs": _vocs_do_item(f.get("vocrequired")),
        "resist": resist, "attrib": monstros._sem_links(f.get("attrib") or "") or None,
        "armor": _num(f.get("armor")) or None,
        "temporario": bool((f.get("duration") or "").strip() not in ("", "--") or (f.get("charges") or "").strip() not in ("", "--")),
        "imagem": None,  # preenchida em _baixar_todos (endereço direto da imagem na wiki)
    }


def _get(params):
    url = WIKI + "?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
        return json.load(r)


def _baixar_todos():
    itens = []
    for cat, slot in CATEGORIAS.items():
        titulos, cont = [], {}
        while True:
            r = _get({"action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat,
                      "cmlimit": "500", "cmtype": "page", **cont})
            titulos += [m["title"] for m in r["query"]["categorymembers"]]
            if "continue" not in r:
                break
            cont = r["continue"]
        for i in range(0, len(titulos), 50):
            r = _get({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                      "titles": "|".join(titulos[i:i + 50])})
            for p in r["query"]["pages"].values():
                try:
                    texto = p["revisions"][0]["slots"]["main"]["*"]
                except (KeyError, IndexError):
                    continue
                if "{{Infobox Object" in texto:
                    item = item_do_wikitext(p["title"], texto, slot)
                    if item:
                        itens.append(item)
    # imagens: a wiki bloqueia Special:FilePath fora do site, então pega o endereço direto (lotes de 50)
    nomes = sorted({i["nome"] for i in itens})
    urls = {}
    for i in range(0, len(nomes), 50):
        r = _get({"action": "query", "prop": "imageinfo", "iiprop": "url",
                  "titles": "|".join(f"File:{n}.gif" for n in nomes[i:i + 50])})
        normal = {x["to"]: x["from"] for x in r["query"].get("normalized", [])}
        for p in r["query"]["pages"].values():
            info = (p.get("imageinfo") or [{}])[0]
            if info.get("url"):
                titulo = normal.get(p["title"], p["title"])
                urls[titulo[len("File:"):-len(".gif")]] = info["url"]
    for it in itens:
        it["imagem"] = urls.get(it["nome"])
    return itens


def carregar_itens(forcar=False):
    """Lista de itens com proteção (cache de 30 dias; sem internet usa o cache velho)."""
    with _trava:
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except (OSError, json.JSONDecodeError):
            cache = {}
        if not forcar and cache.get("itens") and cache.get("v") == VERSAO_CACHE and time.time() - cache.get("t", 0) < VALIDADE:
            return cache["itens"]
        try:
            itens = _baixar_todos()
            if itens:
                try:
                    with open(CACHE_PATH, "w", encoding="utf-8") as f:
                        json.dump({"v": VERSAO_CACHE, "t": time.time(), "itens": itens}, f, ensure_ascii=False)
                except OSError:
                    pass
                return itens
        except Exception:
            pass
        return cache.get("itens") or []


def pontuar(item, elemento=None, distribuicao=None):
    """Proteção no elemento escolhido, ou redução do dano total da hunt (pesando pela distribuição)."""
    if elemento:
        return item["resist"].get(elemento, 0)
    return sum(pct * (distribuicao or {}).get(el, 0) for el, pct in item["resist"].items())


def recomendar(itens, vocacao, level, distribuicao, elemento=None, por_slot=None):
    """{slot: [itens]}: TODOS os itens que essa vocação/level pode usar e que protegem (maior primeiro).
    por_slot limita a quantidade (None = todos)."""
    voc = vocacao_base(vocacao)
    level = int(level or 0)
    out = {}
    for slot, _ in SLOTS:
        candidatos, vistos = [], set()
        for it in itens:
            if it["nome"] in vistos:  # a wiki às vezes tem o mesmo item em duas páginas
                continue
            if it["slot"] != slot or it["level"] > level or (voc and voc not in it["vocs"]):
                continue
            nota = pontuar(it, elemento, distribuicao)
            if nota <= 0:
                continue
            vistos.add(it["nome"])
            candidatos.append({**it, "nota": round(nota, 3)})
        # empate: o de level mais alto costuma ser o item melhor no resto (armor, atributos)
        candidatos.sort(key=lambda x: (-x["nota"], -x["level"], x["nome"]))
        out[slot] = candidatos[:por_slot] if por_slot else candidatos
    return out
