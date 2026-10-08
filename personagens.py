"""Meus personagens: os personagens de quem usa o app, conferidos no tibia.com (via TibiaData).

Ficam em meus_personagens.json, ao lado do programa (cada pessoa tem os seus):
  {"lista": [{"nome": "Zandao", "level": 483, "vocacao": "Master Sorcerer", "mundo": "Rasteibra",
              "atualizado": 1759700000.0}], "atual": "Zandao"}
"atual" é o personagem escolhido no Hunt Analyser (o Hunting Analyser colado é dele).
"""

import json
import os
import sys
import threading
import time

import tibia_info

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ARQUIVO = os.path.join(BASE_DIR, "meus_personagens.json")
SKILLS = ["sword fighting", "axe fighting", "club fighting", "fist fighting", "distance fighting", "shielding", "magic level"]
MODOS = ("offensive", "balanced", "defensive")
ATUALIZAR_APOS = 3600  # levels são reconsultados no tibia.com no máximo a cada 1 hora

_trava = threading.Lock()


def carregar(caminho=None):
    try:
        with open(caminho or ARQUIVO, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError):
        d = {}
    lista = [p for p in d.get("lista", []) if isinstance(p, dict) and p.get("nome")]
    atual = d.get("atual") if any(p["nome"] == d.get("atual") for p in lista) else (lista[0]["nome"] if lista else "")
    return {"lista": lista, "atual": atual}


def _gravar(dados, caminho=None):
    caminho = caminho or ARQUIVO
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)


def adicionar(nome, caminho=None, buscar=None):
    """Confere no tibia.com e adiciona (ou atualiza). Devolve (dados, erro)."""
    buscar = buscar or tibia_info.personagem
    nome = (nome or "").strip()
    if not nome:
        return None, "Digite o nome do personagem."
    info = buscar(nome)
    if not info:
        return None, f"Não achei \"{nome}\" no tibia.com. Confira o nome (e a internet)."
    with _trava:
        d = carregar(caminho)
        antigo = next((p for p in d["lista"] if p["nome"].lower() == info["nome"].lower()), {})
        d["lista"] = [p for p in d["lista"] if p["nome"].lower() != info["nome"].lower()]
        d["lista"].append({**{k: antigo[k] for k in ("skills", "modo") if k in antigo}, **info, "atualizado": time.time()})   # as skills digitadas não se perdem
        d["lista"].sort(key=lambda p: p["nome"].lower())
        if not d["atual"]:
            d["atual"] = info["nome"]
        _gravar(d, caminho)
    return d, None


def achar(nome, caminho=None):
    """Dados do personagem pelo nome (sem diferenciar maiúsculas), ou None."""
    alvo = (nome or "").lower()
    return next((p for p in carregar(caminho)["lista"] if p["nome"].lower() == alvo), None) if alvo else None


def skills_de(nome, caminho=None):
    """{"base": {skill: valor}, "modo": ...} do personagem, ou None se ele não tem skills digitadas."""
    p = achar(nome, caminho)
    return {"base": p["skills"], "modo": p.get("modo") or "offensive"} if p and p.get("skills") else None


def salvar_skills(nome, skills, modo="offensive", caminho=None):
    """Guarda as skills base do personagem (sem itens) e o modo de combate. Devolve os dados, ou None se ele não existir."""
    limpas = {}
    for k in SKILLS:
        v = (skills or {}).get(k)
        try:
            v = int(v)
        except (TypeError, ValueError):
            continue
        if 0 <= v <= 9999:
            limpas[k] = v
    with _trava:
        d = carregar(caminho)
        p = next((x for x in d["lista"] if x["nome"].lower() == (nome or "").lower()), None)
        if not p:
            return None
        p["skills"] = limpas
        p["modo"] = modo if modo in MODOS else "offensive"
        _gravar(d, caminho)
        return d


def remover(nome, caminho=None):
    with _trava:
        d = carregar(caminho)
        d["lista"] = [p for p in d["lista"] if p["nome"].lower() != (nome or "").lower()]
        if d["atual"].lower() == (nome or "").lower():
            d["atual"] = d["lista"][0]["nome"] if d["lista"] else ""
        _gravar(d, caminho)
        return d


def usar(nome, caminho=None):
    with _trava:
        d = carregar(caminho)
        if any(p["nome"] == nome for p in d["lista"]):
            d["atual"] = nome
            _gravar(d, caminho)
        return d


def atualizar_levels(caminho=None, forcar=False, buscar_varios=None):
    """Reconsulta no tibia.com os personagens com dados velhos (o level muda). Sem internet, mantém os antigos."""
    buscar_varios = buscar_varios or tibia_info.personagens
    d = carregar(caminho)
    velhos = [p["nome"] for p in d["lista"] if forcar or time.time() - (p.get("atualizado") or 0) > ATUALIZAR_APOS]
    if not velhos:
        return d
    novos = buscar_varios(velhos)
    with _trava:
        d = carregar(caminho)
        for p in d["lista"]:
            info = novos.get(p["nome"])
            if info:
                p.update(info)
                p["atualizado"] = time.time()
        _gravar(d, caminho)
    return d
