"""Rodas (Wheel of Destiny): o usuário cadastra as rodas dele (título + código do planner do tibia.com) em Configurações
e escolhe qual usou em cada hunt.

- rodas.json: {"formato": "zandao-tibia-tools-rodas", "rodas": [{"id", "titulo", "codigo", "vocacao"}]}
- Na hunt salva: "roda": {"titulo", "codigo"} (cópia, para a hunt não mudar se a roda for apagada/renomeada);
  {} = sem roda; sem o campo = não informada (hunts antigas).
- O código do planner: 1ª letra = vocação (K, P, S, D, M) e o resto é o conteúdo da roda (formato do próprio planner).
- A visualização usa o planner do próprio tibia.com: cada PC baixa os arquivos dele (static.tibia.com) na primeira vez e
  guarda em cache_roda/. Nada disso vai para o GitHub nem para o instalador.
"""

import json
import os
import re
import sys
import threading
import time
import urllib.request
import uuid

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RODAS_PATH = os.path.join(BASE_DIR, "rodas.json")
PASTA_CACHE = os.path.join(BASE_DIR, "cache_roda")
RESUMO_PATH = os.path.join(BASE_DIR, "cache_roda_resumo.json")
VERSAO_RESUMO = 2   # 2: uma linha por elemento do planner (nome, valor, nome, valor...)
FORMATO = "zandao-tibia-tools-rodas"

STATIC = "https://static.tibia.com/"
HEADERS = {"User-Agent": "ZandaoTibiaTools/1.0 (+desktop app)"}
VALIDADE = 30 * 24 * 3600
# nome local -> endereço no static.tibia.com
ARQUIVOS = {
    "skillgrid.js": "javascripts/wheelofdestiny/skillgrid.js",
    "planner.js": "javascripts/wheelofdestiny/wheelofdestinyplanner.min.js",
    "strings.json": "javascripts/wheelofdestiny/SkillwheelStringsJsonLibrary.json",
    "jquery.js": "javascripts/jquery.min.js",
}
# o que cada arquivo precisa conter (para não guardar uma página de erro ou de verificação no lugar do script)
MARCADORES = {"skillgrid.js": "createModule", "planner.js": "runWodPlanner", "strings.json": "SmallPerkInfos", "jquery.js": "jQuery"}

VOCACOES = {"K": "Knight", "P": "Paladin", "S": "Sorcerer", "D": "Druid", "M": "Monk"}
_CODIGO_NA_URL = re.compile(r"code=([-_.~a-zA-Z0-9]+)")
_CODIGO = re.compile(r"^[-_.~a-zA-Z0-9]{8,256}$")
_trava = threading.Lock()


# ---------------------------------------------------------------------------
# código
# ---------------------------------------------------------------------------
def validar_codigo(txt):
    """Aceita o código puro ou o link do planner; devolve o código ou None."""
    if not isinstance(txt, str):
        return None
    t = txt.strip()
    m = _CODIGO_NA_URL.search(t)
    if m:
        t = m.group(1)
    if not _CODIGO.match(t) or t[0] not in VOCACOES:
        return None
    return t


def vocacao_do_codigo(codigo):
    return VOCACOES.get((codigo or "")[:1])


# ---------------------------------------------------------------------------
# cadastro (rodas.json)
# ---------------------------------------------------------------------------
def _ler(caminho=None):
    try:
        with open(caminho or RODAS_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        rodas = d.get("rodas", []) if isinstance(d, dict) else []
    except (OSError, json.JSONDecodeError):
        rodas = []
    return [r for r in rodas if isinstance(r, dict) and r.get("id") and validar_codigo(r.get("codigo"))]


def _gravar(rodas, caminho=None):
    caminho = caminho or RODAS_PATH
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"formato": FORMATO, "rodas": rodas}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)


def listar(caminho=None):
    return _ler(caminho)


def obter(id_, caminho=None):
    return next((r for r in _ler(caminho) if r["id"] == id_), None)


def adicionar(titulo, codigo, caminho=None):
    """Cadastra uma roda. Levanta ValueError se o código não for válido. Título vazio vira "Roda <vocação>"."""
    cod = validar_codigo(codigo)
    if not cod:
        raise ValueError("Esse código não parece ser de uma roda: cole o código do planner (ex.: K0Y2AgDP4jAQA) ou o link dele.")
    voc = vocacao_do_codigo(cod)
    r = {"id": uuid.uuid4().hex, "titulo": (titulo or "").strip()[:60] or f"Roda {voc}", "codigo": cod, "vocacao": voc}
    with _trava:
        rodas = _ler(caminho)
        rodas.append(r)
        _gravar(rodas, caminho)
    return r


def atualizar_codigo(id_, codigo, caminho=None):
    """Troca o código de uma roda já cadastrada (depois de editá-la no planner). Devolve a roda nova, None se não existir,
    e levanta ValueError se o código não for válido (a roda fica como estava)."""
    cod = validar_codigo(codigo)
    if not cod:
        raise ValueError("Esse código não parece ser de uma roda.")
    with _trava:
        rodas = _ler(caminho)
        r = next((x for x in rodas if x["id"] == id_), None)
        if not r:
            return None
        r["codigo"], r["vocacao"] = cod, vocacao_do_codigo(cod)
        _gravar(rodas, caminho)
        return r


def renomear(id_, titulo, caminho=None):
    with _trava:
        rodas = _ler(caminho)
        r = next((x for x in rodas if x["id"] == id_), None)
        if not r:
            return False
        r["titulo"] = (titulo or "").strip()[:60] or f"Roda {r.get('vocacao') or ''}".strip()
        _gravar(rodas, caminho)
        return True


def remover(id_, caminho=None):
    with _trava:
        rodas = _ler(caminho)
        resto = [r for r in rodas if r["id"] != id_]
        if len(resto) == len(rodas):
            return False
        _gravar(resto, caminho)
        return True


# ---------------------------------------------------------------------------
# resumo da roda (os perks que o planner oficial calcula), guardado por código para o Combat Stats
# ---------------------------------------------------------------------------
def resumo_guardar(codigo, secoes, caminho=None):
    """Guarda as seções do resumo ([{"titulo", "linhas"}]) do código. False se o código ou o resumo não prestar."""
    cod = validar_codigo(codigo)
    if not cod or not isinstance(secoes, list):
        return False
    limpas = []
    for s in secoes[:8]:
        if not isinstance(s, dict) or not isinstance(s.get("linhas"), list):
            continue
        linhas = [x.strip()[:200] for x in s["linhas"][:60] if isinstance(x, str) and x.strip()]
        limpas.append({"titulo": (s.get("titulo") or "").strip()[:80] if isinstance(s.get("titulo"), str) else "", "linhas": linhas})
    if not limpas:
        return False
    caminho = caminho or RESUMO_PATH
    with _trava:
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                dados = json.load(f)
        except (OSError, json.JSONDecodeError):
            dados = {}
        if not isinstance(dados, dict):
            dados = {}
        dados[cod] = {"v": VERSAO_RESUMO, "secoes": limpas, "t": time.time()}
        tmp = caminho + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False)
        os.replace(tmp, caminho)
    return True


def resumo_obter(codigo, caminho=None):
    try:
        with open(caminho or RESUMO_PATH, "r", encoding="utf-8") as f:
            item = json.load(f).get(validar_codigo(codigo) or "") or {}
        return item.get("secoes") if item.get("v") == VERSAO_RESUMO else None
    except (OSError, json.JSONDecodeError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# a roda dentro da hunt
# ---------------------------------------------------------------------------
def normalizar_roda(valor):
    """{"titulo", "codigo"} válido; {} = sem roda (informado); None continua None (não informada)."""
    if valor is None:
        return None
    if not isinstance(valor, dict):
        return {}
    cod = validar_codigo(valor.get("codigo"))
    if not cod:
        return {}
    titulo = valor.get("titulo").strip()[:60] if isinstance(valor.get("titulo"), str) else ""
    return {"titulo": titulo or f"Roda {vocacao_do_codigo(cod)}", "codigo": cod}


def rotulo_roda(roda):
    if roda is None:
        return "Roda não informada"
    if not roda:
        return "Sem roda"
    return f"Roda: {roda.get('titulo') or 'sem título'}"


# ---------------------------------------------------------------------------
# arquivos do planner (baixados do tibia.com por cada PC)
# ---------------------------------------------------------------------------
def _baixar(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
        return r.read()


def arquivos_planner(pasta=None, baixar=None):
    """{"ok": True, "arquivos": {nome: texto}} com os arquivos do planner (cache de 30 dias; sem internet usa o velho).
    {"ok": False, "erro": ...} se faltar algum e não der para baixar."""
    pasta = pasta or PASTA_CACHE
    baixar = baixar or _baixar
    arquivos, faltando = {}, []
    with _trava:
        os.makedirs(pasta, exist_ok=True)
        for nome, rel in ARQUIVOS.items():
            caminho = os.path.join(pasta, nome)
            existe = os.path.isfile(caminho)
            velho = not existe or time.time() - os.path.getmtime(caminho) > VALIDADE
            if velho:
                try:
                    dados = baixar(STATIC + rel)
                    if MARCADORES[nome].encode("utf-8") not in dados:
                        raise ValueError(f"{nome}: conteúdo inesperado")
                    tmp = caminho + ".tmp"
                    with open(tmp, "wb") as f:
                        f.write(dados)
                    os.replace(tmp, caminho)
                except Exception:
                    pass  # cai no arquivo velho, se houver
            if os.path.isfile(caminho):
                with open(caminho, "r", encoding="utf-8-sig") as f:
                    arquivos[nome] = f.read()
            else:
                faltando.append(nome)
    if faltando:
        return {"ok": False, "erro": "Não consegui baixar o planner da roda do tibia.com. Confira a internet e tente de novo."}
    return {"ok": True, "arquivos": arquivos}
