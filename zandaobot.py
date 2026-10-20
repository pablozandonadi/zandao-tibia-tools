"""Painel diário independente do Discord. Nenhum dado premium do NabBot é usado."""
import copy
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import tibia_info
import zandaobot_sources as sources

_lock = threading.Lock()
_cache = {}


def _consultar(chave, endpoint, forcar=False, ttl=300, validar=None):
    with _lock:
        anterior = copy.deepcopy(_cache.get(chave))
    if anterior and not forcar and time.time() - anterior['consulta'] < ttl:
        return {**anterior, 'velho': False}
    try:
        dados = tibia_info._get_json(tibia_info.TIBIADATA + endpoint)
        if validar:
            dados = validar(dados)
        novo = {'dados': dados, 'consulta': time.time(), 'velho': False}
        with _lock:
            _cache[chave] = copy.deepcopy(novo)
        return novo
    except Exception:
        if anterior:
            return {**anterior, 'velho': True}
        return {'dados': {}, 'consulta': None, 'velho': True}


def killstatistics(mundo, forcar=False):
    mundo = (mundo or '').strip()
    base = {'mundo': mundo, 'bosses': [], 'consulta': None, 'processamento': None, 'velho': False,
            'fonte': 'https://www.tibia.com/community/?subtopic=killstatistics&world=' + quote(mundo)}
    if not mundo:
        return {**base, 'estado': 'selecionar_mundo'}
    if not re.fullmatch(r'[A-Za-z]{2,40}', mundo):
        return {**base, 'estado': 'indisponivel'}

    def validar(data):
        stats = data['killstatistics']
        information = data['information']
        if information['status']['http_code'] != 200 or stats['world'].casefold() != mundo.casefold() or not isinstance(stats['entries'], list):
            raise ValueError('Resposta de Kill Statistics inválida')
        bosses = []
        for name in sources.BOSSES:
            matches = [e for e in stats['entries'] if isinstance(e, dict) and str(e.get('race', '')).casefold() == name.casefold()]
            entry = matches[0] if len(matches) == 1 else {}
            counts = {key: entry.get(key) if type(entry.get(key)) is int and entry[key] >= 0 else None
                      for key in ('last_day_killed', 'last_week_killed')}
            bosses.append({'nome': name, **counts})
        if not any(e['last_day_killed'] is not None or e['last_week_killed'] is not None for e in bosses):
            raise ValueError('Contagens indisponíveis')
        timestamp = information.get('timestamp')
        try:
            parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            timestamp = parsed.isoformat() if parsed.tzinfo else None
        except (ValueError, TypeError, AttributeError):
            timestamp = None
        return {'bosses': bosses, 'processamento': timestamp}

    result = _consultar('killstatistics:' + mundo.casefold(), '/killstatistics/' + quote(mundo), bool(forcar), validar=validar)
    return {**base, **result['dados'], 'consulta': result['consulta'], 'velho': result['velho'],
            'estado': 'desatualizado' if result['dados'] and result['velho'] else 'disponivel' if result['dados'] else 'indisponivel'}


def mundos(forcar=False):
    r = _consultar('mundos', '/worlds', forcar, 3600)
    lista = r['dados'].get('worlds', {}).get('regular_worlds', [])
    return {'mundos': sorted(x['name'] for x in lista if x.get('name')), 'velho': r['velho']}



def _avisos_completos(avisos, forcar=False):
    def complete(item):
        news_id = item.get('id')
        if not isinstance(news_id, int):
            return None
        detail = _consultar('news:' + str(news_id), '/news/id/' + str(news_id), forcar, 3600)
        content = detail['dados'].get('news', {}).get('content')
        return {'texto': ' '.join((content or item.get('news', '')).split()), 'data': item.get('date', ''),
                'id': news_id, 'velho': detail['velho'], 'completo': bool(content), 'consulta': detail['consulta']}
    with ThreadPoolExecutor(max_workers=4) as pool:
        return [item for item in pool.map(complete, avisos[:6]) if item]


def eventos_compensacao(avisos, mundo, hoje=None):
    """Só extrai o formato explícito do anúncio oficial; outros avisos ficam em texto."""
    hoje = hoje or tibia_info.dia_tibia()
    months = {name.lower(): i for i,name in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}
    events = []
    for item in avisos:
        text = item.get('texto', '')
        if item.get('velho') or not item.get('completo') or not mundo or not re.search(r'\b' + re.escape(mundo) + r'\b', text, re.I):
            continue
        if not re.search(r'As compensation .*?double XP/skill .*?on the game world between the server saves of', text, re.I):
            continue
        match = re.search(r'between the server saves of ([A-Za-z]+) (\d{1,2}) and (?:\1 )?(\d{1,2}), (\d{4})', text, re.I)
        if not match or match.group(1).lower() not in months:
            continue
        try:
            month, year = months[match.group(1).lower()], int(match.group(4))
            start, end = date(year, month, int(match.group(2))), date(year, month, int(match.group(3)))
        except ValueError:
            continue
        if not start < end or end <= hoje or start > hoje + timedelta(days=60):
            continue
        events.append({'titulo': 'Double XP/skill · compensação', 'inicio': start.isoformat(), 'fim': end.isoformat(),
                       'estado': 'ativo' if start <= hoje else 'proximo', 'server_save': True, 'escopo': mundo,
                       'fonte': 'https://www.tibia.com/news/?subtopic=newsarchive&id=' + str(item['id'])})
    return events

def _imagem_noticia(item_id, forcar=False):
    """Primeira imagem do anúncio (só static.tibia.com/images/news), ou None. A imagem não muda: cache de 6 h."""
    if type(item_id) is not int:
        return None
    r = _consultar(f'noticia:{item_id}', f'/news/id/{item_id}', forcar, 21600)
    dados = r['dados'] if isinstance(r['dados'], dict) else {}
    noticia = dados.get('news') if isinstance(dados.get('news'), dict) else {}
    html = noticia.get('content_html') if isinstance(noticia.get('content_html'), str) else ''
    achou = re.search(r'<img[^>]+src="(https://static\.tibia\.com/images/news/[A-Za-z0-9_./-]+\.(?:png|jpe?g|gif))"', html)
    return achou.group(1) if achou else None


def _lista_noticias(dados, tipo):
    artigos, vistos = [], set()
    lista = dados.get('news', []) if isinstance(dados, dict) else []
    if not isinstance(lista, list):
        return artigos
    for item in sorted((x for x in lista if isinstance(x, dict)),
                       key=lambda x: (str(x.get('date', '')), x.get('id') if type(x.get('id')) is int else -1), reverse=True):
        item_id = item.get('id')
        if (type(item_id) is not int or item_id <= 0 or item_id in vistos
                or item.get('type', tipo) != tipo or not isinstance(item.get('category'), str)
                or not item['category'].strip() or not isinstance(item.get('news'), str) or not item['news'].strip()):
            continue
        vistos.add(item_id)
        artigos.append(item)
    return artigos


def buscar(mundo='', forcar=False):
    mundo = (mundo or '').strip()
    if mundo and not re.fullmatch(r'[A-Za-z]{2,40}', mundo):
        return {'erro': 'Informe um nome de mundo válido, como Antica ou Rasteibra.'}
    with ThreadPoolExecutor(max_workers=8) as pool:
        kills = pool.submit(killstatistics, mundo, bool(forcar))
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
    avisos_mundo = _avisos_completos(avisos_mundo, bool(forcar))
    calendario = schedule.result()
    calendario['eventos'] = sorted(calendario.get('eventos', []) + eventos_compensacao(avisos_mundo, mundo), key=lambda e: (e['inicio'], e['titulo']))
    artigos = _lista_noticias(n['dados'], 'news')
    avisos = [x for x in artigos if x['category'] == 'community'][:8]
    noticias_gerais = [x for x in artigos if x['category'] != 'community'][:8]
    selecionados = avisos + noticias_gerais
    with ThreadPoolExecutor(max_workers=8) as pool:
        imagens = list(pool.map(lambda x: _imagem_noticia(x['id'], bool(forcar)), selecionados))
    cards = [{'titulo': x['news'].strip(), 'data': x.get('date', ''), 'id': x['id'],
              'categoria': x['category'], 'imagem': img} for x, img in zip(selecionados, imagens)]
    ids_artigos = {x['id'] for x in artigos}
    tickers_gerais = [x for x in _lista_noticias(ticker['dados'], 'ticker') if x['id'] not in ids_artigos][:10]
    return {
        **tibia_info.resumo_do_dia(), 'boostados': b,
        'mundo': info.get('name') or mundo, 'servidor': mundo_info,
        'servidor_velho': w['velho'], 'servidor_consulta': w['consulta'],
        'anuncios': cards[:len(avisos)], 'noticias': cards[len(avisos):],
        'anuncios_velhos': n['velho'], 'anuncios_consulta': n['consulta'],
        'noticias_velhas': n['velho'], 'noticias_consulta': n['consulta'],
        'news_ticker': [{'texto': x['news'].strip()[:400], 'data': x.get('date', ''), 'id': x['id']}
                        for x in tickers_gerais],
        'news_ticker_velho': ticker['velho'], 'news_ticker_consulta': ticker['consulta'],
        'avisos_mundo': avisos_mundo,
        'avisos_mundo_velhos': ticker['velho'] or any(x['velho'] or not x['completo'] for x in avisos_mundo),
        'killstatistics': kills.result(), 'dream_court': dream.result(), 'yasir': changes.result(), 'calendario': calendario,
        'consulta': datetime.now(timezone.utc).isoformat(),
    }
