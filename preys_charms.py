"""Tabelas de Prey e Charms do Tibia, para marcar o que estava ativo numa hunt (não muda nenhum número:
o que o usuário cola do Tibia já vem com o efeito deles).

Prey: 4 bônus, 1 a 10 estrelas. Charms: majors e minors, nível 1, 2 ou 3, cada um numa criatura.
Na hunt salva: "prey": [{"tipo", "estrelas", "criatura"}] e "charms": [{"nome", "criatura", "nivel"}];
lista vazia = nenhum; sem o campo = não informado (hunts antigas).
"""

# bônus em % por estrela (índice 0 = 1 estrela)
PREY = {
    "xp": {"rotulo": "Bonus Experience", "curto": "XP", "bonus": [13, 16, 19, 22, 25, 28, 31, 34, 37, 40],
           "descricao": "Aumenta a experiência ganha matando a criatura escolhida."},
    "ataque": {"rotulo": "Damage Boost", "curto": "Ataque", "bonus": [7, 9, 11, 13, 15, 17, 19, 21, 23, 25],
               "descricao": "Aumenta o dano que você causa na criatura escolhida."},
    "defesa": {"rotulo": "Damage Reduction", "curto": "Defesa", "bonus": [12, 14, 16, 18, 20, 22, 24, 26, 28, 30],
               "descricao": "Reduz o dano que você recebe da criatura escolhida."},
    "loot": {"rotulo": "Improved Loot", "curto": "Loot", "bonus": [13, 16, 19, 22, 25, 28, 31, 34, 37, 40],
             "descricao": "Aumenta a chance de loot da criatura escolhida."},
}

# (nome, % nos níveis 1, 2 e 3)
CHARMS = {
    "major": [
        ("Carnage", (10, 20, 22)), ("Curse", (5, 10, 11)), ("Divine Wrath", (5, 10, 11)), ("Dodge", (5, 10, 11)),
        ("Enflame", (5, 10, 11)), ("Freeze", (5, 10, 11)), ("Low Blow", (4, 8, 9)), ("Overflux", (5, 10, 11)),
        ("Overpower", (5, 10, 11)), ("Parry", (5, 10, 11)), ("Poison", (5, 10, 11)), ("Savage Blow", (20, 40, 44)),
        ("Wound", (5, 10, 11)), ("Zap", (5, 10, 11)),
    ],
    "minor": [
        ("Adrenaline Burst", (6, 9, 12)), ("Bless", (6, 9, 12)), ("Cleanse", (6, 9, 12)), ("Cripple", (6, 9, 12)),
        ("Fatal Hold", (30, 45, 60)), ("Gut", (6, 9, 12)), ("Numb", (6, 9, 12)), ("Scavenge", (60, 90, 120)),
        ("Vampiric Embrace", (1.6, 2.4, 3.2)), ("Void Inversion", (20, 30, 40)), ("Void's Call", (0.8, 1.2, 1.6)),
    ],
}
_PCT_CHARM = {nome: pct for lista in CHARMS.values() for nome, pct in lista}


def bonus_prey(tipo, estrelas):
    p = PREY.get(tipo)
    if not p or not isinstance(estrelas, int) or not 1 <= estrelas <= 10:
        return None
    return p["bonus"][estrelas - 1]


def porcentagem_charm(nome, nivel):
    pct = _PCT_CHARM.get(nome)
    if not pct or not isinstance(nivel, int) or not 1 <= nivel <= 3:
        return None
    return pct[nivel - 1]


def _texto(v, limite=60):
    return v.strip()[:limite] if isinstance(v, str) else ""


def normalizar_charms(valor):
    """Charms válidos {"nome", "criatura", "nivel" 1..3}, um por charm; None continua None (não informado)."""
    if valor is None:
        return None
    if not isinstance(valor, list):
        return []
    saida, vistos = [], set()
    for c in valor:
        if not isinstance(c, dict) or c.get("nome") not in _PCT_CHARM or c["nome"] in vistos:
            continue
        try:
            nivel = int(c.get("nivel"))
        except (TypeError, ValueError):
            continue
        if not 1 <= nivel <= 3:
            continue
        vistos.add(c["nome"])
        saida.append({"nome": c["nome"], "criatura": _texto(c.get("criatura")), "nivel": nivel})
    return saida


def rotulo_charms(charms):
    if charms is None:
        return "Charms não informados"
    if not charms:
        return "Sem charms"
    return f"{len(charms)} charm" + ("s" if len(charms) > 1 else "")


def tabelas():
    """O que a tela precisa para montar os cards de Prey e Charms."""
    return {
        "prey": [{"tipo": t, "rotulo": p["rotulo"], "curto": p["curto"], "descricao": p["descricao"], "bonus": p["bonus"]}
                 for t, p in PREY.items()],
        "charms": {k: [{"nome": nome, "pct": list(pct)} for nome, pct in lista] for k, lista in CHARMS.items()},
    }
