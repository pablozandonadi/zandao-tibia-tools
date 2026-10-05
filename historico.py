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
