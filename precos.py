"""Histórico dos preços pesquisados no Market (aba Embuimentos), salvo em precos_historico.json ao lado do programa.

Os preços mudam de um mundo (servidor) para outro, então o histórico é separado por MUNDO: o do personagem em uso.
Só entra no histórico quando o usuário clica em "Registrar preços de hoje"; no máximo 1 registro por dia
por item (registrar de novo no mesmo dia troca o valor). Separado do dados_embuimentos.json porque
aquele é regravado a cada tecla digitada.

Formato (versão 2):
{"versao": 2, "mundos": {
   "Honbra": {"item:rope belt": [{"data": "2026-10-03", "preco": 4600}], "scroll:void": [...], "token": [...], "blank": [...]},
   "Xybra": {...},
   "": {...}}}
O mundo "" guarda o que foi registrado antes de existir a separação por mundo (e sem personagem cadastrado): são os "antigos",
que o usuário pode mover para um mundo (mover_antigos). O formato antigo (sem "mundos": {chave: [registros]}) é lido como esse grupo "".
"""

import json
import os
import sys
import threading

from app_paths import data_dir, install_dir, resource_dir
BASE_DIR = data_dir()

PRECOS_PATH = os.path.join(BASE_DIR, "precos_historico.json")

_trava = threading.Lock()


def _limpar(d):
    """{chave: [registros]} só com os registros válidos (um registro estragado é ignorado, não derruba o app)."""
    limpo = {}
    if not isinstance(d, dict):
        return limpo
    for chave, lista in d.items():
        if not isinstance(lista, list):
            continue
        ok = [p for p in lista if isinstance(p, dict) and isinstance(p.get("data"), str) and isinstance(p.get("preco"), int)
              and not isinstance(p.get("preco"), bool) and p["preco"] > 0]
        if ok:
            limpo[chave] = ok
    return limpo


def _carregar_tudo(caminho=None):
    """{mundo: {chave: [registros]}} (o formato antigo, sem mundos, vira {"": ...})."""
    try:
        with open(caminho or PRECOS_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(d, dict):
        return {}
    if isinstance(d.get("mundos"), dict):
        brutos = d["mundos"]
    else:
        brutos = {"": d}
    tudo = {}
    for mundo, hist in brutos.items():
        limpo = _limpar(hist)
        if limpo:
            tudo[mundo] = limpo
    return tudo


def carregar(caminho=None, mundo=""):
    """O histórico de um mundo: {chave: [{"data", "preco"}]}. mundo "" = os antigos / sem personagem."""
    return _carregar_tudo(caminho).get(mundo or "", {})


def _gravar_tudo(tudo, caminho=None):
    caminho = caminho or PRECOS_PATH
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"versao": 2, "mundos": tudo}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)  # nunca deixa o arquivo pela metade


def registrar(precos, data, caminho=None, mundo=""):
    """precos = {chave: int|None}. Grava os preenchidos (> 0) na data, no mundo; devolve quantos gravou."""
    mundo = mundo or ""
    with _trava:
        tudo = _carregar_tudo(caminho)
        hist = tudo.setdefault(mundo, {})
        gravados = 0
        for chave, preco in precos.items():
            if not preco or preco <= 0:
                continue
            lista = [p for p in hist.get(chave, []) if p.get("data") != data]
            lista.append({"data": data, "preco": int(preco)})
            hist[chave] = sorted(lista, key=lambda p: p["data"])
            gravados += 1
        if gravados:
            _gravar_tudo(tudo, caminho)
        return gravados


def contar_antigos(caminho=None):
    """Quantos registros existem no grupo dos antigos (sem mundo)."""
    return sum(len(l) for l in carregar(caminho, "").values())


def mover_antigos(mundo, caminho=None):
    """Passa os registros antigos (sem mundo) para o mundo escolhido; no mesmo dia vale o que já está no mundo. Devolve quantos moveu."""
    if not mundo:
        return 0
    with _trava:
        tudo = _carregar_tudo(caminho)
        antigos = tudo.pop("", {})
        if not antigos:
            return 0
        destino = tudo.setdefault(mundo, {})
        movidos = 0
        for chave, lista in antigos.items():
            atual = destino.get(chave, [])
            datas = {p["data"] for p in atual}
            novos = [p for p in lista if p["data"] not in datas]
            movidos += len(novos)
            destino[chave] = sorted(atual + novos, key=lambda p: p["data"])
        _gravar_tudo(tudo, caminho)
        return movidos


def ultimo_antes(historico, chave, data):
    """Último registro com data anterior a `data` (a pesquisa anterior, para comparar)."""
    antes = [p for p in historico.get(chave, []) if p.get("data", "") < data]
    return antes[-1] if antes else None


def variacao(preco_atual, chave, hoje, historico):
    """Quanto o preço digitado agora mudou em relação ao último registro de antes de hoje."""
    if not preco_atual:
        return None
    ant = ultimo_antes(historico, chave, hoje)
    if not ant or not ant.get("preco") or ant["preco"] == preco_atual:
        return None
    return {"pct": round((preco_atual - ant["preco"]) / ant["preco"] * 100, 1), "antes": ant["preco"],
            "data": ant["data"], "sentido": "subiu" if preco_atual > ant["preco"] else "caiu"}


def serie(historico, chave):
    pontos = list(historico.get(chave, []))
    valores = [p["preco"] for p in pontos]
    if not valores:
        return {"pontos": [], "min": None, "max": None, "media": None}
    return {"pontos": pontos, "min": min(valores), "max": max(valores), "media": sum(valores) // len(valores)}


def apagar(chave, data, caminho=None, mundo=""):
    mundo = mundo or ""
    with _trava:
        tudo = _carregar_tudo(caminho)
        hist = tudo.get(mundo, {})
        lista = hist.get(chave, [])
        resto = [p for p in lista if p.get("data") != data]
        if len(resto) == len(lista):
            return False
        if resto:
            hist[chave] = resto
        else:
            hist.pop(chave, None)
        if not hist:
            tudo.pop(mundo, None)
        _gravar_tudo(tudo, caminho)
        return True
