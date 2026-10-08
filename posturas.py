"""Posturas (stance spells) da hunt: o jogador marca qual postura usou (ex.: "Master of Decay" do Sorcerer) e o efeito dela
entra no Combat Stats e no comparativo.

Dados da TibiaWiki (página "Stance Spells", Vocation Adjustments 2026). Cada postura tem a vocação, o efeito em texto e os números
que dá para somar/comparar. Na hunt salva: "postura": "Nome" (a postura), "" = sem postura (informado), sem o campo = não informada.
Quem usa: historico (salvar/comparar), stats_set.linhas_hunt (grupo "Postura"), web_api (hunt_posturas) e web/sets.js.
"""

# (chave, rótulo, valor, unidade) em "stats"; "efeito" é o texto completo (aparece ao passar o mouse)
POSTURAS = [
    {"nome": "Master of Decay", "voc": "sorcerer", "efeito": "Aumenta em 30% o critical extra damage das spells Death naturais. Ao lançar uma spell Death, o dano da próxima spell que não é Death vira Death.",
     "stats": [("crit_dano_death", "Critical extra damage das spells Death", 30, "%")]},
    {"nome": "Master of Flames", "voc": "sorcerer", "efeito": "Aumenta em 4% o dano base das spells Fire naturais. Ao lançar uma spell Fire, o dano da próxima spell que não é Fire vira Fire.",
     "stats": [("dano_base_fire", "Dano base das spells Fire", 4, "%")]},
    {"nome": "Master of Thunder", "voc": "sorcerer", "efeito": "Aumenta em 4% a chance de crítico das spells Energy naturais. Ao lançar uma spell Energy, o dano da próxima spell que não é Energy vira Energy.",
     "stats": [("crit_chance_energy", "Critical hit chance das spells Energy", 4, "%")]},
    {"nome": "Blood Rage", "voc": "knight", "efeito": "Dá 25% de sword/axe/club fighting (sobre o total, com equipamento e buffs) e aumenta em 15% o dano que você recebe.",
     "stats": [("skill_melee", "Sword/Axe/Club fighting", 25, "%"), ("dano_recebido", "Dano recebido", 15, "%")]},
    {"nome": "Protector", "voc": "knight", "efeito": "Dá 30% de shielding e reduz em 15% o dano recebido e também o dano causado.",
     "stats": [("shielding", "Shielding", 30, "%"), ("dano_recebido", "Dano recebido", -15, "%"), ("dano_causado", "Dano causado", -15, "%")]},
    {"nome": "Sharpshooter", "voc": "paladin", "efeito": "Dá 32% de distance fighting (sobre o total, com equipamento e buffs).",
     "stats": [("distance", "Distance fighting", 32, "%")]},
    {"nome": "Divine Defiance", "voc": "paladin", "efeito": "Dá 6% do seu distance fighting como holy e healing magic level, e 12% de dodge contra inimigos não adjacentes.",
     "stats": [("holy_heal_ml", "Holy e healing magic level (do distance fighting)", 6, "%"), ("dodge", "Dodge contra inimigos não adjacentes", 12, "%")]},
    {"nome": "Sniper", "voc": "paladin", "efeito": "A wiki ainda não descreve o efeito desta postura.", "stats": []},
    {"nome": "Virtue of Harmony", "voc": "monk", "efeito": "Aumenta em 3% (6% se Serene) o bônus base de Harmony. Ao usar um Spender nesta virtude, devolve 1 de Harmony.",
     "stats": [("harmony", "Bônus base de Harmony", 3, "%")]},
    {"nome": "Virtue of Justice", "voc": "monk", "efeito": "Aumenta o Fist Fighting em 8% (16% se Serene).",
     "stats": [("fist", "Fist fighting", 8, "%")]},
    {"nome": "Virtue of Sustain", "voc": "monk", "efeito": "Aumenta em 35% (70% se Serene) toda a cura das spells de Monk, incluindo a cura passiva das Virtues.",
     "stats": [("cura_monk", "Cura das spells de Monk", 35, "%")]},
    {"nome": "Channeled Preservation", "voc": "druid", "efeito": "Aumenta em 100% o cooldown de Heal Friend e Mass Healing e, com isso, aumenta a cura deles em 110%.",
     "stats": [("cura_sio", "Cura de Heal Friend e Mass Healing", 110, "%")]},
    {"nome": "Elemental Synthesis", "voc": "druid", "efeito": "Dá 10% do seu Magic Level como ice e earth magic level adicionais.",
     "stats": [("ice_earth_ml", "Ice e earth magic level (do magic level)", 10, "%")]},
    {"nome": "Rejuvenation", "voc": "druid", "efeito": "Aumenta em 10% a cura em você mesmo.",
     "stats": [("autocura", "Cura em si mesmo", 10, "%")]},
    {"nome": "Shared Conservation", "voc": "druid", "efeito": "Dá +10% de cura em você mesmo. Heal Friend e Nature's Embrace curam um alvo secundário (o de menos vida na tela e na party) com 30% da cura.",
     "stats": [("autocura", "Cura em si mesmo", 10, "%"), ("cura_secundaria", "Cura do alvo secundário", 30, "%")]},
]
VOCACOES = ["sorcerer", "knight", "paladin", "monk", "druid"]


def listar(voc=""):
    """Posturas da vocação (ordem alfabética); sem vocação (ou inválida) devolve todas."""
    lista = [p for p in POSTURAS if not voc or voc not in VOCACOES or p["voc"] == voc]
    return sorted(lista, key=lambda p: p["nome"])


def _achar(nome):
    return next((p for p in POSTURAS if isinstance(nome, str) and p["nome"].lower() == nome.strip().lower()), None)


def normalizar_postura(valor):
    """Nome oficial da postura; "" = sem postura (informado); None continua None (não informada)."""
    if valor is None:
        return None
    p = _achar(valor)
    return p["nome"] if p else ""


def rotulo_postura(valor):
    if valor is None:
        return "Postura não informada"
    return f"Postura: {valor}" if valor else "Sem postura"


def linhas(nome):
    """Linhas do Combat Stats da postura: [{chave, grupo, rotulo, valor, texto, detalhe}]. Postura sem números (Sniper) dá uma linha só com o nome."""
    p = _achar(nome)
    if not p:
        return []
    if not p["stats"]:
        return [{"chave": "postura:nome", "grupo": "Postura", "rotulo": p["nome"], "valor": None, "texto": "ativa", "detalhe": p["efeito"]}]
    return [{"chave": f"postura:{chave}", "grupo": "Postura", "rotulo": rotulo, "valor": valor,
             "texto": f"{'+' if valor > 0 else ''}{valor}{unidade}", "detalhe": p["efeito"] if i == 0 else ""}
            for i, (chave, rotulo, valor, unidade) in enumerate(p["stats"])]
