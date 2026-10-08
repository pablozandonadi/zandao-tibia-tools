"""Combat Stats do set: soma o que os itens e os embuimentos do set dão (armor, defense, attack, resistências, skills,
leech, crítico...), para saber qual set compensa. Valores dos embuimentos Powerful: TibiaWiki, página "Imbuing".

Quem usa: web_api (set_stats), historico.comparar (tabela "Stats do set"), web/sets.js (painel do editor e da janela "Ver set").
"""

import re

import proficiencia

# efeitos dos embuimentos (só os Powerful, os 24 que o app oferece): nome -> [(tipo, chave, valor)]
#   conv = % do dano físico convertido em elemento; leech = % do dano devolvido; crit = chance / dano extra (%);
#   resist = % de proteção; skill = pontos de skill (speed em pontos); capacidade e paralisia em %
IMBUEMENTS = {
    "Powerful Scorch": [("conv", "fire", 50)], "Powerful Venom": [("conv", "earth", 50)], "Powerful Frost": [("conv", "ice", 50)],
    "Powerful Electrify": [("conv", "energy", 50)], "Powerful Reap": [("conv", "death", 50)],
    "Powerful Vampirism": [("leech", "life", 25)], "Powerful Void": [("leech", "mana", 8)],
    "Powerful Strike": [("crit", "chance", 5), ("crit", "dano", 40)],
    "Powerful Lich Shroud": [("resist", "death", 10)], "Powerful Snake Skin": [("resist", "earth", 15)],
    "Powerful Dragon Hide": [("resist", "fire", 15)], "Powerful Quara Scale": [("resist", "ice", 15)],
    "Powerful Cloud Fabric": [("resist", "energy", 15)], "Powerful Demon Presence": [("resist", "holy", 15)],
    "Powerful Vibrancy": [("paralisia", None, 50)], "Powerful Swiftness": [("skill", "speed", 30)],
    "Powerful Featherweight": [("capacidade", None, 15)],
    "Powerful Epiphany": [("skill", "magic level", 4)], "Powerful Punch": [("skill", "fist fighting", 4)],
    "Powerful Bash": [("skill", "club fighting", 4)], "Powerful Slash": [("skill", "sword fighting", 4)],
    "Powerful Chop": [("skill", "axe fighting", 4)], "Powerful Precision": [("skill", "distance fighting", 4)],
    "Powerful Blockade": [("skill", "shielding", 4)],
}

_ELEMENTO = {"physical": "Physical", "fire": "Fire", "earth": "Earth", "energy": "Energy", "ice": "Ice", "holy": "Holy", "death": "Death",
             "lifedrain": "Life Drain", "manadrain": "Mana Drain", "drown": "Drown"}
_ATRIBUTO = re.compile(r"^(?P<nome>[a-z][a-z ]*?)\s*(?P<valor>[+-]?\d+)(?P<pct>%?)$")
_GRUPOS = ["Defesa", "Ataque", "Skills", "Perks da arma", "Outros"]
# perk da arma que vira uma linha normal (o resto fica em "Perks da arma", somado por rótulo): (rótulo em minúsculas, unidade) -> (campo, chave)
_PERK_GLOBAL = {("critical extra damage", "%"): ("crit", "dano"), ("critical hit chance", "%"): ("crit", "chance"),
                ("life leech", "%"): ("leech", "life"), ("mana leech", "%"): ("leech", "mana"), ("attack", ""): ("attack", None), ("defence", ""): ("defense", None)}


def _vazio():
    return {"armor": 0, "defense": 0, "attack": 0, "atk_elem": {}, "resist": {}, "skills": {}, "leech": {}, "crit": {},
            "conversao": {}, "capacidade": 0, "paralisia": 0, "perks": {}, "extras": []}


def _soma(d, chave, v):
    d[chave] = d.get(chave, 0) + v


def _titulo(texto):
    return re.sub(r"\b([a-z])", lambda m: m.group(1).upper(), texto)


def _extra(s, texto):
    if _titulo(texto) not in s["extras"]:
        s["extras"].append(_titulo(texto))


def _atributo(s, texto):
    """Uma parte do campo attrib do item ("magic level +2", "life leech +2%"...). O que não for número soma como texto."""
    m = _ATRIBUTO.match(texto)
    if not m:
        _extra(s, texto)
        return
    nome, valor = m.group("nome").strip(), int(m.group("valor"))
    if nome == "life leech":
        _soma(s["leech"], "life", valor)
    elif nome == "mana leech":
        _soma(s["leech"], "mana", valor)
    elif nome == "critical hit chance":
        _soma(s["crit"], "chance", valor)
    elif nome in ("critical extra damage", "critical hit damage"):
        _soma(s["crit"], "dano", valor)
    elif not m.group("pct") and nome.endswith(("level", "fighting", "shielding", "speed")):
        _soma(s["skills"], nome, valor)
    else:
        _extra(s, texto)


def _perk(s, e):
    """Um efeito de perk da arma ({"rotulo", "valor", "unidade"}): linha normal se for global, senão fica em s["perks"]."""
    rotulo, valor, unidade = e["rotulo"], e["valor"], e["unidade"]
    destino = _PERK_GLOBAL.get((rotulo.lower(), unidade))
    if destino and destino[1]:
        _soma(s[destino[0]], destino[1], valor)
    elif destino:
        s[destino[0]] += valor
    elif not unidade and rotulo.lower().endswith(("level", "fighting", "shielding")):
        _soma(s["skills"], rotulo.lower(), valor)
    else:
        atual = s["perks"].setdefault(rotulo, {"valor": 0, "unidade": unidade})
        atual["valor"] = round(atual["valor"] + valor, 4)


def somar(valor, opcoes=None):
    """Soma o set ({"itens": {slot: item}}) e devolve o dicionário de stats (todos zerados se o set for vazio).
    opcoes: lista do Perk Shaping (só é lida do cache de proficiência se alguma arma tiver troca)."""
    s = _vazio()
    for item in ((valor or {}).get("itens") or {}).values():
        if item.get("perks"):
            if opcoes is None and (item.get("prof") or {}).get("trocas"):
                opcoes = proficiencia.carregar().get("opcoes", [])
            ef = proficiencia.efeitos(item, opcoes or ())
            for e in ef["lista"]:
                _perk(s, e)
            for t in ef["textos"]:
                _extra(s, t)
        s["armor"] += item.get("armor") or 0
        s["defense"] += item.get("defense") or 0
        s["attack"] += item.get("attack") or 0
        for el, v in (item.get("atk_elem") or {}).items():
            _soma(s["atk_elem"], el, v)
        for el, v in (item.get("resist") or {}).items():
            _soma(s["resist"], el, v)
        for parte in (item.get("attrib") or "").lower().split(","):
            if parte.strip():
                _atributo(s, parte.strip())
        for nome in item.get("imbues") or []:
            for tipo, chave, v in IMBUEMENTS.get(nome, []):
                if tipo == "conv":
                    _soma(s["conversao"], chave, v)
                elif tipo == "leech":
                    _soma(s["leech"], chave, v)
                elif tipo == "crit":
                    _soma(s["crit"], chave, v)
                elif tipo == "resist":
                    _soma(s["resist"], chave, v)
                elif tipo == "skill":
                    _soma(s["skills"], chave, v)
                else:
                    s[tipo] += v
    return s


def _sinal(v):
    return f"{v:+d}"


def _sinal_num(v):
    """+7.5, -20, +1 (inteiro sem casas)."""
    return f"{v:+g}"


def linhas(s):
    """O que aparece na tela: [{chave, grupo, rotulo, valor, texto}], só o que não é zero, agrupado (Defesa, Ataque, Skills, Outros)."""
    def lin(chave, grupo, rotulo, valor, texto):
        return {"chave": chave, "grupo": grupo, "rotulo": rotulo, "valor": valor, "texto": texto}
    saida = []
    for chave, rotulo in (("armor", "Armor"), ("defense", "Defense")):
        if s[chave]:
            saida.append(lin(chave, "Defesa", rotulo, s[chave], str(s[chave])))
    for el, v in sorted(s["resist"].items(), key=lambda x: (-x[1], x[0])):
        if v:
            saida.append(lin(f"resist:{el}", "Defesa", _ELEMENTO.get(el, el.capitalize()), v, f"{_sinal(v)}%"))
    if s["paralisia"]:
        saida.append(lin("paralisia", "Defesa", "Paralysis deflection", s["paralisia"], f"{s['paralisia']}%"))
    if s["attack"]:
        saida.append(lin("attack", "Ataque", "Attack", s["attack"], str(s["attack"])))
    for el, v in s["atk_elem"].items():
        saida.append(lin(f"atk_elem:{el}", "Ataque", f"{_ELEMENTO.get(el, el.capitalize())} attack", v, str(v)))
    for el, v in s["conversao"].items():
        saida.append(lin(f"conv:{el}", "Ataque", f"{_ELEMENTO.get(el, el.capitalize())} damage conversion", v, f"{v}%"))
    for chave, rotulo in (("life", "Life leech"), ("mana", "Mana leech")):
        if s["leech"].get(chave):
            saida.append(lin(f"leech:{chave}", "Ataque", rotulo, s["leech"][chave], f"{s['leech'][chave]}%"))
    for chave, rotulo in (("chance", "Critical chance"), ("dano", "Critical extra damage")):
        if s["crit"].get(chave):
            saida.append(lin(f"crit:{chave}", "Ataque", rotulo, s["crit"][chave], f"{s['crit'][chave]}%"))
    for nome, v in sorted(s["skills"].items(), key=lambda x: (-x[1], x[0])):
        if v:
            saida.append(lin(f"skill:{nome}", "Skills", _titulo(nome), v, _sinal(v)))
    for rotulo, e in s["perks"].items():
        if e["valor"]:
            saida.append(lin(f"perk:{rotulo}", "Perks da arma", rotulo[:1].upper() + rotulo[1:], e["valor"], f"{_sinal_num(e['valor'])}{e['unidade']}"))
    if s["capacidade"]:
        saida.append(lin("capacidade", "Outros", "Capacity", s["capacidade"], f"+{s['capacidade']}%"))
    for texto in s["extras"]:
        saida.append(lin(f"extra:{texto.lower()}", "Outros", texto, None, texto))
    return saida
