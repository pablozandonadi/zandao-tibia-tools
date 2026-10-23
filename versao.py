"""Versão do app e repositório das Releases (atualização automática, igual ao Zandonadi Radar).

Para lançar uma versão nova: aumente VERSAO_APP, gere o instalador (instalador/gerar_instalador.ps1)
e publique uma Release no GitHub com a tag vX.Y.Z e o ZandaoTibiaToolsSetup.exe anexado.
"""

VERSAO_APP = "1.0.40"
REPO_GITHUB = "pablozandonadi/zandao-tibia-tools"


# Metadados gerados pelo build; o código compartilhado continua estável.
import json
import os
import sys

VERSAO_BASE = VERSAO_APP
CANAL_APP = "stable"
BUILD_SOURCE_SHA = ""
if getattr(sys, "frozen", False):
    _metadata = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)), "canal_build.json")
    if os.path.isfile(_metadata):
        with open(_metadata, encoding="utf-8-sig") as _f:
            _build = json.load(_f)
        if _build.get("canal") == "beta":
            CANAL_APP = "beta"
            BUILD_SOURCE_SHA = _build.get("source_sha", "")
            VERSAO_APP = _build["versao"]
NOME_APP = "Tibia Tudo" + (" Beta" if CANAL_APP == "beta" else "")
NOME_INSTALADOR = "ZandaoTibiaToolsBetaSetup.exe" if CANAL_APP == "beta" else "ZandaoTibiaToolsSetup.exe"


def porta_http(canal):
    """Porta do servidor local da janela. O pywebview usa 42001 para todo mundo; com a estável e a Beta abertas ao
    mesmo tempo, a segunda janela carregava os arquivos web da primeira. Cada canal tem a sua porta."""
    return 42002 if canal == "beta" else 42001
