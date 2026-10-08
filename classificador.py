"""Classificador de dano (hits e dano por spell, a partir do server log + local chat) dentro do app, com a sessão salva por hunt.

A página é da comunidade (https://github.com/lucasporfz/classificador, publicada em lucasporfz.github.io/classificador). O repositório
dela não declara licença, então o código dela NÃO vai no nosso repositório nem no instalador: cada PC baixa os arquivos da página na
primeira vez (cache em cache_classificador/, 7 dias) e o app monta uma página única, que roda numa caixa isolada (iframe sem acesso
ao app). Uma ponte nossa (web/classificador.js) preenche os logs, clica em "classificar" e guarda os logs e o resultado.

- cache_classificador/ : os arquivos da página (index.html, css/..., js/...), baixados do site dela
- sessoes_classificador.json : {id da hunt: {"local", "server", "html" (resultado), "t"}}, uma sessão por hunt salva
Quem usa: web_api (classificador_*), web/classificador.js.
"""

import json
import os
import re
import sys
import threading
import time
import urllib.request

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BASE = "https://lucasporfz.github.io/classificador/"
PASTA_CACHE = os.path.join(BASE_DIR, "cache_classificador")
SESSOES_PATH = os.path.join(BASE_DIR, "sessoes_classificador.json")
VALIDADE = 7 * 86400          # a página dele muda com frequência: confere de novo depois de uma semana
HEADERS = {"User-Agent": "ZandaoTibiaTools/1.0 (+desktop app)"}
MAX_TEXTO = 8_000_000         # cada log
MAX_HTML = 6_000_000          # resultado salvo
_CSS = re.compile(r'<link[^>]+rel="stylesheet"[^>]+href="(css/[^"]+)"[^>]*>')
_JS = re.compile(r'<script[^>]+src="(js/[^"]+)"[^>]*></script>')
_trava = threading.Lock()


# ---------------------------------------------------------------------------
# os arquivos da página (baixados de lucasporfz.github.io)
# ---------------------------------------------------------------------------
def _baixar(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
        return r.read()


def _valido(nome, dados):
    if not dados:
        return False
    inicio = dados[:200].lstrip().lower()
    if nome == "index.html":
        return b"clsLocalInput" in dados
    return not (inicio.startswith(b"<!doctype html") or inicio.startswith(b"<html"))   # um .js/.css que é página de erro não presta


def _guardar(pasta, nome, dados):
    caminho = os.path.join(pasta, *nome.split("/"))
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "wb") as f:
        f.write(dados)
    os.replace(tmp, caminho)


def arquivos(pasta=None, baixar=None):
    """{"ok": True, "arquivos": {nome: texto}} com a página e tudo o que ela usa (cache de 7 dias; sem internet usa o velho).
    {"ok": False, "erro": ...} se não der para ter a página completa."""
    pasta = pasta or PASTA_CACHE
    baixar = baixar or _baixar
    with _trava:
        os.makedirs(pasta, exist_ok=True)
        index = os.path.join(pasta, "index.html")
        velho = not os.path.isfile(index) or time.time() - os.path.getmtime(index) > VALIDADE
        if velho:
            try:
                dados = baixar(BASE + "index.html")
                if not _valido("index.html", dados):
                    raise ValueError("index inesperado")
                novos = {"index.html": dados}
                texto = dados.decode("utf-8", "replace")
                for nome in [*_CSS.findall(texto), *_JS.findall(texto)]:
                    d = baixar(BASE + nome)
                    if not _valido(nome, d):
                        raise ValueError(f"{nome}: conteúdo inesperado")
                    novos[nome] = d
                for nome, d in novos.items():        # só grava quando baixou a página inteira (nunca fica metade nova, metade velha)
                    _guardar(pasta, nome, d)
            except Exception:
                pass                                  # cai no cache velho, se houver
        try:
            with open(index, "r", encoding="utf-8") as f:
                texto = f.read()
            saida = {"index.html": texto}
            for nome in [*_CSS.findall(texto), *_JS.findall(texto)]:
                with open(os.path.join(pasta, *nome.split("/")), "r", encoding="utf-8") as f:
                    saida[nome] = f.read()
            return {"ok": True, "arquivos": saida}
        except OSError:
            return {"ok": False, "erro": "Não consegui baixar o classificador (precisa de internet na primeira vez). Confira a conexão e tente de novo."}


def _inline_js(codigo):
    return "<script>\n" + codigo.replace("</script", "<" + chr(92) + "/script") + "\n</script>"


def montar_pagina(arq):
    """A página inteira numa string só: css e js dela embutidos (a biblioteca de gráficos e as fontes continuam vindo da internet)."""
    html = arq["index.html"]
    html = _CSS.sub(lambda m: "<style>\n" + arq.get(m.group(1), "") + "\n</style>", html)
    return _JS.sub(lambda m: _inline_js(arq.get(m.group(1), "")), html)


def pagina_resultado(arq, corpo_html):
    """Só o resultado salvo (sem a tela de colar logs e sem nenhum script), com o css da página: para ver na hora, sem reclassificar."""
    css = "\n".join(arq[n] for n in arq if n.startswith("css/"))
    return ('<!doctype html><html><head><meta charset="utf-8"><style>' + css + '</style></head><body><div class="wrap"><div id="clsResults">'
            + corpo_html + '</div></div></body></html>')


# ---------------------------------------------------------------------------
# sessão salva por hunt
# ---------------------------------------------------------------------------
def _ler(caminho=None):
    try:
        with open(caminho or SESSOES_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _gravar(dados, caminho=None):
    caminho = caminho or SESSOES_PATH
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False)
    os.replace(tmp, caminho)


def _linhas(texto):
    return len([l for l in (texto or "").split("\n") if l.strip()])


def salvar_sessao(id_hunt, local, server, html, caminho=None):
    """Guarda os logs e (se vier) o resultado da hunt. Sem html mantém o resultado que já estava. False se não houver o que guardar."""
    if not isinstance(id_hunt, str) or not id_hunt:
        return False
    local = local[:MAX_TEXTO] if isinstance(local, str) else ""
    server = server[:MAX_TEXTO] if isinstance(server, str) else ""
    if not local.strip() and not server.strip():
        return False
    with _trava:
        dados = _ler(caminho)
        atual = dados.get(id_hunt) or {}
        if isinstance(html, str):
            novo_html = html if len(html) <= MAX_HTML else ""     # resultado grande demais não é guardado (os logs continuam)
        else:
            novo_html = atual.get("html", "")
        dados[id_hunt] = {"local": local, "server": server, "html": novo_html, "t": time.time()}
        _gravar(dados, caminho)
    return True


def obter_sessao(id_hunt, caminho=None):
    s = _ler(caminho).get(id_hunt) if isinstance(id_hunt, str) else None
    if not isinstance(s, dict):
        return None
    return {"local": s.get("local", ""), "server": s.get("server", ""), "html": s.get("html", ""), "t": s.get("t", 0),
            "linhas_local": _linhas(s.get("local")), "linhas_server": _linhas(s.get("server"))}


def apagar_sessao(id_hunt, caminho=None):
    with _trava:
        dados = _ler(caminho)
        if id_hunt not in dados:
            return False
        del dados[id_hunt]
        _gravar(dados, caminho)
        return True
