"""Checagem de atualização via GitHub Releases (mesmo esquema do Zandonadi Radar).

Fail-open: sem internet, GitHub fora do ar ou repositório sem release, a checagem só devolve None.
Nunca trava nem atrapalha o uso normal do programa.
"""

import json
import os
import re
import tempfile
import urllib.request

from versao import REPO_GITHUB, VERSAO_APP, CANAL_APP, NOME_INSTALADOR

HEADERS = {"User-Agent": "ZandaoTibiaTools", "Accept": "application/vnd.github+json"}


def versao_para_tupla(versao):
    """Ordena versões estáveis e beta (inclui execução e tentativa do build)."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:-beta\.(\d+)(?:\.(\d+))?)?", versao.strip(), re.I)
    if not m:
        raise ValueError("Versão inválida")
    major, minor, patch, build, attempt = m.groups()
    return (int(major), int(minor), int(patch), build is None,
            int(build or 0), int(attempt or 0))


def verificar_atualizacao():
    """Cada instalação consulta somente seu canal e seu instalador."""
    try:
        endpoint = "releases?per_page=100" if CANAL_APP == "beta" else "releases/latest"
        req = urllib.request.Request(f"https://api.github.com/repos/{REPO_GITHUB}/{endpoint}", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            dados = json.load(r)
        releases = dados if isinstance(dados, list) else [dados]
        candidatas = []
        for release in releases:
            if release.get("draft") or bool(release.get("prerelease")) != (CANAL_APP == "beta"):
                continue
            tag = release.get("tag_name") or ""
            if ("-beta." in tag) != (CANAL_APP == "beta"):
                continue
            try:
                ordem = versao_para_tupla(tag)
            except ValueError:
                continue
            url = next((a.get("browser_download_url") for a in release.get("assets", [])
                        if a.get("name") == NOME_INSTALADOR), None)
            if url and ordem > versao_para_tupla(VERSAO_APP):
                candidatas.append((ordem, release, url))
        if not candidatas:
            return None
        _, release, url = max(candidatas, key=lambda x: x[0])
        return {"versao": release["tag_name"], "url_instalador": url,
                "notas": release.get("body") or "", "url_release": release.get("html_url") or ""}
    except Exception:
        return None


def baixar_instalador(url, callback_progresso=None):
    """Baixa o instalador para a pasta temporária. Devolve o caminho ou None."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ZandaoTibiaTools"})
        destino = os.path.join(tempfile.gettempdir(), NOME_INSTALADOR.replace(".exe", "_novo.exe"))
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
