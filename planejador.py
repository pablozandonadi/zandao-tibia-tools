"""Planejamento de hunt: dados atuais da Tibia Wiki BR, sem frequência inventada."""
import json
import math
import os
import re
import time
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode, quote
import monstros
import creature_sources
from damage_core import ROTULO, parse_damage_input

API = 'https://www.tibiawiki.com.br/api.php'
CACHE = os.path.join(monstros.BASE_DIR, 'cache_planejador.json')
ELEMENTOS = [e for e in ROTULO if e != 'healing']
BASE_CONHECIMENTO = os.path.join(monstros.BASE_DIR, 'data', 'creature_knowledge.json')
_base_conhecimento = None

def _read():
    try:
        with open(CACHE, encoding='utf-8') as f: return json.load(f)
    except (OSError, ValueError): return {}

def _write(c):
    with monstros._trava:
        with open(CACHE, 'w', encoding='utf-8') as f: json.dump(c, f, ensure_ascii=False)

def catalogo(atualizar=False):
    c = _read()
    old = c.get('lista', {})
    if not atualizar and time.time()-old.get('t', 0) < 7*86400: return {'lista': old['dados'], 'aviso': ''}
    try:
        names = set()
        params = dict(action='query', list='embeddedin', eititle='Template:Infobox_Criatura', einamespace=0, eilimit=500, format='json')
        while True:
            r = monstros._get_json(API+'?'+urlencode(params))
            names.update(x['title'] for x in r.get('query', {}).get('embeddedin', []))
            if 'continue' not in r: break
            params.update(r['continue'])
        if not names: raise ValueError('Lista vazia')
        data = [{'name': n} for n in sorted(names)]
        c['lista'] = {'t': time.time(), 'dados': data}; _write(c)
        return {'lista': data, 'aviso': ''}
    except Exception:
        return {'lista': old.get('dados') or monstros.lista_criaturas(), 'aviso': 'Não foi possível atualizar a lista da Wiki; usando a lista disponível em cache/TibiaData.'}

def parse_wiki(text, name):
    fields = monstros._campos_infobox(text, 'Infobox_Criatura')
    attacks, warnings = [], []
    for el in ELEMENTOS:
        raw = fields.get('hab_'+el, '').strip()
        if not raw: continue
        clean = monstros._sem_links(re.sub(r'<br\s*/?>', ';', raw, flags=re.I))
        # Commas inside parentheses are not attack separators.
        for part in re.split(r';|,(?![^()]*\))|<br\s*/?>', clean):
            part = part.strip()
            if not part: continue
            match = re.search(r'\((\d[\d.,]*)\s*[-–]\s*(\d[\d.,]*)\)', part)
            if not match:
                warnings.append(f'{ROTULO[el]}: sem faixa numérica para {part}')
                continue
            lo, hi = [int(re.sub(r'[^\d]', '', v)) for v in match.groups()]
            if hi < lo:
                warnings.append(f'Faixa inválida: {part}'); continue
            attacks.append(dict(nome=part[:match.start()].strip() or ROTULO[el], elemento=el, min=lo, max=hi))
            if re.search(r'\b\d+\s*[x×]', part, re.I):
                warnings.append(f'Ataque múltiplo: {part}; máximo exibido por impacto, sem somar a sequência.')
        if re.search(r'turno|poison|envenena|causando', clean, re.I):
            warnings.append(f'{ROTULO[el]}: condições de dano contínuo não incluídas na média')
    if not attacks: warnings.append('Sem ataques com faixas conhecidas; esta criatura não tem estimativa de dano.')
    if fields.get('abilities', '').strip(): warnings.append('Habilidades em texto livre precisam de revisão; não inferimos o elemento pelo nome.')
    resist = {}
    for key, el in monstros.MOD_CHAVES.items():
        if el == 'healing': continue
        raw = fields.get(key, '')
        m = re.match(r'\s*(-?\d+)\s*%', raw)
        if m and '?' not in raw: resist[el] = int(m.group(1))
    out = dict(nome=fields.get('name') or name, ataques=attacks, avisos=warnings, resist=resist,
                fonte='https://www.tibiawiki.com.br/wiki/'+quote(name.replace(' ', '_'), safe=''), consultado=time.time())
    for key,target in [('hp','hp'),('exp','xp'),('defense','armor'),('mitigation','mitigation'),('speed','speed')]:
        raw = fields.get(key, '').strip()
        if re.fullmatch(r'\d+(?:\.\d+)?',raw): out[target] = float(raw) if '.' in raw else int(raw)
    return out

def _consultar_fonte(name, key):
    api = API if key == 'br' else monstros.WIKI
    r = monstros._get_json(api+'?'+urlencode(dict(action='parse', page=name, prop='wikitext|revid', format='json', redirects=1)))
    page = r['parse']; text = page['wikitext']['*']
    if key == 'br':
        if not monstros._campos_infobox(text, 'Infobox_Criatura'): raise ValueError('Sem ficha BR')
        out = parse_wiki(text, page['title'])
    else: out = creature_sources.parse_en(text, page['title'])
    out['revisao'] = page.get('revid')
    return out


def _base_ficha(name):
    global _base_conhecimento
    if _base_conhecimento is None:
        try:
            with open(BASE_CONHECIMENTO, encoding='utf-8') as f: _base_conhecimento = json.load(f).get('criaturas', {})
        except (OSError, ValueError): _base_conhecimento = {}
    return _base_conhecimento.get(name)


def ficha(name, atualizar=False):
    c = _read(); candidates = [f for f in [c.get('fichas', {}).get(name), _base_ficha(name)] if f]
    old = max(candidates, key=lambda f:(f.get('schema', 0), f.get('consultado', 0) or 0)) if candidates else None
    if old and old.get('schema') == creature_sources.SCHEMA and not atualizar and time.time()-old.get('consultado', 0) < old.get('validade', 7*86400): return old
    sources, errors = {}, []
    for key in ['br','en']:
        try: sources[key] = _consultar_fonte(name, key)
        except Exception:
            errors.append(('Tibia Wiki BR' if key == 'br' else 'TibiaWiki EN')+': consulta indisponível.')
            previous = (old or {}).get('dados_fontes', {}).get(key)
            if previous:
                sources[key] = previous
                errors.append(('Tibia Wiki BR' if key == 'br' else 'TibiaWiki EN')+': preservados os dados anteriores em cache.')
    if not sources and old: return dict(old, avisos=old.get('avisos',[])+errors+['Exibindo a ficha anterior em cache.'])
    out = creature_sources.merge(name, sources.get('br'), sources.get('en'), errors)
    if sources:
        with monstros._trava:
            c = _read(); c.setdefault('fichas', {})[name] = out
            with open(CACHE, 'w', encoding='utf-8') as f: json.dump(c, f, ensure_ascii=False)
    return out


def calcular(rows, dano=None):
    total = sum(r['peso'] for r in rows)
    values = {e: 0.0 for e in ELEMENTOS}
    peaks, creatures = [], []
    shares = {e: 0.0 for e in ELEMENTOS}
    for row in rows:
        f = row['ficha']; weight = row['peso']/total
        attacks = f.get('ataques', [])
        local = {e: 0.0 for e in ELEMENTOS}
        for a in attacks:
            # Index = sum of midpoints of listed attacks, once each. No inferred cast rate.
            midpoint = (a['min']+a['max'])/2
            values[a['elemento']] += weight*midpoint
            local[a['elemento']] += midpoint
            if a['max'] > 0:
                peaks.append(dict(criatura=f['nome'], ataque=a['nome'], elemento=a['elemento'], max=a['max'], participacao=weight*100))
        hp_sum = sum(v for e,v in local.items() if e != 'manadrain')
        if hp_sum:
            for e in ELEMENTOS:
                if e != 'manadrain': shares[e] += weight*local[e]/hp_sum
        creatures.append(dict(f, peso=row['peso'], participacao=weight*100))
    resistencias = []
    for el in ELEMENTOS:
        known = [c for c in creatures if el in c.get('resist', {})]
        covered = sum(c['participacao'] for c in known)
        if covered:
            modifier = sum(c['resist'][el]*c['participacao'] for c in known)/covered
            resistencias.append(dict(elemento=el, modificador=modifier, cobertura=covered))
    known_share = sum(shares.values())
    measured = (dano or {}).get('tipos') or {}
    real = any(e != 'manadrain' and v['valor'] > 0 for e,v in measured.items())
    hp_measured = sum(v['pct'] for e,v in measured.items() if e != 'manadrain')
    elements = []
    for e in ELEMENTOS:
        estimated_pct = shares[e]/known_share*100 if known_share and e != 'manadrain' else (None if e == 'manadrain' else 0)
        actual = measured.get(e, {})
        pct = ((actual.get('pct', 0)/hp_measured*100) if hp_measured and e != 'manadrain' else None) if real else estimated_pct
        elements.append(dict(elemento=e, rotulo=ROTULO[e], media=values[e], pct=pct,
                             estimativa_pct=estimated_pct, valor=actual.get('valor', 0)))
    elements.sort(key=lambda e: -(e['valor'] if real else e['media']))
    resistencias.sort(key=lambda e: -e['modificador'])
    return dict(criaturas=creatures, resistencias=resistencias, elementos=elements,
                picos=sorted(peaks,key=lambda a:a['max'],reverse=True),
                cobertura=sum(c['participacao'] for c in creatures if c['ataques']),
                real=real, origem='Received Damage' if real else 'Estimativa da Wiki',
                dano_total=(dano or {}).get('total'), avisos=[])


def analisar(selection, atualizar=False, dano_texto=""):
    if not isinstance(selection, list) or not selection or len(selection)>30: return {'erro':'Selecione de 1 a 30 criaturas.'}
    rows = []; seen = set()
    for r in selection:
        try:
            name = str(r['nome']).strip(); weight = float(r['peso'])
        except (KeyError, TypeError, ValueError): return {'erro':'Criatura ou quantidade inválida.'}
        if not name or len(name)>120 or name in seen or not math.isfinite(weight) or weight<=0 or weight>1000000: return {'erro':'Use criaturas diferentes e quantidades maiores que zero, até 1.000.000.'}
        seen.add(name); rows.append(dict(nome=name,peso=weight))
    with ThreadPoolExecutor(max_workers=4) as pool:
        fichas = list(pool.map(lambda r: ficha(r['nome'], atualizar), rows))
    dano = parse_damage_input(dano_texto) if dano_texto.strip() else None
    if dano_texto.strip() and not any(e != 'manadrain' and v['valor'] > 0 for e,v in (dano or {}).get('tipos', {}).items()):
        return {'erro': 'Não encontrei dano recebido por elemento. Cole o Input Analyser (Received Damage), com Damage Types, ou limpe essa caixa para usar a estimativa.'}
    return calcular([dict(r,ficha=f) for r,f in zip(rows,fichas)], dano)


def _slug(name):
    normalized = unicodedata.normalize('NFKD', name.lower()).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '_', normalized).strip('_')


def catalogo_visual(atualizar=False):
    result = catalogo(atualizar)
    resource_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    try:
        with open(os.path.join(resource_dir, 'web', 'assets', 'creatures.json'), encoding='utf-8') as f:
            images = json.load(f)
        images = {key:filename for key,filename in images.items()
                  if os.path.isfile(os.path.join(resource_dir, 'web', 'assets', 'creatures', filename))}
    except (OSError, ValueError): images = {}
    result['imagens'] = images
    result['lista'] = [c for c in result['lista'] if _slug(c['name']) in images]
    return result


def importar_texto(texto):
    from solo_hunt_core import parse_solo_session
    from loot_core import ParseError
    if not isinstance(texto, str) or len(texto) > 500000: return {'erro': 'Texto inválido ou muito grande.'}
    try:
        session = parse_solo_session(texto)
    except (ValueError, ParseError) as e: return {'erro': str(e)}
    if not session.killed_monsters:
        return {'erro': 'Não encontrei Killed Monsters. Cole o Hunting Analyser, com a lista de criaturas mortas.'}
    index = {monstros.singularizar(c['name']):c['name'] for c in catalogo_visual()['lista']}
    counts, unknown = {}, []
    for kill in session.killed_monsters:
        if kill.count <= 0: continue
        name = index.get(monstros.singularizar(kill.name))
        if not name:
            unknown.append(f'{kill.count}x {kill.name}'); continue
        counts[name] = counts.get(name, 0)+kill.count
    if not counts: return {'erro': 'Não encontrei abates de criaturas com GIF disponível. Confira os nomes ou escolha criaturas na busca.'}
    if len(counts) > 30: return {'erro': 'Este log tem mais de 30 criaturas diferentes. Reduza a lista para analisar todas as selecionadas.'}
    return {'selecao': [{'nome':n, 'peso':v} for n,v in sorted(counts.items(), key=lambda x:x[1], reverse=True)],
            'total':sum(counts.values()), 'avisos':(['Criaturas sem GIF disponível foram removidas da composição: '+', '.join(unknown)] if unknown else [])}
