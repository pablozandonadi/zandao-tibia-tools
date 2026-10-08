"""Itens do Character Set: todos os equipamentos de cada slot (capacete, armadura, arma...), da TibiaWiki.

Cada item vem do Infobox Object da página (slot, level, vocação, armor/defense/attack, attrib, resist e as vagas de
embuimento "imbueslots") e a imagem pelo endereço direto do arquivo. Fica em cache_itens_set.json, um cache por slot
(30 dias); sem internet usa o cache velho. É diferente do equipamentos.py, que só carrega itens com proteção.
"""

import json
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request

import equipamentos
import monstros

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CACHE_PATH = os.path.join(BASE_DIR, "cache_itens_set.json")
VALIDADE = 30 * 86400
WIKI = "https://tibia.fandom.com/api.php"
HEADERS = {"User-Agent": "ZandaoTibiaTools/1.0 (+desktop app)"}
VOCACOES = equipamentos.VOCACOES

# slot do app -> categorias da wiki que o alimentam
CATEGORIAS = {
    "cabeca": ["Helmets"], "amuleto": ["Amulets and Necklaces"], "armadura": ["Armors"], "arma": ["Weapons"],
    "mao": ["Shields", "Spellbooks", "Quivers"], "pernas": ["Legs"], "botas": ["Boots"], "anel": ["Rings"],
    "trinket": [],                       # só os trinkets de TRINKETS (lista fechada, não vem de categoria)
    "consumivel": ["Potions", "Runes"],  # não é espaço de equipamento: só nome + ícone
}
SLOTS = [("cabeca", "Capacete"), ("amuleto", "Amuleto"), ("armadura", "Armadura"), ("arma", "Arma"),
         ("mao", "Escudo / Spellbook / Quiver"), ("pernas", "Calça"), ("botas", "Botas"), ("anel", "Anel"), ("trinket", "Trinket")]
# o campo "slot" da página da wiki -> slot do app
_SLOT_WIKI = {"head": "cabeca", "neck": "amuleto", "body": "armadura", "legs": "pernas", "feet": "botas", "finger": "anel",
              "weapon hand": "arma", "two-handed": "arma", "shield hand": "mao", "shield": "mao"}
_NOME_ELEMENTO = {"lifedrain": "Life Drain", "manadrain": "Mana Drain"}
ELEMENTOS_ATAQUE = ("physical", "fire", "ice", "earth", "energy", "death", "holy")

# Trinkets (Extra Slot): só estes, os que o usuário escolheu na TibiaWiki. nome -> (resistências, atributo)
TRINKETS = {
    "Bone Fiddle": ({"lifedrain": 5}, None), "Conch Shell Horn": ({"ice": 2}, None), "Cursed Coin": ({"physical": -20}, "critical hit chance 1%"),
    "Ink Blade": ({"energy": 2}, None), "Ink Brush": ({"energy": 2}, None), "Ink Claw": ({"energy": 2}, None),
    "Ink Quill": ({"energy": 2}, None), "Ink Vine": ({"energy": 2}, None), "Lit Torch": ({"holy": 2}, None),
    "Mariner's Anchor": ({}, "hard drinking"), "Moon Mirror": ({"death": 5}, None), "Scarab Ocarina": ({"earth": 2}, None),
    "Starlight Vial": ({"manadrain": 5}, None), "Sun Catcher": ({"fire": 5}, None),
}
_trava = threading.Lock()


def _item_simples(nome, slot):
    return {"nome": nome, "slot": slot, "level": None, "vocs": list(VOCACOES), "imbue": 0, "atk_elem": {}, "armor": None, "defense": None,
            "attack": None, "attrib": None, "resist": {}, "temporario": False, "imagem": None}


def trinkets():
    """Os trinkets liberados no app (sem imagem; a imagem vem do download do slot)."""
    saida = []
    for nome, (resist, attrib) in TRINKETS.items():
        saida.append({**_item_simples(nome, "trinket"), "resist": dict(resist), "attrib": attrib})
    return saida


def _inteiro(v):
    n = equipamentos._num(v)
    return n or None


def item_do_wikitext(titulo, wikitext, slot_padrao):
    """Item a partir do wikitext da página; None se não houver Infobox Object. O campo slot da página vence o da
    categoria; na categoria das armas, página sem slot reconhecido não é arma (é munição, item de quest...)."""
    f = monstros._campos_infobox(wikitext, "Infobox Object")
    if not f:
        return None
    slot = _SLOT_WIKI.get((f.get("slot") or "").strip().lower())
    if slot is None:
        if slot_padrao == "arma":
            return None
        slot = slot_padrao
    return {
        "nome": f.get("name") or titulo, "slot": slot, "level": equipamentos._num(f.get("levelrequired")),
        "vocs": equipamentos._vocs_do_item(f.get("vocrequired")), "imbue": equipamentos._num(f.get("imbueslots")),
        "atk_elem": {el: n for el in ELEMENTOS_ATAQUE if (n := _inteiro(f.get(el + "_attack")))},
        "armor": _inteiro(f.get("armor")), "defense": _inteiro(f.get("defense")), "attack": _inteiro(f.get("attack")),
        "attrib": monstros._sem_links(f.get("attrib") or "") or None, "resist": equipamentos.parse_resist(f.get("resist")),
        "temporario": bool((f.get("duration") or "").strip() not in ("", "--") or (f.get("charges") or "").strip() not in ("", "--")),
        "imagem": None,
    }


def _maiuscula(texto):
    return re.sub(r"\b([a-z])", lambda m: m.group(1).upper(), texto)


def descricao(item):
    """"Arm: 8, Magic Level +2, Energy +8%, Physical +3%, Ice -2%" (o que aparece ao lado do nome do item)."""
    partes = []
    for rotulo, chave in (("Arm", "armor"), ("Def", "defense"), ("Atk", "attack")):
        if item.get(chave):
            partes.append(f"{rotulo}: {item[chave]}")
    for el, v in (item.get("atk_elem") or {}).items():
        partes.append(f"{el.capitalize()} Atk: {v}")
    if item.get("attrib"):
        partes += [_maiuscula(p.strip()) for p in item["attrib"].split(",") if p.strip()]
    for el, v in sorted((item.get("resist") or {}).items(), key=lambda x: (-x[1], x[0])):
        partes.append(f"{_NOME_ELEMENTO.get(el, el.capitalize())} {'+' if v > 0 else ''}{v}%")
    return ", ".join(partes)


# ---------------------------------------------------------------------------
# download (TibiaWiki) e cache por slot
# ---------------------------------------------------------------------------
def _get(params):
    url = WIKI + "?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
        return json.load(r)


def _imagens(nomes):
    """nome -> endereço direto da imagem (a wiki bloqueia Special:FilePath fora do site; lotes de 50)."""
    urls = {}
    nomes = sorted(set(nomes))
    for i in range(0, len(nomes), 50):
        r = _get({"action": "query", "prop": "imageinfo", "iiprop": "url", "titles": "|".join(f"File:{n}.gif" for n in nomes[i:i + 50])})
        normal = {x["to"]: x["from"] for x in r["query"].get("normalized", [])}
        for p in r["query"]["pages"].values():
            info = (p.get("imageinfo") or [{}])[0]
            if info.get("url"):
                urls[normal.get(p["title"], p["title"])[len("File:"):-len(".gif")]] = info["url"]
    return urls


def _titulos_da_categoria(cat):
    titulos, cont = [], {}
    while True:
        r = _get({"action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat, "cmlimit": "500", "cmtype": "page", **cont})
        titulos += [m["title"] for m in r["query"]["categorymembers"]]
        if "continue" not in r:
            return titulos
        cont = r["continue"]


def _baixar_slot(slot):
    if slot in ("trinket", "consumivel"):
        if slot == "trinket":
            itens = trinkets()
        else:
            itens = [_item_simples(t, "consumivel") for cat in CATEGORIAS[slot] for t in _titulos_da_categoria(cat)]
        urls = _imagens(i["nome"] for i in itens)
        for item in itens:
            item["imagem"] = urls.get(item["nome"])
        return [i for i in itens if i["imagem"]]   # páginas de categoria ("Runes", "Area Runes"...) não têm imagem
    itens = []
    for cat in CATEGORIAS[slot]:
        titulos = _titulos_da_categoria(cat)
        for i in range(0, len(titulos), 50):
            r = _get({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "titles": "|".join(titulos[i:i + 50])})
            for p in r["query"]["pages"].values():
                try:
                    texto = p["revisions"][0]["slots"]["main"]["*"]
                except (KeyError, IndexError):
                    continue
                item = item_do_wikitext(p["title"], texto, slot)
                if item and item["slot"] == slot:
                    itens.append(item)
    urls = _imagens(i["nome"] for i in itens)
    for item in itens:
        item["imagem"] = urls.get(item["nome"])
    return itens


def _organizar(itens):
    vistos, saida = set(), []
    for i in sorted(itens, key=lambda x: x["nome"].lower()):
        if i["nome"].lower() not in vistos:
            vistos.add(i["nome"].lower())
            saida.append(i)
    return saida


def itens_do_slot(slot, caminho=None, buscar=None):
    """Itens do slot ordenados por nome, sem repetir. Cache de 30 dias por slot; sem internet usa o velho (ou [])."""
    if slot not in CATEGORIAS:
        return []
    caminho = caminho or CACHE_PATH
    with _trava:
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except (OSError, json.JSONDecodeError):
            cache = {}
        slots = cache.get("slots") if isinstance(cache.get("slots"), dict) else {}
        entrada = slots.get(slot) or {}
        if entrada.get("itens") and time.time() - entrada.get("t", 0) < VALIDADE:
            return entrada["itens"]
        try:
            itens = _organizar((buscar or _baixar_slot)(slot))
            if itens:
                slots[slot] = {"t": time.time(), "itens": itens}
                try:
                    with open(caminho, "w", encoding="utf-8") as f:
                        json.dump({"v": 1, "slots": slots}, f, ensure_ascii=False)
                except OSError:
                    pass
                return itens
        except Exception:
            pass
        return entrada.get("itens") or []
