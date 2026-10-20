"""Média diária de venda do TC por mundo. Cache só em memória, sem histórico local."""
from datetime import datetime, timezone
import re
import threading
import time

import zandaobot_sources as sources

SOURCE = 'https://tibiatrade.gg/tc-to-gold'
TTL = 3600
COOLDOWN = 60
MAX_AGE = 36 * 3600
_lock = threading.Lock()
_rows = None
_consulta = None
_success = None
_attempt = None
_failed = False


def _now():
    return datetime.now(timezone.utc)


def consultar(mundo, atualizar=False):
    global _rows, _consulta, _success, _attempt, _failed
    if not isinstance(mundo, str) or not re.fullmatch(r'[A-Za-z]{2,40}', mundo) or type(atualizar) is not bool:
        return {'estado': 'invalida', 'motivo': 'Informe um mundo válido.', 'fonte': SOURCE}
    with _lock:
        clock = time.monotonic()
        due = _failed or _success is None or clock - _success >= TTL or atualizar
        permitted = _attempt is None or clock - _attempt >= COOLDOWN
        if due and permitted:
            _attempt = clock
            try:
                data = sources.trade('tibiaCoinPrice.list')
                rows = data.get('prices')
                if not isinstance(rows, list) or not rows or len(rows) > 2000:
                    raise ValueError('Lista inválida')
                _rows, _consulta, _success, _failed = rows, _now().isoformat(), clock, False
            except Exception:
                _failed = True
        result = {'mundo': mundo, 'fonte': SOURCE, 'consulta': _consulta, 'estado': 'indisponivel',
                  'motivo': 'Cotação indisponível. Valor manual em uso.'}
        if _failed or _rows is None:
            return result
        matches = [row for row in _rows if isinstance(row, dict) and isinstance(row.get('world_name'), str) and row['world_name'].lower() == mundo.lower()]
        if not matches:
            return {**result, 'estado': 'ausente', 'motivo': 'Mundo sem cotação. Valor manual em uso.'}
        if len(matches) != 1:
            return {**result, 'estado': 'invalida', 'motivo': 'Cotação inconsistente para este mundo. Valor manual em uso.'}
        row = matches[0]
        price = row.get('sell_average_price')
        try:
            raw = row.get('created_at')
            if not isinstance(raw, str) or len(raw) > 64:
                raise ValueError()
            created = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            if created.utcoffset() is None or type(price) is not int or not 1 <= price <= 10**12:
                raise ValueError()
            age = (_now() - created).total_seconds()
            if age < -300:
                raise ValueError()
        except (ValueError, TypeError, OverflowError):
            return {**result, 'estado': 'invalida', 'motivo': 'Cotação inválida para este mundo. Valor manual em uso.'}
        result.update(data_base=created.isoformat(), gold_por_tc=price)
        if age > MAX_AGE:
            return {**result, 'estado': 'antiga', 'motivo': 'Cotação com mais de 36 horas. Valor manual em uso.'}
        return {**result, 'estado': 'ok', 'motivo': 'Média diária de venda; não é uma cotação do Market em tempo real.'}
