"""Histórico das hunts (Loot Split + Dano juntos), salvo em historico_hunts.json ao lado do programa.

Cada pessoa tem o seu, no próprio computador (igual ao Zandonadi Radar). Para levar para
outro PC ou mandar para um amigo: exportar gera um .json; importar soma (sem duplicar a mesma
hunt) ou substitui tudo.

Formato do arquivo (o mesmo do exportado):
{
  "formato": "zandao-tibia-tools-hunts", "versao_formato": 1, "exportado_em": "2026-10-05T13:06:00",
  "hunts": [{
    "id": "9f1c...", "assinatura": "sha1 dos textos", "criado_em": "...", "atualizado_em": "...",
    "nome": "norfectarus pt 4x", "data_hunt": "2026-10-05 10:19", "personagem": "Zandao",
    "entrada": {"party": "...", "solo": "...", "dano": "...", "despesas": [...], "excluidos": [...]},
    "pagos": ["Pagador>Recebedor", ...],
    "resumo": {"duracao": "02:47h", "balance": 0, "lucro": 0, "xp": 0, ...},
    "membros": ["Zandao", ...], "monstros": [{"nome": "...", "kills": 0}],
    "prey": [{"tipo": "xp", "estrelas": 7}],   # opcional: [] = sem prey; sem o campo = não informada
    "dano": {"elementos": [...], "protecoes": [...], "ofensivo": [...]}   # quando a análise de dano termina
  }]
}
"""

import json
import os
import sys
import threading
import uuid

import personagens as _personagens
import posturas as _posturas
import preys_charms
import roda as _roda
import sets as _sets
import stats_set as _stats_set
from datetime import datetime

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HIST_PATH = os.path.join(BASE_DIR, "historico_hunts.json")
FORMATO = "zandao-tibia-tools-hunts"
VERSAO_FORMATO = 1

_trava = threading.Lock()


def _agora():
    return datetime.now().isoformat(timespec="seconds")


def carregar(caminho=None):
    try:
        with open(caminho or HIST_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        hunts = d.get("hunts", []) if isinstance(d, dict) else []
    except (OSError, json.JSONDecodeError):
        hunts = []
    return [h for h in hunts if isinstance(h, dict) and h.get("id")]


def _gravar(hunts, caminho=None):
    caminho = caminho or HIST_PATH
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"formato": FORMATO, "versao_formato": VERSAO_FORMATO, "hunts": hunts}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)  # nunca deixa o histórico pela metade se o PC desligar no meio


def ordenar(hunts):
    return sorted(hunts, key=lambda h: (h.get("data_hunt") or h.get("criado_em") or ""), reverse=True)


def salvar(registro, caminho=None):
    """Cria ou atualiza (pelo id; senão pela assinatura dos textos). Devolve o registro gravado.
    Sem o campo "prey" no registro, a prey já gravada é mantida (hunt antiga aberta e salva não perde nem inventa prey)."""
    registro = _com_prey_normalizada(registro)
    with _trava:
        hunts = carregar(caminho)
        atual = next((h for h in hunts if h["id"] == registro.get("id")), None) \
            or next((h for h in hunts if registro.get("assinatura") and h.get("assinatura") == registro["assinatura"]), None)
        if atual:
            preservar = {"id": atual["id"], "criado_em": atual.get("criado_em"), "pagos": atual.get("pagos", [])}
            if not registro.get("dano") and atual.get("dano") and atual.get("assinatura") == registro.get("assinatura"):
                preservar["dano"] = atual["dano"]
            if "pagos" in registro:
                preservar["pagos"] = registro["pagos"]
            for campo in ("prey", "charms", "roda", "set", "postura"):  # sem o campo no registro = o usuário não mexeu: mantém o gravado
                if campo not in registro and campo in atual:
                    preservar[campo] = atual[campo]
            atual.clear()
            atual.update(registro)
            atual.update(preservar)
            atual["atualizado_em"] = _agora()
            gravado = atual
        else:
            gravado = dict(registro)
            gravado["id"] = uuid.uuid4().hex
            gravado["criado_em"] = gravado["atualizado_em"] = _agora()
            gravado.setdefault("pagos", [])
            hunts.append(gravado)
        _gravar(hunts, caminho)
        return gravado


def atualizar(id_, caminho=None, **campos):
    with _trava:
        hunts = carregar(caminho)
        h = next((x for x in hunts if x["id"] == id_), None)
        if not h:
            return None
        h.update(_com_prey_normalizada(campos))   # prey, charms, roda, set e postura passam pela mesma limpeza do salvar
        h["atualizado_em"] = _agora()
        _gravar(hunts, caminho)
        return h


def apagar(id_, caminho=None):
    with _trava:
        hunts = carregar(caminho)
        resto = [h for h in hunts if h["id"] != id_]
        if len(resto) == len(hunts):
            return False
        _gravar(resto, caminho)
        return True


def obter(id_, caminho=None):
    return next((h for h in carregar(caminho) if h["id"] == id_), None)


def do_personagem(h, personagem):
    p = personagem.lower()
    return (h.get("personagem") or "").lower() == p or p in [m.lower() for m in h.get("membros", [])]


def exportar(ids=None, personagem=None, caminho=None):
    hunts = carregar(caminho)
    if ids:
        alvo = set(ids)
        hunts = [h for h in hunts if h["id"] in alvo]
    if personagem:
        hunts = [h for h in hunts if do_personagem(h, personagem)]
    return {"formato": FORMATO, "versao_formato": VERSAO_FORMATO, "exportado_em": _agora(), "hunts": ordenar(hunts)}


def importar(dados, substituir=False, caminho=None):
    """Devolve (importadas, ignoradas_por_já_existirem). Levanta ValueError se não for um arquivo nosso."""
    if not isinstance(dados, dict) or dados.get("formato") != FORMATO or not isinstance(dados.get("hunts"), list):
        raise ValueError("Esse arquivo não parece ser uma exportação de hunts do Zandao Tibia Tools.")
    with _trava:
        hunts = [] if substituir else carregar(caminho)
        ids = {h["id"] for h in hunts}
        assinaturas = {h.get("assinatura") for h in hunts if h.get("assinatura")}
        novas = ignoradas = 0
        for h in dados["hunts"]:
            if not isinstance(h, dict) or not isinstance(h.get("entrada"), dict):
                continue
            if h.get("id") in ids or (h.get("assinatura") and h["assinatura"] in assinaturas):
                ignoradas += 1
                continue
            h = _com_prey_normalizada(dict(h))
            h["id"] = h.get("id") or uuid.uuid4().hex
            h.setdefault("criado_em", _agora())
            h["importado_em"] = _agora()
            hunts.append(h)
            ids.add(h["id"])
            if h.get("assinatura"):
                assinaturas.add(h["assinatura"])
            novas += 1
        _gravar(hunts, caminho)
        return novas, ignoradas


def tamanho_party(h):
    return ((h.get("resumo") or {}).get("membros")) or 1


def do_tamanho(h, filtro):
    """filtro: '' (todas), '1' (solo), '2', '3', '4' ou '5+'."""
    if not filtro:
        return True
    n = tamanho_party(h)
    return n >= 5 if filtro == "5+" else n == int(filtro)


# (chave, rótulo, o que é melhor: 'max' | 'min' | None, tipo de número)
LINHAS_COMPARACAO = [
    ("duracao", "Duração", None, "txt"),
    ("membros", "Tamanho da party", None, "num"),
    ("lucro_membro_h", "Lucro por membro / hora", "max", "gp"),
    ("lucro_membro", "Lucro por membro (total)", "max", "gp"),
    ("balance_h", "Balance da party / hora", "max", "gp"),
    ("balance", "Balance da party (total)", "max", "gp"),
    ("loot_membro_h", "Loot por membro / hora", "max", "gp"),
    ("supplies_membro_h", "Supplies por membro / hora", "min", "gp"),
    ("xp_h", "XP / hora", "max", "num"),
    ("xp_raw_h", "Raw XP / hora", "max", "num"),
    ("xp", "XP (total)", "max", "num"),
    ("despesas", "Despesas extras", "min", "gp"),
    ("dano_total", "Dano total da party", "max", "num"),
    ("dano_h", "Dano da party / hora", "max", "num"),
    ("dano_membro_h", "Dano por membro / hora", "max", "num"),
    ("cura_total", "Cura total da party", "max", "num"),
    ("cura_h", "Cura da party / hora", "max", "num"),
    ("loot_total", "Loot da party (total)", "max", "gp"),
    ("supplies_total", "Supplies da party (total)", "min", "gp"),
    ("top_dano", "Quem bateu mais", None, "txt"),
    ("top_cura", "Quem curou mais", None, "txt"),
    ("top_supplies", "Quem gastou mais supplies", None, "txt"),
    ("top_loot", "Quem lootou mais", None, "txt"),
    ("top_balance", "Maior balance", None, "txt"),
]

# Só Hunt Analyser (sem Party Hunt): quem está sozinho não tem membros nem "quem bateu mais"; essas linhas somem
LINHAS_SO_PARTY = {"membros", "balance_h", "balance", "dano_membro_h", "loot_total", "supplies_total",
                   "top_dano", "top_cura", "top_supplies", "top_loot", "top_balance"}
ROTULOS_SOLO = {"dano_total": "Dano total", "dano_h": "Dano / hora", "cura_total": "Cura total", "cura_h": "Cura / hora"}


def tem_party(h):
    """A hunt tem o texto do Party Hunt? Sem ele só existe o Hunt Analyser (um jogador). Hunts sem os textos guardados
    (importadas antigas) valem pelo tamanho da party."""
    e = h.get("entrada")
    if isinstance(e, dict) and e:
        return bool((e.get("party") or "").strip())
    return tamanho_party(h) > 1


# por jogador: (chave, rótulo, o que é melhor)
METRICAS_JOGADOR = [
    ("dano", "Dano", "max"), ("dano_h", "Dano / hora", "max"),
    ("cura", "Cura", "max"), ("cura_h", "Cura / hora", "max"),
    ("supplies", "Supplies", "min"), ("supplies_h", "Supplies / hora", "min"),
    ("loot", "Loot", "max"), ("balance", "Balance", "max"),
]


def _membros_da_hunt(h):
    """Membros com dano/cura/supplies/loot/balance, recalculados dos textos guardados (vale para hunts antigas)."""
    import hunt as _hunt
    try:
        a = _hunt.montar(h.get("entrada") or {})
    except Exception:
        return []
    if a.get("vazio"):
        return []
    if a.get("membros"):
        return [{"nome": m["nome"], "dano": m["dano"], "cura": m["cura"], "supplies": m["supplies"],
                 "loot": m["loot"], "balance": m["balance"]} for m in a["membros"]]
    s = a.get("solo")
    if s:
        return [{"nome": h.get("personagem") or "Você", "dano": s["dano"], "cura": s["cura"], "supplies": s["supplies"],
                 "loot": s["loot"], "balance": s["balance"]}]
    return []


def _destaque(membros, chave, total=None):
    if not membros:
        return None
    m = max(membros, key=lambda x: x[chave])
    pct = f" ({m[chave] / total * 100:.1f}%)" if total else ""
    return f"{m['nome']} · {m[chave]:,}{pct}"


def _metricas_jogadores(membros, minutos):
    tem = bool(membros)
    tot_dano = sum(m["dano"] for m in membros)
    tot_cura = sum(m["cura"] for m in membros)
    extra = {
        "dano_total": tot_dano if tem else None, "cura_total": tot_cura if tem else None,
        "dano_h": _por_hora(tot_dano, minutos) if tem else None,
        "cura_h": _por_hora(tot_cura, minutos) if tem else None,
        "dano_membro_h": _por_hora(tot_dano // len(membros), minutos) if tem else None,
        "loot_total": sum(m["loot"] for m in membros) if tem else None,
        "supplies_total": sum(m["supplies"] for m in membros) if tem else None,
        "top_dano": _destaque(membros, "dano", tot_dano), "top_cura": _destaque(membros, "cura", tot_cura),
        "top_supplies": _destaque(membros, "supplies"), "top_loot": _destaque(membros, "loot"),
        "top_balance": _destaque(membros, "balance"),
    }
    por_jogador = {}
    for m in membros:
        por_jogador[m["nome"].lower()] = {
            "nome": m["nome"], "dano": m["dano"], "dano_pct": (m["dano"] / tot_dano * 100) if tot_dano else 0,
            "dano_h": _por_hora(m["dano"], minutos), "cura": m["cura"],
            "cura_pct": (m["cura"] / tot_cura * 100) if tot_cura else 0, "cura_h": _por_hora(m["cura"], minutos),
            "supplies": m["supplies"], "supplies_h": _por_hora(m["supplies"], minutos),
            "loot": m["loot"], "balance": m["balance"],
        }
    return extra, por_jogador


def _por_hora(v, minutos):
    return (v * 60) // minutos if (v is not None and minutos) else None


def metricas(h):
    """Números de uma hunt já normalizados por hora e por membro, para comparar hunts diferentes."""
    r = h.get("resumo") or {}
    m = r.get("minutos") or 0
    n = tamanho_party(h)
    por_membro = lambda v: (v // n) if v is not None else None
    return {
        "duracao": r.get("duracao") or "—", "minutos": m, "membros": n,
        "lucro_membro": r.get("lucro"), "lucro_membro_h": _por_hora(r.get("lucro"), m),
        "balance": r.get("balance"), "balance_h": r.get("balance_h") if r.get("balance_h") is not None else _por_hora(r.get("balance"), m),
        "loot_membro_h": _por_hora(por_membro(r.get("loot")), m),
        "supplies_membro_h": _por_hora(por_membro(r.get("supplies")), m),
        "xp": r.get("xp"), "xp_h": r.get("xp_h"), "xp_raw_h": r.get("xp_raw_h"),
        "despesas": r.get("despesas") or 0,
    }


def _monstros(h):
    import monstros as mon
    return {mon.singularizar(m.get("nome", "")) for m in h.get("monstros") or [] if m.get("nome")}


# ---------------------------------------------------------------------------
# Prey: só marca qual estava ativa (os números colados já vêm com o efeito dela).
# "prey": [] = sem prey; sem o campo = não informada (hunts antigas). Nunca confundir os dois.
# ---------------------------------------------------------------------------
TIPOS_PREY = {t: p["curto"] for t, p in preys_charms.PREY.items()}
_EFEITO_PREY = [("xp", "a XP/h"), ("loot", "o loot"), ("dano", "o dano")]  # ataque e defesa mexem no dano


def normalizar_prey(valor):
    """Até 3 preys válidas {"tipo", "estrelas" 1..10}; None continua None (não informada)."""
    if valor is None:
        return None
    if not isinstance(valor, list):
        return []
    saida, criaturas = [], set()
    for p in valor:
        if not isinstance(p, dict) or p.get("tipo") not in TIPOS_PREY:
            continue
        try:
            estrelas = int(p.get("estrelas"))
        except (TypeError, ValueError):
            continue
        item = {"tipo": p["tipo"], "estrelas": max(1, min(10, estrelas))}
        criatura = p.get("criatura").strip()[:60] if isinstance(p.get("criatura"), str) else ""
        if criatura and criatura.lower() not in criaturas:  # a mesma criatura não pode ter duas preys
            criaturas.add(criatura.lower())
            item["criatura"] = criatura
        saida.append(item)
    return saida[:3]


def _com_prey_normalizada(registro):
    """Normaliza "prey" e "charms" do registro; um None vira "sem o campo" (não informado)."""
    for campo, normalizar in (("prey", normalizar_prey), ("charms", preys_charms.normalizar_charms), ("roda", _roda.normalizar_roda), ("set", _sets.normalizar_set), ("postura", _posturas.normalizar_postura)):
        if campo not in registro:
            continue
        registro = dict(registro)
        valor = normalizar(registro[campo])
        if valor is None:
            registro.pop(campo)
        else:
            registro[campo] = valor
    return registro


def rotulo_prey(prey, com_criatura=False):
    """"Prey Ataque ★10 + Prey XP ★7". A criatura só entra quando pedida (no aviso do comparativo); no chip fica só tipo e estrelas."""
    if prey is None:
        return "Prey não informada"
    if not prey:
        return "Sem prey"
    return " + ".join(f"Prey {TIPOS_PREY[p['tipo']]} ★{p['estrelas']}" + (f" · {p['criatura']}" if com_criatura and p.get("criatura") else "")
                      for p in prey)


def _aviso_prey(hunts, cab):
    """Só avisa quando todas as hunts têm a prey informada e elas não são iguais."""
    if not all("prey" in h for h in hunts):
        return None
    preys = [normalizar_prey(h["prey"]) or [] for h in hunts]
    chave = lambda p: (p["estrelas"], (p.get("criatura") or "").lower())  # mesma prey em outra criatura também muda
    if len({frozenset((p["tipo"],) + chave(p) for p in pr) for pr in preys}) < 2:
        return None
    # só os tipos que mudam entre as hunts (XP ★7 nas duas não atrapalha comparar a XP/h)
    diferentes = [t for t in TIPOS_PREY if len({frozenset(chave(p) for p in pr if p["tipo"] == t) for pr in preys}) > 1]
    tipos = {"dano" if t in ("ataque", "defesa") else t for t in diferentes}
    partes = [txt for t, txt in _EFEITO_PREY if t in tipos]
    partes[0] = partes[0][0].upper() + partes[0][1:]
    efeito = partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " e " + partes[-1]
    verbo = "não é comparável" if len(partes) == 1 else "não são comparáveis"
    quem = ", ".join(f"\"{c['nome']}\" " + ("sem prey" if not pr else "com " + rotulo_prey(pr, True)) for c, pr in zip(cab, preys))
    return f"Prey diferente: {quem}. {efeito} {verbo} diretamente."


# tipo de prey -> (nome, métrica do comparativo que ela mexe, rótulo da métrica); defesa mexe no dano recebido (não medido)
_EFEITO_NUMERICO = {"xp": ("XP", "xp_h", "XP/h"), "loot": ("Loot", "loot_membro_h", "Loot por membro/h"),
                    "ataque": ("Ataque", "dano_membro_h", "Dano por membro/h"), "defesa": ("Defesa", None, "")}


def _bonus_do_tipo(prey, tipo):
    return sum(preys_charms.bonus_prey(p["tipo"], p["estrelas"]) or 0 for p in prey if p["tipo"] == tipo)


def _descreve_prey(c, prey, tipo, nome):
    do_tipo = [p for p in prey if p["tipo"] == tipo]
    if not do_tipo:
        return f"\"{c['nome']}\" sem Prey {nome}"
    estrelas = " + ".join(f"★{p['estrelas']}" for p in do_tipo)
    return f"\"{c['nome']}\" com Prey {nome} {estrelas} (+{_bonus_do_tipo(prey, tipo)}%)"


def _efeito_prey(hunts, cab, ms):
    """Explica, tipo de prey por tipo de prey, o que a diferença de prey entre as hunts deve ter causado (só quando todas
    têm a prey informada): XP/h, loot, dano; a defesa mexe no dano recebido, que o app não mede."""
    if not all("prey" in h for h in hunts):
        return []
    preys = [normalizar_prey(h["prey"]) or [] for h in hunts]
    saida = []
    for tipo, (nome, metrica, rotulo) in _EFEITO_NUMERICO.items():
        bonus = [_bonus_do_tipo(pr, tipo) for pr in preys]
        if len(set(bonus)) < 2:
            continue
        i_hi, i_lo = bonus.index(max(bonus)), bonus.index(min(bonus))
        texto = f"Prey {nome}: {_descreve_prey(cab[i_hi], preys[i_hi], tipo, nome)} contra {_descreve_prey(cab[i_lo], preys[i_lo], tipo, nome)}."
        if metrica is None:
            texto += (f" Ela reduz o dano recebido em {bonus[i_hi]}% em \"{cab[i_hi]['nome']}\" (contra {bonus[i_lo]}% em \"{cab[i_lo]['nome']}\"); "
                      "o app não mede o dano recebido total, então isso não aparece nos números.")
        else:
            hi, lo = ms[i_hi].get(metrica), ms[i_lo].get(metrica)
            if hi is not None and lo:
                real = (hi - lo) / lo * 100
                esperado = ((100 + bonus[i_hi]) / (100 + bonus[i_lo]) - 1) * 100
                sinal = "maior" if real >= 0 else "menor"
                texto += (f" {rotulo} de \"{cab[i_hi]['nome']}\" é {abs(real):.0f}% {sinal} "
                          f"(só pela prey seria cerca de {round(esperado)}%).")
        saida.append(texto)
    return saida


def _nivel_do_personagem(h):
    """Level atual do personagem da hunt (de Meus personagens), para o Flat Damage and Healing; None se não cadastrado."""
    p = _personagens.achar(h.get("personagem"))
    return p.get("level") if p and isinstance(p.get("level"), int) else None


def _stats_da_hunt(h):
    """{chave: linha} do Combat Stats da hunt (set + prey + charms + roda), só as numéricas; None se a hunt não tem nenhum desses dados."""
    s = _sets.normalizar_set(h.get("set"))
    prey = normalizar_prey(h.get("prey")) or []
    charms = preys_charms.normalizar_charms(h.get("charms")) or []
    r = _roda.normalizar_roda(h.get("roda"))
    resumo = _roda.resumo_obter(r["codigo"]) if r else None
    postura = _posturas.normalizar_postura(h.get("postura")) or ""
    if not ((s and s.get("itens")) or prey or charms or resumo or postura):
        return None
    return {l["chave"]: l for l in _stats_set.linhas_hunt(s, prey, charms, resumo, postura=postura, nivel=_nivel_do_personagem(h), skills=_personagens.skills_de(h.get("personagem"))) if l["valor"] is not None}


def _stats_do_set(hunts):
    """Tabela "Stats do set": uma linha por stat (armor, resistências, skills...), um valor por hunt (None = hunt sem set;
    0 = tem set mas não tem esse stat). Vazia se nenhuma hunt tem set. O que só vem em texto (Faster Regeneration...) fica de fora."""
    por_hunt = [_stats_da_hunt(h) for h in hunts]
    ordem = {}
    for linhas in por_hunt:
        for chave, l in (linhas or {}).items():
            ordem.setdefault(chave, l)
    saida = []
    for chave, l in sorted(ordem.items(), key=lambda x: _GRUPOS_STATS.index(x[1]["grupo"])):   # estável: mantém a ordem de cada grupo
        valores = [None if linhas is None else (linhas.get(chave) or {}).get("valor", 0) for linhas in por_hunt]
        numeros = [(i, v) for i, v in enumerate(valores) if v is not None]
        melhor = max(numeros, key=lambda x: x[1])[0] if len(numeros) >= 2 and len({v for _, v in numeros}) > 1 else None
        saida.append({"chave": chave, "grupo": l["grupo"], "rotulo": l["rotulo"], "valores": valores, "melhor": melhor, "misc": bool(l.get("misc"))})
    return saida


_GRUPOS_STATS = ["Defesa", "Ataque", "Skills", "Perks da arma", "Prey", "Charms", "Roda", "Postura", "Outros"]


def _aviso_postura(hunts, cab):
    """Só avisa quando todas as hunts têm a postura informada e elas não são todas iguais."""
    if not all("postura" in h for h in hunts):
        return None
    posturas = [_posturas.normalizar_postura(h["postura"]) or "" for h in hunts]
    if len(set(posturas)) < 2:
        return None
    quem = ", ".join(f"\"{c['nome']}\" " + ("sem postura" if not p else "com " + _posturas.rotulo_postura(p)) for c, p in zip(cab, posturas))
    return f"Postura diferente: {quem}. O dano e a cura podem não ser comparáveis diretamente."


def _aviso_roda(hunts, cab):
    """Só avisa quando todas as hunts têm a roda informada e os códigos não são todos iguais (o título não conta)."""
    if not all("roda" in h for h in hunts):
        return None
    rodas = [_roda.normalizar_roda(h["roda"]) or {} for h in hunts]
    if len({r.get("codigo", "") for r in rodas}) < 2:
        return None
    quem = ", ".join(f"\"{c['nome']}\" " + ("sem roda" if not r else "com " + _roda.rotulo_roda(r)) for c, r in zip(cab, rodas))
    return f"Roda diferente: {quem}. O dano e a cura podem não ser comparáveis diretamente."


def _aviso_set(hunts, cab):
    """Só avisa quando todas as hunts têm o set informado e algum item/embuimento/consumível muda (o título não conta)."""
    if not all("set" in h for h in hunts):
        return None
    conjuntos = [_sets.normalizar_set(h["set"]) or {} for h in hunts]
    base = conjuntos[0]
    mudou = []
    for outro in conjuntos[1:]:
        for rotulo in _sets.diferencas(base, outro):
            if rotulo not in mudou:
                mudou.append(rotulo)
    if not mudou:
        return None
    quem = ", ".join(f"\"{c['nome']}\" " + ("sem set" if not s else "com " + _sets.rotulo_set(s)) for c, s in zip(cab, conjuntos))
    return f"Set diferente: {quem} (muda: {', '.join(mudou)}). O dano, a cura e o lucro podem não ser comparáveis diretamente."


def _fmt_dur(minutos):
    return f"{minutos // 60}h{minutos % 60:02d}" if minutos else "?"


def comparar(hunts):
    """Compara 2 ou mais hunts do histórico lado a lado. Devolve linhas com o melhor valor de cada uma,
    avisos de quando a comparação não é direta (party/duração/personagem/spawn diferentes) e um veredito."""
    ms = [metricas(h) for h in hunts]
    por_jogador = []
    for h, m in zip(hunts, ms):
        extra, pj = _metricas_jogadores(_membros_da_hunt(h), m["minutos"])
        m.update(extra)
        por_jogador.append(pj)
    cab = [{"id": h["id"], "nome": h.get("nome") or "Hunt", "data": h.get("data_hunt") or (h.get("criado_em") or "")[:16].replace("T", " "),
            "personagem": h.get("personagem") or "", "membros": m["membros"], "duracao": "" if m["duracao"] == "—" else m["duracao"], "party": tem_party(h),
            "monstros": (h.get("monstros") or [])[:4], "prey": rotulo_prey(normalizar_prey(h.get("prey"))),
            "charms": preys_charms.rotulo_charms(preys_charms.normalizar_charms(h.get("charms"))),
            "roda": _roda.rotulo_roda(_roda.normalizar_roda(h.get("roda"))),
            "set": _sets.rotulo_set(_sets.normalizar_set(h.get("set"))),
            "postura": _posturas.rotulo_postura(_posturas.normalizar_postura(h.get("postura"))),
            "protecoes": [p["rotulo"] for p in ((h.get("dano") or {}).get("protecoes") or [])[:3]]}
           for h, m in zip(hunts, ms)]

    party = [c["party"] for c in cab]
    so_solo = not any(party)
    linhas = []
    for chave, rotulo, melhor, tipo in LINHAS_COMPARACAO:
        if so_solo and chave in LINHAS_SO_PARTY:
            continue
        if so_solo:
            rotulo = ROTULOS_SOLO.get(chave, rotulo)
        valores = [None if chave.startswith("top_") and not p else m[chave] for m, p in zip(ms, party)]
        if all(v is None for v in valores):
            continue
        idx = None
        numeros = [(i, v) for i, v in enumerate(valores) if isinstance(v, (int, float))]
        if melhor and len(numeros) >= 2 and len({v for _, v in numeros}) > 1:
            idx = (max if melhor == "max" else min)(numeros, key=lambda x: x[1])[0]
        linhas.append({"chave": chave, "rotulo": rotulo, "tipo": tipo, "valores": valores, "melhor": idx})

    avisos = []
    tamanhos = [m["membros"] for m in ms]
    if len(set(tamanhos)) > 1:
        avisos.append(f"Parties de tamanhos diferentes ({' x '.join(str(t) for t in tamanhos)} membros): "
                      "compare pelas linhas \"por membro\".")
    minutos = [m["minutos"] for m in ms if m["minutos"]]
    if minutos and max(minutos) > 1.2 * min(minutos):
        avisos.append(f"Durações diferentes ({' x '.join(_fmt_dur(m['minutos']) for m in ms)}): "
                      "compare pelas linhas \"/ hora\".")
    personagens = {c["personagem"].lower() for c in cab if c["personagem"]}
    if len(personagens) > 1:
        avisos.append("Personagens diferentes: a XP é de cada um (vocação e level mudam muito a XP/h).")
    conjuntos = [_monstros(h) for h in hunts]
    if all(conjuntos):
        base = conjuntos[0]
        for c, s in zip(cab[1:], conjuntos[1:]):
            if len(base & s) / len(base | s) < 0.5:
                avisos.append(f"\"{c['nome']}\" foi em outro spawn (monstros diferentes de \"{cab[0]['nome']}\").")
    if not so_solo and not all(party):
        sem = ", ".join(f"\"{c['nome']}\"" for c, p in zip(cab, party) if not p)
        avisos.append(f"{sem} só tem o Hunt Analyser (sem Party Hunt): não há dados por membro dele. "
                      "Compare pelas linhas \"por membro\" e \"/ hora\".")
    aviso_prey = _aviso_prey(hunts, cab)
    if aviso_prey:
        avisos.append(aviso_prey)
    aviso_roda = _aviso_roda(hunts, cab)
    if aviso_roda:
        avisos.append(aviso_roda)
    aviso_set = _aviso_set(hunts, cab)
    if aviso_set:
        avisos.append(aviso_set)
    aviso_postura = _aviso_postura(hunts, cab)
    if aviso_postura:
        avisos.append(aviso_postura)

    veredito = []
    for chave, rotulo in (("lucro_membro_h", "lucro por membro por hora"), ("xp_h", "XP por hora"),
                          ("dano_h", "dano por hora" if so_solo else "dano da party por hora")):
        vals = [(i, m[chave]) for i, m in enumerate(ms) if m[chave] is not None]
        if len(vals) < 2:
            continue
        vals.sort(key=lambda x: -x[1])
        (i1, v1), (i2, v2) = vals[0], vals[1]
        if v1 == v2:
            continue
        dif = f"{(v1 - v2) / v2 * 100:.0f}% a mais" if v2 > 0 else "mais"
        veredito.append(f"\"{cab[i1]['nome']}\" rendeu {dif} de {rotulo} que \"{cab[i2]['nome']}\".")
    # tabela por jogador: quem aparece em mais hunts primeiro; melhor valor de cada métrica entre as hunts
    nomes = {}
    for pj in por_jogador:
        for k, v in pj.items():
            nomes.setdefault(k, v["nome"])
    jogadores = []
    for k, nome in nomes.items():
        vals = [pj.get(k) for pj in por_jogador]
        melhor = {}
        for chave, _, criterio in METRICAS_JOGADOR:
            nums = [(i, v[chave]) for i, v in enumerate(vals) if v and v[chave] is not None]
            if len(nums) >= 2 and len({x for _, x in nums}) > 1:
                melhor[chave] = (max if criterio == "max" else min)(nums, key=lambda x: x[1])[0]
        jogadores.append({"nome": nome, "em": sum(v is not None for v in vals), "valores": vals, "melhor": melhor})
    jogadores.sort(key=lambda j: (-j["em"], -sum((v or {}).get("dano", 0) for v in j["valores"])))
    if so_solo:   # um jogador só: sem ranking nem detalhe por jogador
        jogadores = []
    return {"hunts": cab, "linhas": linhas, "avisos": avisos, "veredito": veredito, "jogadores": jogadores,
            "efeito_prey": _efeito_prey(hunts, cab, ms), "stats_set": _stats_do_set(hunts),
            "ranking": [] if so_solo else _ranking([(m["minutos"], pj) for m, pj in zip(ms, por_jogador)]),
            "metricas_jogador": [{"chave": c, "rotulo": r} for c, r, _ in METRICAS_JOGADOR]}


# ---------------------------------------------------------------------------
# Filtro por spawn e panorama ("Comparar todas": muitas hunts, uma por linha)
# ---------------------------------------------------------------------------
def monstros_da_hunt(h):
    """Nomes dos monstros (Title Case, singular) de uma hunt salva."""
    import monstros as mon
    return {mon.canonico(m["nome"]) for m in h.get("monstros") or [] if m.get("nome")}


def do_monstro(h, nome):
    return not nome or nome in monstros_da_hunt(h)


def opcoes_monstros(hunts):
    """Monstros que aparecem nas hunts, os mais frequentes primeiro: [(nome, quantas hunts)]."""
    cont = {}
    for h in hunts:
        for m in monstros_da_hunt(h):
            cont[m] = cont.get(m, 0) + 1
    return sorted(cont.items(), key=lambda x: (-x[1], x[0]))


def filtrar(hunts, personagem="", tamanho="", monstro=""):
    return [h for h in hunts if (not personagem or do_personagem(h, personagem))
            and do_tamanho(h, tamanho) and do_monstro(h, monstro)]


# (chave, rótulo curto, o que é melhor, tipo)
COLUNAS_PANORAMA = [
    ("lucro_membro_h", "Lucro/membro/h", "max", "gp"),
    ("lucro_membro", "Lucro/membro", "max", "gp"),
    ("balance_h", "Balance/h", "max", "gp"),
    ("xp_h", "XP/h", "max", "num"),
    ("dano_membro_h", "Dano/membro/h", "max", "num"),
    ("cura_h", "Cura/h", "max", "num"),
    ("loot_membro_h", "Loot/membro/h", "max", "gp"),
    ("supplies_membro_h", "Supplies/membro/h", "min", "gp"),
]


def panorama(hunts):
    """Todas as hunts (já filtradas) numa tabela: uma linha por hunt, colunas normalizadas por hora/membro,
    média/melhor/pior de cada coluna e ranking somado por jogador."""
    linhas, pares = [], []
    for h in hunts:
        m = metricas(h)
        extra, pj = _metricas_jogadores(_membros_da_hunt(h), m["minutos"])
        m.update(extra)
        pares.append((m["minutos"], pj))
        linhas.append({
            "id": h["id"], "nome": h.get("nome") or "Hunt",
            "data": h.get("data_hunt") or (h.get("criado_em") or "")[:16].replace("T", " "),
            "personagem": h.get("personagem") or "", "membros": m["membros"], "duracao": m["duracao"],
            "minutos": m["minutos"], "monstros": (h.get("monstros") or [])[:3],
            **{c: m.get(c) for c, *_ in COLUNAS_PANORAMA},
        })

    stats = {}
    for chave, _, criterio, _ in COLUNAS_PANORAMA:
        vals = [l[chave] for l in linhas if l[chave] is not None]
        if not vals:
            continue
        stats[chave] = {"media": sum(vals) // len(vals),
                        "melhor": max(vals) if criterio == "max" else min(vals),
                        "pior": min(vals) if criterio == "max" else max(vals)}

    minutos = sum(l["minutos"] or 0 for l in linhas)
    return {"colunas": [{"chave": c, "rotulo": r, "melhor": b, "tipo": t} for c, r, b, t in COLUNAS_PANORAMA],
            "linhas": sorted(linhas, key=lambda l: l["data"]), "stats": stats, "jogadores": _ranking(pares),
            "total": {"hunts": len(linhas), "minutos": minutos}}


def _ranking(pares):
    """pares = [(minutos da hunt, {jogador: métricas})]. Soma por jogador só as hunts em que ele estava."""
    jogadores = {}
    for minutos, pj in pares:
        for k, v in pj.items():
            j = jogadores.setdefault(k, {"nome": v["nome"], "hunts": 0, "minutos": 0, "dano": 0, "cura": 0,
                                         "supplies": 0, "loot": 0, "balance": 0})
            j["hunts"] += 1
            j["minutos"] += minutos or 0
            for campo in ("dano", "cura", "supplies", "loot", "balance"):
                j[campo] += v[campo] or 0
    ranking = []
    for j in jogadores.values():
        mn = j["minutos"]
        ranking.append({**j, "dano_h": _por_hora(j["dano"], mn), "cura_h": _por_hora(j["cura"], mn),
                        "supplies_h": _por_hora(j["supplies"], mn), "balance_media": j["balance"] // j["hunts"]})
    ranking.sort(key=lambda j: -(j["dano_h"] or 0))
    return ranking


def ranking_jogadores(hunts):
    """Ranking por jogador somando as hunts (o mesmo do "Comparar todas" e do comparativo lado a lado)."""
    pares = []
    for h in hunts:
        minutos = metricas(h)["minutos"]
        pares.append((minutos, _metricas_jogadores(_membros_da_hunt(h), minutos)[1]))
    return _ranking(pares)


def totais(hunts):
    """Totais para o topo do histórico."""
    minutos = sum((h.get("resumo") or {}).get("minutos") or 0 for h in hunts)
    lucro = sum((h.get("resumo") or {}).get("lucro") or 0 for h in hunts)
    xp = sum((h.get("resumo") or {}).get("xp") or 0 for h in hunts)
    return {
        "hunts": len(hunts), "minutos": minutos, "lucro": lucro, "xp": xp,
        "lucro_h": (lucro * 60 // minutos) if minutos else None,
        "xp_h": (xp * 60 // minutos) if minutos else None,
    }
