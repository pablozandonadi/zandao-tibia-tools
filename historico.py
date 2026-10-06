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
    "dano": {"elementos": [...], "protecoes": [...], "ofensivo": [...]}   # quando a análise de dano termina
  }]
}
"""

import json
import os
import sys
import threading
import uuid
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
    """Cria ou atualiza (pelo id; senão pela assinatura dos textos). Devolve o registro gravado."""
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
        h.update(campos)
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
            h = dict(h)
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
            "personagem": h.get("personagem") or "", "membros": m["membros"], "duracao": m["duracao"],
            "monstros": (h.get("monstros") or [])[:4],
            "protecoes": [p["rotulo"] for p in ((h.get("dano") or {}).get("protecoes") or [])[:3]]}
           for h, m in zip(hunts, ms)]

    linhas = []
    for chave, rotulo, melhor, tipo in LINHAS_COMPARACAO:
        valores = [m[chave] for m in ms]
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

    veredito = []
    for chave, rotulo in (("lucro_membro_h", "lucro por membro por hora"), ("xp_h", "XP por hora"),
                          ("dano_h", "dano da party por hora")):
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
    return {"hunts": cab, "linhas": linhas, "avisos": avisos, "veredito": veredito, "jogadores": jogadores,
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
    linhas, jogadores = [], {}
    for h in hunts:
        m = metricas(h)
        extra, pj = _metricas_jogadores(_membros_da_hunt(h), m["minutos"])
        m.update(extra)
        linhas.append({
            "id": h["id"], "nome": h.get("nome") or "Hunt",
            "data": h.get("data_hunt") or (h.get("criado_em") or "")[:16].replace("T", " "),
            "personagem": h.get("personagem") or "", "membros": m["membros"], "duracao": m["duracao"],
            "minutos": m["minutos"], "monstros": (h.get("monstros") or [])[:3],
            **{c: m.get(c) for c, *_ in COLUNAS_PANORAMA},
        })
        for k, v in pj.items():
            j = jogadores.setdefault(k, {"nome": v["nome"], "hunts": 0, "minutos": 0, "dano": 0, "cura": 0,
                                         "supplies": 0, "loot": 0, "balance": 0})
            j["hunts"] += 1
            j["minutos"] += m["minutos"] or 0
            for campo in ("dano", "cura", "supplies", "loot", "balance"):
                j[campo] += v[campo] or 0

    stats = {}
    for chave, _, criterio, _ in COLUNAS_PANORAMA:
        vals = [l[chave] for l in linhas if l[chave] is not None]
        if not vals:
            continue
        stats[chave] = {"media": sum(vals) // len(vals),
                        "melhor": max(vals) if criterio == "max" else min(vals),
                        "pior": min(vals) if criterio == "max" else max(vals)}

    ranking = []
    for j in jogadores.values():
        mn = j["minutos"]
        ranking.append({**j, "dano_h": _por_hora(j["dano"], mn), "cura_h": _por_hora(j["cura"], mn),
                        "supplies_h": _por_hora(j["supplies"], mn), "balance_media": j["balance"] // j["hunts"]})
    ranking.sort(key=lambda j: -(j["dano_h"] or 0))

    minutos = sum(l["minutos"] or 0 for l in linhas)
    return {"colunas": [{"chave": c, "rotulo": r, "melhor": b, "tipo": t} for c, r, b, t in COLUNAS_PANORAMA],
            "linhas": sorted(linhas, key=lambda l: l["data"]), "stats": stats, "jogadores": ranking,
            "total": {"hunts": len(linhas), "minutos": minutos}}


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
