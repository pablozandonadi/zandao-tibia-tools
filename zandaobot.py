"""Painel diário independente do Discord. Nenhum dado premium do NabBot é usado."""
import copy
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import quote

import tibia_info
import zandaobot_sources as sources

_lock = threading.Lock()
_cache = {}


def _consultar(chave, endpoint, forcar=False, ttl=300):
    with _lock:
        anterior = copy.deepcopy(_cache.get(chave))
    if anterior and not forcar and time.time() - anterior['consulta'] < ttl:
        return {**anterior, 'velho': False}
    try:
        dados = tibia_info._get_json(tibia_info.TIBIADATA + endpoint)
        novo = {'dados': dados, 'consulta': time.time(), 'velho': False}
        with _lock:
            _cache[chave] = copy.deepcopy(novo)
        return novo
    except Exception:
        if anterior:
            return {**anterior, 'velho': True}
        return {'dados': {}, 'consulta': None, 'velho': True}


def mundos(forcar=False):
    r = _consultar('mundos', '/worlds', forcar, 3600)
    lista = r['dados'].get('worlds', {}).get('regular_worlds', [])
    return {'mundos': sorted(x['name'] for x in lista if x.get('name')), 'velho': r['velho']}


def buscar(mundo='', forcar=False):
    mundo = (mundo or '').strip()
    if mundo and not re.fullmatch(r'[A-Za-z]{2,40}', mundo):
        return {'erro': 'Informe um nome de mundo válido, como Antica ou Rasteibra.'}
    with ThreadPoolExecutor(max_workers=7) as pool:
        boosted = pool.submit(tibia_info.boostados, bool(forcar))
        noticias = pool.submit(_consultar, 'noticias', '/news/latest', bool(forcar), 900)
        servidor = pool.submit(_consultar, 'mundo:' + mundo.lower(), '/world/' + quote(mundo), bool(forcar)) if mundo else None
        changes = pool.submit(sources.mini_changes, mundo, bool(forcar))
        dream = pool.submit(sources.dream_court, mundo, bool(forcar))
        schedule = pool.submit(sources.calendar, mundo, bool(forcar))
        tickers = pool.submit(_consultar, 'tickers', '/news/newsticker', bool(forcar), 300)
        b, n = boosted.result(), noticias.result()
        w = servidor.result() if servidor else {'dados': {}, 'consulta': None, 'velho': False}
    info = w['dados'].get('world', {})
    if mundo and not info.get('name') and not w['velho']:
        return {'erro': 'Mundo não encontrado. Confira o nome ou escolha uma sugestão.'}
    # world_quest_titles é histórico de conquistas, não eventos ativos.
    mundo_info = {k: info.get(k) for k in ('name', 'status', 'players_online', 'location', 'pvp_type', 'battleye_protected')}
    ticker = tickers.result()
    avisos_mundo = [x for x in ticker['dados'].get('news', []) if mundo and re.search(r'\b' + re.escape(mundo) + r'\b', x.get('news', ''), re.I)]
    avisos = [x for x in n['dados'].get('news', []) if x.get('category') == 'community'][:8]
    return {
        **tibia_info.resumo_do_dia(), 'boostados': b,
        'mundo': info.get('name') or mundo, 'servidor': mundo_info,
        'servidor_velho': w['velho'], 'servidor_consulta': w['consulta'],
        'anuncios': [{'titulo': x.get('news', ''), 'data': x.get('date', ''), 'id': x.get('id')} for x in avisos],
        'anuncios_velhos': n['velho'], 'anuncios_consulta': n['consulta'],
        'avisos_mundo': [{'texto': x.get('news', ''), 'data': x.get('date', '')} for x in avisos_mundo[:6]],
        'avisos_mundo_velhos': ticker['velho'],
        'dream_court': dream.result(), 'yasir': changes.result(), 'calendario': schedule.result(),
        'consulta': datetime.now(timezone.utc).isoformat(),
    }
