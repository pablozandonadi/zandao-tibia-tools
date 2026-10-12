"""Fontes públicas do ZandaoBot: TibiaTrade, TibiaWiki e TibiaCalendar.

Só JSON/texto é interpretado. Nenhum script remoto, token ou HTML entra na interface.
"""
import copy
import json
import re
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit

import tibia_info

TRADE = 'https://tibiatrade.gg'
WIKI = 'https://tibia.fandom.com/api.php'
CALENDAR = 'https://tibiacalendar.com/en/calendar'
DREAM_SOURCE = 'https://tibia.fandom.com/wiki/Dream_Scar/Boss_of_the_Day'
BOSSES = ('Maxxenius', 'Alptramun', 'Izcandar the Banished', 'Plagueroot', 'Malofur Mangrinder')
_cache = {}
_lock = threading.Lock()


def get_text(url, limit=2000000):
    req = urllib.request.Request(url, headers=tibia_info.HEADERS)
    with urllib.request.urlopen(req, timeout=12) as response:
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Resposta maior que o esperado')
    return raw.decode('utf-8')


def get_json(url):
    return json.loads(get_text(url))


def cached(key, fetch, force=False, ttl=300, daily=True):
    today = tibia_info.dia_tibia().isoformat()
    with _lock:
        previous = copy.deepcopy(_cache.get(key))
    if previous and not force and time.time() - previous['consulta'] < ttl and (not daily or previous['dia'] == today):
        return {**previous, 'velho': False}
    try:
        data = fetch()
        # Não atribuir uma consulta iniciada ontem ao novo dia do Tibia.
        if daily and today != tibia_info.dia_tibia().isoformat():
            raise ValueError('Server save durante a consulta')
        result = {'dados': data, 'consulta': time.time(), 'dia': today, 'velho': False}
        with _lock:
            _cache[key] = copy.deepcopy(result)
        return result
    except Exception:
        return {**previous, 'velho': True} if previous else {'dados': None, 'consulta': None, 'dia': today, 'velho': True}


def trade(method, parameters=None):
    suffix = '?' + urlencode({'input': json.dumps(parameters, separators=(',', ':'))}) if parameters is not None else ''
    value = get_json(TRADE + '/trpc/' + method + suffix)
    data = value.get('result', {}).get('data')
    if not isinstance(data, dict):
        raise ValueError('Resposta TibiaTrade inválida')
    return data


def _trade_worlds():
    worlds = trade('world.list').get('worlds')
    if not isinstance(worlds, list) or not worlds or any(not isinstance(w, dict) or not isinstance(w.get('name'), str) or not isinstance(w.get('id'), int) for w in worlds):
        raise ValueError('Lista de mundos inválida')
    return {w['name'].lower(): w['id'] for w in worlds}


def mini_changes(world, force=False):
    source = TRADE + '/mini-world-changes'
    unavailable = {'estado': 'indisponivel', 'motivo': 'Não foi possível consultar as Mini World Changes deste mundo.', 'fonte': source, 'consulta': None, 'mudancas': []}
    if not world:
        return {**unavailable, 'motivo': 'Selecione um mundo para consultar Yasir.'}
    worlds = cached('trade-worlds', _trade_worlds, force, 3600, daily=False)
    world_id = (worlds['dados'] or {}).get(world.lower())
    if world_id is None or worlds['velho']:
        return unavailable
    def fetch():
        changes = trade('miniWorldChange.listActive', {'world_id': world_id}).get('active_mini_world_changes')
        if not isinstance(changes, list) or any(not isinstance(c, dict) or not isinstance(c.get('mini_world_change_name'), str) for c in changes):
            raise ValueError('Mini World Changes inválidas')
        return sorted({c['mini_world_change_name'] for c in changes})
    r = cached('changes:' + world.lower(), fetch, force)
    if r['dados'] is None:
        return unavailable
    present = 'Oriental Trader' in r['dados']
    return {'estado': 'desatualizado' if r['velho'] else ('presente' if present else 'ausente'),
            'presente': present, 'dia': r['dia'], 'consulta': r['consulta'], 'fonte': source,
            'mudancas': r['dados'], 'cidade': None,
            'motivo': 'Cidade não informada pela fonte. Verifique Carlin, Ankrahmun ou Liberty Bay.' if present else 'Oriental Trader não aparece na lista de mudanças ativas consultada.',
            'velho': r['velho'], 'atualizacao_fonte': None}


def parse_dream_rules(data):
    pages = data.get('query', {}).get('pages', {})
    texts, updated = {}, None
    for page in pages.values():
        revision = page.get('revisions', [{}])[0]
        texts[page.get('title')] = revision.get('slots', {}).get('main', {}).get('*', '')
        if page.get('title') == 'Template:Dream Scar Boss/Offsets':
            updated = revision.get('timestamp')
    offsets = texts.get('Template:Dream Scar Boss/Offsets', '')
    formula = texts.get('Template:Dream Scar Boss', '')
    # A expressão inteira é validada; nunca avaliamos wikitext remoto como código.
    expected = '{{#if:{{{1}}}|{{#switch:{{#expr:ceil(({{#time:U|now+{{#expr:3600*{{RashidLocation/DST}}}}seconds-10hours}}/60/60/24)+{{{1|}}})mod5}}|' + '|'.join(f'{i}={name.replace(" ", "")}' for i,name in enumerate(BOSSES)) + '|}}|Unknown}}'
    normalized = ''.join(re.sub(r'<!--.*?-->', '', formula, flags=re.S).split())
    if normalized != expected:
        raise ValueError('Fórmula da Dream Court mudou')
    normalized_offsets = ''.join(re.sub(r'<!--.*?-->', '', offsets, flags=re.S).split())
    match = re.fullmatch(r'\{\{#expr:(-?\d+)\+\{\{#switch:\{\{\{1\}\}\}((?:\|[A-Za-z]+=-?\d+)*)\|0\}\}\}\}', normalized_offsets)
    if not match:
        raise ValueError('Fórmula dos offsets mudou')
    worlds = {}
    for name, value, comment in re.findall(r'\|([A-Za-z]+)\s*=\s*(-?\d+)([^\n]*)', offsets):
        worlds[name.lower()] = {'offset': int(value), 'incerto': 'Uncertain' in comment}
    if not worlds or not updated:
        raise ValueError('Regras incompletas')
    return {'global': int(match.group(1)), 'mundos': worlds, 'atualizado': updated}


def dream_rules():
    params = {'action': 'query', 'prop': 'revisions', 'titles': 'Template:Dream Scar Boss/Offsets|Template:Dream Scar Boss',
              'rvprop': 'timestamp|content', 'rvslots': 'main', 'format': 'json'}
    return parse_dream_rules(get_json(WIKI + '?' + urlencode(params)))


def dream_court(world, force=False):
    r = cached('dream-rules', dream_rules, force, 3600, daily=False)
    rule = ((r['dados'] or {}).get('mundos') or {}).get(world.lower())
    if not rule:
        return {'estado': 'indisponivel', 'motivo': 'A TibiaWiki não tem uma rotação disponível para este mundo.', 'fonte': DREAM_SOURCE, 'consulta': r['consulta']}
    day = tibia_info.dia_tibia()
    # ceil da fórmula Wiki equivale ao dia do Tibia desde epoch + 1.
    cycle = (day - date(1970, 1, 1)).days + 1 + r['dados']['global'] + rule['offset']
    return {'estado': 'desatualizado' if r['velho'] else 'previsto', 'nome': BOSSES[cycle % 5],
            'dia': day.isoformat(), 'consulta': r['consulta'], 'fonte': DREAM_SOURCE,
            'atualizacao_fonte': r['dados']['atualizado'], 'incerto': rule['incerto'],
            'motivo': ('A própria TibiaWiki marca a rotação deste mundo como incerta. ' if rule['incerto'] else '') +
                      'Previsão pela rotação deste mundo na TibiaWiki. Um server save extra pode mudar o boss.', 'velho': r['velho']}


def calendar_bundle():
    html = get_text(CALENDAR)
    match = re.search(r'window\.__BUNDLE_META__\s*=\s*(\{[^<]+?\})\s*;', html)
    if not match:
        raise ValueError('Metadados do calendário indisponíveis')
    meta = json.loads(match.group(1))
    url = meta.get('hotUrl')
    parts = urlsplit(url or '')
    if parts.scheme != 'https' or parts.hostname != 'cdn.tibiacalendar.com' or not parts.path.endswith('.json'):
        raise ValueError('URL do calendário não reconhecida')
    data = get_json(url)
    if not isinstance(data.get('events'), list) or not isinstance(data.get('generatedAt'), (int, float)):
        raise ValueError('Calendário inválido')
    # O bundle base é estático; o delta contém correções e eventos publicados depois dele.
    parameters = {'json': {'sinceUpdatedAt': meta['maxUpdatedAt'], 'afterStartDate': meta['maxStartDate']}}
    delta_url = 'https://tibiacalendar.com/api/trpc/events.listDelta?' + urlencode({'input': json.dumps(parameters, separators=(',', ':'))})
    delta = get_json(delta_url).get('result', {}).get('data', {}).get('json')
    if not isinstance(delta, list) or any(not isinstance(e, dict) or not e.get('id') for e in delta):
        raise ValueError('Delta do calendário indisponível')
    merged = {e['id']: e for e in data['events'] if isinstance(e, dict) and e.get('id')}
    for event in delta:
        merged[event['id']] = event
    return {**data, 'events': list(merged.values()), 'delta_consulta': datetime.now(timezone.utc).isoformat()}


def calendar_date(value):
    if not isinstance(value, str):
        raise ValueError('Data inválida')
    if 'T' in value:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return date.fromisoformat(value[:10])
    return date.fromisoformat(value)


def parse_calendar(data, world='', today=None):
    today = today or tibia_info.dia_tibia()
    end_limit = today + timedelta(days=60)
    events, seen = [], set()
    for e in data['events']:
        if not isinstance(e, dict) or e.get('type') != 'scheduled' or e.get('calendarId') != 'scheduled_events':
            continue
        start, end = calendar_date(e['startDate']), calendar_date(e['endDate'])
        if end < start:
            raise ValueError('Evento com intervalo inválido')
        # Eventos de server save encerram no SS da data final (limite exclusivo).
        save = e.get('serverSaveEvent') is True
        if (end <= today if save else end < today) or start > end_limit:
            continue
        scoped = e.get('worldId') is not None or bool(e.get('worldScopeLabel'))
        scoped_world = str(e.get('worldId') or e.get('worldScopeLabel') or '')
        if scoped and (not world or scoped_world.casefold() != world.casefold()):
            continue
        key = (e.get('title'), start, end, e.get('worldId'))
        if key in seen:
            continue
        seen.add(key)
        events.append({'titulo': e['title'], 'inicio': start.isoformat(), 'fim': end.isoformat(),
                       'estado': 'ativo' if start <= today else 'proximo', 'server_save': save,
                       'escopo': world if scoped else 'Todos os mundos', 'fonte': CALENDAR})
    events.sort(key=lambda e: (e['inicio'], e['titulo']))
    return events


def calendar(world='', force=False):
    r = cached('calendar', calendar_bundle, force, 3600, daily=False)
    if r['dados'] is None:
        return {'estado': 'indisponivel', 'eventos': [], 'consulta': None, 'fonte': CALENDAR}
    try:
        events = parse_calendar(r['dados'], world)
    except (KeyError, ValueError, TypeError):
        return {'estado': 'indisponivel', 'eventos': [], 'consulta': r['consulta'], 'fonte': CALENDAR}
    generated = datetime.fromtimestamp(r['dados']['generatedAt'] / 1000, timezone.utc)
    return {'estado': 'desatualizado' if r['velho'] else 'disponivel', 'eventos': events, 'consulta': r['consulta'],
            'atualizacao_fonte': r['dados'].get('delta_consulta') or generated.isoformat(), 'snapshot': generated.isoformat(), 'fonte': CALENDAR, 'velho': r['velho'],
            'nota': 'Calendário TibiaCalendar com correções consultadas online. Compensações exclusivas anunciadas em notícias podem não constar aqui. O fim ocorre no server save da data indicada.'}
