"""GuildStats public tabs with private cache and an isolated verification WebView."""
import re
import json
import hashlib
import os
from pathlib import Path
from app_paths import data_dir
import urllib.error
import time
import threading
import urllib.request
import urllib.parse
from html.parser import HTMLParser

BASE = 'https://guildstats.eu/'
TABS = {'character', 'experience', 'deaths', 'timeonline', 'highscore', 'insomnia', 'drome', 'history'}
_cache = {}
_lock = threading.RLock()
_browser_lock = threading.Lock()
_browser = None
_failures = {}

class VerificationRequired(Exception):
    pass

def _cache_file(key):
    digest = hashlib.sha256(json.dumps(key).encode()).hexdigest()
    return Path(data_dir()) / 'cache_guild_stats' / (digest + '.json')

def _read_cache(key):
    try:
        path = _cache_file(key)
        if path.stat().st_size > 2_000_000: return None
        item = json.loads(path.read_text(encoding='utf-8'))
        if item['key'] == list(key) and isinstance(item['data'], dict) and not item['data'].get('erro'):
            return (float(item['time']), item['data'])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None

def _save_cache(key, data):
    try:
        path = _cache_file(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps({'key':key, 'time':time.time(), 'data':data}, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, path)
        # Bound disk usage; keep the latest 128 successful queries.
        files = sorted(path.parent.glob('*.json'), key=lambda p:p.stat().st_mtime, reverse=True)
        for old in files[128:]: old.unlink(missing_ok=True)
    except OSError:
        pass  # A successful online query remains usable if the disk is unavailable.

def _challenge(html):
    return 'cf-chl-' in html or 'Just a moment' in html

def _browser_html(url, tab, interactive=False):
    """Read in the same WebView session; never expose the application's Python API."""
    global _browser
    with _browser_lock:
        if _browser is None:
            if not interactive: raise VerificationRequired('Verifique o acesso dentro do aplicativo.')
            import webview
            window = webview.create_window('GuildStats · verifique o acesso para continuar', url,
                js_api=None, width=900, height=700, min_size=(400, 400))
            _browser = window
            def closed():
                global _browser
                if _browser is window: _browser = None
            window.events.closed += closed
        else:
            window = _browser
            if interactive: window.show()
            window.load_url(url)
        deadline = time.monotonic() + (120 if interactive else 12)
        while time.monotonic() < deadline:
            if _browser is not window: raise VerificationRequired('Verificação cancelada. Tente novamente dentro do app.')
            try:
                current = urllib.parse.urlsplit(window.get_current_url() or '')
                expected = urllib.parse.urlsplit(url)
                query = urllib.parse.parse_qs(current.query)
                matches = all(query.get(k) == v for k, v in urllib.parse.parse_qs(expected.query).items())
                if current.scheme == 'https' and current.hostname == 'guildstats.eu' and current.path == expected.path and matches:
                    html = window.evaluate_js('document.documentElement.outerHTML')
                    if isinstance(html, str) and len(html) <= 2_000_000 and not _challenge(html):
                        parsed = parse(html, tab)
                        valid = bool(profile(html).get('Level')) if tab == 'character' else bool(parsed['tables']) or 'charHistoryTurnstile' in html
                        if valid:
                            window.hide()
                            return html
            except VerificationRequired:
                raise
            except Exception:
                pass
            time.sleep(0.5)
        raise VerificationRequired('O GuildStats ainda exige verificação. Conclua na janela do app e tente atualizar.')


class Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None
        self.stack = []
        self.skip = 0
        self.text = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        hidden = tag in ('script', 'style') or 'md:hidden' in attrs.get('class', '').split() or attrs.get('x-show') == 'open'
        if tag not in ('br', 'input', 'img', 'meta', 'link', 'hr', 'col'):
            self.stack.append((tag, hidden))
            self.skip += int(hidden)
        if self.skip: return
        if tag == 'table': self.table = {'headers': [], 'rows': []}
        if tag == 'tr': self.row = []
        if tag in ('td', 'th'): self.cell = []; self.kind = tag
        if tag == 'br' and self.cell is not None: self.cell.append(' ')
    def handle_endtag(self, tag):
        if not self.skip:
            if tag in ('td', 'th') and self.cell is not None:
                value = ' '.join(''.join(self.cell).split())
                if self.kind == 'th' and self.table is not None: self.table['headers'].append(value)
                elif self.row is not None: self.row.append(value)
                self.cell = None
            if tag == 'tr' and self.row is not None:
                if self.row and self.table is not None: self.table['rows'].append(self.row)
                self.row = None
            if tag == 'table' and self.table is not None:
                self.tables.append(self.table); self.table = None
        for i in range(len(self.stack)-1, -1, -1):
            if self.stack[i][0] == tag:
                self.skip -= sum(int(h) for _, h in self.stack[i:])
                del self.stack[i:]
                break
    def handle_data(self, value):
        if not self.skip:
            self.text.append(value)
            if self.cell is not None: self.cell.append(value)

def parse(html, tab):
    p = Tables(); p.feed(html)
    text = ' '.join(' '.join(p.text).split())
    update = re.search(r'Update:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?:\s+CE[ST]+)?)', text)
    result = {'tables': p.tables, 'updated': update.group(1) if update else '', 'notice': ''}
    if not p.tables and tab != 'character':
        result['notice'] = 'Nenhum registro público disponível nesta aba.'
    if tab == 'history' and 'charHistoryTurnstile' in html:
        result['notice'] = 'O histórico exige verificação do navegador no GuildStats. Use Abrir no site para consultar.'
    if tab == 'experience':
        days = []
        for table in p.tables:
            for row in table['rows']:
                if len(row) >= 5 and re.fullmatch(r'\d{4}-\d{2}-\d{2}', row[0]):
                    raw = row[1].replace(',', '').replace(' ', '').replace('−', '-')
                    gain = int(raw) if re.fullmatch(r'[+-]?\d+', raw) else None
                    days.append({'date': row[0], 'gain': gain, 'level': row[3], 'total': row[4], 'online': row[5] if len(row)>5 else ''})
        result['days'] = sorted(days, key=lambda x: x['date'], reverse=True)
        months = {}
        for d in days:
            m = months.setdefault(d['date'][:7], {'gain': 0, 'days': 0, 'missing': 0})
            m['days'] += 1
            if d['gain'] is None: m['missing'] += 1
            else: m['gain'] += d['gain']
        result['months'] = months
        result['notice'] = 'XP líquida registrada pelo GuildStats (inclui perdas). Totais mensais somam apenas as datas disponíveis; o histórico público pode ser limitado. Dados coletados do top 1000 por vocação no mundo.'
    if tab == 'deaths':
        result['notice'] = 'A perda de XP é aproximada: o GuildStats considera promoção e todas as blessings. A tabela mostra os registros públicos retornados pelo site.'
        summary = re.search(r'(\d+) Number of death ([\d,]+) Experience lost (\d+) Level of character without dying (\d+) Killed by players', text)
        if summary: result['summary'] = list(summary.groups())
    return result

def buscar(nome, tab='experience', forcar=False, pagina=1, interagir=False):
    nome = ' '.join((nome or '').split())
    if not nome or len(nome)>60 or any(ord(c)<32 for c in nome): return {'erro': 'Digite um nome de personagem válido.'}
    if tab not in TABS: return {'erro': 'Aba inválida.'}
    try: pagina = max(1, min(1000, int(pagina)))
    except (TypeError, ValueError): pagina = 1
    key = (nome.casefold(), tab) if pagina == 1 else (nome.casefold(), tab, pagina)
    with _lock:
        previous = _cache.get(key) or _read_cache(key)
        if previous and not forcar and time.time()-previous[0]<900: return previous[1]
        failure = _failures.get(key)
        if failure and not forcar and not interagir and time.time()-failure[0]<60:
            return {**previous[1], 'stale': True, 'erro_cache': failure[1], 'verification_required': failure[2]} if previous else {'erro':failure[1], 'verification_required':failure[2]}
        url = BASE + ('character/' + urllib.parse.quote(nome, safe='') if tab=='character' else 'include/character/tab.php?' + urllib.parse.urlencode({'nick': nome, 'tab': tab}))
        try:
            if tab == 'deaths' and pagina > 1: url += '&part=table&page=' + str(pagina)
            request = urllib.request.Request(url, headers={'User-Agent': 'ZandaoTibiaTools/1.0', 'Accept-Language': 'en'})
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    html = response.read(2_000_000).decode('utf-8', errors='replace')
                if _challenge(html): raise VerificationRequired('Verificação necessária.')
            except (urllib.error.HTTPError, VerificationRequired) as blocked:
                if isinstance(blocked, urllib.error.HTTPError) and blocked.code != 403: raise
                if previous and not forcar:
                    raise VerificationRequired('O GuildStats exige verificação. Use Verificar acesso no app para atualizar.')
                html = _browser_html(url, tab, interagir)
            if _challenge(html): raise VerificationRequired('Verificação necessária.')
            data = parse(html, tab)
            if tab == 'deaths':
                paging = re.search(r'deathPagination\((\d+),\s*(\d+)\)', html)
                data['pages'] = int(paging.group(1)) if paging else pagina
                data['page'] = pagina
            if tab == 'experience' and not data.get('days'):
                data['notice'] = 'Sem histórico de XP público para este nome. Confira a grafia ou a presença no top 1000 por vocação.'
            data.update({'name': nome, 'tab': tab, 'url': BASE+'character/'+urllib.parse.quote(nome, safe='')+'#'+tab, 'fetched': time.strftime('%Y-%m-%d %H:%M:%S'), 'stale': False})
            if tab == 'character':
                data['profile'] = profile(html)
            if len(_cache)>128: _cache.clear()
            _cache[key] = (time.time(), data)
            _save_cache(key, data)
            _failures.pop(key, None)
            return data
        except Exception as e:
            verification = isinstance(e, VerificationRequired)
            message = str(e) if verification else 'Não foi possível atualizar o GuildStats. Tente novamente em instantes.'
            _failures[key] = (time.time(), message, verification)
            if previous: return {**previous[1], 'stale': True, 'erro_cache': message + ' Exibindo a última consulta salva.', 'verification_required': verification}
            return {'erro': message, 'verification_required': verification, 'detail': str(e)}


def profile(html):
    # Extract only the character panel, never navigation, scripts or tooltip text.
    match = re.search(r'<!-- Tab: Character.*?-->(.*?)(?=<!-- Tab:|</main>)', html, re.S)
    p = Tables(); p.feed(match.group(1) if match else html)
    text = ' '.join(' '.join(p.text).split())
    labels = ['Nationality:', 'Sex:', 'Vocation:', 'Achievements points:', 'Titles:', 'Account created:', 'World:', 'Residence:', 'Last login:', 'Account status:', 'Tibian age:']
    fields = {}
    pattern = '(' + '|'.join(re.escape(x) for x in labels) + ')'
    parts = re.split(pattern, text)
    for i in range(1, len(parts)-1, 2):
        fields[parts[i].rstrip(':')] = parts[i+1].split('Tibia Completed')[0].strip()[:180]
    full = Tables(); full.feed(html)
    fulltext = ' '.join(' '.join(full.text).split())
    level = re.search(r'Level\s+(\d+)\b', fulltext)
    if level: fields = {'Level': level.group(1), **fields}
    guild = re.search(r'Guild (.*?) since (\d{2}-\d{2}-\d{4})', fulltext)
    if guild: fields['Guild'] = guild.group(1) + ' · desde ' + guild.group(2)
    return fields
