"""Ficha dos monstros: TibiaWiki (tibia.fandom.com) como fonte principal, TibiaData como complemento.

Porte para Python do monster-engine do Tibia Damage. Nada é inventado: o que nenhuma das duas
fontes traz fica None. As respostas ficam em cache_monstros.json, ao lado do programa, para a
segunda análise da mesma hunt não precisar de internet.

Modificador de dano recebido (resistências), em %:
  > 100 fraqueza · 100 normal · 0 < v < 100 resistente · 0 imune · < 0 absorve (cura)
"""

import json
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CACHE_PATH = os.path.join(BASE_DIR, "cache_monstros.json")
WIKI = "https://tibia.fandom.com/api.php"
TIBIADATA = "https://api.tibiadata.com/v4"
HEADERS = {"User-Agent": "ZandaoTibiaTools/1.0 (+desktop app)"}
TIMEOUT = 15
VALIDADE_LISTA = 7 * 86400       # lista de criaturas do TibiaData
VALIDADE_MONSTRO = 30 * 86400    # ficha de cada monstro

# ---------------------------------------------------------------------------
# Nomes: singular, Title Case e casamento aproximado com a lista do TibiaData
# ---------------------------------------------------------------------------

def singularizar(nome):
    s = re.sub(r"\s+", " ", (nome or "").lower()).strip()
    if not s:
        return s
    partes = s.split(" ")
    ult = partes[-1]
    if len(ult) > 3 and ult.endswith("ies"):
        ult = ult[:-3] + "y"
    elif re.search(r"(ches|shes|xes|sses|zzes)$", ult):
        ult = ult[:-2]
    elif re.search(r"[^s]s$", ult) and not re.search(r"(ss|us|is)$", ult):
        ult = ult[:-1]
    partes[-1] = ult
    return " ".join(partes)


def titulo(s):
    return " ".join(w[:1].upper() + w[1:] for w in s.split(" "))


def canonico(nome):
    return titulo(singularizar(nome))


def _levenshtein(a, b):
    if a == b:
        return 0
    if not a or not b:
        return len(a) or len(b)
    linha = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        ant, linha[0] = linha[0], i
        for j in range(1, len(b) + 1):
            tmp = linha[j]
            linha[j] = ant if a[i - 1] == b[j - 1] else 1 + min(ant, linha[j], linha[j - 1])
            ant = tmp
    return linha[-1]


def casar_criatura(nome_cru, lista):
    """Melhor criatura da lista (dicts do TibiaData) para um nome do log, ou None.
    Igual no singular ganha; senão aceita 1 letra de diferença (2 em nomes de 8+ letras), para
    erro de digitação não virar outro monstro (ex.: 'Zandao' não pode casar com 'Panda')."""
    sing = singularizar(nome_cru)
    melhor, dist = None, None
    for c in lista:
        cs = singularizar(c["name"])
        if cs == sing:
            return c
        d = _levenshtein(cs, sing)
        if dist is None or d < dist:
            melhor, dist = c, d
    if melhor and len(sing) > 4 and dist <= (2 if len(sing) >= 8 else 1):
        return melhor
    return None


# ---------------------------------------------------------------------------
# Cache em disco
# ---------------------------------------------------------------------------
_trava = threading.Lock()
_cache = None


def _carregar_cache():
    global _cache
    if _cache is None:
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        except (OSError, json.JSONDecodeError):
            _cache = {}
        _cache.setdefault("criaturas", None)
        _cache.setdefault("monstros", {})
    return _cache


def _salvar_cache():
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
    except OSError:
        pass


def _get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def lista_criaturas():
    """Lista oficial (nome, race, image_url). Usa o cache; se a internet falhar, o cache vencido serve."""
    with _trava:
        c = _carregar_cache()
        guardada = c["criaturas"]
    if guardada and time.time() - guardada["t"] < VALIDADE_LISTA:
        return guardada["lista"]
    try:
        js = _get_json(f"{TIBIADATA}/creatures")
        lista = [
            {"name": x["name"], "race": x["race"], "image_url": x.get("image_url", "")}
            for x in js.get("creatures", {}).get("creature_list", [])
        ]
        if lista:
            with _trava:
                c["criaturas"] = {"t": time.time(), "lista": lista}
                _salvar_cache()
            return lista
    except Exception:
        pass
    return guardada["lista"] if guardada else []


# ---------------------------------------------------------------------------
# Parser do wikitext (Infobox Creature)
# ---------------------------------------------------------------------------
ELEMENTO_ALIAS = {
    "physical": "physical", "phys": "physical", "melee": "physical",
    "fire": "fire", "ice": "ice", "energy": "energy",
    "earth": "earth", "poison": "earth",
    "death": "death", "holy": "holy",
    "drown": "drowning", "drowning": "drowning",
    "hpdrain": "lifedrain", "lifedrain": "lifedrain", "life drain": "lifedrain",
    "manadrain": "manadrain", "mana drain": "manadrain",
    "healing": "healing", "heal": "healing",
}

MOD_CHAVES = {
    "physicalDmgMod": "physical", "fireDmgMod": "fire", "iceDmgMod": "ice",
    "energyDmgMod": "energy", "earthDmgMod": "earth", "deathDmgMod": "death",
    "holyDmgMod": "holy", "drownDmgMod": "drowning", "hpDrainDmgMod": "lifedrain",
    "manaDrainDmgMod": "manadrain", "healMod": "healing",
}

FORMA = {"strike": "Alvo único", "wave": "Wave", "twave": "Wave", "ball": "Área",
         "ballself": "Ao redor", "beam": "Beam", "ring": "Anel", "square": "Área"}


def _norm_el(s):
    return ELEMENTO_ALIAS.get((s or "").strip().lower())


def _adivinhar_elemento(nome):
    n = nome.lower()
    for padrao, el in ((r"fire|flame|burn|magma|lava", "fire"), (r"ice|freez|frost", "ice"),
                       (r"energy|lightning|shock|electr", "energy"), (r"earth|poison|venom|terra", "earth"),
                       (r"death|curse|unholy|necro", "death"), (r"holy|divine", "holy"), (r"drown", "drowning"),
                       (r"mana\s*drain", "manadrain"), (r"life\s*drain|drain", "lifedrain"), (r"heal", "healing")):
        if re.search(padrao, n):
            return el
    return "physical"


def _faixa(s):
    if not s:
        return None, None
    s = s.replace(",", "")
    m = re.search(r"(\d+)\s*[-–]\s*(\d+)", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+)", s)
    return (None, int(m.group(1))) if m else (None, None)


def _separar_params(corpo):
    """Divide os parâmetros de um template em '|', respeitando {{ }} e [[ ]] aninhados."""
    out, prof, buf, i = [], 0, [], 0
    while i < len(corpo):
        dois = corpo[i:i + 2]
        if dois in ("{{", "[["):
            prof += 1; buf.append(dois); i += 2; continue
        if dois in ("}}", "]]"):
            prof -= 1; buf.append(dois); i += 2; continue
        ch = corpo[i]
        if ch == "|" and prof == 0:
            out.append("".join(buf)); buf = []
        else:
            buf.append(ch)
        i += 1
    out.append("".join(buf))
    return out


def _extrair_template(texto, inicio):
    """Corpo do primeiro {{...}} a partir de 'inicio' (sem as chaves)."""
    ini = texto.find("{{", inicio)
    if ini < 0:
        return None
    prof, i = 0, ini
    while i < len(texto) - 1:
        dois = texto[i:i + 2]
        if dois == "{{":
            prof += 1; i += 2; continue
        if dois == "}}":
            prof -= 1; i += 2
            if prof == 0:
                return texto[ini + 2:i - 2]
            continue
        i += 1
    return None


def _campos_infobox(wikitext, template="Infobox Creature"):
    idx = wikitext.find("{{" + template)
    if idx < 0:
        return {}
    corpo = _extrair_template(wikitext, idx)
    if corpo is None:
        return {}
    campos = {}
    for parte in _separar_params(corpo):
        k, sep, v = parte.partition("=")
        if sep and k.strip():
            campos[k.strip()] = v.strip()
    return campos


def _sem_links(s):
    s = re.sub(r"\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", s)
    return re.sub(r"<[^>]+>", " ", s).strip()


def _cena(cena):
    m = re.search(r"spell\s*=\s*([^|}\n]+)", cena)
    if not m:
        return None
    spell = m.group(1).strip()
    m = re.match(r"^(\d+)sqm(\w+)$", spell)
    if not m:
        return spell
    return f"{FORMA.get(m.group(2).lower(), m.group(2))} · {m.group(1)} sqm"


def _ataques(bruto):
    ataques, invoca = [], []
    if not bruto:
        return ataques, invoca
    idx = bruto.find("{{Ability List")
    container = (_extrair_template(bruto, idx) if idx >= 0 else None) or bruto
    for parte in _separar_params(container):
        p = parte.strip()
        if not p.startswith("{{"):
            continue
        interno = _extrair_template(p, 0)
        if interno is None:
            continue
        params = _separar_params(interno)
        tipo = params[0].strip().lower()
        posicionais, nomeados = [], {}
        for r in params[1:]:
            k, sep, v = r.partition("=")
            if sep and "{{" not in k:
                nomeados[k.strip()] = v.strip()
            else:
                posicionais.append(r.strip())
        if tipo == "summon":
            n = _sem_links(posicionais[0] if posicionais else "")
            if n:
                invoca.append(n)
            continue
        if tipo not in ("haste", "healing", "melee", "ability"):
            continue
        melee, haste = tipo == "melee", tipo == "haste"
        if melee:
            nome = "Melee"
        else:
            nome = _sem_links(posicionais[0] if posicionais else ("Haste" if haste else ""))
        if not nome or haste or re.search(r"invisib|paraly|outfit|teleport|speed|haste|summon", nome, re.I):
            continue  # habilidade sem dano: não entra na distribuição
        dano_bruto = (posicionais[0] if posicionais else None) if melee else (posicionais[1] if len(posicionais) > 1 else None)
        el_bruto = nomeados.get("element") or ("physical" if melee else (posicionais[2] if len(posicionais) > 2 else None))
        el = _norm_el(el_bruto) or ("physical" if melee else _adivinhar_elemento(nome))
        if haste:
            el = "physical"
        cond = ", ".join(f"{k[:1].upper()}{k[1:]} {v}" for k, v in nomeados.items()
                         if k.lower() in ("poison", "fire", "energy", "bleed", "curse", "dazzled", "drown", "electrified", "freezing"))
        dist = re.search(r"from\s+([\d-]+)\s+squares?", dano_bruto or "", re.I)
        primeira = (dano_bruto or "").split(";")[0]
        mn, mx = _faixa(primeira)
        try:
            chance = float(nomeados["chance"]) if "chance" in nomeados else None
        except ValueError:
            chance = None
        ataques.append({
            "nome": nome, "elemento": el, "min": mn, "max": mx,
            "dano": primeira.strip() if dano_bruto and dano_bruto != "?" else None,
            "chance": chance,
            "area": _cena(nomeados["scene"]) if "scene" in nomeados else None,
            "distancia": "Corpo a corpo" if melee else (f"{dist.group(1)} sqm" if dist else None),
            "condicao": cond or None,
            "cura": el == "healing" or bool(re.search(r"heal", nome, re.I)),
        })
    return ataques, invoca


def ficha_do_wikitext(wikitext, titulo_pagina):
    """Converte o wikitext de uma criatura numa ficha. Público para os testes."""
    f = _campos_infobox(wikitext)

    def num(v):
        if not v:
            return None
        s = re.sub(r"[^\d.]", "", v)
        try:
            n = float(s)
        except ValueError:
            return None
        return int(n) if n.is_integer() else n

    def traco(v):
        if not v:
            return None
        t = _sem_links(v)
        return None if t in ("--", "-", "?", "") else t

    resist, incertos = {}, []
    for k, el in MOD_CHAVES.items():
        v = f.get(k)
        if not v:
            continue
        m = re.match(r"\s*(-?\d+)", v.replace("%", ""))
        if m:
            resist[el] = int(m.group(1))
            if "?" in v:
                incertos.append(el)
    ataques, invoca = _ataques(f.get("abilities", ""))
    return {
        "nome": f.get("name") or titulo_pagina,
        "hp": num(f.get("hp")), "xp": num(f.get("exp")), "armor": num(f.get("armor")),
        "mitigation": num(f.get("mitigation")), "speed": num(f.get("speed")),
        "summon": traco(f.get("summon")), "convince": traco(f.get("convince")),
        "pushable": traco(f.get("pushable")), "walksthrough": traco(f.get("walksthrough")),
        "classe": traco(f.get("bestiaryclass")), "nivel_bestiario": traco(f.get("bestiarylevel")),
        "ataques": ataques, "invoca": invoca,
        "resist": resist, "incertos": incertos,
        "maxdmg": traco(f.get("maxdmg")),
        "local": traco(f.get("location")),
    }


def _wikitext(titulo_pag):
    url = f"{WIKI}?action=parse&page={urllib.parse.quote(titulo_pag)}&prop=wikitext&format=json&redirects=1"
    try:
        js = _get_json(url)
    except Exception:
        return None
    texto = js.get("parse", {}).get("wikitext", {}).get("*")
    if not texto or "{{Infobox Creature" not in texto:
        return None
    return texto, js["parse"].get("title", titulo_pag)


def _buscar_titulo(nome):
    url = f"{WIKI}?action=query&list=search&srsearch={urllib.parse.quote(nome)}&srlimit=5&format=json"
    try:
        hits = _get_json(url).get("query", {}).get("search", [])
    except Exception:
        return None
    return hits[0]["title"] if hits else None


def _ficha_wiki(nome):
    base = titulo(re.sub(r"\s+", " ", nome.strip()))
    candidatos = [base]
    if base.lower().endswith("ies"):
        candidatos.append(base[:-3] + "y")
    elif base.lower().endswith("s"):
        candidatos.append(base[:-1])
    for c in candidatos:
        r = _wikitext(c)
        if r:
            return ficha_do_wikitext(*r)
    achado = _buscar_titulo(base)
    if achado:
        r = _wikitext(achado)
        if r:
            return ficha_do_wikitext(*r)
    return None


_BALDES = {"physical": "physical", "fire": "fire", "ice": "ice", "energy": "energy", "earth": "earth",
           "poison": "earth", "death": "death", "holy": "holy", "drown": "drowning", "drowning": "drowning",
           "hpdrain": "lifedrain", "lifedrain": "lifedrain", "life drain": "lifedrain",
           "manadrain": "manadrain", "mana drain": "manadrain", "healing": "healing"}


def _balde(bruto):
    t = bruto.lower().strip()
    m = re.search(r"[a-z][a-z ]*", t)
    el = _BALDES.get(m.group(0).strip()) if m else None
    if not el:
        return None, None
    p = re.search(r"(-?\d+)\s*%", t)
    return el, (int(p.group(1)) if p else None)


def _ficha_tibiadata(race):
    try:
        return _get_json(f"{TIBIADATA}/creature/{urllib.parse.quote(race.lower())}").get("creature") or None
    except Exception:
        return None


def carregar_monstro(nome, race=None, imagem=None):
    """Ficha unificada de um monstro (com cache em disco). Nunca levanta exceção."""
    chave = nome.lower()
    with _trava:
        c = _carregar_cache()
        g = c["monstros"].get(chave)
    if g and time.time() - g["t"] < VALIDADE_MONSTRO:
        return g["k"]

    wiki = _ficha_wiki(nome)
    data = _ficha_tibiadata(race or nome.replace(" ", ""))
    if wiki is None and data is None and g:
        return g["k"]  # sem internet: fica com a ficha antiga

    resist = dict(wiki["resist"]) if wiki else {}
    parcial = []
    if data:
        completados = []
        for bruto in data.get("immune") or []:
            el, _ = _balde(bruto)
            if el and el not in resist:
                resist[el] = 0; completados.append(el)
        for bruto in data.get("strong") or []:
            el, p = _balde(bruto)
            if el and el not in resist and p is not None:
                resist[el] = 100 - p; completados.append(el)
        for bruto in data.get("weakness") or []:
            el, p = _balde(bruto)
            if el and el not in resist and p is not None:
                resist[el] = 100 + p; completados.append(el)
        if completados:
            parcial.append(f"resistências ({', '.join(completados)}) só do TibiaData")
    if not wiki:
        parcial.append("sem ficha na TibiaWiki")
    elif not wiki["ataques"]:
        parcial.append("a TibiaWiki não lista ataques")

    k = dict(wiki or {"ataques": [], "invoca": [], "incertos": []})
    k.update({
        "nome": (wiki or {}).get("nome") or canonico(nome),
        "race": race,
        "imagem": imagem or (data or {}).get("image_url"),
        "hp": (wiki or {}).get("hp") or (data or {}).get("hitpoints"),
        "xp": (wiki or {}).get("xp") or (data or {}).get("experience_points"),
        "resist": resist,
        "fontes": {"wiki": bool(wiki), "tibiadata": bool(data)},
        "parcial": parcial,
    })
    if wiki or data:  # não grava ficha vazia (sem internet), para tentar de novo da próxima vez
        with _trava:
            c["monstros"][chave] = {"t": time.time(), "k": k}
            _salvar_cache()
    return k
