"""Monitor privado de levels/mortes. Uma consulta por personagem a cada 60 s, sem IA."""
import copy
import hashlib
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import tibia_info
from comandos_tibia import _nome_voc

NOME = re.compile(r"[A-Za-z][A-Za-z '\-.]{1,39}")


def _nome(value):
    if not isinstance(value, str):
        raise ValueError('Informe um nome de personagem válido.')
    value = ' '.join(value.split())
    if not NOME.fullmatch(value):
        raise ValueError('Informe um nome de personagem válido (até 40 caracteres).')
    return value


def _fetch(nome):
    return tibia_info._get_json(tibia_info.TIBIADATA + '/character/' + quote(nome))


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


class Monitor:
    def __init__(self, base_dir, fetch=None, clock=None):
        self.path = os.path.join(base_dir, 'monitor-personagens.json')
        self.fetch, self.clock = fetch or _fetch, clock or time.time
        self.lock = threading.RLock()
        self.scan_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.next_poll, self.status = {}, {}
        self.data = {'schema': 1, 'personagens': [], 'up': [], 'death': []}
        self.warning = ''
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding='utf-8') as file:
                    loaded = json.load(file)
                if not isinstance(loaded, dict) or loaded.get('schema') != 1 or not isinstance(loaded.get('personagens'), list) or len(loaded['personagens']) > 20:
                    raise ValueError()
                for row in loaded['personagens']:
                    _nome(row['nome'])
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
                row['estado'] = self.status.get(row['nome'].casefold(), 'Aguardando consulta')
                row.pop('mortes', None)
                row.pop('versao', None)
            result['aviso'] = self.warning
            return result

    def configurar(self, nome, up=True, death=True, remover=False):
        nome = _nome(nome)
        if any(type(x) is not bool for x in (up, death, remover)):
            raise ValueError('Opções de monitoramento inválidas.')
        with self.lock:
            data = copy.deepcopy(self.data)
            row = next((r for r in data['personagens'] if r['nome'].casefold() == nome.casefold()), None)
            if remover:
                if row:
                    data['personagens'].remove(row)
            else:
                if row is None:
                    if len(data['personagens']) >= 20:
                        raise ValueError('Limite de 20 personagens monitorados.')
                    row = {'nome': nome, 'up': up, 'death': death, 'level': None, 'mortes': None}
                    data['personagens'].append(row)
                if row['up'] != up:
                    row['level'] = None
                if row['death'] != death:
                    row['mortes'] = None
                row.update(up=up, death=death, versao=uuid.uuid4().hex)
            self._save(data)
            # Não remove o prazo: toggles não podem causar consultas remotas mais frequentes.
            self.status.pop(nome.casefold(), None)
        return self.estado()

    def scan(self):
        if not self.scan_lock.acquire(blocking=False):
            return
        try:
            with self.lock:
                rows = copy.deepcopy(self.data['personagens'])
            for previous in rows:
                if self.stop_event.is_set():
                    return
                key = previous['nome'].casefold()
                now = self.clock()
                if not (previous['up'] or previous['death']) or now < self.next_poll.get(key, float('-inf')):
                    continue
                self.next_poll[key] = now + 60
                try:
                    payload = self.fetch(previous['nome'])
                    block = payload['character']
                    char = block['character']
                    if char['name'].casefold() != key or type(char.get('level')) is not int or char['level'] < 1:
                        raise ValueError('Personagem indisponível.')
                    deaths = block.get('deaths') if previous['death'] else []
                    if not isinstance(deaths, list):
                        raise ValueError('Mortes indisponíveis.')
                    parsed = sorted((_morte(x) for x in deaths), key=lambda x: x[1])
                    with self.lock:
                        data = copy.deepcopy(self.data)
                        row = next((r for r in data['personagens'] if r['nome'].casefold() == key), None)
                        if row is None or row['versao'] != previous['versao'] or self.stop_event.is_set():
                            continue
                        nome = _nome_voc(char['name'], char.get('vocation'))
                        def event(channel, at, text):
                            data[channel].append({'id': uuid.uuid4().hex, 'at': at, 'nome': char['name'], 'texto': text})
                            data[channel] = data[channel][-200:]
                        detected = datetime.fromtimestamp(now, timezone.utc).isoformat()
                        if row['up']:
                            if row['level'] is not None and char['level'] > row['level']:
                                event('up', detected, f"{nome} subiu do level {row['level']} para {char['level']} · horário da detecção.")
                            row['level'] = char['level']
                        if row['death']:
                            seen = set(row['mortes'] or [])
                            for ident, at, level, cause in parsed:
                                if row['mortes'] is not None and ident not in seen:
                                    event('death', at, f'{nome} morreu no level {level}: {cause}')
                                seen.add(ident)
                            row['mortes'] = list(dict.fromkeys([*(row['mortes'] or []), *(x[0] for x in parsed)]))[-1000:]
                        self._save(data)
                        self.status[key] = 'Consulta atualizada'
                except Exception:
                    with self.lock:
                        self.status[key] = 'Fonte indisponível; última referência preservada'
        finally:
            self.scan_lock.release()

    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                return
            self.stop_event.clear()
            def run():
                while not self.stop_event.is_set():
                    self.scan()
                    self.stop_event.wait(1)
            self.thread = threading.Thread(target=run, name='MonitorPersonagens', daemon=True)
            self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=2)
