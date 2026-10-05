"""Checagem de atualização via GitHub Releases (mesmo esquema do Zandonadi Radar).

Fail-open: sem internet, GitHub fora do ar ou repositório sem release, a checagem só devolve None.
Nunca trava nem atrapalha o uso normal do programa.
"""

import json
import os
import tempfile
import urllib.request

from versao import REPO_GITHUB, VERSAO_APP

HEADERS = {"User-Agent": "ZandaoTibiaTools", "Accept": "application/vnd.github+json"}


def versao_para_tupla(versao):
    """'v1.2.10' ou '1.2.10' -> (1, 2, 10), para comparar número com número."""
    numeros = []
    for p in versao.strip().lstrip("vV").split("."):
        digitos = "".join(ch for ch in p if ch.isdigit())
        numeros.append(int(digitos) if digitos else 0)
    return tuple(numeros)


def verificar_atualizacao():
    """{'versao', 'url_instalador', 'notas', 'url_release'} se a última release for mais nova e tiver um .exe; senão None."""
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{REPO_GITHUB}/releases/latest", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            dados = json.load(r)
        tag = dados.get("tag_name") or ""
        if not tag or versao_para_tupla(tag) <= versao_para_tupla(VERSAO_APP):
            return None
        url = next((a.get("browser_download_url") for a in dados.get("assets", [])
                    if (a.get("name") or "").lower().endswith(".exe")), None)
        if not url:
            return None
        return {"versao": tag, "url_instalador": url, "notas": dados.get("body") or "",
                "url_release": dados.get("html_url") or ""}
    except Exception:
        return None


def baixar_instalador(url, callback_progresso=None):
    """Baixa o instalador para a pasta temporária. Devolve o caminho ou None."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ZandaoTibiaTools"})
        destino = os.path.join(tempfile.gettempdir(), "ZandaoTibiaToolsSetup_novo.exe")
        with urllib.request.urlopen(req, timeout=30) as r, open(destino, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            baixado = 0
            while True:
                pedaco = r.read(262144)
                if not pedaco:
                    break
                f.write(pedaco)
                baixado += len(pedaco)
                if callback_progresso and total:
                    callback_progresso(min(100, baixado * 100 // total))
        return destino
    except Exception:
        return None
