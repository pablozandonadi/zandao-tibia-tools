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
]


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
    for chave, rotulo in (("lucro_membro_h", "lucro por membro por hora"), ("xp_h", "XP por hora")):
        vals = [(i, m[chave]) for i, m in enumerate(ms) if m[chave] is not None]
        if len(vals) < 2:
            continue
        vals.sort(key=lambda x: -x[1])
        (i1, v1), (i2, v2) = vals[0], vals[1]
        if v1 == v2:
            continue
        dif = f"{(v1 - v2) / v2 * 100:.0f}% a mais" if v2 > 0 else "mais"
        veredito.append(f"\"{cab[i1]['nome']}\" rendeu {dif} de {rotulo} que \"{cab[i2]['nome']}\".")
    return {"hunts": cab, "linhas": linhas, "avisos": avisos, "veredito": veredito}


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
