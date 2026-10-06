"""Informações do dia no Tibia: boss e criatura boostados, Rashid, server save, shared XP e XP por level.

- Boss/criatura boostados vêm do TibiaData (api.tibiadata.com), guardados em cache_tibia.json até o
  próximo server save (mudam só nele).
- Server save: todo dia às 10:00 no horário de Berlim (CET/CEST, com o horário de verão europeu).
- Rashid: cada dia da semana numa cidade; o "dia" do Tibia vira no server save.
- Shared XP: o maior level da party pode ser no máximo 3/2 do menor (ou seja, o menor precisa ter pelo
  menos 2/3 do maior). Além disso, todos precisam estar ativos (atacando/curando) e perto do líder.
- XP total para chegar ao level L: (50/3) * (L³ - 6L² + 17L - 12).
"""

import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CACHE_PATH = os.path.join(BASE_DIR, "cache_tibia.json")
TIBIADATA = "https://api.tibiadata.com/v4"
HEADERS = {"User-Agent": "ZandaoTibiaTools/1.0 (+desktop app)"}

# dia da semana (segunda = 0) -> cidade do Rashid
RASHID = ["Svargrond", "Liberty Bay", "Port Hope", "Ankrahmun", "Darashia", "Edron", "Carlin"]


# ---------------------------------------------------------------------------
# Server save e Rashid
# ---------------------------------------------------------------------------
def _ultimo_domingo(ano, mes):
    d = (datetime(ano, mes + 1, 1) - timedelta(days=1)) if mes < 12 else datetime(ano, 12, 31)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _horario_verao_europa(agora_utc):
    """CEST vale do último domingo de março, 01:00 UTC, ao último domingo de outubro, 01:00 UTC."""
    a = agora_utc.year
    ini = _ultimo_domingo(a, 3).replace(hour=1, tzinfo=timezone.utc)
    fim = _ultimo_domingo(a, 10).replace(hour=1, tzinfo=timezone.utc)
    return ini <= agora_utc < fim


def _offset_berlim(agora_utc):
    return timedelta(hours=2 if _horario_verao_europa(agora_utc) else 1)


def proximo_server_save(agora_utc=None):
    """Próximo server save (10:00 em Berlim) como datetime UTC."""
    agora_utc = agora_utc or datetime.now(timezone.utc)
    for dias in range(0, 3):
        d = (agora_utc + timedelta(days=dias)).date()
        meio_dia = datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc)
        ss = datetime(d.year, d.month, d.day, 10, tzinfo=timezone.utc) - _offset_berlim(meio_dia)
        if ss > agora_utc:
            return ss
    raise RuntimeError("server save não encontrado")


def dia_tibia(agora_utc=None):
    """Data do 'dia' do Tibia: começa no server save (antes das 10:00 de Berlim ainda é o dia anterior)."""
    agora_utc = agora_utc or datetime.now(timezone.utc)
    return (proximo_server_save(agora_utc) - timedelta(days=1)).date()


def rashid(agora_utc=None):
    return RASHID[dia_tibia(agora_utc).weekday()]


# ---------------------------------------------------------------------------
# Boss e criatura boostados (TibiaData, cache até o próximo server save)
# ---------------------------------------------------------------------------
_trava = threading.Lock()


def _get_json(url, timeout=12):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=timeout) as r:
        return json.load(r)


def boostados(forcar=False):
    """{'dia', 'boss': {nome, imagem}, 'criatura': {nome, imagem}, 'velho': bool}. Nunca levanta exceção."""
    hoje = dia_tibia().isoformat()
    with _trava:
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except (OSError, json.JSONDecodeError):
            cache = {}
    if not forcar and cache.get("dia") == hoje and cache.get("boss") and cache.get("criatura"):
        return {**cache, "velho": False}
    try:
        b = _get_json(f"{TIBIADATA}/boostablebosses")["boostable_bosses"]["boosted"]
        c = _get_json(f"{TIBIADATA}/creatures")["creatures"]["boosted"]
        novo = {"dia": hoje, "boss": {"nome": b["name"], "imagem": b.get("image_url")},
                "criatura": {"nome": c["name"], "imagem": c.get("image_url")}}
        with _trava:
            try:
                with open(CACHE_PATH, "w", encoding="utf-8") as f:
                    json.dump(novo, f, ensure_ascii=False)
            except OSError:
                pass
        return {**novo, "velho": False}
    except Exception:
        if cache.get("boss"):
            return {**cache, "velho": True}  # sem internet: mostra o último conhecido, avisando
        return {"dia": hoje, "boss": None, "criatura": None, "velho": True}


def resumo_do_dia(agora_utc=None):
    agora_utc = agora_utc or datetime.now(timezone.utc)
    return {"rashid": rashid(agora_utc), "server_save_ms": int(proximo_server_save(agora_utc).timestamp() * 1000),
            "dia": dia_tibia(agora_utc).isoformat()}


# ---------------------------------------------------------------------------
# Shared XP
# ---------------------------------------------------------------------------
def faixa_shared(level):
    """Levels com quem 'level' pode dividir XP: de ceil(2/3 * level) a floor(3/2 * level)."""
    level = int(level)
    return -(-2 * level // 3), (3 * level) // 2


def verificar_shared(levels):
    """levels: {nome: level}. O shared funciona se o maior for no máximo 3/2 do menor."""
    validos = {n: int(l) for n, l in levels.items() if l}
    if len(validos) < 2:
        return {"ok": None, "motivo": "Informe pelo menos 2 levels."}
    menor_n = min(validos, key=validos.get)
    maior_n = max(validos, key=validos.get)
    menor, maior = validos[menor_n], validos[maior_n]
    ok = 2 * maior <= 3 * menor
    teto = (3 * menor) // 2           # maior level permitido com esse menor
    piso = -(-2 * maior // 3)         # menor level permitido com esse maior
    if ok:
        motivo = f"Shared ativo: o maior ({maior}) está dentro de 3/2 do menor ({menor}), que vai até {teto}."
    else:
        motivo = (f"Shared NÃO funciona: {maior_n} ({maior}) passa de 3/2 de {menor_n} ({menor}), que vai até {teto}. "
                  f"Com {maior_n} na party, todos precisam ter level {piso} ou mais.")
    return {"ok": ok, "menor": [menor_n, menor], "maior": [maior_n, maior], "teto": teto, "piso": piso,
            "abaixo": sorted([n for n, l in validos.items() if l < piso], key=lambda n: validos[n]),
            "motivo": motivo}


_cache_chars = {}


def personagem(nome):
    """Level/vocação/mundo de agora (TibiaData), com cache de 10 minutos. None se não achar."""
    chave = nome.strip().lower()
    hit = _cache_chars.get(chave)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    try:
        c = _get_json(f"{TIBIADATA}/character/{urllib.parse.quote(nome.strip())}")["character"]["character"]
        info = {"nome": c["name"], "level": c["level"], "vocacao": c.get("vocation"), "mundo": c.get("world")}
    except Exception:
        info = None
    _cache_chars[chave] = (time.time(), info)
    return info


def personagens(nomes):
    with ThreadPoolExecutor(max_workers=6) as ex:
        return dict(zip(nomes, ex.map(personagem, nomes)))


# ---------------------------------------------------------------------------
# XP por level ("quando eu upo?")
# ---------------------------------------------------------------------------
def xp_total(level):
    """XP total para chegar ao level (fórmula oficial)."""
    level = int(level)
    return (50 * (level ** 3 - 6 * level ** 2 + 17 * level - 12)) // 3


def level_da_xp(xp):
    """Level de quem tem essa XP total (a 'Experience' da janela Skills do Tibia)."""
    xp = int(xp)
    lo, hi = 1, 3000
    while lo < hi:
        meio = (lo + hi + 1) // 2
        if xp_total(meio) <= xp:
            lo = meio
        else:
            hi = meio - 1
    return lo
