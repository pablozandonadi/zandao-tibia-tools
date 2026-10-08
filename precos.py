"""Histórico dos preços pesquisados no Market (aba Embuimentos), salvo em precos_historico.json ao lado do programa.

Só entra no histórico quando o usuário clica em "Registrar preços de hoje"; no máximo 1 registro por dia
por item (registrar de novo no mesmo dia troca o valor). Separado do dados_embuimentos.json porque
aquele é regravado a cada tecla digitada.

Formato:
{
  "item:rope belt": [{"data": "2026-10-03", "preco": 4600}, {"data": "2026-10-07", "preco": 4973}],
  "scroll:void": [...], "token": [...], "blank": [...]
}
"""

import json
import os
import sys
import threading

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PRECOS_PATH = os.path.join(BASE_DIR, "precos_historico.json")

_trava = threading.Lock()


def carregar(caminho=None):
    try:
        with open(caminho or PRECOS_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(d, dict):
        return {}
    limpo = {}
    for chave, lista in d.items():
        if not isinstance(lista, list):
            continue
        ok = [p for p in lista if isinstance(p, dict) and isinstance(p.get("data"), str) and isinstance(p.get("preco"), int)
              and not isinstance(p.get("preco"), bool) and p["preco"] > 0]   # registro estragado é ignorado, não derruba o app
        if ok:
            limpo[chave] = ok
    return limpo


def _gravar(hist, caminho=None):
    caminho = caminho or PRECOS_PATH
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)  # nunca deixa o arquivo pela metade


def registrar(precos, data, caminho=None):
    """precos = {chave: int|None}. Grava os preenchidos (> 0) na data; devolve quantos gravou."""
    with _trava:
        hist = carregar(caminho)
        gravados = 0
        for chave, preco in precos.items():
            if not preco or preco <= 0:
                continue
            lista = [p for p in hist.get(chave, []) if p.get("data") != data]
            lista.append({"data": data, "preco": int(preco)})
            hist[chave] = sorted(lista, key=lambda p: p["data"])
            gravados += 1
        if gravados:
            _gravar(hist, caminho)
        return gravados


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


def apagar(chave, data, caminho=None):
    with _trava:
        hist = carregar(caminho)
        lista = hist.get(chave, [])
        resto = [p for p in lista if p.get("data") != data]
        if len(resto) == len(lista):
            return False
        if resto:
            hist[chave] = resto
        else:
            hist.pop(chave, None)
        _gravar(hist, caminho)
        return True
