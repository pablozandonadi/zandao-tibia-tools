"""Monitor privado: UP pela lista online do mundo e mortes pela ficha pública, sem IA."""
import copy
import hashlib
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError
from urllib.parse import quote

import tibia_info
from comandos_tibia import _nome_voc

NOME = re.compile(r"[A-Za-z][A-Za-z '\-.]{1,39}")
MAX_TRACKED = 1000
MUNDO = re.compile(r'[A-Za-z]{2,40}')


def _nome(value):
    if not isinstance(value, str):
        raise ValueError('Informe um nome de personagem válido.')
    value = ' '.join(value.split())
    if not NOME.fullmatch(value):
        raise ValueError('Informe um nome de personagem válido (até 40 caracteres).')
    return value


def _fetch(nome):
    return tibia_info._get_json(tibia_info.TIBIADATA + '/character/' + quote(nome))


def _fetch_world(mundo):
    return tibia_info._get_json(tibia_info.TIBIADATA + '/world/' + quote(mundo))


def _timestamp(value):
    at = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if at.tzinfo is None:
        raise ValueError('Horário da fonte inválido.')
    return at.timestamp()


def _morte(item):
    if not isinstance(item, dict) or type(item.get('level')) is not int or not isinstance(item.get('time'), str):
        raise ValueError('Mortes indisponíveis.')
    try:
        at = datetime.fromisoformat(item['time'].replace('Z', '+00:00'))
        if at.tzinfo is None:
            raise ValueError()
    except ValueError:
        raise ValueError('Horário de morte inválido.') from None
    reason = item.get('reason', '')
    killers = item.get('killers', [])
    if not isinstance(reason, str) or not isinstance(killers, list) or any(not isinstance(x, dict) for x in killers):
        raise ValueError('Causa de morte indisponível.')
    normalized = {'time': at.astimezone(timezone.utc).isoformat(), 'level': item['level'], 'reason': reason,
                  'killers': sorted((json.dumps(x, sort_keys=True, ensure_ascii=False) for x in killers))}
    fingerprint = hashlib.sha256(json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    cause = reason or ', '.join(str(x.get('name', '')) for x in killers if x.get('name')) or 'causa não informada'
    return fingerprint, normalized['time'], item['level'], cause[:500]


def guild_preview(nome, consultar):
    """Uma consulta ao roster público; prévia não cadastra nem consulta fichas."""
    if not isinstance(nome,str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9 '\-.]{1,99}",nome.strip()):
        raise ValueError('Informe um nome de guild válido (até 100 caracteres).')
    nome=' '.join(nome.split())
    result=consultar('guild:'+nome.casefold(),'/guild/'+quote(nome),ttl=300)
    payload=result.get('dados') if isinstance(result,dict) else None
    guild=payload.get('guild') if isinstance(payload,dict) else None
    if not isinstance(guild,dict) or not isinstance(guild.get('members'),list) or not guild.get('name'):
        raise ValueError('Guild indisponível ou não encontrada. Tente novamente depois.')
    world=guild.get('world')
    if not isinstance(world,str) or not MUNDO.fullmatch(world):raise ValueError('Mundo da guild indisponível.')
    members=[];seen=set()
    for member in guild['members']:
        if not isinstance(member,dict):raise ValueError('Lista de membros inválida; nenhum personagem foi importado.')
        name=_nome(member.get('name'));key=name.casefold()
        if key not in seen:
            seen.add(key)
            members.append({'nome':name,'world':world,'vocation':member.get('vocation') if isinstance(member.get('vocation'),str) else None})
    return {'guild':str(guild['name'])[:100],'world':world,'members':members,'total':len(members),
            'consulta':result.get('consulta'),'velho':bool(result.get('velho')),'fonte':'TibiaData /guild (cache de 5 min)'}


class Monitor:
    def __init__(self, base_dir, fetch=None, clock=None, fetch_world=None, wait=None, notify_windows=None, notify_sound=None):
        self.notify_windows,self.notify_sound=notify_windows,notify_sound
        self.path = os.path.join(base_dir, 'monitor-personagens.json')
        self.fetch, self.clock = fetch or _fetch, clock or time.time
        self.lock = threading.RLock()
        self.scan_lock = threading.Lock()
        self.world_scan_lock = threading.Lock()
        self.network_lock = threading.Lock()
        self.guild_lock = threading.Lock()
        self.guild_cache = {}
        self.stop_event = threading.Event()
        self.fetch_world = fetch_world or _fetch_world
        self.wait = wait or self.stop_event.wait
        self.network_clock = clock or time.monotonic
        self.last_request = None
        self.network_until = 0
        self.network_warning = ''
        self.thread = None
        self.char_thread = None
        self.next_poll, self.status = {}, {}
        self.next_world, self.up_status, self.checks = {}, {}, {}
        self.data = {'schema': 1, 'personagens': [], 'up': [], 'death': []}
        self.warning = ''
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding='utf-8') as file:
                    loaded = json.load(file)
                if not isinstance(loaded, dict) or loaded.get('schema') != 1 or not isinstance(loaded.get('personagens'), list) or len(loaded['personagens']) > MAX_TRACKED:
                    raise ValueError()
                for row in loaded['personagens']:
                    _nome(row['nome'])
                    for key in ('notify_windows','notify_sound'):
                        row.setdefault(key,False)
                        if type(row[key]) is not bool:raise ValueError()
                    if any(type(row.get(k)) is not bool for k in ('up', 'death')) or not isinstance(row.get('versao'), str):
                        raise ValueError()
                    if row.get('level') is not None and type(row['level']) is not int:
                        raise ValueError()
                    if row.get('mortes') is not None and (not isinstance(row['mortes'], list) or any(not isinstance(x, str) for x in row['mortes'])):
                        raise ValueError()
                for channel in ('up', 'death'):
                    if not isinstance(loaded.get(channel), list) or any(not isinstance(x, dict) or not isinstance(x.get('id'), str) or not isinstance(x.get('texto'), str) for x in loaded[channel]):
                        raise ValueError()
                    loaded[channel] = loaded[channel][-200:]
                self.data = loaded
            except (OSError, ValueError, TypeError, KeyError):
                self.warning = 'Arquivo de monitoramento inválido. Os dados foram preservados; revise antes de cadastrar novamente.'

    def _save(self, data):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        temp = self.path + '.tmp'
        with open(temp, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, self.path)
        self.data = data

    def estado(self):
        with self.lock:
            result = copy.deepcopy(self.data)
            for row in result['personagens']:
                key = row['nome'].casefold()
                row['estado_up'] = self.up_status.get(key, 'Aguardando leitura online do mundo') if row['up'] else 'Desligado'
                row['estado_death'] = self.status.get(key, 'Aguardando ficha pública') if row['death'] else 'Desligado'
                row['estado'] = f"UP: {row['estado_up']} · Death: {row['estado_death']}"
                row['ultima_verificacao_up'] = self.checks.get((key, 'up'))
                row['ultima_verificacao_death'] = self.checks.get((key, 'death'))
                row.pop('mortes', None)
                row.pop('versao', None)
            result['aviso'] = self.warning
            result['aviso_rede'] = self.network_warning if self.clock() < self.network_until else ''
            result['fontes'] = {'up': {'intervalo_segundos': 60, 'cache_segundos': 60, 'fonte': 'TibiaData /world'},
                                'death': {'intervalo_segundos': 60, 'cache_segundos': 300, 'fonte': 'TibiaData /character'}}
            return result

    def configurar(self, nome, up=True, death=True, remover=False, notify_windows=None, notify_sound=None):
        nome = _nome(nome)
        if any(type(x) is not bool for x in (up, death, remover)):
            raise ValueError('Opções de monitoramento inválidas.')
        if any(value is not None and type(value) is not bool for value in (notify_windows,notify_sound)):
            raise ValueError('Opções de aviso inválidas.')
        with self.lock:
            data = copy.deepcopy(self.data)
            row = next((r for r in data['personagens'] if r['nome'].casefold() == nome.casefold()), None)
            if remover:
                if row:
                    data['personagens'].remove(row)
            else:
                if row is None:
                    if len(data['personagens']) >= MAX_TRACKED:
                        raise ValueError(f'Limite de {MAX_TRACKED} personagens monitorados.')
                    row = {'nome': nome, 'up': up, 'death': death, 'level': None, 'mortes': None,'notify_windows':False,'notify_sound':False}
                    data['personagens'].append(row)
                if row['up'] != up:
                    row['level'] = None
                    row['world_baseline'] = False
                    row['up_timestamp'] = None
                if row['death'] != death:
                    row['mortes'] = None
                if notify_windows is not None:row['notify_windows']=notify_windows
                if notify_sound is not None:row['notify_sound']=notify_sound
                row.update(up=up, death=death, versao=uuid.uuid4().hex)
            self._save(data)
            # Não remove o prazo: toggles não podem causar consultas remotas mais frequentes.
            self.status.pop(nome.casefold(), None)
            self.up_status.pop(nome.casefold(), None)
        return self.estado()

    def guild(self,nome):
        # Prévia manual compartilha o gate/backoff das fontes, com cache de 5 min.
        def consultar(key,endpoint,ttl=300):
            with self.guild_lock:
                previous=self.guild_cache.get(key)
                if previous and self.clock()-previous['consulta']<ttl:return copy.deepcopy(previous)
                try:
                    payload=self._request(lambda path:tibia_info._get_json(tibia_info.TIBIADATA+path),endpoint)
                    result={'dados':payload,'consulta':self.clock(),'velho':False}
                    self.guild_cache[key]=copy.deepcopy(result)
                    return result
                except Exception as error:
                    self._failure(error,base=300)
                    if previous:return {**copy.deepcopy(previous),'velho':True}
                    return {'dados':{},'consulta':None,'velho':True}
        return guild_preview(nome,consultar)

    def importar(self,membros,up=True,death=True):
        if type(up) is not bool or type(death) is not bool:raise ValueError('Opções de monitoramento inválidas.')
        if not isinstance(membros,list) or not membros or len(membros)>MAX_TRACKED:raise ValueError(f'Informe de 1 a {MAX_TRACKED} membros.')
        normalized={}
        for member in membros:
            if not isinstance(member,dict):raise ValueError('Lista de membros inválida.')
            nome=_nome(member.get('nome'));world=member.get('world')
            if not isinstance(world,str) or not MUNDO.fullmatch(world):raise ValueError('Mundo dos membros inválido.')
            key=nome.casefold()
            if key in normalized and normalized[key]['world'].casefold()!=world.casefold():raise ValueError('Mundos conflitantes no cadastro.')
            normalized[key]={'nome':nome,'world':world,'vocation':member.get('vocation') if isinstance(member.get('vocation'),str) and len(member['vocation'])<=100 else None}
        with self.lock:
            data=copy.deepcopy(self.data);existing={r['nome'].casefold() for r in data['personagens']}
            novos=[row for key,row in normalized.items() if key not in existing]
            if len(data['personagens'])+len(novos)>MAX_TRACKED:raise ValueError(f'Limite de {MAX_TRACKED} personagens monitorados. Nenhum membro foi adicionado.')
            for member in novos:
                data['personagens'].append({**member,'up':up,'death':death,'level':None,'mortes':None,'world_baseline':False,'up_timestamp':None,'notify_windows':False,'notify_sound':False,'versao':uuid.uuid4().hex})
            if novos:self._save(data)
            result=self.estado()
            result['importacao']={'adicionados':len(novos),'existentes':len(normalized)-len(novos),'total':len(data['personagens'])}
            return result

    def _request(self, fetch, arg):
        # Só o início da chamada é espaçado; uma ficha lenta não segura a consulta do mundo.
        with self.network_lock:
            if self.clock() < self.network_until:
                raise RuntimeError('Consultas pausadas após limite da fonte.')
            delay = max(0, 1 - (self.network_clock() - self.last_request)) if self.last_request is not None else 0
            if self.stop_event.is_set() or delay and self.wait(delay):
                raise InterruptedError()
            if self.clock() < self.network_until:
                raise RuntimeError('Consultas pausadas após limite da fonte.')
            self.last_request = self.network_clock()
        return fetch(arg)

    def _failure(self, error, base=60):
        if isinstance(error, HTTPError) and error.code in (403, 429, 503):
            raw = error.headers.get('Retry-After', '') if error.headers else ''
            try:
                delay = float(raw)
            except ValueError:
                try:
                    delay = parsedate_to_datetime(raw).timestamp() - self.clock()
                except (ValueError, TypeError, OverflowError):
                    delay = 300
            delay = min(3600, max(300, delay))
            with self.network_lock:
                self.network_until = max(self.network_until, self.clock() + delay)
                self.network_warning = f'Fonte HTTP {error.code}: consultas em pausa até ' + datetime.fromtimestamp(self.network_until, timezone.utc).isoformat()
                warning = self.network_warning
            return delay, warning
        return base, 'Fonte indisponível; última referência preservada'

    @staticmethod
    def _event(data, channel, nome, at, text):
        data[channel].append({'id': uuid.uuid4().hex, 'at': at, 'nome': nome, 'texto': text})
        data[channel] = data[channel][-200:]

    def _scan_char(self):
        if not self.scan_lock.acquire(blocking=False):
            return
        try:
            with self.lock:
                rows = copy.deepcopy(self.data['personagens'])
            for previous in rows:
                if self.stop_event.is_set() or self.clock() < self.network_until:
                    return
                key = previous['nome'].casefold()
                now = self.clock()
                if not (previous['up'] or previous['death']) or now < self.next_poll.get(key, float('-inf')):
                    continue
                self.next_poll[key] = now + (60 if previous['death'] else 300)
                try:
                    if previous['death']:
                        with self.lock:
                            self.checks[(key, 'death')] = now
                    payload = self._request(self.fetch, previous['nome'])
                    block = payload['character']
                    char = block['character']
                    if char['name'].casefold() != key or type(char.get('level')) is not int or char['level'] < 1:
                        raise ValueError('Personagem indisponível.')
                    world = char.get('world')
                    if not isinstance(world, str) or not MUNDO.fullmatch(world):
                        raise ValueError('Mundo do personagem indisponível.')
                    deaths = block.get('deaths') if previous['death'] else []
                    try:
                        if not isinstance(deaths, list):
                            raise ValueError('Mortes indisponíveis.')
                        parsed = sorted((_morte(x) for x in deaths), key=lambda x: x[1])
                    except ValueError:
                        parsed = None
                    with self.lock:
                        data = copy.deepcopy(self.data)
                        row = next((r for r in data['personagens'] if r['nome'].casefold() == key), None)
                        if row is None or row['versao'] != previous['versao'] or self.stop_event.is_set():
                            continue
                        nome = _nome_voc(char['name'], char.get('vocation'))
                        if row.get('world', '').casefold() != world.casefold():
                            row.update(world=world, world_baseline=False, up_timestamp=None, level=None)
                            self.up_status[key] = 'Mundo identificado; aguardando lista online'
                        row['vocation'] = char.get('vocation') if isinstance(char.get('vocation'), str) else None
                        if row['death'] and parsed is not None:
                            seen = set(row['mortes'] or [])
                            for ident, at, level, cause in parsed:
                                if row['mortes'] is not None and ident not in seen:
                                    self._event(data, 'death', char['name'], at, f'{nome} morreu no level {level}: {cause}')
                                seen.add(ident)
                            row['mortes'] = list(dict.fromkeys([*(row['mortes'] or []), *(x[0] for x in parsed)]))[-1000:]
                        self._save(data)
                        self.status[key] = 'Ficha atualizada (cache da fonte: até 5 min)' if parsed is not None else 'Mortes inválidas; referência preservada'
                except Exception as error:
                    delay, message = self._failure(error)
                    self.next_poll[key] = max(self.next_poll[key], self.clock() + delay)
                    with self.lock:
                        self.status[key] = message
                        if previous['up'] and not previous.get('world'):
                            self.up_status[key] = 'Mundo ainda não identificado: ' + message
        finally:
            self.scan_lock.release()

    def _scan_world(self):
        if not self.world_scan_lock.acquire(blocking=False):
            return
        try:
            with self.lock:
                rows = copy.deepcopy(self.data['personagens'])
            worlds = {r['world'].casefold(): r['world'] for r in rows if r['up'] and isinstance(r.get('world'), str) and MUNDO.fullmatch(r['world'])}
            for world_key, world in worlds.items():
                now = self.clock()
                if self.stop_event.is_set() or now < self.network_until:
                    return
                if now < self.next_world.get(world_key, float('-inf')):
                    continue
                self.next_world[world_key] = now + 60
                selected = [r for r in rows if r['up'] and r.get('world', '').casefold() == world_key]
                with self.lock:
                    for r in selected:
                        self.checks[(r['nome'].casefold(), 'up')] = now
                try:
                    payload = self._request(self.fetch_world, world)
                    block = payload['world']
                    if block['name'].casefold() != world_key or not isinstance(block.get('online_players'), list):
                        raise ValueError('Lista online indisponível.')
                    source_time = _timestamp(payload['information']['timestamp'])
                    online = {}
                    for player in block['online_players']:
                        if not isinstance(player, dict) or not isinstance(player.get('name'), str) or type(player.get('level')) is not int or player['level'] < 1:
                            raise ValueError('Lista online inválida.')
                        key = player['name'].casefold()
                        if key in online:
                            raise ValueError('Personagem duplicado na lista online.')
                        online[key] = player
                    notifications=[]
                    with self.lock:
                        data = copy.deepcopy(self.data)
                        for previous in selected:
                            key = previous['nome'].casefold()
                            row = next((r for r in data['personagens'] if r['nome'].casefold() == key), None)
                            if row is None or row['versao'] != previous['versao'] or row.get('world', '').casefold() != world_key or self.stop_event.is_set():
                                continue
                            if row.get('up_timestamp') is not None and source_time < row['up_timestamp']:
                                self.up_status[key] = 'Resposta antiga do mundo ignorada; referência preservada'
                                continue
                            player = online.get(key)
                            if player is None:
                                row['up_timestamp'] = source_time
                                self.up_status[key] = 'Não aparece online neste mundo; referência preservada'
                                continue
                            nome = _nome_voc(player['name'], player.get('vocation') or row.get('vocation'))
                            if row.get('world_baseline') and row.get('level') is not None and player['level'] > row['level']:
                                text=f"{nome} subiu do level {row['level']} para {player['level']} · horário da detecção (lista online do mundo)."
                                self._event(data, 'up', player['name'], datetime.fromtimestamp(now, timezone.utc).isoformat(),text)
                                notifications.append((row.get('notify_windows',False),row.get('notify_sound',False),text))
                            row.update(level=player['level'], world_baseline=True, up_timestamp=source_time)
                            self.up_status[key] = 'Online: referência atualizada (cache da fonte: até 60 s)'
                        self._save(data)
                    # Only persisted new UP events notify; callbacks run outside the state lock.
                    for windows,sound,text in notifications:
                        for enabled,callback in ((windows,self.notify_windows),(sound,self.notify_sound)):
                            if enabled and callback:
                                try:callback(text)
                                except Exception:pass  # The feed event is saved; never retry delivery.
                except Exception as error:
                    delay, message = self._failure(error)
                    self.next_world[world_key] = max(self.next_world[world_key], self.clock() + delay)
                    with self.lock:
                        for row in selected:
                            self.up_status[row['nome'].casefold()] = message
        finally:
            self.world_scan_lock.release()

    def scan(self):
        """Passo síncrono para testes; em produção cada fonte tem seu próprio loop."""
        self._scan_char()
        self._scan_world()

    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                return
            self.stop_event.clear()
            def run(scan):
                while not self.stop_event.is_set():
                    scan()
                    self.stop_event.wait(1)
            self.thread = threading.Thread(target=run, args=(self._scan_world,), name='MonitorMundos', daemon=True)
            self.char_thread = threading.Thread(target=run, args=(self._scan_char,), name='MonitorMortes', daemon=True)
            self.thread.start()
            self.char_thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=2)
        if self.char_thread and self.char_thread is not threading.current_thread():
            self.char_thread.join(timeout=2)
