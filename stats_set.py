"""Combat Stats do set: soma o que os itens e os embuimentos do set dão (armor, defense, attack, resistências, skills,
leech, crítico...), para saber qual set compensa. Valores dos embuimentos Powerful: TibiaWiki, página "Imbuing".

Quem usa: web_api (set_stats), historico.comparar (tabela "Stats do set"), web/sets.js (painel do editor e da janela "Ver set").
"""

import re

import posturas
import preys_charms
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
_GRUPOS = ["Defesa", "Ataque", "Skills", "Prey", "Charms", "Roda", "Postura", "Outros"]
# perk da arma que vira uma linha normal (o resto fica em "Perks da arma", somado por rótulo): (rótulo em minúsculas, unidade) -> (campo, chave)
_PERK_GLOBAL = {("critical extra damage", "%"): ("crit", "dano"), ("critical hit chance", "%"): ("crit", "chance"),
                ("life leech", "%"): ("leech", "life"), ("mana leech", "%"): ("leech", "mana"), ("attack", ""): ("attack", None), ("defence", ""): ("defense", None)}


_PREFIXO = {"leech": "leech", "crit": "crit", "skills": "skill", "conversao": "conv", "atk_elem": "atk_elem", "resist": "resist"}


def _vazio():
    return {"armor": 0, "defense": 0, "attack": 0, "atk_elem": {}, "resist": {}, "skills": {}, "leech": {}, "crit": {},
            "conversao": {}, "capacidade": 0, "paralisia": 0, "perks": {}, "extras": [], "fontes": {}}


def _soma(d, chave, v):
    d[chave] = d.get(chave, 0) + v


def _fonte(s, chave, origem, valor):
    """Guarda de onde veio uma parte do valor da linha (Equipamento, Embuimento, Proficiência, Roda...)."""
    if valor:
        s["fontes"].setdefault(chave, []).append({"origem": origem, "valor": valor})


def _acc(s, campo, chave, v, origem):
    """Soma em s[campo][chave] (leech, crit, skills...) e guarda a origem. As resistências são fechadas depois (multiplicam)."""
    _soma(s[campo], chave, v)
    _fonte(s, f"{_PREFIXO[campo]}:{chave}", origem, v)


def _acc_n(s, campo, v, origem):
    """Mesma coisa para os números soltos (armor, defense, attack, capacidade, paralisia)."""
    s[campo] += v
    _fonte(s, campo, origem, v)


def _titulo(texto):
    return re.sub(r"\b([a-z])", lambda m: m.group(1).upper(), texto)


def _extra(s, texto):
    if _titulo(texto) not in s["extras"]:
        s["extras"].append(_titulo(texto))


def _atributo(s, texto, origem):
    """Uma parte do campo attrib do item ("magic level +2", "life leech +2%"...). O que não for número soma como texto."""
    m = _ATRIBUTO.match(texto)
    if not m:
        _extra(s, texto)
        return
    nome, valor = m.group("nome").strip(), int(m.group("valor"))
    if nome == "life leech":
        _acc(s, "leech", "life", valor, origem)
    elif nome == "mana leech":
        _acc(s, "leech", "mana", valor, origem)
    elif nome == "critical hit chance":
        _acc(s, "crit", "chance", valor, origem)
    elif nome in ("critical extra damage", "critical hit damage"):
        _acc(s, "crit", "dano", valor, origem)
    elif not m.group("pct") and nome.endswith(("level", "fighting", "shielding", "speed")):
        _acc(s, "skills", nome, valor, origem)
    else:
        _extra(s, texto)


def _perk(s, e, origem):
    """Um efeito de perk da arma ({"rotulo", "valor", "unidade"}): linha normal se for global, senão fica em s["perks"] (misc)."""
    rotulo, valor, unidade = e["rotulo"], e["valor"], e["unidade"]
    destino = _PERK_GLOBAL.get((rotulo.lower(), unidade))
    if destino and destino[1]:
        _acc(s, destino[0], destino[1], valor, origem)
    elif destino:
        _acc_n(s, destino[0], valor, origem)
    elif not unidade and rotulo.lower().endswith(("level", "fighting", "shielding")):
        _acc(s, "skills", rotulo.lower(), valor, origem)
    else:
        atual = s["perks"].setdefault(rotulo, {"valor": 0, "unidade": unidade})
        atual["valor"] = round(atual["valor"] + valor, 4)
        _fonte(s, f"perk:{rotulo}", origem, valor)


def _mesclar(s, parcial, origem):
    """Junta valores que vêm de fora do set (a roda, o bônus fixo): {"resist": {...}, "leech": {...}, "crit": {...}, "skills": {...}}."""
    for campo in ("resist", "leech", "crit", "skills", "conversao", "atk_elem"):
        for chave, v in (parcial.get(campo) or {}).items():
            _acc(s, campo, chave, v, origem)


def _fechar(s):
    """Resistências do mesmo elemento se combinam multiplicando (como o Tibia mostra): total = 1 - produto de (1 - cada)."""
    for chave, partes in s["fontes"].items():
        if chave.startswith("resist:"):
            produto = 1.0
            for f in partes:
                produto *= 1 - f["valor"] / 100
            total = round((1 - produto) * 100, 2)
            s["resist"][chave[len("resist:"):]] = int(total) if float(total).is_integer() else total


def somar(valor, opcoes=None, extras=None, antes=None):
    """Soma o set ({"itens": {slot: item}}) e devolve o dicionário de stats (todos zerados se o set for vazio).
    Cada linha guarda em s["fontes"] de onde veio (Equipamento, Embuimento, Proficiência, ...).
    opcoes: lista do Perk Shaping (só é lida do cache de proficiência se alguma arma tiver troca).
    extras: [(origem, parcial)] com o que vem de fora do set e entra depois dele (roda); antes: o que entra antes (bônus fixo)."""
    s = _vazio()
    for origem, parcial in antes or []:
        _mesclar(s, parcial, origem)
    for item in ((valor or {}).get("itens") or {}).values():
        for campo in ("armor", "defense", "attack"):
            _acc_n(s, campo, item.get(campo) or 0, "Equipamento")
        for el, v in (item.get("atk_elem") or {}).items():
            _acc(s, "atk_elem", el, v, "Equipamento")
        for el, v in (item.get("resist") or {}).items():
            _acc(s, "resist", el, v, "Equipamento")
        for parte in (item.get("attrib") or "").lower().split(","):
            if parte.strip():
                _atributo(s, parte.strip(), "Equipamento")
        for nome in item.get("imbues") or []:
            for tipo, chave, v in IMBUEMENTS.get(nome, []):
                if tipo == "conv":
                    _acc(s, "conversao", chave, v, "Embuimento")
                elif tipo == "leech":
                    _acc(s, "leech", chave, v, "Embuimento")
                elif tipo == "crit":
                    _acc(s, "crit", chave, v, "Embuimento")
                elif tipo == "resist":
                    _acc(s, "resist", chave, v, "Embuimento")
                elif tipo == "skill":
                    _acc(s, "skills", chave, v, "Embuimento")
                else:
                    _acc_n(s, tipo, v, "Embuimento")
        if item.get("perks"):
            if opcoes is None and (item.get("prof") or {}).get("trocas"):
                opcoes = proficiencia.carregar().get("opcoes", [])
            ef = proficiencia.efeitos(item, opcoes or ())
            for e in ef["lista"]:
                _perk(s, e, "Proficiência")
            for t in ef["textos"]:
                _extra(s, t)
    for origem, parcial in extras or []:
        _mesclar(s, parcial, origem)
    _fechar(s)
    return s


def _sinal(v):
    return f"{v:+d}"


def _sinal_num(v):
    """+7.5, -20, +1 (inteiro sem casas)."""
    return f"{v:+g}"


def _num(v):
    """Número sem casas inúteis: 50 -> "50", 15.98 -> "15.98"."""
    return f"{v:g}"


def _fontes_agrupadas(chave, partes):
    """Junta as partes da mesma origem (como o Tibia: "+20% do Equipamento"); nas resistências a mesma origem também combina multiplicando."""
    porigem = {}
    for f in partes:
        porigem.setdefault(f["origem"], []).append(f["valor"])
    saida = []
    for origem, vals in porigem.items():
        if chave.startswith("resist:"):
            produto = 1.0
            for v in vals:
                produto *= 1 - v / 100
            v = round((1 - produto) * 100, 2)
        else:
            v = round(sum(vals), 4)
        saida.append({"origem": origem, "valor": int(v) if float(v).is_integer() else v})
    return saida


def linhas(s):
    """O que aparece na tela: [{chave, grupo, rotulo, valor, texto, fontes, misc}], só o que não é zero.
    "fontes" diz de onde vem cada parte do valor; "misc" marca o que o Tibia mostra na aba Misc (perks de spell específica),
    que aqui fica junto do ataque, mas marcado."""
    def lin(chave, grupo, rotulo, valor, texto, misc=False):
        return {"chave": chave, "grupo": grupo, "rotulo": rotulo, "valor": valor, "texto": texto, "misc": misc, "fontes": _fontes_agrupadas(chave, s["fontes"].get(chave, []))}
    saida = []
    for chave, rotulo in (("armor", "Armor"), ("defense", "Defense")):
        if s[chave]:
            saida.append(lin(chave, "Defesa", rotulo, s[chave], str(s[chave])))
    for el, v in sorted(s["resist"].items(), key=lambda x: (-x[1], x[0])):
        if v:
            saida.append(lin(f"resist:{el}", "Defesa", _ELEMENTO.get(el, el.capitalize()), v, f"{_sinal_num(v)}%"))
    if s["paralisia"]:
        saida.append(lin("paralisia", "Defesa", "Paralysis deflection", s["paralisia"], f"{_num(s['paralisia'])}%"))
    if s["attack"]:
        saida.append(lin("attack", "Ataque", "Attack", s["attack"], str(s["attack"])))
    for el, v in s["atk_elem"].items():
        saida.append(lin(f"atk_elem:{el}", "Ataque", f"{_ELEMENTO.get(el, el.capitalize())} attack", v, str(v)))
    for el, v in s["conversao"].items():
        saida.append(lin(f"conv:{el}", "Ataque", f"{_ELEMENTO.get(el, el.capitalize())} damage conversion", v, f"{_num(v)}%"))
    for chave, rotulo in (("life", "Life leech"), ("mana", "Mana leech")):
        if s["leech"].get(chave):
            saida.append(lin(f"leech:{chave}", "Ataque", rotulo, s["leech"][chave], f"{_num(s['leech'][chave])}%"))
    for chave, rotulo in (("chance", "Critical chance"), ("dano", "Critical extra damage")):
        if s["crit"].get(chave):
            saida.append(lin(f"crit:{chave}", "Ataque", rotulo, s["crit"][chave], f"{_num(s['crit'][chave])}%"))
    for rotulo, e in s["perks"].items():
        if e["valor"]:
            saida.append(lin(f"perk:{rotulo}", "Ataque", rotulo[:1].upper() + rotulo[1:], e["valor"], f"{_sinal_num(e['valor'])}{e['unidade']}", misc=True))
    for nome, v in sorted(s["skills"].items(), key=lambda x: (-x[1], x[0])):
        if v:
            saida.append(lin(f"skill:{nome}", "Skills", _titulo(nome), v, _sinal_num(v)))
    if s["capacidade"]:
        saida.append(lin("capacidade", "Outros", "Capacity", s["capacidade"], f"+{_num(s['capacidade'])}%"))
    for texto in s["extras"]:
        saida.append(lin(f"extra:{texto.lower()}", "Outros", texto, None, texto))
    return saida


# ---------------------------------------------------------------------------
# Combat Stats da HUNT: o set + prey + charms + roda (prey e charms valem só contra a criatura escolhida)
# ---------------------------------------------------------------------------
_PREY_ROTULO = {"xp": "Prey XP (bônus de XP)", "loot": "Prey Loot (chance de loot)", "ataque": "Prey Ataque (dano causado)", "defesa": "Prey Defesa (dano recebido)"}
_EFEITO_CHARM = {
    "Carnage": "ao matar, {p}% de chance de dano físico = 15% da vida máx. do monstro, em área",
    "Curse": "{p}% de chance por ataque: dano Death = 5% da vida máx. do monstro", "Divine Wrath": "{p}% de chance por ataque: dano Holy = 5% da vida máx. do monstro",
    "Enflame": "{p}% de chance por ataque: dano Fire = 5% da vida máx. do monstro", "Freeze": "{p}% de chance por ataque: dano Ice = 5% da vida máx. do monstro",
    "Poison": "{p}% de chance por ataque: dano Earth = 5% da vida máx. do monstro", "Wound": "{p}% de chance por ataque: dano físico = 5% da vida máx. do monstro",
    "Zap": "{p}% de chance por ataque: dano Energy = 5% da vida máx. do monstro", "Dodge": "{p}% de chance de desviar do ataque (sem dano)",
    "Low Blow": "+{p}% de chance de crítico", "Savage Blow": "+{p}% de critical extra damage",
    "Overflux": "{p}% de chance por ataque: dano = 2,5% da sua mana máx.", "Overpower": "{p}% de chance por ataque: dano = 5% da sua vida máx.",
    "Parry": "{p}% de chance de refletir o dano recebido", "Adrenaline Burst": "{p}% de chance, ao ser atingido, de ficar bem mais rápido por 10 s",
    "Bless": "-{p}% de perda de XP e skills ao morrer para ela", "Cleanse": "{p}% de chance, ao ser atingido, de remover uma condição negativa",
    "Cripple": "{p}% de chance de paralisar a criatura por 10 s", "Fatal Hold": "{p}% de chance de impedir a fuga da criatura",
    "Gut": "+{p}% de creature products", "Numb": "{p}% de chance, após o ataque dela, de paralisá-la por 10 s", "Scavenge": "+{p}% de chance de skinning/dust",
    "Vampiric Embrace": "+{p}% de life leech (com equipamento que dê life leech)", "Void Inversion": "{p}% de chance de ganhar mana em vez de perder (Mana Drain)",
    "Void's Call": "+{p}% de mana leech (com equipamento que dê mana leech)",
}
_VALOR_RODA = re.compile(r"^[+-]?[0-9][0-9,]*(?:[.][0-9]+)?%?$")
_NIVEL_RODA = re.compile(r"^(?:[IVX]+|Stage [0-9]+)$")


def _g(v):
    return f"{v:g}"


def _linhas_prey(prey):
    por_tipo = {}
    for p in prey or []:
        b = preys_charms.bonus_prey(p.get("tipo"), p.get("estrelas"))
        if b is None:
            continue
        acc = por_tipo.setdefault(p["tipo"], {"valor": 0, "detalhes": []})
        acc["valor"] += b
        acc["detalhes"].append(f"★{p['estrelas']}" + (f" · {p['criatura']}" if p.get("criatura") else ""))
    saida = []
    for tipo in ("xp", "loot", "ataque", "defesa"):
        if tipo in por_tipo:
            v = por_tipo[tipo]["valor"]
            saida.append({"chave": f"prey:{tipo}", "grupo": "Prey", "rotulo": _PREY_ROTULO[tipo], "valor": v,
                          "texto": f"-{v}%" if tipo == "defesa" else f"+{v}%", "detalhe": "; ".join(por_tipo[tipo]["detalhes"])})
    return saida


def _linhas_charms(charms):
    saida = []
    for c in charms or []:
        nome, nivel = c.get("nome"), c.get("nivel")
        pct = preys_charms.porcentagem_charm(nome, nivel)
        if pct is None:
            continue
        efeito = _EFEITO_CHARM.get(nome, "").format(p=_g(pct))
        contra = f"contra {c['criatura']}" if c.get("criatura") else "sem criatura escolhida"
        saida.append({"chave": f"charm:{nome}", "grupo": "Charms", "rotulo": nome, "valor": pct, "texto": f"{_g(pct)}%",
                      "detalhe": f"nível {nivel} · {contra}: {efeito}".rstrip(": ")})
    return saida


def _linhas_roda(secoes):
    """Itens do resumo do planner da roda: nome + valor em elementos seguidos (ex.: "Hit Points", "+1,500")."""
    ocorrencias = {}
    ordem = []
    for sec in secoes or []:
        itens = [x for x in (sec.get("linhas") or []) if isinstance(x, str) and x.strip() and x.strip().lower() != "none"]
        i = 0
        while i < len(itens):
            nome = itens[i].strip()
            val = itens[i + 1].strip() if i + 1 < len(itens) else None
            if val is not None and (val == "Locked" or _VALOR_RODA.match(val) or _NIVEL_RODA.match(val)) and not _VALOR_RODA.match(nome):
                ocorrencias.setdefault(nome, []).append(val)
                i += 2
            else:
                ocorrencias.setdefault(nome, []).append(None)
                i += 1
            if nome not in ordem:
                ordem.append(nome)
    saida = []
    for nome in ordem:
        vals = ocorrencias[nome]
        numericos = [v for v in vals if v and _VALOR_RODA.match(v)]
        if numericos:
            soma = sum(float(v.replace(",", "").rstrip("%")) for v in numericos)
            soma = int(soma) if float(soma).is_integer() else round(soma, 4)
            texto = numericos[0] if len(numericos) == 1 else f"{soma:+g}{'%' if numericos[0].endswith('%') else ''}"
            saida.append({"chave": f"roda:{nome}", "grupo": "Roda", "rotulo": nome, "valor": soma, "texto": texto})
        else:
            texto = next((v for v in vals if v), "ativo")
            linha = {"chave": f"roda:{nome}", "grupo": "Roda", "rotulo": nome, "valor": None, "texto": texto}
            pontos = _pontos_roda(nome, texto)
            if pontos:
                linha["pontos"] = pontos
            saida.append(linha)
    return saida


_ROMANOS = {"I": 1, "II": 2, "III": 3}


def _pontos_roda(nome, texto):
    """Bolinhas do resumo: revelação ("Locked" = 0, "Stage N" = N de 3), augment ("Augmented X I/II/III") e ressonância das gemas."""
    if texto == "Locked":
        return {"tipo": "revelacao", "n": 0, "de": 3}
    m = re.match(r"^Stage ([0-9]+)$", texto)
    if m:
        return {"tipo": "revelacao", "n": min(3, int(m.group(1))), "de": 3}
    if texto in _ROMANOS:
        return {"tipo": "aumento" if nome.startswith("Augmented") else "gema", "n": _ROMANOS[texto], "de": 3}
    return None


def pontos_roda(secoes):
    """Só o que tem bolinhas (revelações, augments, gemas): [{"rotulo", "texto", "tipo", "n", "de"}], para mostrar embaixo da roda."""
    return [{"rotulo": l["rotulo"], "texto": l["texto"], **l["pontos"]} for l in _linhas_roda(secoes) if l.get("pontos")]


# Bônus fixo que o personagem tem no Tibia (conferido na aba Offence Stats de um Elite Knight level 170): +5% de chance e +10% de extra damage de crítico
BONUS_FIXO = {"crit": {"chance": 5, "dano": 10}}
_RES_RODA = re.compile(r"^(Physical|Fire|Earth|Energy|Ice|Holy|Death) Resistance$")
_STRINGS = {}


def _strings_roda():
    """Textos do planner da roda (arquivo baixado do tibia.com para o cache da roda); {} se ainda não existe."""
    if not _STRINGS:
        try:
            import json
            import os
            import roda as _r
            with open(os.path.join(_r.PASTA_CACHE, "strings.json"), "r", encoding="utf-8-sig") as f:
                _STRINGS.update(json.load(f))
        except (OSError, ValueError, ImportError):
            return {}
    return _STRINGS


def _efeitos_augment(nome, nivel):
    """Efeitos de "Augmented <Spell>" no nível I (1º efeito) ou II e III (os dois), segundo o planner."""
    spell = nome[len("Augmented "):].strip()
    for info in (_strings_roda().get("MediumPerkInfos") or {}).values():
        if isinstance(info, dict) and (info.get("Name") or "").split("|")[0].strip() == nome:
            textos = [info.get("Aug1Info")] + ([info.get("Aug2Info")] if nivel >= 2 else [])
            return spell, [x for x in textos if x]
    return spell, []


_AUG_NUM = re.compile(r"^([+-][0-9.]+)% (.+)$")


def _roda_nos_totais(roda):
    """Separa o que o resumo da roda já soma nos totais (resistências, leech, damage and healing) do que continua no grupo Roda."""
    parcial, flat, resto = {"resist": {}, "leech": {}}, 0, []
    for sec in roda or []:
        itens = [x for x in (sec.get("linhas") or []) if isinstance(x, str) and x.strip() and x.strip().lower() != "none"]
        livre, i = [], 0
        while i < len(itens):
            nome, val = itens[i].strip(), (itens[i + 1].strip() if i + 1 < len(itens) else "")
            numerico = bool(_VALOR_RODA.match(val)) and not _VALOR_RODA.match(nome)
            valor = float(val.replace(",", "").rstrip("%")) if numerico else None
            m = _RES_RODA.match(nome)
            if numerico and m:
                parcial["resist"][m.group(1).lower()] = parcial["resist"].get(m.group(1).lower(), 0) + valor
            elif numerico and nome in ("Life Leech", "Mana Leech"):
                parcial["leech"][nome.split()[0].lower()] = parcial["leech"].get(nome.split()[0].lower(), 0) + valor
            elif numerico and nome == "Damage and Healing":
                flat += valor
            else:
                livre += [nome] + ([val] if numerico or val == "Locked" or _NIVEL_RODA.match(val) else [])
                i += 2 if (numerico or val == "Locked" or _NIVEL_RODA.match(val)) else 1
                continue
            i += 2
        resto.append({"titulo": sec.get("titulo"), "linhas": livre})
    return parcial, flat, resto


def _linhas_augments(roda):
    saida = []
    for l in _linhas_roda(roda):
        pt = l.get("pontos")
        if not pt or pt["tipo"] != "aumento" or not pt["n"]:
            continue
        spell, textos = _efeitos_augment(l["rotulo"], pt["n"])
        for tx in textos:
            m = _AUG_NUM.match(tx)
            valor, texto, rotulo = (float(m.group(1)), f"{m.group(1)}%", m.group(2)) if m else (None, tx, tx)
            valor = int(valor) if valor is not None and valor.is_integer() else valor
            chave = f"aug:{spell}:{rotulo}"
            saida.append({"chave": chave, "grupo": "Ataque", "rotulo": f"{spell}: {rotulo}", "valor": valor, "texto": texto, "misc": True,
                          "fontes": [{"origem": "Roda (augment)", "valor": valor}] if valor else []})
    return saida


# skill que cada tipo de arma usa
_SKILL_DA_ARMA = {"sword weapons": "sword fighting", "axe weapons": "axe fighting", "club weapons": "club fighting",
                  "distance weapons": "distance fighting", "fist fighting weapons": "fist fighting"}
_AUTO_ATAQUE = re.compile(r"^do seu (.+?) como extra damage para auto-attacks$", re.I)


def _arma_e_escudo(set_):
    itens = (set_ or {}).get("itens") or {}
    return itens.get("arma"), itens.get("mao")


def _skill_da_arma(arma):
    import itens_set
    tipo = (arma.get("tipo") or itens_set.tipo_da_arma(arma.get("nome")) or "").lower()
    return _SKILL_DA_ARMA.get(tipo)


def _skills_finais(s, base, postura):
    """Skill de cada tipo: base digitada + bônus de itens/embuimentos, vezes a postura (arredonda para baixo, como o Tibia).
    Devolve {skill: {"valor", "fontes"}}."""
    pct = posturas.skill_pct(postura)
    saida = {}
    for nome, b in (base or {}).items():
        if not isinstance(b, int) or b <= 0:
            continue
        itens = s["skills"].get(nome, 0)
        total = b + itens
        final = int(total * (1 + pct.get(nome, 0) / 100) + 1e-9)
        fontes = [{"origem": "Base", "valor": b}] + ([{"origem": "Equipamento", "valor": itens}] if itens else []) + ([{"origem": "Postura", "valor": final - total}] if final != total else [])
        saida[nome] = {"valor": final, "fontes": fontes}
    return saida


def _ataque_e_defesa(set_, s, finais, flat, modo):
    """Attack Value e Defence Value como o Tibia calcula (fórmulas da TibiaWiki, conferidas com os prints do jogo):
    ataque = B + floor(floor(m x W) x (S + 4) / 28), com m = 1,2 / 1 / 0,6 (Offensive / Balanced / Defensive);
    defesa = floor(D x (S + 10) / 40), com D = Def do escudo (se tem) ou da arma, e S = shielding ou a skill da arma."""
    arma, escudo = _arma_e_escudo(set_)
    saida = []
    if not arma:
        return saida
    skill_arma = _skill_da_arma(arma)
    W = arma.get("attack") or 0
    if W and skill_arma in finais:
        S = finais[skill_arma]["valor"]
        base_balanceado = W * (S + 4) // 28
        alvo = {"offensive": (W * 12 // 10), "balanced": W, "defensive": -(-W * 6 // 10)}.get(modo, W * 12 // 10)
        total_skill = alvo * (S + 4) // 28
        fontes = [{"origem": "Bônus fixo", "valor": flat}, {"origem": "Equipamento", "valor": W}, {"origem": "Skill", "valor": base_balanceado - W},
                  {"origem": "Tática de combate", "valor": total_skill - base_balanceado}]
        saida.append({"chave": "attackvalue", "grupo": "Ataque", "rotulo": "Attack Value", "valor": flat + total_skill, "texto": str(flat + total_skill),
                      "misc": False, "fontes": [f for f in fontes if f["valor"]]})
    if escudo and escudo.get("defense"):
        D, nome_s = escudo["defense"], "shielding"
    else:
        D, nome_s = arma.get("defense") or 0, skill_arma
    if D and nome_s in finais:
        S = finais[nome_s]["valor"]
        v = D * (S + 10) // 40
        saida.append({"chave": "defencevalue", "grupo": "Defesa", "rotulo": "Defence Value", "valor": v, "texto": str(v), "misc": False,
                      "fontes": [{"origem": "Equipamento", "valor": D}, {"origem": "Skill", "valor": v - D}]})
    return saida


def _auto_ataque(s, finais):
    """Auto-Attack Extra Damage: % do perk x a skill (ex.: 4% do Sword Fighting). Devolve (linha ou None, rótulos de perk já usados)."""
    fontes, usados, total = [], [], 0
    for rotulo, e in s["perks"].items():
        m = _AUTO_ATAQUE.match(rotulo)
        if m and m.group(1).lower() in finais:
            v = int(e["valor"] / 100 * finais[m.group(1).lower()]["valor"] + 0.5)
            fontes.append({"origem": _titulo(m.group(1).lower()), "valor": v})
            usados.append(rotulo)
            total += v
    if not fontes:
        return None, []
    return {"chave": "autoextra", "grupo": "Ataque", "rotulo": "Auto-Attack Extra Damage", "valor": total, "texto": str(total), "misc": False, "fontes": fontes}, usados


def linhas_hunt(set_, prey=None, charms=None, roda=None, opcoes=None, postura=None, nivel=None, skills=None):
    """Combat Stats de uma hunt, no formato do Tibia: o set (com bônus fixo e a roda somados nos totais, cada valor com a sua origem),
    mais Prey, Charms, Roda, Postura e os augments da roda (misc). nivel = level do personagem (Flat Damage and Healing = nível / 5).
    skills = {"base": {skill: valor sem itens}, "modo": "offensive"}: com elas saem o total de cada skill (com a postura), o Attack Value,
    o Defence Value e o Auto-Attack Extra Damage."""
    if not ((set_ and set_.get("itens")) or prey or charms or roda or postura):
        return []                              # nada informado: o bônus fixo sozinho não diz nada
    parcial_roda, flat_roda, roda_resto = _roda_nos_totais(roda)
    s = somar(set_, opcoes, extras=[("Roda", parcial_roda)], antes=[("Bônus fixo", BONUS_FIXO)])
    todas = linhas(s)
    flat_fontes = ([{"origem": "Nível", "valor": nivel // 5}] if nivel else []) + ([{"origem": "Roda", "valor": flat_roda}] if flat_roda else [])
    flat = sum(f["valor"] for f in flat_fontes)
    flat = int(flat) if float(flat).is_integer() else flat
    if flat_fontes:
        todas.append({"chave": "flat", "grupo": "Ataque", "rotulo": "Flat Damage and Healing", "valor": flat, "texto": _num(flat), "misc": False, "fontes": flat_fontes})
    finais = _skills_finais(s, (skills or {}).get("base"), postura)
    if finais:
        for nome, d in finais.items():
            todas.append({"chave": f"skillfinal:{nome}", "grupo": "Skills", "rotulo": _titulo(nome) + " (total)", "valor": d["valor"], "texto": str(d["valor"]), "misc": False, "fontes": d["fontes"]})
        extra = _ataque_e_defesa(set_, s, finais, flat, (skills or {}).get("modo") or "offensive")
        if any(l["chave"] == "defencevalue" for l in extra):
            todas = [l for l in todas if l["chave"] != "defense"]       # o Defence Value substitui a soma simples dos Def
        todas += extra
        auto, usados = _auto_ataque(s, finais)
        if auto:
            todas = [l for l in todas if l["chave"] not in {f"perk:{r}" for r in usados}] + [auto]
    todas += _linhas_prey(prey) + _linhas_charms(charms) + _linhas_roda(roda_resto) + _linhas_augments(roda) + posturas.linhas(postura)
    ordem = {g: i for i, g in enumerate(_GRUPOS)}
    return sorted(todas, key=lambda l: (ordem[l["grupo"]], bool(l.get("misc"))))
