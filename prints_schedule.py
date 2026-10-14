"""Rotina local de prints: execução no aplicativo aberto, com estado privado por canal."""
import copy
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import threading

from app_paths import data_dir

ARQUIVO = os.path.join(data_dir(), 'prints_schedule.json')
PADRAO = {'enabled': False, 'mode': 'interval', 'interval_minutes': 30,
          'daily_count': 3, 'daily_start': '08:00', 'times': ['09:00', '18:00']}


def _inteiro(value, name, maximum=1440):
    text = str(value).strip()
    if not re.fullmatch(r'\d+', text) or not 1 <= int(text) <= maximum:
        raise ValueError(f'{name}: informe um número inteiro entre 1 e {maximum}.')
    return int(text)


def _hora(value):
    match = re.fullmatch(r'(\d{1,2}):(\d{2})', str(value).strip())
    if not match or int(match[1]) > 23 or int(match[2]) > 59:
        raise ValueError('Informe horários válidos no formato HH:MM, entre 00:00 e 23:59.')
    return f'{int(match[1]):02d}:{int(match[2]):02d}'


def normalizar(config):
    if not isinstance(config, dict):
        raise ValueError('Rotina inválida.')
    result = copy.deepcopy(PADRAO)
    result['enabled'] = bool(config.get('enabled', False))
    result['mode'] = config.get('mode', 'interval')
    if result['mode'] not in ('interval', 'daily', 'times'):
        raise ValueError('Escolha o modo de agendamento.')
    if result['mode'] == 'interval':
        result['interval_minutes'] = _inteiro(config.get('interval_minutes', 30), 'Intervalo em minutos')
    elif result['mode'] == 'daily':
        result['daily_count'] = _inteiro(config.get('daily_count', 3), 'Vezes por dia')
        result['daily_start'] = _hora(config.get('daily_start', '08:00'))
    else:
        times = config.get('times', [])
        if isinstance(times, str):
            times = [t for t in re.split(r'[,;\s]+', times.strip()) if t]
        if not isinstance(times, list) or not times or len(times) > 1440:
            raise ValueError('Informe pelo menos um horário exato, separado por vírgulas.')
        result['times'] = sorted({_hora(t) for t in times})
    return result


def horarios(config):
    if config['mode'] == 'times':
        return list(config['times'])
    if config['mode'] != 'daily':
        return []
    hour, minute = map(int, config['daily_start'].split(':'))
    count = config['daily_count']
    minutes = sorted({(hour * 60 + minute + i * 1440 // count) % 1440 for i in range(count)})
    return [f'{minute // 60:02d}:{minute % 60:02d}' for minute in minutes]


def proxima(config, agora):
    if not config['enabled']:
        return None
    if config['mode'] == 'interval':
        return agora + timedelta(minutes=config['interval_minutes'])
    for days in (0, 1):
        day = agora.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days)
        for value in horarios(config):
            hour, minute = map(int, value.split(':'))
            candidate = day.replace(hour=hour, minute=minute)
            if candidate > agora:
                return candidate


class Agendador:
    def __init__(self, executar, caminho=None, agora=datetime.now):
        self._path = Path(caminho or ARQUIVO)
        self._executar = executar
        self._agora = agora
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._generation = 0
        self._running = False
        self._data = {'config': copy.deepcopy(PADRAO), 'prints': {}, 'last': '', 'result': ''}
        self._next = None
        try:
            if self._path.exists():
                saved = json.loads(self._path.read_text(encoding='utf-8'))
                self._data['config'] = normalizar(saved['config'])
                self._data['prints'] = dict(saved.get('prints') or {})
                self._data['last'] = str(saved.get('last') or '')
                self._data['result'] = str(saved.get('result') or '')
                self._next = datetime.fromisoformat(saved['next']) if saved.get('next') else None
                if self._next is None or self._next <= self._agora():
                    self._next = proxima(self._data['config'], self._agora())
        except (OSError, ValueError, KeyError, TypeError):
            self._data['config'] = copy.deepcopy(PADRAO)
            self._data['result'] = 'Não foi possível ler a rotina salva. Configure e salve novamente.'
            self._next = None

    def _salvar(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_suffix('.tmp')
        payload = {**self._data, 'next': self._next.isoformat() if self._next else ''}
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, self._path)

    def estado(self):
        with self._lock:
            return {**copy.deepcopy(self._data), 'next': self._next.isoformat() if self._next else '',
                    'running': self._running, 'horarios': horarios(self._data['config'])}

    def configurar(self, config, prints):
        config = normalizar(config)
        with self._lock:
            previous, due = copy.deepcopy(self._data), self._next
            self._data['config'] = config
            self._data['prints'] = dict(prints)
            self._next = proxima(config, self._agora())
            try:
                self._salvar()
            except OSError:
                self._data, self._next = previous, due
                raise
            self._generation += 1
            return self.estado()

    def passo(self):
        now = self._agora()
        with self._lock:
            if self._running or not self._data['config']['enabled'] or not self._next or now < self._next:
                return False
            generation = self._generation
            # Reserva a próxima execução antes de iniciar: sem rajadas após suspensão.
            old_due = self._next
            self._next = proxima(self._data['config'], now)
            try:
                self._salvar()
            except OSError as error:
                self._next = old_due
                self._data['result'] = f'Não foi possível salvar a rotina: {error}'
                return False
            self._running = True
            prints = copy.deepcopy(self._data['prints'])
        try:
            result = self._executar(prints) or {}
        except Exception as error:
            result = {'ok': False, 'mensagem': str(error)}
        finally:
            with self._lock:
                self._running = False
        with self._lock:
            if result.get('ocupado'):
                if generation == self._generation:
                    self._next = self._agora() + timedelta(seconds=5)
                self._data['result'] = 'Aguardando a organização atual terminar.'
            else:
                self._data['last'] = self._agora().isoformat()
                self._data['result'] = result.get('mensagem') or ('Concluído.' if result.get('ok') else 'Não foi possível salvar os prints.')
                if generation == self._generation and self._next and self._next <= self._agora():
                    self._next = proxima(self._data['config'], self._agora())
            try:
                self._salvar()
            except OSError:
                self._data['result'] += ' Não foi possível guardar o resultado da execução.'
        return True

    def iniciar(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._rodar, daemon=True)
            self._thread.start()

    def parar(self, esperar=False):
        self._stop.set()
        if esperar and self._thread and threading.current_thread() is not self._thread:
            self._thread.join()

    def _rodar(self):
        while not self._stop.wait(1):
            try:
                self.passo()
            except Exception:
                pass  # Uma falha da rotina não derruba o aplicativo.
