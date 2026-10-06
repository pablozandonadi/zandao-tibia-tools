"""Organiza as screenshots do Tibia em Personagem / Tipo (/ Mês).
Cópia da lógica do tibia-screenshot-organizer, sem a interface (que fica no Zandao Tibia Tools)."""

import json
import os
import re
import shutil
import sys
from collections import Counter

# ==================================================
# Caminhos e configurações
# ==================================================
# settings.json fica sempre ao lado do script (ou do .exe), independente
# de onde o programa foi aberto.
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

# Onde o Tibia costuma salvar os prints neste PC. Só é usado quando a pessoa clica em
# "Usar pasta padrão do Tibia": quem instala o app começa com as duas pastas em branco.
PASTA_PADRAO_TIBIA = os.path.join(
    os.environ.get("LOCALAPPDATA", ""), "Tibia", "packages", "Tibia", "screenshots"
).replace("\\", "/")

DEFAULTS = {
    "print-dir": "",
    "destination": "",
    "copy": True,
    "by-month": False,
    "open-when-done": False,
}

EXTENSOES = (".png", ".jpg", ".jpeg")


def carregar_config():
    cfg = dict(DEFAULTS)
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg


def salvar_config(cfg):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


# ==================================================
# Organiza as screenshots
# ==================================================
# Nome padrão do Tibia: 2026-07-29_121050328_Zandao_LevelUp.png
#                       data       hora      personagem tipo
def mes_do_arquivo(arquivo):
    """Retorna '2026-07' a partir do nome do print, ou None."""
    data = arquivo.split("_")[0]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", data):
        return data[:7]
    return None


def mover_ou_descartar_duplicada(caminho, novo):
    """Move o print para o novo lugar. Se já existe um igual lá (mesmo nome
    e tamanho), apaga a cópia repetida. Retorna 1 se algo mudou."""
    if os.path.exists(novo):
        if os.path.getsize(novo) == os.path.getsize(caminho):
            os.remove(caminho)
            return 1
        return 0
    os.makedirs(os.path.dirname(novo), exist_ok=True)
    shutil.move(caminho, novo)
    return 1


def reorganizar_destino(destino, por_mes, log):
    """Ajusta prints que já estão no destino ao modo atual:
    com 'separar por mês', move os soltos para a pasta do mês;
    sem ele, traz os das pastas de mês de volta para a pasta do tipo.
    Cópias repetidas (mesmo nome e tamanho) são removidas."""
    movidas = 0
    for personagem in os.listdir(destino):
        pasta_personagem = os.path.join(destino, personagem)
        if not os.path.isdir(pasta_personagem):
            continue
        for tipo in os.listdir(pasta_personagem):
            pasta_tipo = os.path.join(pasta_personagem, tipo)
            if not os.path.isdir(pasta_tipo):
                continue

            if por_mes:
                for arquivo in os.listdir(pasta_tipo):
                    caminho = os.path.join(pasta_tipo, arquivo)
                    mes = mes_do_arquivo(arquivo)
                    if not mes or not os.path.isfile(caminho):
                        continue
                    novo = os.path.join(pasta_tipo, mes, arquivo)
                    movidas += mover_ou_descartar_duplicada(caminho, novo)
            else:
                for mes in os.listdir(pasta_tipo):
                    pasta_mes = os.path.join(pasta_tipo, mes)
                    if not re.fullmatch(r"\d{4}-\d{2}", mes) or not os.path.isdir(pasta_mes):
                        continue
                    for arquivo in os.listdir(pasta_mes):
                        movidas += mover_ou_descartar_duplicada(
                            os.path.join(pasta_mes, arquivo),
                            os.path.join(pasta_tipo, arquivo),
                        )
                    if not os.listdir(pasta_mes):
                        os.rmdir(pasta_mes)

    if movidas:
        log(f"{movidas} prints que já estavam no destino foram reorganizados.\n")
    return movidas


def organizar(cfg, log):
    origem = cfg["print-dir"]
    destino = cfg["destination"]

    if not origem:
        raise ValueError('Escolha a pasta de screenshots do Tibia (ou clique em "Usar pasta padrão do Tibia").')
    if not os.path.isdir(origem):
        raise ValueError(f"Pasta do Tibia não encontrada:\n{origem}")
    if not destino:
        raise ValueError("Escolha a pasta de destino.")

    os.makedirs(destino, exist_ok=True)
    operacao = shutil.copy2 if cfg["copy"] else shutil.move

    resultado = Counter()
    por_tipo = Counter()

    resultado["reorganizadas"] = reorganizar_destino(destino, cfg["by-month"], log)

    for arquivo in sorted(os.listdir(origem)):
        if not arquivo.lower().endswith(EXTENSOES):
            continue

        partes = os.path.splitext(arquivo)[0].split("_")
        if len(partes) < 4:
            resultado["invalidas"] += 1
            log(f"Nome não reconhecido, ignorado: {arquivo}")
            continue

        personagem = partes[2].strip()
        tipo = partes[3].strip()

        pasta_tipo = os.path.join(destino, personagem, tipo)
        mes = mes_do_arquivo(arquivo)
        pasta_destino = pasta_tipo
        if cfg["by-month"] and mes:
            pasta_destino = os.path.join(pasta_tipo, mes)

        caminho_origem = os.path.join(origem, arquivo)
        caminho_destino = os.path.join(pasta_destino, arquivo)

        # Já organizado antes, solto ou na pasta do mês: não copia de novo.
        ja_existe = os.path.exists(os.path.join(pasta_tipo, arquivo)) or (
            mes and os.path.exists(os.path.join(pasta_tipo, mes, arquivo))
        )
        if ja_existe:
            resultado["existentes"] += 1
            continue

        try:
            os.makedirs(pasta_destino, exist_ok=True)
            operacao(caminho_origem, caminho_destino)
        except OSError as e:
            resultado["erros"] += 1
            log(f"Erro em {arquivo}: {e}")
            continue

        resultado["processadas"] += 1
        por_tipo[tipo] += 1
        log(f"{personagem:<20} {tipo:<20} {arquivo}")

    return resultado, por_tipo


