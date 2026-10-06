"""Backup de tudo do usuário num arquivo só (Configurações > Backup).

Leva: histórico de hunts, meus personagens, preços dos embuimentos, pastas dos prints,
"fixar por cima"/transparência e as teclas do Simulated Keys. Caches (fichas de monstros,
boss do dia) não entram: o app baixa de novo sozinho.

Formato do arquivo:
{
  "formato": "zandao-tibia-tools-backup", "versao_formato": 1,
  "versao_app": "1.0.4", "exportado_em": "2026-10-06T12:00:00",
  "arquivos": {
    "historico": {...conteúdo do historico_hunts.json...},
    "teclas": {"base64": "..."}        # o .ini do AutoHotkey vai em bytes (ele grava em UTF-16)
  }
}
Restaurar substitui cada arquivo que vier no backup; antes, guarda o atual como <arquivo>.antes-do-backup.
"""

import base64
import json
import os
import shutil
from datetime import datetime

FORMATO = "zandao-tibia-tools-backup"
VERSAO_FORMATO = 1

# chave -> (rótulo para a tela, é json?)
ITENS = {
    "historico": ("Histórico de hunts", True),
    "personagens": ("Meus personagens", True),
    "embuimentos": ("Preços e escolhas dos embuimentos", True),
    "prints": ("Pastas e opções dos prints", True),
    "janela": ("Fixar por cima e transparência", True),
    "teclas": ("Teclas do Simulated Keys", False),
}


def exportar(caminhos, versao_app=""):
    """caminhos: {chave: caminho do arquivo}. Arquivo que ainda não existe fica de fora."""
    arquivos = {}
    for chave, caminho in caminhos.items():
        if chave not in ITENS or not os.path.isfile(caminho):
            continue
        if ITENS[chave][1]:
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    arquivos[chave] = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
        else:
            with open(caminho, "rb") as f:
                arquivos[chave] = {"base64": base64.b64encode(f.read()).decode("ascii")}
    return {"formato": FORMATO, "versao_formato": VERSAO_FORMATO, "versao_app": versao_app,
            "exportado_em": datetime.now().isoformat(timespec="seconds"), "arquivos": arquivos}


def resumo(dados):
    """Para a tela: o que tem dentro de um backup."""
    arq = dados.get("arquivos") or {}
    out = []
    for chave, (rotulo, _) in ITENS.items():
        if chave not in arq:
            continue
        extra = ""
        if chave == "historico":
            extra = f" ({len((arq[chave] or {}).get('hunts', []))} hunts)"
        elif chave == "personagens":
            extra = f" ({len((arq[chave] or {}).get('lista', []))})"
        out.append(rotulo + extra)
    return out


def importar(dados, caminhos):
    """Restaura o backup. Devolve a lista do que foi restaurado. Levanta ValueError se não for um backup nosso."""
    if not isinstance(dados, dict) or dados.get("formato") != FORMATO or not isinstance(dados.get("arquivos"), dict):
        raise ValueError("Esse arquivo não parece ser um backup do Zandao Tibia Tools.")
    restaurados = []
    for chave, conteudo in dados["arquivos"].items():
        if chave not in ITENS or chave not in caminhos:
            continue
        caminho = caminhos[chave]
        os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
        if os.path.isfile(caminho):
            shutil.copy2(caminho, caminho + ".antes-do-backup")
        tmp = caminho + ".tmp"
        if ITENS[chave][1]:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(conteudo, f, ensure_ascii=False, indent=1)
        else:
            with open(tmp, "wb") as f:
                f.write(base64.b64decode(conteudo["base64"]))
        os.replace(tmp, caminho)
        restaurados.append(ITENS[chave][0])
    return restaurados
