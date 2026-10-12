"""Classificação local do loot do Hunting Analyser; catálogo público de 12/10/2026."""
import json
import os
import re
import sys
from collections import Counter

BASE = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))

def normalize(name):
    return re.sub(r'^(?:an?|some)\s+', '', name.strip().lower())

def variants(name):
    n = normalize(name)
    result = {n, n + 's'}
    if n.endswith('y'):
        result.add(n[:-1] + 'ies')
    if n.endswith(('s', 'ch', 'sh', 'x')):
        result.add(n + 'es')
    if n.endswith('f'):
        result.add(n[:-1] + 'ves')
    for singular, plural in [('tooth', 'teeth'), ('foot', 'feet'), ('man', 'men')]:
        if n.endswith(singular):
            result.add(n[:-len(singular)] + plural)
    if n.endswith('s'):
        result.add(n[:-1])
    return result

def analyse(text, people=1):
    try:
        if float(people) != int(float(people)):
            raise ValueError()
        people = int(float(people))
    except (TypeError, ValueError, OverflowError):
        return {'erro': 'Informe um número inteiro de pessoas.'}
    if people < 1 or people > 1000:
        return {'erro': 'Divida entre 1 e 1000 pessoas.'}
    if not isinstance(text, str) or not text.strip():
        return {'erro': 'Cole o Hunting Analyser ou a lista de itens.'}
    if len(text) > 1000000:
        return {'erro': 'O texto excede o limite de 1 milhão de caracteres.'}
    with open(os.path.join(BASE, 'data', 'task_items.json'), encoding='utf-8') as f:
        catalog = json.load(f)
    with open(os.path.join(BASE, 'data', 'imbuements.json'), encoding='utf-8') as f:
        imbs = json.load(f)
    lookup = {}
    for item in catalog:
        for key in variants(item['name']):
            lookup.setdefault(key, item)
        lookup[normalize(item['name'])] = item
    imb_lookup = {}
    for imb in imbs:
        for item in imb['items']:
            entry = lookup.get(normalize(item['name']), {'name': item['name']})
            for alias in [item['name']] + item.get('aliases', []):
                for key in variants(alias):
                    lookup.setdefault(key, entry)
                    imb_lookup.setdefault(key, set()).add(imb['name'])
    lines = text.splitlines()
    has_header = any(re.match(r'^\s*Looted Items\b', line, re.I) for line in lines)
    active = not has_header and not any(re.match(r"^\s*(?:Killed Monsters|Session Data|Session:)\b", line, re.I) for line in lines)
    counts = Counter()
    for line in lines:
        line = line.strip()
        if re.match(r'^Looted Items\b', line, re.I):
            active = True
            continue
        if re.match(r'^Killed Monsters\b', line, re.I) or (line.endswith(':') and not re.match(r'^Looted Items', line, re.I)):
            active = False if has_header else active
        match = re.fullmatch(r'([\d][\d,. ]*)\s*[x×]\s+(.+)', line, re.I)
        if not active or not match:
            continue
        qty = int(re.sub(r'\D', '', match[1]))
        if qty > 0:
            counts[normalize(match[2])] += qty
    groups = {'tasks': [], 'imbuements': [], 'other': []}
    merged = {}
    for key, qty in counts.items():
        item = lookup.get(key, {'name': key})
        canonical = item['name']
        if canonical not in merged:
            uses = sorted(imb_lookup.get(key, set()) | imb_lookup.get(normalize(canonical), set()))
            merged[canonical] = {**item, 'quantity': 0, 'imbuements': uses}
        merged[canonical]['quantity'] += qty
    for item in merged.values():
        item['each'], item['remainder'] = divmod(item['quantity'], people)
        # Task items with an imbuement use retain the badge in the task category.
        group = 'tasks' if item.get('isWeeklyTask') else 'imbuements' if item['imbuements'] else 'other'
        groups[group].append(item)
    for items in groups.values():
        items.sort(key=lambda item: item['name'].lower())
    if not merged:
        return {'erro': 'Nenhum item encontrado. Cole o Hunting Analyser com Looted Items ou linhas como 15x werewolf fangs.'}
    return {'groups': groups, 'people': people, 'total': sum(counts.values()), 'distinct': len(merged), 'catalog_date': '12/10/2026'}
