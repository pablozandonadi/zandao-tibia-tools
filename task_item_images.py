"""Sprites GIF dos itens: recursos empacotados e cache local para novos drops."""
import base64
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from app_paths import data_dir, resource_dir
BASE = data_dir()
RESOURCES = str(resource_dir())
ASSETS = os.path.join(RESOURCES, 'web', 'assets')
CACHE = os.path.join(BASE, 'cache_task_images')
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def key(name):
    return re.sub(r'^(?:an?|some)\s+', '', str(name).strip().lower())

def candidates(name):
    original = key(name)
    names = [original]
    if ' of ' in original:
        head, tail = original.split(' of ', 1)
        if head.endswith('s'): names.append(head[:-1] + ' of ' + tail)
    if original.endswith('ies'): names.append(original[:-3] + 'y')
    if original.endswith('ves'): names.extend([original[:-3] + 'f', original[:-3] + 'fe'])
    if original.endswith('s'): names.append(original[:-1])
    result = [name] if name[:1].isupper() else []
    for n in names:
        title = re.sub(r"(?<=[a-z])'([A-Z])", lambda m: "'" + m[1].lower(), n.title())
        for value in [title, re.sub(r'\b(Of|The|In|To|And)\b', lambda m: m[0].lower(), title)]:
            if value not in result: result.append(value)
    aliases = {'grimeleech wings': 'Some Grimeleech Wings', 'sabretooth': 'Sabretooth (Item)'}
    if original in aliases: result.insert(0, aliases[original])
    return result

def valid(data):
    return data.startswith((b'GIF87a', b'GIF89a', b'\x89PNG\r\n\x1a\n'))

def download(name, item_id=None):
    for title in candidates(name):
        filename = title.replace(' ', '_') + '.gif'
        digest = hashlib.md5(filename.encode()).hexdigest()
        url = f'https://www.tibiawiki.com.br/images/{digest[0]}/{digest[:2]}/{urllib.parse.quote(filename)}'
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=5) as response:
                data = response.read(1024 * 1024)
            if valid(data): return data, url
        except (OSError, ValueError): pass
    if isinstance(item_id, int) and item_id > 0:
        url = f'https://tibiacacau.com.br/api/items/{item_id}/image'
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=5) as response:
                data = response.read(1024 * 1024)
            if valid(data): return data, url
        except (OSError, ValueError): pass
    return None, None

def load_one(item, manifest):
    name = item.get('name', '')
    if not isinstance(name, str) or not 0 < len(name) <= 200: return name, None
    normalized = key(name)
    bundled = manifest.get(normalized) or next((manifest.get(key(n)) for n in candidates(name) if manifest.get(key(n))), None)
    digest = hashlib.sha256(normalized.encode()).hexdigest() + '.gif'
    paths = [os.path.join(ASSETS, 'items', os.path.basename(bundled))] if bundled else []
    paths.append(os.path.join(CACHE, digest))
    data = None
    for path in paths:
        try:
            with open(path, 'rb') as f: candidate = f.read(1024 * 1024)
            if valid(candidate): data = candidate; break
        except OSError: pass
    if data is None:
        data, _ = download(name, item.get('id'))
        if data:
            try:
                os.makedirs(CACHE, exist_ok=True)
                temp = os.path.join(CACHE, digest + '.tmp')
                with open(temp, 'wb') as f: f.write(data)
                os.replace(temp, os.path.join(CACHE, digest))
            except OSError: pass
    if data:
        media = 'image/gif' if data.startswith(b'GIF') else 'image/png'
        return name, f'data:{media};base64,' + base64.b64encode(data).decode('ascii')
    return name, None

def resolve(items):
    if not isinstance(items, list) or len(items) > 1000: return {}
    try:
        with open(os.path.join(ASSETS, 'item_images.json'), encoding='utf-8') as f: manifest = json.load(f)
    except (OSError, ValueError): manifest = {}
    unique = {key(i.get('name', '')): i for i in items if isinstance(i, dict) and isinstance(i.get('name'), str)}
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(pool.map(lambda item: load_one(item, manifest), unique.values()))
